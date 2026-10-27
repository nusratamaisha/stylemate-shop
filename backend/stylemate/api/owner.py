"""Routes for the shop owner's dashboard. All except login need a logged-in owner."""

from flask import Blueprint, current_app, g, jsonify, request, send_from_directory, session

from ..extensions import db
from ..models import User
from ..services import catalog, help, insights, orders, payments, plans
from .helpers import error, json_body, owner_required, services

bp = Blueprint("owner", __name__, url_prefix="/api/owner")


@bp.post("/login")
def login():
    body = json_body()
    email = str(body.get("email") or "").strip().lower()
    user = db.session.scalar(db.select(User).where(User.email == email))
    if user is None or not user.check_password(str(body.get("password") or "")):
        return error("Wrong email or password.", 401)
    session.clear()
    session["user_id"] = user.id
    return jsonify(_owner_info(user))


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/me")
@owner_required
def me():
    return jsonify(_owner_info(g.user))


@bp.get("/usage")
@owner_required
def plan_usage():
    """This month's use of the shop's plan, for the dashboard's warning banner."""
    return jsonify(plans.usage_summary(g.tenant))


@bp.get("/business")
@owner_required
def business_insights():
    """The Insights tab: restocking, best sellers, this month against last, and what the chat shows.
    Only summaries: the chat conversations themselves are never sent to the owner."""
    return jsonify(insights.business_insights(g.tenant))


@bp.get("/orders")
@owner_required
def all_orders():
    return jsonify({"summary": orders.sales_summary(g.tenant), "orders": orders.all_orders(g.tenant)})


@bp.patch("/orders/<int:order_id>/payment")
@owner_required
def update_payment(order_id: int):
    """The owner has checked the wallet (or collected the cash) and records the result."""
    order = payments.set_payment_status(g.tenant, order_id, str(json_body().get("status") or ""))
    return jsonify({"order_id": order.id, "payment_status": order.payment_status})


@bp.get("/custom-orders")
@owner_required
def custom_orders():
    items = orders.custom_order_queue(g.tenant, request.args.get("status") or None)
    return jsonify([item.to_dict() for item in items])


@bp.patch("/custom-orders/<int:item_id>")
@owner_required
def update_custom_order(item_id: int):
    item = orders.update_item_status(g.tenant, item_id, str(json_body().get("status") or ""))
    return jsonify(item.to_dict())


@bp.get("/custom-orders/<int:item_id>/reference-picture")
@owner_required
def reference_picture(item_id: int):
    """The customer's picture for the tailor. Only the owner of that order's shop can open it."""
    name = orders.reference_picture_name(g.tenant, item_id)
    return send_from_directory(current_app.config["UPLOADS_DIR"], name)


@bp.get("/messages")
@owner_required
def customer_messages():
    return jsonify([message.to_dict() for message in help.messages(g.tenant)])


@bp.get("/messages/<int:message_id>/picture")
@owner_required
def message_picture(message_id: int):
    """The photo a customer sent with a message. Only the owner of that shop can open it."""
    name = help.message_picture_name(g.tenant, message_id)
    return send_from_directory(current_app.config["UPLOADS_DIR"], name)


@bp.get("/products")
@owner_required
def products():
    return jsonify([product.to_dict() for product in catalog.list_products(g.tenant)])


@bp.post("/products/sync")
@owner_required
def sync_products():
    """Tell the assistant today's stock (orders change it in the database, not in Maira)."""
    services().catalog_importer.sync_stock(g.tenant)
    return jsonify({"message": "The assistant is learning today's stock; this takes about a minute."})


@bp.post("/products/upload")
@owner_required
def upload_products():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return error("Choose a CSV file to upload.", 400)
    if not upload.filename.lower().endswith(".csv"):
        return error("The file must be a .csv file.", 400)
    result = services().catalog_importer.import_csv(g.tenant, upload.filename, upload.read())
    return jsonify(result.to_dict())


def _owner_info(user: User) -> dict:
    return {"email": user.email, "shop": {"name": user.tenant.name, "slug": user.tenant.slug}}
