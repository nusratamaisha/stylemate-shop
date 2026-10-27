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
        "name": "Nadia Rahman", "email": "nadia@example.com", "phone": "01711000000", "address": "",
        "delivery_area": "", "payment_method": "", "preferred_size": "", "measurements": {}}


def test_sign_up_checks_the_details(client):
    assert "valid email" in sign_up(client, email="nadia").get_json()["error"]
    assert "at least 6" in sign_up(client, password="short").get_json()["error"]
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
    assert client.get("/api/owner/business").status_code == 401
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


HOME = {"name": "Nadia Rahman", "phone": "01999000000", "address": "House 4, Road 2, Sylhet", "delivery_area": "outside_dhaka"}


def me(client):
    return client.get("/api/account/me").get_json()["customer"]


def test_an_order_remembers_the_details_for_next_time(client):
    sign_up(client)
    client.post("/api/orders", json={"customer": HOME, "items": [BELA], "remember": True,
                                     "payment": {"method": "cash_on_delivery"}})

    saved = me(client)
    assert (saved["phone"], saved["address"], saved["delivery_area"]) == (
        "01999000000", "House 4, Road 2, Sylhet", "outside_dhaka")
    assert (saved["payment_method"], saved["preferred_size"]) == ("cash_on_delivery", "M")


def test_a_made_to_measure_order_remembers_the_measurements_but_not_as_a_size(client):
    from .conftest import option_id
    sign_up(client)
    client.post("/api/orders", json={"customer": HOME, "remember": True, "items": [
        {"product_code": "SR-002", "colour": "Maroon", "option_ids": [option_id("Fit", "Made to your measurements")],
         "measurements": {"bust": 36, "waist": "30"}}]})
    saved = me(client)
    assert saved["measurements"] == {"bust": 36, "waist": 30} and saved["preferred_size"] == ""


def test_nothing_is_remembered_without_the_tick_or_for_a_guest(client):
    client.post("/api/orders", json={"customer": HOME, "items": [BELA], "remember": True})  # a guest: no account
    sign_up(client)
    client.post("/api/orders", json={"customer": HOME, "items": [BELA]})  # box unticked
    assert me(client)["address"] == ""


def test_a_customer_can_change_or_clear_their_saved_details(client):
    sign_up(client)
    response = client.patch("/api/account/details", json={"address": "Flat 3B, Dhanmondi", "delivery_area": "inside_dhaka",
                                                          "preferred_size": "L", "measurements": {"bust": "38"}})
    assert response.status_code == 200
    saved = me(client)
    assert (saved["address"], saved["preferred_size"], saved["measurements"]) == ("Flat 3B, Dhanmondi", "L", {"bust": 38})
    assert saved["name"] == "Nadia Rahman"  # fields not sent stay as they were

    client.patch("/api/account/details", json={"preferred_size": "", "measurements": None})
    assert (me(client)["preferred_size"], me(client)["measurements"]) == ("", {})
    assert client.patch("/api/account/details", json={"delivery_area": "the moon"}).status_code == 400
    assert client.patch("/api/account/details", json={"name": ""}).status_code == 400


def test_saved_details_need_a_login(client):
    assert client.patch("/api/account/details", json={"address": "x"}).status_code == 401
