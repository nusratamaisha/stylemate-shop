"""Business insights for the owner: what to restock, what not to, best sellers, fit and this month's trend."""

from datetime import datetime, timedelta, timezone

from stylemate.extensions import db
from stylemate.models import Order
from stylemate.services.insights import business_insights, missing_topics, topic_of

from .conftest import option_id

CUSTOMER = {"name": "Nusrat", "phone": "01700000000", "address": "Dhaka", "delivery_area": "inside_dhaka"}
NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def order(client, *items, days_ago=0):
    response = client.post("/api/orders", json={"customer": CUSTOMER, "items": list(items)})
    assert response.status_code == 201, response.get_json()
    placed = db.session.get(Order, response.get_json()["order_id"])
    placed.created_at = NOW - timedelta(days=days_ago)  # so the 30-day window doesn't depend on today
    db.session.commit()


def ready(code, size, colour, quantity=1):
    return {"product_code": code, "size": size, "colour": colour, "quantity": quantity}


def measured(code="SR-002", colour="Maroon"):
    return {"product_code": code, "colour": colour, "measurements": {"bust": 38},
            "option_ids": [option_id("Fit", "Made to your measurements")]}


def test_insights_need_an_owner(client):
    assert client.get("/api/owner/business").status_code == 401


def test_a_fast_seller_running_low_is_flagged_for_restocking(client, tenant):
    order(client, ready("SR-010", "M", "Sage", 3), days_ago=5)  # 7 in stock, 2 orders: 5 sold, 2 left
    order(client, ready("SR-010", "S", "Sage", 2), days_ago=2)
    order(client, ready("SR-003", "M", "Mustard"))  # 24 left at 1 a month: plenty

    restock = business_insights(tenant, NOW)["restock"]
    assert [item["code"] for item in restock] == ["SR-010"]
    assert restock[0]["stock"] == 2 and restock[0]["sold_recently"] == 5
    assert restock[0]["days_left"] == 12  # 2 left at 5 per 30 days


def test_pieces_that_did_not_sell_lately_are_listed_as_slow(client, tenant):
    order(client, ready("SR-008", "M", "Black"), days_ago=60)  # sold once, two months ago
    order(client, ready("SR-007", "L", "Indigo"), days_ago=3)  # sold this month: not slow

    data = business_insights(tenant, NOW)
    slow = {item["code"]: item for item in data["slow"]}
    assert "SR-007" not in slow
    assert slow["SR-008"]["sold_total"] == 1 and slow["SR-008"]["last_sold"].startswith("2026-08-21")
    assert "SR-004" not in slow  # sold out: nothing to decide
    assert data["days_of_orders"] == 60


def test_best_sellers_say_which_size_and_colour_sell(client, tenant):
    order(client, ready("SR-009", "M", "White", 2), ready("SR-009", "S", "Blush Pink"))
    order(client, ready("SR-009", "M", "White"), ready("SR-003", "M", "Mustard"))

    best = business_insights(tenant, NOW)["best_sellers"][0]
    assert best["code"] == "SR-009" and best["sold"] == 4 and best["revenue_bdt"] == 4 * 1450
    assert best["top_size"] == "M" and best["top_colour"] == "White"


def test_a_piece_mostly_made_to_measure_is_flagged_for_its_sizes(client, tenant):
    order(client, measured())
    order(client, measured())
    order(client, ready("SR-002", "M", "Maroon"))
    order(client, measured("SR-006", "Teal"), ready("SR-006", "M", "Teal"), ready("SR-006", "L", "Teal"))

    fit = business_insights(tenant, NOW)["made_to_measure"]
    assert [item["code"] for item in fit] == ["SR-002"]  # SR-006: 1 of 3, a third
    assert fit[0]["share"] == 67 and fit[0]["orders"] == 3 and fit[0]["sizes"] == ["S", "M", "L"]


def test_this_month_is_compared_with_last_month(owner_client, tenant):
    order(owner_client, ready("SR-003", "M", "Mustard", 2), days_ago=1)  # October
    order(owner_client, ready("SR-003", "S", "White"), days_ago=25)  # September
    order(owner_client, ready("SR-003", "S", "White"), days_ago=60)  # August: in neither

    trend = business_insights(tenant, NOW)["trend"]
    assert trend["this_month_name"] == "October" and trend["last_month_name"] == "September"
    assert trend["this_month"]["orders"] == 1 and trend["this_month"]["sales_bdt"] == 2 * 1850
    assert trend["last_month"]["orders"] == 1 and trend["last_month"]["pieces"] == 1
    assert owner_client.get("/api/owner/business").status_code == 200


def test_unanswered_questions_are_grouped_into_topics(owner_client, maira):
    for question, score in [("Do you have XXL?", 23.0), ("is there 2xl", 20.0), ("Plus size dresses?", 18.0),
                            ("Do you sell shoes", 21.0), ("Do you have a pink dress?", 42.0)]:
        maira.top_score = score  # below the threshold: not answered from the catalogue
        owner_client.post("/api/chat", json={"message": question})

    chat = owner_client.get("/api/owner/business").get_json()["chat"]
    assert chat["total_questions"] == 5 and chat["answer_rate"] == 20
    assert [(item["topic"], item["count"]) for item in chat["missing"]] == [("Bigger sizes", 3), ("Shoes and bags", 1)]
    assert chat["missing"][0]["examples"] == ["Plus size dresses?", "is there 2xl", "Do you have XXL?"]  # newest first
    assert "recent" not in chat and maira.answer not in str(chat)  # the stylist's answers are never sent


def test_topics_match_whole_words_and_put_the_rest_under_other():
    assert topic_of("Any SAREE for Eid?") == "Sarees"
    assert topic_of("Do you deliver to the UK?") == "Delivery abroad"
    assert topic_of("Is this cotton?") == "Other"
    assert topic_of("Do you have a manual?") == "Other"  # "man" inside "manual" is not men's clothes


def test_the_chat_share_of_orders_is_counted(client, tenant):
    order(client, ready("SR-003", "M", "Mustard"))
    chat = business_insights(tenant, NOW)["chat"]
    assert chat["order_count"] == 1 and chat["chat_orders"] == 0


def test_unreadable_questions_count_but_are_not_shown_as_examples():
    assert missing_topics([".", "ok", "Is this cotton?"]) == [
        {"topic": "Other", "count": 3, "examples": ["Is this cotton?"]}]
