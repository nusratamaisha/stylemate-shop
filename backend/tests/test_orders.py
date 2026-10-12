"""Checkout: prices are recalculated on the server, and custom pieces join the owner's queue."""

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
    assert item["unit_price_bdt"] == 4200 + 150
    assert item["custom_details"] == "Sleeves: Short sleeves"
    assert item["ready_by"] is not None
    assert item["status"] == "new"


def test_out_of_stock_items_cannot_be_ordered_ready_made(client):
    response = order(client, {"product_code": "SR-004", "size": "M", "colour": "Black"})
    assert response.status_code == 400
    assert "out of stock" in response.get_json()["error"]


def test_out_of_stock_items_can_be_made_to_order(client):
    response = order(client, {"product_code": "SR-004", "size": "M", "colour": "Black",
                              "option_ids": [option_id("Length", "Shorter by 2 inches")]})
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
