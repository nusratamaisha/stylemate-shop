"""The size guide: what body each size fits and how long each sleeve is."""

from stylemate.extensions import db
from stylemate.models import SizeGuideRow, Tenant


def test_size_guide_lists_sizes_and_sleeves_in_order(client):
    guide = client.get("/api/size-guide").get_json()

    assert [row["size"] for row in guide["sizes"]] == ["XS", "S", "M", "L", "XL", "XXL"]
    assert guide["sizes"][4] == {"size": "XL", "bust_inches": 40, "waist_inches": 34, "hip_inches": 43}
    assert guide["sleeves"][0] == {"name": "Short", "length_inches": 7}


def test_size_guide_shows_only_this_shops_rows(app, client):
    other = Tenant(slug="other-shop", name="Other Shop")
    db.session.add(other)
    db.session.commit()
    db.session.add(SizeGuideRow(tenant_id=other.id, size="ONE", bust_inches=50, waist_inches=50, hip_inches=50))
    db.session.commit()

    assert "ONE" not in [row["size"] for row in client.get("/api/size-guide").get_json()["sizes"]]


def test_sleeve_options_say_how_long_the_sleeve_is(client):
    # SR-001 has three-quarter sleeves, so every sleeve option is offered
    groups = {group["group"]: group for group in client.get("/api/products/SR-001").get_json()["customization"]}
    lengths = {item["label"]: item["sleeve_length_inches"] for item in groups["Sleeves"]["options"]}

    assert lengths == {"Short sleeves": 7, "Full sleeves": 23, "Sleeveless": None}  # no length for no sleeve
    assert groups["Lining"]["options"][0]["sleeve_length_inches"] is None
