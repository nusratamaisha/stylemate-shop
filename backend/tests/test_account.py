"""Customer accounts, order history and reviews."""

SIGNUP = {"name": "Nadia Rahman", "email": "Nadia@Example.com", "password": "long-enough", "phone": "01711000000"}
DELIVERY = {"name": "Nadia Rahman", "phone": "01711000000", "address": "Dhaka", "delivery_area": "inside_dhaka"}
BELA = {"product_code": "SR-003", "size": "M", "colour": "Mustard"}


def sign_up(client, **changes):
    return client.post("/api/account/register", json={**SIGNUP, **changes})


def buy(client, item=BELA):
    return client.post("/api/orders", json={"customer": DELIVERY, "items": [item]})


def test_sign_up_logs_the_customer_in(client):
    assert client.get("/api/account/me").get_json() == {"customer": None}  # a guest

    response = sign_up(client)
    assert response.status_code == 201
    assert client.get("/api/account/me").get_json()["customer"] == {
        "name": "Nadia Rahman", "email": "nadia@example.com", "phone": "01711000000"}


def test_sign_up_checks_the_details(client):
    assert "valid email" in sign_up(client, email="nadia").get_json()["error"]
    assert "at least 8" in sign_up(client, password="short").get_json()["error"]
    sign_up(client)
    assert "already exists" in sign_up(client).get_json()["error"]


def test_log_out_and_log_in_again(client):
    sign_up(client)
    client.post("/api/account/logout")
    assert client.get("/api/account/me").get_json()["customer"] is None

    assert client.post("/api/account/login", json={"email": SIGNUP["email"], "password": "wrong"}).status_code == 401
    assert client.post("/api/account/login", json={"email": "NADIA@example.com", "password": "long-enough"}).status_code == 200


def test_customer_login_does_not_open_the_owner_dashboard(client):
    sign_up(client)
    assert client.get("/api/owner/insights").status_code == 401
    assert client.get("/api/owner/messages").status_code == 401


def test_order_history_shows_only_the_customers_own_orders(app, client):
    buy(client)  # a guest order: belongs to nobody
    assert client.get("/api/account/orders").status_code == 401

    sign_up(client)
    buy(client)
    history = client.get("/api/account/orders").get_json()
    assert len(history) == 1
    assert history[0]["total_bdt"] == 1850 + 80 and history[0]["items"][0]["product_code"] == "SR-003"

    other = app.test_client()  # a second customer in another browser
    sign_up(other, email="other@example.com")
    assert other.get("/api/account/orders").get_json() == []


def test_each_customer_counts_their_own_orders_from_one(app, client):
    buy(client)  # a guest order takes the shop's order 1
    sign_up(client)
    first, second = buy(client).get_json(), buy(client).get_json()

    assert (first["order_id"], first["customer_order_number"]) == (2, 1)  # the shop's 2nd order, Nadia's 1st
    assert (second["order_id"], second["customer_order_number"]) == (3, 2)
    assert [order["customer_order_number"] for order in client.get("/api/account/orders").get_json()] == [2, 1]

    other = app.test_client()
    sign_up(other, email="other@example.com")
    assert buy(other).get_json()["customer_order_number"] == 1  # the other customer starts at 1 too
    assert buy(app.test_client()).get_json()["customer_order_number"] is None  # a guest has no numbering


def test_review_needs_a_login_and_an_order(client):
    assert client.post("/api/products/SR-003/reviews", json={"rating": 5}).status_code == 401
    assert client.get("/api/products/SR-003/reviews").get_json()["blocked_reason"] == "login"

    sign_up(client)
    assert client.get("/api/products/SR-003/reviews").get_json()["blocked_reason"] == "not_ordered"
    refused = client.post("/api/products/SR-003/reviews", json={"rating": 5})
    assert refused.status_code == 400 and "after you've ordered" in refused.get_json()["error"]


def test_customer_reviews_a_piece_they_ordered(app, client):
    sign_up(client)
    buy(client)
    assert client.post("/api/products/SR-003/reviews", json={"rating": 9}).status_code == 400  # 1 to 5 only

    saved = client.post("/api/products/SR-003/reviews", json={"rating": 4, "comment": "Soft and cool."})
    assert saved.status_code == 201
    # Writing again replaces the first review instead of adding a second
    client.post("/api/products/SR-003/reviews", json={"rating": 5, "comment": "Even better after a wash."})

    page = app.test_client().get("/api/products/SR-003/reviews").get_json()  # as any visitor sees it
    assert (page["count"], page["average"]) == (1, 5.0)
    assert page["reviews"][0]["name"] == "Nadia"  # first name only
    assert page["reviews"][0]["comment"] == "Even better after a wash."
    assert client.get("/api/products/SR-003/reviews").get_json()["my_review"]["rating"] == 5
