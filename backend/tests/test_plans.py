"""StyleMate's plans: the public price list, monthly limits the app enforces, and demo requests."""

import io

from stylemate.extensions import db
from stylemate.models import PlanUsage, Tenant
from stylemate.services import plans


def put_on(tenant: Tenant, plan: str, **used):
    tenant.plan = plan
    for kind, count in used.items():
        db.session.add(PlanUsage(tenant_id=tenant.id, kind=kind, month=plans._month(), count=count))
    db.session.commit()


GROWTH = plans.PLANS["growth"]  # DRY: the tests read the plan's own numbers, so a new price or limit doesn't break them


def test_the_public_page_gets_the_plans_from_one_place(client):
    data = client.get("/api/plans").get_json()
    assert [plan["key"] for plan in data["plans"]] == ["growth", "pro"]
    assert data["plans"][0]["chat_questions"] == GROWTH.chat_questions
    assert data["prices_are_examples"] is True  # until Maisha has Gigalogy's prices


def test_chat_questions_stop_after_the_grace_margin_and_maira_is_not_asked(customer_client, tenant, maira):
    last_allowed = int(GROWTH.chat_questions * (1 + plans.GRACE))  # 2000 a month + 10% grace = 2200
    put_on(tenant, "growth", chat=last_allowed - 1)
    assert customer_client.post("/api/chat", json={"message": "Any dresses?"}).status_code == 200  # the last one allowed

    response = customer_client.post("/api/chat", json={"message": "And tops?"})
    assert response.status_code == 429 and "Help page" in response.get_json()["error"]
    assert len(maira.asked) == 1


def test_a_question_maira_fails_to_answer_is_not_counted(customer_client, tenant, maira):
    maira.fail = True
    customer_client.post("/api/chat", json={"message": "Any dresses?"})
    assert plans.used(tenant, "chat") == 0


def test_growth_has_voice_and_previews(client, tenant):
    put_on(tenant, "growth")
    assert client.get("/api/shop").get_json()["features"] == {"voice": True, "previews": True}


def test_previews_are_hidden_when_the_plan_has_none_left(client, tenant):
    tenant.maira_image_profile_id = "image-profile"
    put_on(tenant, "growth", preview=220)  # 200 + 10% grace, all used
    assert client.get("/api/products/SR-002").get_json()["preview_available"] is False
    put_on(tenant, "pro")
    assert client.get("/api/products/SR-002").get_json()["preview_available"] is True


def test_a_catalogue_bigger_than_the_plan_is_refused(owner_client, tenant):
    put_on(tenant, "growth")  # the test shop already has 10 products
    header = "product_id,name,image,category,occasion,sizes,colours,fabric,length_inches,sleeve,price_bdt,stock,customizable,description\n"
    rows = "".join(f"SR-{100 + number},Piece {number},,Dress,Everyday,M,Black,Cotton,,,1000,5,no,A piece\n"
                   for number in range(GROWTH.products - 9))  # 10 + 191 = one more than Growth's 200
    response = owner_client.post("/api/owner/products/upload",
                                 data={"file": (io.BytesIO((header + rows).encode()), "products.csv")})
    assert response.status_code == 400 and f"up to {GROWTH.products} products" in response.get_json()["error"]


def test_the_owner_is_warned_from_80_percent(owner_client, tenant):
    warn_from = int(GROWTH.chat_questions * plans.WARN_AT)  # 80% of 2000 = 1600
    put_on(tenant, "growth", chat=warn_from)
    meters = owner_client.get("/api/owner/usage").get_json()["meters"]
    assert meters[0] == {"kind": "chat", "used": warn_from, "limit": GROWTH.chat_questions, "warn": True, "over": False}


def test_a_shop_owner_can_request_a_demo_and_stylemate_lists_it(app, client):
    response = client.post("/api/demo-requests", json={
        "shop_name": "Rongin Closet", "owner_name": "Sumaiya", "phone": "01712000000",
        "facebook_page": "https://facebook.com/ronginclosest", "product_count": "About 80", "plan": "growth"})
    assert response.status_code == 201
    assert client.post("/api/demo-requests", json={"shop_name": "No phone"}).status_code == 400

    listed = app.test_cli_runner().invoke(args=["demo-requests"]).output
    assert "Rongin Closet (Sumaiya, 01712000000)  plan: growth" in listed and "About 80" in listed


def test_set_plan_changes_the_shops_plan(app, tenant):
    result = app.test_cli_runner().invoke(args=["set-plan", "pro"])
    assert result.exit_code == 0 and "now on Pro" in result.output and tenant.plan == "pro"
    assert app.test_cli_runner().invoke(args=["set-plan", "gold"]).exit_code != 0
