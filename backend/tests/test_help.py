"""The Help page: questions and answers, contact details, and messages to the owner."""

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
    assert maira.created_datasets == [{"name": "house-of-m-help", "idx_column": "help_id", "tags": ["house_of_m"]}]
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
