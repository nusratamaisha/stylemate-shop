"""The Help page: questions and answers, contact details, and messages to the owner."""

import io

from stylemate.extensions import db
from stylemate.models import ContactMessage, Tenant

MESSAGE = {"name": "Nadia", "contact": "01711-000000", "message": "Do you deliver to Sylhet?"}


def test_help_page_lists_questions_and_contact_details(client):
    data = client.get("/api/help").get_json()

    assert data["faq"][0]["question"] == "How do I choose my size?"
    assert all(item["answer"] for item in data["faq"])
    assert data["contact"]["phone"] and data["contact"]["hours"]


def test_customer_message_reaches_the_owner(client, owner_client):
    assert client.post("/api/contact", json=MESSAGE).status_code == 201

    inbox = owner_client.get("/api/owner/messages").get_json()
    assert len(inbox) == 1
    assert (inbox[0]["name"], inbox[0]["contact"], inbox[0]["message"]) == \
        ("Nadia", "01711-000000", "Do you deliver to Sylhet?")


def test_message_without_a_way_to_reply_is_refused(client):
    response = client.post("/api/contact", json={**MESSAGE, "contact": "  "})
    assert response.status_code == 400
    assert "phone number or email" in response.get_json()["error"]
    assert db.session.scalar(db.select(ContactMessage)) is None


def photo_form(**changes):
    return {**MESSAGE, "picture": (io.BytesIO(b"photo of a measuring tape"), "wrong size.jpg", "image/jpeg"), **changes}


def test_message_can_carry_a_photo_that_only_the_owner_can_open(app, client, owner_client):
    assert client.post("/api/contact", data=photo_form(), content_type="multipart/form-data").status_code == 201

    message = owner_client.get("/api/owner/messages").get_json()[0]
    assert message["has_picture"] is True and message["message"] == "Do you deliver to Sylhet?"
    picture = owner_client.get(f"/api/owner/messages/{message['id']}/picture")
    assert picture.data == b"photo of a measuring tape"
    # Saved under a random name, never the customer's own file name
    assert db.session.scalar(db.select(ContactMessage.picture)) != "wrong size.jpg"

    owner_client.post("/api/owner/logout")
    assert client.get(f"/api/owner/messages/{message['id']}/picture").status_code == 401


def test_a_file_that_is_not_a_photo_is_refused_and_not_counted(app, client):
    app.config["CONTACT_MESSAGES_PER_DAY"] = 1
    wrong = photo_form(picture=(io.BytesIO(b"%PDF"), "bill.pdf", "application/pdf"))

    response = client.post("/api/contact", data=wrong, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "JPG, PNG or WebP" in response.get_json()["error"]
    assert db.session.scalar(db.select(ContactMessage)) is None
    assert client.post("/api/contact", json=MESSAGE).status_code == 201  # today's one message is still available


def test_a_message_without_a_photo_has_none_to_open(client, owner_client):
    client.post("/api/contact", json=MESSAGE)
    message = owner_client.get("/api/owner/messages").get_json()[0]

    assert message["has_picture"] is False
    assert owner_client.get(f"/api/owner/messages/{message['id']}/picture").status_code == 400


def test_messages_need_the_owner_login(client):
    assert client.get("/api/owner/messages").status_code == 401


def test_owner_sees_only_their_own_shops_messages(app, owner_client):
    other = Tenant(slug="other-shop", name="Other Shop")
    db.session.add(other)
    db.session.commit()
    db.session.add(ContactMessage(tenant_id=other.id, name="X", contact="x@x.test", message="For another shop"))
    db.session.commit()

    assert owner_client.get("/api/owner/messages").get_json() == []


def test_one_visitor_can_send_only_a_few_messages_a_day(app, client):
    app.config["CONTACT_MESSAGES_PER_DAY"] = 2
    assert client.post("/api/contact", json=MESSAGE).status_code == 201
    assert client.post("/api/contact", json={**MESSAGE, "name": ""}).status_code == 400  # a mistake isn't counted
    assert client.post("/api/contact", json=MESSAGE).status_code == 201

    third = client.post("/api/contact", json=MESSAGE)
    assert third.status_code == 429
    assert "call or email" in third.get_json()["error"]
    assert len(db.session.scalars(db.select(ContactMessage)).all()) == 2

    # A different visitor (another address) is not affected
    assert client.post("/api/contact", json=MESSAGE, environ_base={"REMOTE_ADDR": "10.0.0.9"}).status_code == 201


def test_help_answers_are_sent_to_their_own_maira_dataset(app, tenant, maira):
    publisher = app.extensions["stylemate"].help_publisher

    count = publisher.publish(tenant)

    # A new dataset with the product dataset's tag, so the chat profile finds it
    assert maira.created_datasets == [{"name": "stylemate-help", "idx_column": "help_id", "tags": ["house_of_m"]}]
    assert tenant.maira_help_dataset_id == "help-dataset-1"
    dataset_id, filename, content = maira.uploads[0]
    text = content.decode()
    assert dataset_id == "help-dataset-1" and maira.trained == ["help-dataset-1"]
    assert text.splitlines()[0] == "help_id,topic,question,answer"
    assert "Can I return or exchange an order?" in text  # the FAQ
    assert "Size XL is cut for a bust of 40 inches" in text  # the size guide
    assert "Short sleeves are about 7 inches long" in text
    assert "How can I contact the shop?" in text
    assert count == len(text.splitlines()) - 1

    # Sending again reuses the dataset instead of creating a second one
    publisher.publish(tenant)
    assert len(maira.created_datasets) == 1


def test_the_assistant_gets_the_customization_charges_from_the_database(app, tenant):
    # Oct 15: without them the assistant said the price of longer sleeves "isn't specified"
    from stylemate.models import CustomizationOption
    from stylemate.services.help import help_documents

    answers = {row["help_id"]: row["answer"] for row in help_documents(tenant)}
    assert "Full sleeves (about 23 inches): 200 taka extra" in answers["CUSTOM-CHARGES"]
    assert "Made to your measurements: no extra charge" in answers["CUSTOM-CHARGES"]
    assert "longer than the piece costs 250 taka extra" in answers["CUSTOM-LENGTH"]
    assert "1,900 + 200 = 2,100 taka" in answers["CUSTOM-SLEEVES"]

    # A new price in the database is what the assistant is told next time
    full = db.session.scalar(db.select(CustomizationOption).where(CustomizationOption.label == "Full sleeves"))
    full.extra_price_bdt = 220
    db.session.commit()
    answers = {row["help_id"]: row["answer"] for row in help_documents(tenant)}
    assert "Full sleeves (about 23 inches): 220 taka extra" in answers["CUSTOM-CHARGES"]
    assert "1,900 + 220 = 2,120 taka" in answers["CUSTOM-SLEEVES"]  # the worked example follows it
