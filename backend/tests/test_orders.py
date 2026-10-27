"""Checkout: prices are recalculated on the server, and custom pieces join the owner's queue."""

import io

from .conftest import option_id

CUSTOMER = {"name": "Nusrat", "phone": "01700000000", "address": "Dhaka", "delivery_area": "inside_dhaka"}


def order(client, *items):
    return client.post("/api/orders", json={"customer": CUSTOMER, "items": list(items)})


def test_regular_order_uses_server_prices(client):
    response = order(client, {"product_code": "SR-003", "size": "M", "colour": "Mustard",
                              "quantity": 2, "unit_price_bdt": 1})  # a tampered price is ignored
    assert response.status_code == 201
    data = response.get_json()
    assert (data["subtotal_bdt"], data["shipping_bdt"], data["total_bdt"]) == (3700, 80, 3780)


def test_custom_order_adds_extras_and_ready_date(client):
    response = order(client, {"product_code": "SR-002", "size": "M", "colour": "Maroon", "quantity": 1,
                              "option_ids": [option_id("Sleeves", "Short sleeves")], "notes": "Bust 34"})
    item = response.get_json()["items"][0]
    assert item["is_custom"] is True
    assert item["unit_price_bdt"] == 4200 - 100
    assert item["custom_details"] == "Sleeves: Short sleeves"
    assert item["ready_by"] is not None
    assert item["status"] == "new"


def test_out_of_stock_items_cannot_be_ordered_ready_made(client):
    response = order(client, {"product_code": "SR-004", "size": "M", "colour": "Black"})
    assert response.status_code == 400
    assert "out of stock" in response.get_json()["error"]


def test_out_of_stock_items_can_be_made_to_order(client):
    response = order(client, {"product_code": "SR-004", "size": "M", "colour": "Black",
                              "option_ids": [option_id("Length", "Shorter by 2 inches or more")]})
    assert response.status_code == 201


def test_size_and_colour_must_exist(client):
    assert order(client, {"product_code": "SR-002", "size": "XXL", "colour": "Maroon"}).status_code == 400
    assert order(client, {"product_code": "SR-002", "size": "M", "colour": "Red"}).status_code == 400


def test_customer_details_are_required(client):
    response = client.post("/api/orders", json={"customer": {"name": "N"}, "items": [
        {"product_code": "SR-003", "size": "M", "colour": "Mustard"}]})
    assert response.status_code == 400


BELA = {"product_code": "SR-003", "size": "M", "colour": "Mustard"}


def test_shipping_is_150_outside_dhaka_and_charged_once_per_order(client):
    response = client.post("/api/orders", json={
        "customer": {**CUSTOMER, "delivery_area": "outside_dhaka", "shipping_bdt": 0},  # a tampered charge is ignored
        "items": [{**BELA, "quantity": 2}, {**BELA, "colour": "White"}],
    })
    data = response.get_json()
    assert response.status_code == 201
    assert (data["subtotal_bdt"], data["shipping_bdt"], data["total_bdt"]) == (1850 * 3, 150, 1850 * 3 + 150)


def test_order_needs_a_delivery_area(client):
    for area in ("", "moon"):
        response = client.post("/api/orders", json={"customer": {**CUSTOMER, "delivery_area": area}, "items": [BELA]})
        assert response.status_code == 400
        assert "inside or outside Dhaka" in response.get_json()["error"]


def test_checkout_page_gets_the_shops_shipping_charges(client):
    assert client.get("/api/shop").get_json()["shipping"] == [
        {"area": "inside_dhaka", "label": "Inside Dhaka", "charge_bdt": 80},
        {"area": "outside_dhaka", "label": "Outside Dhaka", "charge_bdt": 150},
    ]


def measured(**changes):
    return {"product_code": "SR-002", "colour": "Maroon",
            "option_ids": [option_id("Fit", "Made to your measurements"), option_id("Sleeves", "Sleeveless")],
            "measurements": {"bust": 38, "waist": "32", "sleeve_length": 20, "length": 36}, **changes}


def test_made_to_measure_needs_no_size(client):
    response = client.post("/api/orders", json={"customer": CUSTOMER, "items": [measured()]})  # no "size" at all
    assert response.status_code == 201
    item = response.get_json()["items"][0]
    assert item["size"] == "Made to measure"
    # No charge for made to measure. A 20 in sleeve on this full-sleeved (23 in) piece is nearest the short
    # sleeve (-100), replacing the Sleeveless sent along, and 36 in instead of 56 is shorter (-100)
    assert item["unit_price_bdt"] == 4200 - 100 - 100
    assert item["custom_details"] == ("Sleeves: Short sleeves; Length: shorter than shown; "
                                      "Fit: Made to your measurements; "
                                      "Measurements: bust 38 in, waist 32 in, sleeve length 20 in, length 36 in")


def test_made_to_measure_needs_the_measurements(client):
    missing = client.post("/api/orders", json={"customer": CUSTOMER, "items": [measured(measurements={"waist": 30})]})
    assert missing.status_code == 400 and "bust measurement" in missing.get_json()["error"]
    silly = client.post("/api/orders", json={"customer": CUSTOMER, "items": [
        measured(measurements={"bust": 380, "waist": 32})]})
    assert silly.status_code == 400 and "between 20 and 72" in silly.get_json()["error"]
    long_sleeve = client.post("/api/orders", json={"customer": CUSTOMER, "items": [
        measured(measurements={"bust": 38, "sleeve_length": 40})]})
    assert long_sleeve.status_code == 400 and "sleeve length measurement should be between 0 and 25" in long_sleeve.get_json()["error"]


def test_made_to_measure_needs_only_the_bust(client):
    response = client.post("/api/orders", json={"customer": CUSTOMER, "items": [measured(measurements={"bust": 38})]})
    assert response.status_code == 201
    assert response.get_json()["items"][0]["custom_details"].endswith("Measurements: bust 38 in")


def test_made_to_measure_replaces_the_length_options(client):
    response = client.post("/api/price-quote", json={"product_code": "SR-002", "option_ids": [
        option_id("Fit", "Made to your measurements"), option_id("Length", "Shorter by 2 inches or more")]})
    assert response.status_code == 400 and "exact length" in response.get_json()["error"]


PNG = b"\x89PNG fake picture"


def upload_picture(client, content=PNG, name="idea.png", mimetype="image/png"):
    return client.post("/api/reference-pictures", data={"picture": (io.BytesIO(content), name, mimetype)},
                       content_type="multipart/form-data")


def test_reference_picture_reaches_only_the_owner(app, client, owner_client):
    uploaded = upload_picture(client)
    assert uploaded.status_code == 201
    name = uploaded.get_json()["reference_image"]
    assert name.endswith(".png") and "idea" not in name  # a random name, never the customer's file name

    placed = client.post("/api/orders", json={"customer": CUSTOMER, "items": [measured(reference_image=name)]})
    item = placed.get_json()["items"][0]
    assert item["has_reference_image"] is True

    url = f"/api/owner/custom-orders/{item['id']}/reference-picture"
    assert owner_client.get(url).data == PNG
    assert app.test_client().get(url).status_code == 401  # a visitor who is not the owner


def test_reference_picture_must_be_a_real_upload(client):
    assert upload_picture(client, b"%PDF", "idea.pdf", "application/pdf").status_code == 400
    # A made-up or tampered name is ignored, not trusted
    placed = client.post("/api/orders", json={"customer": CUSTOMER, "items": [
        measured(reference_image="../../stylemate.db")]})
    assert placed.status_code == 201 and placed.get_json()["items"][0]["has_reference_image"] is False
    # A ready-made piece has no tailor, so a picture sent with it is dropped
    name = upload_picture(client).get_json()["reference_image"]
    ready = client.post("/api/orders", json={"customer": CUSTOMER, "items": [{**BELA, "reference_image": name}]})
    assert ready.get_json()["items"][0]["has_reference_image"] is False


def stock_of(client, code):
    return client.get(f"/api/products/{code}").get_json()["stock"]


def test_ordering_a_ready_made_piece_lowers_its_stock(client):
    assert stock_of(client, "SR-003") == 25
    order(client, {**BELA, "quantity": 2}, {**BELA, "colour": "White"})  # two lines of the same piece
    assert stock_of(client, "SR-003") == 22


def test_made_to_order_pieces_use_no_stock(client):
    before = stock_of(client, "SR-002")
    order(client, {"product_code": "SR-002", "size": "M", "colour": "Maroon",
                   "option_ids": [option_id("Sleeves", "Short sleeves")]})
    assert stock_of(client, "SR-002") == before


def test_an_order_for_more_than_is_left_is_refused_and_changes_nothing(client):
    maxi = {"product_code": "SR-002", "size": "M", "colour": "Maroon"}  # 6 in stock
    # 4 + 4 across two lines is more than 6, even though each line alone would fit
    refused = order(client, {**BELA}, {**maxi, "quantity": 4}, {**maxi, "colour": "Emerald", "quantity": 4})
    assert refused.status_code == 400 and "only 6" in refused.get_json()["error"]
    assert (stock_of(client, "SR-002"), stock_of(client, "SR-003")) == (6, 25)  # the tunic in the same order wasn't taken

    assert order(client, {**maxi, "quantity": 6}).status_code == 201
    assert stock_of(client, "SR-002") == 0
    sold_out = order(client, maxi)
    assert sold_out.status_code == 400 and "out of stock" in sold_out.get_json()["error"]


def test_a_chat_order_gets_the_same_checks_and_prices_as_checkout(client):
    chat_order = {"customer": CUSTOMER, "source": "chat", "items": [
        {"product_code": "SR-003", "size": "M", "colour": "Mustard", "unit_price_bdt": 1}]}  # a tampered price
    response = client.post("/api/orders", json=chat_order)
    assert response.status_code == 201
    assert (response.get_json()["source"], response.get_json()["total_bdt"]) == ("chat", 1850 + 80)

    no_address = client.post("/api/orders", json={**chat_order, "customer": {**CUSTOMER, "address": ""}})
    assert no_address.status_code == 400


def test_an_unknown_order_source_is_refused(client):
    response = client.post("/api/orders", json={"customer": CUSTOMER, "source": "facebook", "items": [
        {"product_code": "SR-003", "size": "M", "colour": "Mustard"}]})
    assert response.status_code == 400


def quote(client, code, **measurements):
    return client.post("/api/price-quote", json={"product_code": code, "measurements": measurements}).get_json()


def test_measurements_alone_make_the_piece_to_measure_at_no_extra_charge(client):
    data = quote(client, "SR-002", bust=38)
    assert data["needs_measurements"] and data["total_bdt"] == 4200
    assert [extra["label"] for extra in data["extras"]] == ["Made to your measurements"]


def test_a_longer_sleeve_length_adds_the_full_sleeve_charge(client):
    # SR-006 has short sleeves (7 in in the size guide); 21 in is nearest the full sleeve (23 in)
    data = quote(client, "SR-006", bust=36, sleeve_length=21)
    assert data["total_bdt"] == 1650 + 200
    assert "Sleeves: Full sleeves;" in data["details"]


def test_a_longer_length_adds_the_longer_charge_and_a_close_one_changes_nothing(client):
    assert quote(client, "SR-006", bust=36, length=42)["total_bdt"] == 1650 + 250  # 38 in as shown
    assert quote(client, "SR-006", bust=36, length=39, sleeve_length=8)["total_bdt"] == 1650  # within an inch

def test_measurements_must_be_within_the_standard_ranges(client):
    for measurements, words in [({"bust": 36, "waist": 10}, "waist measurement should be between 20 and 72"),
                                ({"bust": 36, "length": 60}, "length measurement should be between 20 and 58"),
                                ({"bust": 36, "sleeve_length": -3}, "sleeve length measurement should be between 0 and 25")]:
        response = client.post("/api/price-quote", json={"product_code": "SR-006", "measurements": measurements})
        assert response.status_code == 400 and words in response.get_json()["error"]


def test_a_sleeve_length_of_zero_makes_it_sleeveless(client):
    # SR-006 has short sleeves; 0 in is sleeveless, which costs 150 less
    data = quote(client, "SR-006", bust=36, sleeve_length=0)
    assert data["total_bdt"] == 1650 - 150
    assert "Sleeves: Sleeveless" in data["details"]


def test_a_sleeve_chosen_in_the_chat_stays_when_no_sleeve_length_is_given(client):
    response = client.post("/api/price-quote", json={"product_code": "SR-002", "measurements": {"bust": 38},
                                                    "option_ids": [option_id("Sleeves", "Sleeveless")]})
    assert response.get_json()["total_bdt"] == 4200 - 150
