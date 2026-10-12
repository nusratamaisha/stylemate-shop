"""Routes for the shop owner's dashboard. All except login need a logged-in owner."""

from flask import Blueprint, g, jsonify, request, session

from ..extensions import db
from ..models import User
from ..services import catalog, help, insights, orders
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


@bp.get("/insights")
@owner_required
def owner_insights():
    return jsonify(insights.owner_insights(g.tenant))


@bp.get("/custom-orders")
@owner_required
def custom_orders():
    items = orders.custom_order_queue(g.tenant, request.args.get("status") or None)
    return jsonify([item.to_dict() for item in items])


@bp.patch("/custom-orders/<int:item_id>")
@owner_required
def update_custom_order(item_id: int):
    item = orders.update_custom_order_status(g.tenant, item_id, str(json_body().get("status") or ""))
    return jsonify(item.to_dict())


@bp.get("/messages")
@owner_required
def customer_messages():
    return jsonify([message.to_dict() for message in help.messages(g.tenant)])


@bp.get("/products")
@owner_required
def products():
    return jsonify([product.to_dict() for product in catalog.list_products(g.tenant)])


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
