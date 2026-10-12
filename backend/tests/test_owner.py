"""The owner dashboard: login, insights, the custom order queue and CSV upload."""

import io

from .conftest import OWNER_EMAIL, option_id


def test_dashboard_needs_login(client):
    assert client.get("/api/owner/insights").status_code == 401


def test_wrong_password_is_rejected(client):
    response = client.post("/api/owner/login", json={"email": OWNER_EMAIL, "password": "nope"})
    assert response.status_code == 401


def test_insights_group_questions_and_list_unanswered(owner_client, maira):
    for question in ["Do you sell shoes?", "do you sell shoes", "Do you sell SHOES!"]:
        maira.top_score = 23.0
        owner_client.post("/api/chat", json={"message": question})
    maira.top_score = 42.0
    owner_client.post("/api/chat", json={"message": "Wedding dress under 4500?"})

    data = owner_client.get("/api/owner/insights").get_json()
    assert data["total_questions"] == 4
    assert data["unanswered_count"] == 3
    assert data["answer_rate"] == 25
    assert data["unanswered_questions"][0]["count"] == 3


def test_custom_order_queue_and_status_update(owner_client):
    owner_client.post("/api/orders", json={
        "customer": {"name": "A", "phone": "1", "address": "Dhaka", "delivery_area": "inside_dhaka"},
        "items": [
            {"product_code": "SR-002", "size": "M", "colour": "Maroon",
             "option_ids": [option_id("Lining", "Add full cotton lining")]},
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
