"""The assistant: text chat, voice, product cards and the unanswered-question flag."""
#(9 tests)
import io

from stylemate.extensions import db
from stylemate.models import ChatTurn
from stylemate.services.chat import is_answered, mentioned_products
from stylemate.services.catalog import list_products


def test_chat_returns_answer_and_mentioned_products(client, maira):
    response = client.post("/api/chat", json={"message": "Something for a wedding?", "visitor_id": "v1"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["answer"] == maira.answer
    assert [product["code"] for product in data["products"]] == ["SR-002"]
    assert data["answered"] is True
    assert maira.asked[0]["profile_id"] == "profile-1"  # the shop's profile, from the database


def test_chat_passes_session_id_for_follow_ups(client, maira):
    client.post("/api/chat", json={"message": "Does it come in XL?", "visitor_id": "v1", "session_id": "abc"})
    assert maira.asked[0]["session_id"] == "abc"


def test_chat_saves_each_turn(app, client, maira):
    maira.answer, maira.top_score = "No, we don't sell shoes.", 23.7
    client.post("/api/chat", json={"message": "Do you sell shoes?", "visitor_id": "v1"})

    turn = db.session.scalar(db.select(ChatTurn))
    assert turn.question == "Do you sell shoes?"
    assert turn.answered is False  # low score: the answer wasn't in the shop's data


def test_empty_question_is_rejected(client):
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400


def test_maira_outage_shows_a_friendly_message(client, maira):
    maira.fail = True
    response = client.post("/api/chat", json={"message": "Hello?"})
    assert response.status_code == 502
    assert "try again" in response.get_json()["error"]


def test_is_answered_uses_the_threshold():
    assert is_answered(42.5, 30) is True
    assert is_answered(23.7, 30) is False
    assert is_answered(None, 30) is False


def test_mentioned_products_follow_answer_order(app, tenant):
    answer = ("No, the **Nira Shirt Dress** is out of stock. Try the **Rumi Wrap Midi Dress** "
              "or the Kaya Linen Co-ord Set.")
    codes = [product.code for product in mentioned_products(list_products(tenant), answer)]
    assert codes == ["SR-004", "SR-001", "SR-010"]


def test_voice_transcribes_then_answers(client, chorus, maira):
    response = client.post("/api/voice", data={
        "audio": (io.BytesIO(b"RIFF fake wav"), "question.wav", "audio/wav"),
        "visitor_id": "v1",
    }, content_type="multipart/form-data")

    data = response.get_json()
    assert data["heard"] is True
    assert data["transcript"] == chorus.transcript
    assert maira.asked[0]["query"] == chorus.transcript
    assert db.session.scalar(db.select(ChatTurn)).via_voice is True


def test_voice_with_no_speech_does_not_call_maira(client, chorus, maira):
    chorus.transcript = ""
    response = client.post("/api/voice", data={"audio": (io.BytesIO(b"..."), "q.wav")},
                           content_type="multipart/form-data")
    assert response.get_json()["heard"] is False
    assert maira.asked == []


ORDER_ANSWER = ("Lovely choice. Taking you to checkout now.\n"
                "[ORDER product_id=SR-002; size=s; colour=emerald; quantity=1]")


def test_confirmed_order_is_checked_and_returned_without_the_marker(client, maira):
    maira.answer = ORDER_ANSWER
    data = client.post("/api/chat", json={"message": "yes, order it", "visitor_id": "v1"}).get_json()

    assert data["answer"] == "Lovely choice. Taking you to checkout now."  # the marker is never shown
    order = data["order"]
    assert order["product"]["code"] == "SR-002"
    assert (order["size"], order["colour"], order["quantity"]) == ("S", "Emerald", 1)  # the shop's spelling
    assert order["unit_price_bdt"] == 4200  # from the database, not from the assistant
    assert "[ORDER" not in db.session.scalar(db.select(ChatTurn)).answer


def test_order_for_a_size_the_piece_does_not_come_in_is_refused(client, maira):
    maira.answer = ORDER_ANSWER.replace("size=s", "size=XXL")
    data = client.post("/api/chat", json={"message": "yes"}).get_json()

    assert data["order"] is None
    assert "I couldn't start that order" in data["answer"] and "S, M, L" in data["answer"]
    assert "[ORDER" not in data["answer"]


def test_order_for_an_out_of_stock_piece_is_refused(client, maira):
    # SR-004 has no stock in the test catalogue
    maira.answer = "Done!\n[ORDER product_id=SR-004; size=M; colour=Black; quantity=1]"
    data = client.post("/api/chat", json={"message": "yes"}).get_json()

    assert data["order"] is None
    assert "out of stock" in data["answer"]


def test_ordinary_answers_have_no_order(client):
    assert client.post("/api/chat", json={"message": "Something for a wedding?"}).get_json()["order"] is None


def test_a_described_custom_piece_opens_the_product_page_prefilled(client, maira):
    maira.answer = ("I've set that up for you. Check the price on the product page.\n"
                    "[CUSTOMIZE product_id=SR-002; sleeves=sleeveless; bust=38; length=36; waist=; hip=]")
    data = client.post("/api/chat", json={"message": "shefali, sleeveless, length 36, bust 38"}).get_json()

    assert "[CUSTOMIZE" not in data["answer"]
    custom = data["customize"]
    assert custom["product"]["code"] == "SR-002"
    assert custom["sleeves"] == "Sleeveless"  # an option this piece offers, in the shop's wording
    assert custom["measurements"] == {"bust": 38, "length": 36}  # only what the customer gave
    assert "price" not in custom and "total_bdt" not in custom  # the chat never prices a custom piece


def test_customize_keeps_only_what_the_shop_can_make(client, maira):
    # SR-002 already has full sleeves, and 400 inches is not a bust measurement
    maira.answer = "Here you go.\n[CUSTOMIZE product_id=SR-002; sleeves=Full; bust=400; waist=30]"
    custom = client.post("/api/chat", json={"message": "x"}).get_json()["customize"]
    assert custom["sleeves"] == "" and custom["measurements"] == {"waist": 30}

    # SR-003 can't be customized at all
    maira.answer = "Sure.\n[CUSTOMIZE product_id=SR-003; bust=38]"
    data = client.post("/api/chat", json={"message": "x"}).get_json()
    assert data["customize"] is None and "can't be customized" in data["answer"]
