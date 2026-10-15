"""Recommendations: Gigalogy's suggestions, filtered to what this shop can sell, with the shop's own picks as backup."""

from stylemate.clients.recommender import parse_item_ids
from stylemate.extensions import db
from stylemate.models import Product


def codes(response):
    return [product["code"] for product in response.get_json()["products"]]


def switch_on(tenant):
    tenant.recommender_ready = True
    db.session.commit()


def test_before_setup_the_shop_shows_its_own_picks_without_calling_gigalogy(client, recommender):
    response = client.get("/api/products/SR-003/recommendations?visitor_id=v1")
    # Other dresses, closest in price first; SR-004 is sold out but can be made to order
    assert codes(response) == ["SR-006", "SR-004", "SR-001", "SR-005"]
    assert response.get_json()["source"] == "shop" and recommender.calls == []


def test_gigalogys_order_is_kept_and_what_the_shop_cant_sell_is_dropped(client, tenant, recommender):
    switch_on(tenant)
    db.session.scalar(db.select(Product).where(Product.code == "SR-009")).stock = 0  # sold out, not customizable
    db.session.commit()
    recommender.similar = ["SR-003", "SR-999", "SR-009", "SR-010", "SR-007"]  # itself, unknown, sold out, two good

    response = client.get("/api/products/SR-003/recommendations?visitor_id=v1")
    assert codes(response) == ["SR-010", "SR-007", "SR-006", "SR-004"]  # topped up with the shop's own picks
    assert response.get_json()["source"] == "gigalogy"
    assert recommender.calls == [("similar_items", "v1", "SR-003", None)]


def test_a_product_page_seen_again_soon_costs_no_new_call(client, tenant, recommender):
    switch_on(tenant)
    recommender.similar = ["SR-010"]
    client.get("/api/products/SR-003/recommendations?visitor_id=v1")
    client.get("/api/products/SR-003/recommendations?visitor_id=v2")
    assert len(recommender.calls) == 1


def test_when_gigalogy_fails_the_page_still_gets_suggestions(client, tenant, recommender):
    switch_on(tenant)
    recommender.fail = True
    response = client.get("/api/products/SR-003/recommendations")
    assert response.status_code == 200 and len(codes(response)) == 4 and response.get_json()["source"] == "shop"


def test_a_customer_with_a_usual_size_sees_pieces_in_that_size(client, tenant, recommender):
    switch_on(tenant)
    client.post("/api/account/register", json={"name": "Rina", "email": "rina@example.com", "password": "long-enough"})
    client.patch("/api/account/details", json={"preferred_size": "XS"})
    recommender.similar = ["SR-010", "SR-005", "SR-006"]  # SR-010 has no XS; SR-006 has none but can be made to measure

    response = client.get("/api/products/SR-003/recommendations?visitor_id=v1")
    assert codes(response)[:2] == ["SR-005", "SR-006"] and "SR-010" not in codes(response)
    assert recommender.calls[0][3].startswith("customer-")  # Gigalogy's member_id for a logged-in customer


def test_the_bag_gets_pieces_that_complete_the_look(client, tenant, recommender):
    response = client.post("/api/recommendations/bag", json={"codes": ["SR-009"], "visitor_id": "v1"})
    # A top in the bag: other sections first, sharing an occasion (Office, Party), nearest in price
    assert codes(response)[0] == "SR-008" and "SR-009" not in codes(response)

    switch_on(tenant)
    recommender.cart = ["SR-009", "SR-010"]
    response = client.post("/api/recommendations/bag", json={"codes": ["SR-009"], "visitor_id": "v1"})
    assert codes(response)[0] == "SR-010"
    assert recommender.calls == [("cart_items", "v1", ("SR-009",), None)]
    assert client.post("/api/recommendations/bag", json={"codes": []}).get_json()["products"] == []


def test_sync_recommender_sets_up_gigalogy_and_switches_it_on(app, tenant, recommender):
    result = app.test_cli_runner().invoke(args=["sync-recommender"])

    assert result.exit_code == 0, result.output
    assert [call[0] for call in recommender.calls] == ["create_indices", "save_mapper", "train_items"]
    filename, content = recommender.uploads[0]
    lines = content.decode().splitlines()
    assert lines[0].startswith("product_id,name,category") and len(lines) == 11  # header + 10 products
    assert "SR-004" in content.decode() and ",in_stock," in lines[4]  # sold out but customizable: still offered
    assert tenant.recommender_ready


def test_a_failed_setup_leaves_the_shop_on_its_own_picks(app, tenant, recommender):
    recommender.fail = True
    result = app.test_cli_runner().invoke(args=["sync-recommender"])
    assert result.exit_code != 0 and "own picks" in result.output
    assert not tenant.recommender_ready


def test_item_ids_are_read_from_the_likely_response_shapes():
    assert parse_item_ids({"detail": ["SR-1", "SR-2"]}) == ["SR-1", "SR-2"]
    assert parse_item_ids({"detail": [{"item_id": "SR-1", "score": 0.9}, {"item_id": "SR-2"}]}) == ["SR-1", "SR-2"]
    assert parse_item_ids({"detail": {"items": [{"item_id": "SR-1"}], "total": 1}}) == ["SR-1"]
    assert parse_item_ids({"detail": {"recommended_items": [{"id": 7}, {"id": 7}]}}) == ["7"]  # repeats dropped
    assert parse_item_ids({"detail": "Not trained yet"}) == []
