"""Custom order prices: calculated by Flask, never by the AI."""

import pytest

from stylemate.errors import UserInputError
from stylemate.models import CustomizationOption, Product
from stylemate.services.pricing import calculate_quote

from .conftest import option_id


def make_product(customizable=True, price=4200, length_inches=None, sleeve=""):
    return Product(code="SR-002", name="Shefali Embroidered Maxi", category="Dress", sizes="S, M, L",
                   colours="Maroon", price_bdt=price, customizable=customizable,
                   length_inches=length_inches, sleeve=sleeve)


def option(group, label, price, days, length_change=0):
    return CustomizationOption(group=group, label=label, extra_price_bdt=price, extra_days=days,
                               length_change_inches=length_change)


def test_regular_item_costs_the_listed_price():
    quote = calculate_quote(make_product(), [], base_days=7)
    assert quote.total_bdt == 4200
    assert not quote.is_custom
    assert quote.ready_in_days is None


def test_extras_add_price_and_days():
    quote = calculate_quote(
        make_product(),
        [option("Sleeves", "Short sleeves", 150, 2), option("Length", "Longer by 2 inches", 250, 2)],
        base_days=7,
    )
    assert quote.total_bdt == 4200 + 150 + 250
    assert quote.ready_in_days == 7 + 2 + 2
    assert quote.details == "Sleeves: Short sleeves; Length: Longer by 2 inches"


def test_non_customizable_products_reject_options():
    with pytest.raises(UserInputError, match="can't be customized"):
        calculate_quote(make_product(customizable=False), [option("Sleeves", "Short sleeves", 150, 2)], 7)


def test_only_one_option_per_group():
    with pytest.raises(UserInputError, match="only one option"):
        calculate_quote(make_product(),
                        [option("Sleeves", "Short sleeves", 150, 2), option("Sleeves", "Sleeveless", 100, 1)], 7)


def test_price_quote_endpoint(client):
    response = client.post("/api/price-quote", json={
        "product_code": "SR-002",
        "option_ids": [option_id("Sleeves", "Short sleeves"), option_id("Fit", "Made to your measurements")],
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_bdt"] == 4200 - 100  # short sleeves use less fabric; made to measure is free
    assert data["ready_in_days"] == 7 + 2 + 3


def test_price_quote_rejects_unknown_options(client):
    response = client.post("/api/price-quote", json={"product_code": "SR-002", "option_ids": [9999]})
    assert response.status_code == 400
    assert "doesn't exist" in response.get_json()["error"]


def test_product_page_includes_customization_menu_only_when_customizable(client):
    customizable = client.get("/api/products/SR-002").get_json()
    regular = client.get("/api/products/SR-003").get_json()
    assert [group["group"] for group in customizable["customization"]] == ["Sleeves", "Length", "Fit"]
    assert regular["customization"] == []


def test_length_option_states_the_new_length_when_the_length_is_known():
    shorter = option("Length", "Shorter by 2 inches", 100, 1, length_change=-2)
    assert calculate_quote(make_product(length_inches=56), [shorter], base_days=7).details == \
        "Length: Shorter by 2 inches (54 in)"
    # Without a measured length the option still works; it just can't say the result
    assert calculate_quote(make_product(), [shorter], base_days=7).details == "Length: Shorter by 2 inches"


def test_an_option_the_piece_already_has_is_refused():
    with pytest.raises(UserInputError, match="already has full sleeves"):
        calculate_quote(make_product(sleeve="Full"), [option("Sleeves", "Full sleeves", 200, 2)], base_days=7)
    # A different sleeve is fine
    calculate_quote(make_product(sleeve="Full"), [option("Sleeves", "Short sleeves", 150, 2)], base_days=7)


def test_product_page_menu_fits_the_product(client):
    # SR-002 in the sample data: 56 inches long with full sleeves
    groups = {group["group"]: group for group in client.get("/api/products/SR-002").get_json()["customization"]}

    assert groups["Sleeves"]["current"] == "Full"
    assert [item["label"] for item in groups["Sleeves"]["options"]] == ["Short sleeves", "Sleeveless"]
    assert groups["Length"]["current"] == "56 in"
    assert [item["new_length_inches"] for item in groups["Length"]["options"]] == [54, 58]


def test_changes_that_use_less_fabric_lower_the_price(client):
    # SR-002 in the test catalogue: ৳4,200, full sleeves, 56 inches
    response = client.post("/api/price-quote", json={
        "product_code": "SR-002",
        "option_ids": [option_id("Sleeves", "Sleeveless"), option_id("Length", "Shorter by 2 inches or more")],
    })
    data = response.get_json()
    assert data["total_bdt"] == 4200 - 150 - 100
    assert data["is_custom"] is True and data["ready_in_days"] == 7 + 1 + 1  # cheaper, but still made to order
