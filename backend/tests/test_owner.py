"""The owner dashboard: login, insights, the custom order queue and CSV upload."""

import io

from .conftest import OWNER_EMAIL, option_id


def test_dashboard_needs_login(client):
    assert client.get("/api/owner/business").status_code == 401


def test_wrong_password_is_rejected(client):
    response = client.post("/api/owner/login", json={"email": OWNER_EMAIL, "password": "nope"})
    assert response.status_code == 401


def test_custom_order_queue_and_status_update(owner_client):
    owner_client.post("/api/orders", json={
        "customer": {"name": "A", "phone": "1", "address": "Dhaka", "delivery_area": "inside_dhaka"},
        "items": [
            {"product_code": "SR-002", "size": "M", "colour": "Maroon",
             "option_ids": [option_id("Sleeves", "Short sleeves")]},
            {"product_code": "SR-003", "size": "M", "colour": "Mustard"},  # regular: not in the queue
        ],
    })
    queue = owner_client.get("/api/owner/custom-orders").get_json()
    assert len(queue) == 1

    item_id = queue[0]["id"]
    updated = owner_client.patch(f"/api/owner/custom-orders/{item_id}", json={"status": "in_production"})
    assert updated.get_json()["status"] == "in_production"
    assert owner_client.patch(f"/api/owner/custom-orders/{item_id}", json={"status": "lost"}).status_code == 400


CSV = (
    "product_id,name,image,category,occasion,sizes,colours,fabric,price_bdt,stock,customizable,description\n"
    "SR-002,Shefali Embroidered Maxi,SR-002.jpg,Dress,Wedding guest,\"S, M, L\",Maroon,Georgette,3900,4,yes,On sale\n"
    "SR-011,Noor Silk Kaftan,SR-011.jpg,Dress,Festive,\"M, L\",Gold,Silk,5200,3,no,New arrival\n"
)


def test_ready_made_line_cannot_be_in_production(owner_client):
    order = owner_client.post("/api/orders", json={
        "customer": {"name": "A", "phone": "1", "address": "Dhaka", "delivery_area": "inside_dhaka"},
        "items": [{"product_code": "SR-003", "size": "M", "colour": "Mustard"}],
    }).get_json()
    item_id = order["items"][0]["id"]

    response = owner_client.patch(f"/api/owner/custom-orders/{item_id}", json={"status": "in_production"})
    assert response.status_code == 400
    assert owner_client.patch(f"/api/owner/custom-orders/{item_id}", json={"status": "shipped"}).status_code == 200


def upload(client, content: str, filename="products.csv"):
    return client.post("/api/owner/products/upload",
                       data={"file": (io.BytesIO(content.encode()), filename)},
                       content_type="multipart/form-data")


def test_csv_upload_updates_database_and_assistant(owner_client, maira, client):
    response = upload(owner_client, CSV)
    data = response.get_json()

    assert response.status_code == 200
    assert (data["created"], data["updated"]) == (1, 1)
    assert data["assistant_status"] == "updating"
    assert maira.uploads[0][0] == "dataset-1" and maira.trained == ["dataset-1"]
    assert client.get("/api/products/SR-002").get_json()["price_bdt"] == 3900


def test_csv_upload_reports_bad_rows(owner_client):
    bad = CSV.replace("3900", "cheap")
    response = upload(owner_client, bad)
    assert response.status_code == 400
    assert "Row 2: price_bdt must be a whole number" in response.get_json()["error"]


def test_csv_upload_still_saves_products_when_maira_is_down(owner_client, maira):
    maira.fail = True
    data = upload(owner_client, CSV).get_json()
    assert data["created"] == 1
    assert data["assistant_status"] == "failed"


def test_csv_upload_reads_length_and_sleeve(owner_client, client):
    with_specs = CSV.replace("fabric,price_bdt", "fabric,length_inches,sleeve,price_bdt") \
                    .replace("Georgette,3900", "Georgette,56,Full,3900").replace("Silk,5200", "Silk,,,5200")
    assert upload(owner_client, with_specs).status_code == 200

    maxi = client.get("/api/products/SR-002").get_json()
    assert (maxi["length_inches"], maxi["sleeve"]) == (56, "Full")
    kaftan = client.get("/api/products/SR-011").get_json()
    assert (kaftan["length_inches"], kaftan["sleeve"]) == (None, "")  # both columns are optional

    bad = upload(owner_client, with_specs.replace("56,Full", "long,Full"))
    assert "length_inches must be a whole number" in bad.get_json()["error"]


DELIVERY = {"name": "Nadia", "phone": "01711000000", "address": "House 4, Sylhet", "delivery_area": "outside_dhaka"}


def test_owner_sees_every_order_and_the_sales_numbers(owner_client):
    assert owner_client.get("/api/owner/orders").get_json()["summary"]["order_count"] == 0

    owner_client.post("/api/orders", json={"customer": DELIVERY, "items": [
        {"product_code": "SR-003", "size": "M", "colour": "Mustard", "quantity": 2},  # ready-made
        {"product_code": "SR-002", "size": "M", "colour": "Maroon",
         "option_ids": [option_id("Length", "Longer by 2 inches or more")]},  # made to order
    ]})
    owner_client.post("/api/orders", json={"customer": {**DELIVERY, "delivery_area": "inside_dhaka"}, "items": [
        {"product_code": "SR-003", "size": "S", "colour": "White"}]})

    data = owner_client.get("/api/owner/orders").get_json()
    summary = data["summary"]
    assert (summary["order_count"], summary["pieces_sold"], summary["custom_pieces"]) == (2, 4, 1)
    assert summary["sales_bdt"] == 1850 * 3 + 4200 + 250  # the clothes
    assert summary["delivery_bdt"] == 150 + 80  # kept apart: it is not income
    assert summary["best_sellers"][0] == {"name": "Bela Tiered Sundress", "quantity": 3}
    assert summary["to_ship"] == 3

    newest, first = data["orders"]
    assert (first["customer_name"], first["address"], first["delivery_area"]) == ("Nadia", "House 4, Sylhet", "outside_dhaka")
    assert [line["is_custom"] for line in first["items"]] == [False, True]  # ready-made lines are listed too
    assert first["items"][0]["product_image_url"] == "/api/images/SR-003.jpg"  # the owner sees which piece it is
    assert newest["total_bdt"] == 1850 + 80


def test_owner_can_mark_a_ready_made_line_as_shipped(owner_client):
    owner_client.post("/api/orders", json={"customer": DELIVERY, "items": [
        {"product_code": "SR-003", "size": "M", "colour": "Mustard"}]})
    line = owner_client.get("/api/owner/orders").get_json()["orders"][0]["items"][0]

    updated = owner_client.patch(f"/api/owner/custom-orders/{line['id']}", json={"status": "shipped"})
    assert updated.get_json()["status"] == "shipped"
    assert owner_client.get("/api/owner/orders").get_json()["summary"]["to_ship"] == 0


def test_orders_need_the_owner_login(client):
    assert client.get("/api/owner/orders").status_code == 401


def test_owner_can_send_todays_stock_to_the_assistant(owner_client, maira):
    owner_client.post("/api/orders", json={"customer": DELIVERY, "items": [
        {"product_code": "SR-003", "size": "M", "colour": "Mustard", "quantity": 5}]})

    assert owner_client.post("/api/owner/products/sync").status_code == 200

    dataset_id, _, content = maira.uploads[0]
    row = next(line for line in content.decode().splitlines() if line.startswith("SR-003,"))
    assert dataset_id == "dataset-1" and maira.trained == ["dataset-1"]
    assert ",1850,20,no," in row  # price, then the stock after the order: 25 - 5


def test_an_order_confirmed_in_the_chat_reaches_the_orders_tab_marked_as_chat(owner_client):
    owner_client.post("/api/orders", json={"customer": DELIVERY, "source": "chat", "items": [
        {"product_code": "SR-003", "size": "M", "colour": "Mustard"}]})
    owner_client.post("/api/orders", json={"customer": DELIVERY, "items": [  # the checkout page, as before
        {"product_code": "SR-003", "size": "S", "colour": "White"}]})

    data = owner_client.get("/api/owner/orders").get_json()
    assert [order["source"] for order in data["orders"]] == ["website", "chat"]  # newest first
    assert (data["summary"]["order_count"], data["summary"]["chat_orders"]) == (2, 1)


def test_an_order_line_only_moves_forward(owner_client):
    order = owner_client.post("/api/orders", json={
        "customer": {"name": "A", "phone": "1", "address": "Dhaka", "delivery_area": "inside_dhaka"},
        "items": [{"product_code": "SR-002", "size": "M", "colour": "Maroon",
                   "option_ids": [option_id("Sleeves", "Short sleeves")]},
                  {"product_code": "SR-003", "size": "M", "colour": "Mustard"}],
    }).get_json()
    custom, ready_made = order["items"]
    assert custom["next_statuses"] == ["in_production", "shipped"]
    assert ready_made["next_statuses"] == ["shipped"]  # already made: no production step

    def move(item, status):
        return owner_client.patch(f"/api/owner/custom-orders/{item['id']}", json={"status": status})

    assert move(custom, "in_production").get_json()["next_statuses"] == ["shipped"]
    assert move(custom, "new").status_code == 400  # production has started
    shipped = move(custom, "shipped").get_json()
    assert (shipped["status"], shipped["next_statuses"]) == ("shipped", [])
    response = move(custom, "in_production")
    assert response.status_code == 400 and "can't go back" in response.get_json()["error"]  # a sent parcel can't come back
    assert move(custom, "shipped").status_code == 200  # the same status again (a double click) changes nothing
