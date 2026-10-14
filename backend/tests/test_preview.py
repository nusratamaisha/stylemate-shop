"""Image preview: the prompt, the reference images, and what is refused before Maira is called."""

import io

from stylemate.extensions import db
from stylemate.models import Tenant

from .conftest import option_id

PNG = b"\x89PNG fake picture bytes"


def post_preview(client, code="SR-002", **form):
    return client.post(f"/api/products/{code}/preview", data=form, content_type="multipart/form-data")


def test_preview_describes_the_dress_and_the_chosen_options(client, maira):
    response = post_preview(client, visitor_id="v1", colour="Maroon",
                            option_ids=[str(option_id("Sleeves", "Short sleeves"))])

    assert response.status_code == 200
    data = response.get_json()
    assert data["image_url"] == "https://images.test/preview-1.png"
    assert data["details"] == "Sleeves: Short sleeves"
    assert data["on_customer"] is False

    request = maira.image_requests[0]
    assert request["profile_id"] == "image-profile-1"  # the shop's image profile, not the chat profile
    assert "Shefali Embroidered Maxi" in request["prompt"]
    assert "Colour: Maroon" in request["prompt"]
    assert "Changes to make: Sleeves: Short sleeves." in request["prompt"]
    assert "As sold, its sleeves are: Full." in request["prompt"]  # so the model knows what to change
    assert request["reference_images"] == []  # no product photo in the test images folder


def test_preview_includes_the_customers_typed_idea(client, maira):
    response = post_preview(client, wish="  add a   gold border at the hem ")
    assert response.status_code == 200
    assert "The customer also asks: add a gold border at the hem" in maira.image_requests[0]["prompt"]


def test_preview_on_the_customer_sends_their_photo_first(app, client, maira, tmp_path):
    (tmp_path / "SR-002.jpg").write_bytes(b"dress photo")  # the shop's own photo of the dress

    response = post_preview(client, size="M", photo=(io.BytesIO(PNG), "me.png", "image/png"))

    assert response.status_code == 200
    assert response.get_json()["on_customer"] is True
    request = maira.image_requests[0]
    assert [image.filename for image in request["reference_images"]] == ["me.png", "SR-002.jpg"]
    assert "The first reference image is the customer" in request["prompt"]
    assert "The second reference image is the real piece" in request["prompt"]


def test_preview_without_a_photo_shows_the_piece_alone_with_no_person(client, maira):
    post_preview(client, size="M", wish="a gold border at the hem")

    prompt = maira.image_requests[0]["prompt"]
    assert "product photo of this piece on its own" in prompt
    assert "No person, no model, no face" in prompt
    assert "wearing" not in prompt
    assert "size M" not in prompt  # a size only matters when someone is wearing the piece


def test_try_on_shows_the_chosen_size_on_the_customers_real_body(client, maira):
    post_preview(client, size="M", photo=(io.BytesIO(PNG), "me.png", "image/png"))

    prompt = maira.image_requests[0]["prompt"]
    # The size guide's numbers for M, so the model knows what body that size is cut for
    assert "The piece is size M, cut for a bust of 36 inches, a waist of 30 inches and a hip of 39 inches." in prompt
    assert "too small for them it must look tight" in prompt
    assert "Never reshape the person" in prompt


def test_try_on_needs_a_size_the_piece_comes_in(client, maira):
    no_size = post_preview(client, photo=(io.BytesIO(PNG), "me.png", "image/png"))
    assert no_size.status_code == 400
    assert "Choose a size first" in no_size.get_json()["error"]

    wrong = post_preview(client, size="XXL", photo=(io.BytesIO(PNG), "me.png", "image/png"))  # SR-002 stops at L
    assert wrong.status_code == 400
    assert maira.image_requests == []  # neither reached the paid call


def test_try_on_of_a_made_to_measure_piece_uses_the_customers_measurements(client, maira):
    response = post_preview(client, option_ids=[str(option_id("Fit", "Made to your measurements"))],
                            bust="38", waist="32", hip="40", photo=(io.BytesIO(PNG), "me.png", "image/png"))

    assert response.status_code == 200  # no S, M or L needed
    prompt = maira.image_requests[0]["prompt"]
    assert "made to this person's own measurements (bust 38 in, waist 32 in, hip 40 in)" in prompt
    assert "fits their body exactly" in prompt


def test_preview_needs_something_to_show(client, maira):
    response = post_preview(client)
    assert response.status_code == 400
    assert maira.image_requests == []  # refused before any paid call


def test_preview_refuses_a_file_that_is_not_a_photo(client, maira):
    response = post_preview(client, photo=(io.BytesIO(b"%PDF"), "me.pdf", "application/pdf"))
    assert response.status_code == 400
    assert "JPG, PNG or WebP" in response.get_json()["error"]
    assert maira.image_requests == []


def test_preview_refuses_options_from_two_of_the_same_group(client, maira):
    response = post_preview(client, option_ids=[str(option_id("Sleeves", "Short sleeves")),
                                                str(option_id("Sleeves", "Sleeveless"))])
    assert response.status_code == 400
    assert maira.image_requests == []


def test_preview_refuses_a_colour_the_dress_does_not_come_in(client):
    response = post_preview(client, colour="Neon Green", wish="longer sleeves")
    assert response.status_code == 400


def test_preview_is_hidden_when_the_shop_has_no_image_profile(app, client, maira):
    tenant = db.session.scalar(db.select(Tenant))
    tenant.maira_image_profile_id = ""
    db.session.commit()

    assert client.get("/api/products/SR-002").get_json()["preview_available"] is False
    response = post_preview(client, wish="longer sleeves")
    assert response.status_code == 400
    assert maira.image_requests == []


def test_preview_outage_shows_a_friendly_message(client, maira):
    maira.fail = True
    response = post_preview(client, wish="longer sleeves")
    assert response.status_code == 502


def test_previews_are_limited_per_visitor_per_day(app, client, maira):
    app.config["PREVIEWS_PER_DAY"] = 1
    assert post_preview(client, wish="longer sleeves").status_code == 200
    assert post_preview(client).status_code == 400  # refused for another reason: not counted

    second = post_preview(client, wish="a gold border")
    assert second.status_code == 429
    assert len(maira.image_requests) == 1  # the second picture was never paid for
