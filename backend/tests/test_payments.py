"""Paying for an order: cash on delivery, or a bKash, Nagad or Rocket transaction ID the owner checks."""

from stylemate.extensions import db
from stylemate.models import Order, Product, Tenant

CUSTOMER = {"name": "Nusrat", "phone": "01700000000", "address": "Dhaka", "delivery_area": "inside_dhaka"}
ITEM = {"product_code": "SR-003", "size": "M", "colour": "Mustard", "quantity": 1}


def order(client, payment=None):
    return client.post("/api/orders", json={"customer": CUSTOMER, "items": [ITEM], "payment": payment})


def test_checkout_is_told_the_ways_to_pay_and_where_to_send_money(client):
    options = client.get("/api/shop").get_json()["payment"]

    assert [option["method"] for option in options] == ["cash_on_delivery", "bkash", "nagad", "rocket"]
    assert options[0]["number"] == "" and options[1] == {"method": "bkash", "label": "bKash", "number": "01700-000000"}


def test_an_order_without_a_choice_is_paid_on_delivery(client):
    data = order(client).get_json()

    assert (data["payment_method"], data["payment_label"], data["payment_status"]) == \
        ("cash_on_delivery", "Cash on delivery", "unpaid")


def test_wallet_payment_keeps_the_transaction_id_for_the_owner_to_check(client):
    response = order(client, {"method": "bkash", "transaction_id": " 9hk2 l7mq0x "})

    assert response.status_code == 201
    data = response.get_json()
    assert (data["payment_label"], data["payment_reference"], data["payment_status"]) == ("bKash", "9HK2L7MQ0X", "to_check")


def test_wallet_payment_without_a_transaction_id_is_refused_and_nothing_is_saved(client):
    stock = db.session.scalar(db.select(Product.stock).where(Product.code == "SR-003"))

    response = order(client, {"method": "nagad", "transaction_id": "??"})

    assert response.status_code == 400
    assert "transaction ID (TrxID) from your Nagad message" in response.get_json()["error"]
    assert db.session.scalar(db.select(Order)) is None
    assert db.session.scalar(db.select(Product.stock).where(Product.code == "SR-003")) == stock


def test_one_transaction_id_cannot_pay_for_two_orders(client):
    assert order(client, {"method": "bkash", "transaction_id": "9HK2L7MQ0X"}).status_code == 201

    again = order(client, {"method": "bkash", "transaction_id": "9hk2l7mq0x"})

    assert again.status_code == 400
    assert "already used" in again.get_json()["error"]


def test_a_wallet_the_shop_has_no_number_for_is_not_offered(client, tenant):
    tenant.rocket_number = ""
    db.session.commit()

    assert "rocket" not in [option["method"] for option in client.get("/api/shop").get_json()["payment"]]
    assert order(client, {"method": "rocket", "transaction_id": "1234567890"}).status_code == 400


def test_owner_marks_a_checked_payment_as_paid(client, owner_client):
    order_id = order(client, {"method": "rocket", "transaction_id": "1234567890"}).get_json()["order_id"]
    assert owner_client.get("/api/owner/orders").get_json()["summary"]["payments_to_check"] == 1

    response = owner_client.patch(f"/api/owner/orders/{order_id}/payment", json={"status": "paid"})

    assert response.get_json() == {"order_id": order_id, "payment_status": "paid"}
    data = owner_client.get("/api/owner/orders").get_json()
    assert data["summary"]["payments_to_check"] == 0
    assert (data["orders"][0]["payment_reference"], data["orders"][0]["payment_status"]) == ("1234567890", "paid")
    assert owner_client.patch(f"/api/owner/orders/{order_id}/payment", json={"status": "free"}).status_code == 400


def test_payment_status_needs_the_owner_of_that_shop(app, client):
    order_id = order(client).get_json()["order_id"]
    assert client.patch(f"/api/owner/orders/{order_id}/payment", json={"status": "paid"}).status_code == 401

    other = Tenant(slug="other-shop", name="Other Shop")
    db.session.add(other)
    db.session.commit()
    theirs = Order(tenant_id=other.id, customer_name="X", phone="1", address="Y", total_bdt=100)
    db.session.add(theirs)
    db.session.commit()
    client.post("/api/owner/login", json={"email": "owner@example.com", "password": "secret-pass"})

    assert client.patch(f"/api/owner/orders/{theirs.id}/payment", json={"status": "paid"}).status_code == 400
    assert theirs.payment_status == "unpaid"

