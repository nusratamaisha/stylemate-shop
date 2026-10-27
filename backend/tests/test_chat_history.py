"""A customer's chats: the one they are in now, and past chats they can open again. Never the owner's to read."""

from stylemate.services import chat_history

SIGNUP = {"name": "Nadia Rahman", "email": "nadia@example.com", "password": "long-enough"}
CHAT = {
    "messages": [
        {"role": "customer", "text": "Do you have a yellow top?"},
        {"role": "stylist", "text": "Which size would you like?", "draftId": 1, "answered": None,
         "question": {"field": "size", "choices": [{"label": "M", "value": "M"}]}},
    ],
    "drafts": {"1": {"id": 1, "size": "", "colour": "Yellow", "quantity": 1}},
    "session_id": "maira-session-1",
}
EMPTY = {"messages": [], "drafts": {}, "session_id": None}


def sign_up(client, email=SIGNUP["email"]):
    return client.post("/api/account/register", json={**SIGNUP, "email": email})


def chat_about(text):
    return {**CHAT, "messages": [{"role": "customer", "text": text}]}


def test_a_guest_has_no_chats_on_the_server(client):
    assert client.get("/api/account/chats/current").status_code == 401
    assert client.put("/api/account/chats/current", json=CHAT).status_code == 401
    assert client.get("/api/account/chats").status_code == 401


def test_the_current_chat_comes_back_after_logging_in_again(client):
    sign_up(client)
    assert client.get("/api/account/chats/current").get_json() == EMPTY
    assert client.put("/api/account/chats/current", json=CHAT).status_code == 200

    client.post("/api/account/logout")
    client.post("/api/account/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]})
    assert client.get("/api/account/chats/current").get_json() == CHAT  # an order still being filled in too
    assert client.get("/api/account/chats").get_json() == []  # not ended, so not a past chat yet


def test_new_chat_moves_the_chat_to_the_list(client):
    sign_up(client)
    client.put("/api/account/chats/current", json=chat_about("Do you have a yellow top?"))
    client.post("/api/account/chats/current/end")
    client.put("/api/account/chats/current", json=chat_about("Is the Bela dress cotton?"))
    client.post("/api/account/chats/current/end")

    assert client.get("/api/account/chats/current").get_json() == EMPTY  # a fresh chat
    past = client.get("/api/account/chats").get_json()
    assert [chat["title"] for chat in past] == ["Is the Bela dress cotton?", "Do you have a yellow top?"]  # newest first
    opened = client.get(f"/api/account/chats/{past[1]['id']}").get_json()
    assert opened["messages"] == [{"role": "customer", "text": "Do you have a yellow top?"}]


def test_an_empty_chat_is_not_added_to_the_list(client):
    sign_up(client)
    client.put("/api/account/chats/current", json=CHAT)
    client.put("/api/account/chats/current", json=EMPTY)
    client.post("/api/account/chats/current/end")
    assert client.get("/api/account/chats").get_json() == []


def test_a_past_chat_can_be_deleted(client):
    sign_up(client)
    client.put("/api/account/chats/current", json=CHAT)
    client.post("/api/account/chats/current/end")
    chat_id = client.get("/api/account/chats").get_json()[0]["id"]
    assert client.delete(f"/api/account/chats/{chat_id}").status_code == 200
    assert client.get("/api/account/chats").get_json() == []
    assert client.get(f"/api/account/chats/{chat_id}").status_code == 400


def test_only_the_newest_past_chats_are_kept(client, monkeypatch):
    monkeypatch.setattr(chat_history, "MAX_PAST_CHATS", 2)
    sign_up(client)
    for text in ["first", "second", "third"]:
        client.put("/api/account/chats/current", json=chat_about(text))
        client.post("/api/account/chats/current/end")
    assert [chat["title"] for chat in client.get("/api/account/chats").get_json()] == ["third", "second"]

def test_a_past_chat_can_be_continued(client):
    sign_up(client)
    client.put("/api/account/chats/current", json=CHAT)
    client.post("/api/account/chats/current/end")
    client.put("/api/account/chats/current", json=chat_about("Is the Bela dress cotton?"))
    chat_id = client.get("/api/account/chats").get_json()[0]["id"]

    assert client.post(f"/api/account/chats/{chat_id}/resume").get_json() == CHAT  # with its order and Maira's session
    assert client.get("/api/account/chats/current").get_json() == CHAT
    past = client.get("/api/account/chats").get_json()
    assert [chat["title"] for chat in past] == ["Is the Bela dress cotton?"]  # the two chats swapped places


def test_continuing_the_oldest_chat_does_not_delete_it(client, monkeypatch):
    monkeypatch.setattr(chat_history, "MAX_PAST_CHATS", 2)
    sign_up(client)
    for text in ["first", "second"]:
        client.put("/api/account/chats/current", json=chat_about(text))
        client.post("/api/account/chats/current/end")
    client.put("/api/account/chats/current", json=chat_about("third"))
    oldest = client.get("/api/account/chats").get_json()[-1]["id"]

    assert client.post(f"/api/account/chats/{oldest}/resume").status_code == 200
    assert client.get("/api/account/chats/current").get_json()["messages"] == [{"role": "customer", "text": "first"}]
    assert [chat["title"] for chat in client.get("/api/account/chats").get_json()] == ["third", "second"]


def test_each_customer_sees_only_their_own_chats(app):
    nadia, rima = app.test_client(), app.test_client()
    sign_up(nadia)
    sign_up(rima, email="rima@example.com")
    nadia.put("/api/account/chats/current", json=CHAT)
    nadia.post("/api/account/chats/current/end")
    chat_id = nadia.get("/api/account/chats").get_json()[0]["id"]

    assert rima.get("/api/account/chats").get_json() == []
    assert rima.get(f"/api/account/chats/{chat_id}").status_code == 400
    assert rima.delete(f"/api/account/chats/{chat_id}").status_code == 400
    assert rima.post(f"/api/account/chats/{chat_id}/resume").status_code == 400
    assert len(nadia.get("/api/account/chats").get_json()) == 1  # still there


def test_the_owner_cannot_read_customer_chats(client, owner_client):
    sign_up(client)
    client.put("/api/account/chats/current", json=CHAT)
    client.post("/api/account/chats/current/end")
    client.post("/api/account/logout")  # the same browser, now logged in only as the owner
    assert owner_client.get("/api/account/chats").status_code == 401
    assert "Do you have a yellow top?" not in owner_client.get("/api/owner/business").get_data(as_text=True)


def test_a_malformed_or_huge_chat_is_refused(client):
    sign_up(client)
    assert client.put("/api/account/chats/current", json={"messages": "hello"}).status_code == 400
    assert client.put("/api/account/chats/current", json={"messages": [{"text": "hi"}], "session_id": 5}).status_code == 400
    too_many = [{"role": "customer", "text": "hi"}] * (chat_history.MAX_MESSAGES + 1)
    assert client.put("/api/account/chats/current", json={"messages": too_many}).status_code == 400
    too_big = [{"role": "customer", "text": "x" * 5000}] * chat_history.MAX_MESSAGES
    assert "too long" in client.put("/api/account/chats/current", json={"messages": too_big}).get_json()["error"]
    assert client.get("/api/account/chats/current").get_json() == EMPTY  # nothing half-saved
