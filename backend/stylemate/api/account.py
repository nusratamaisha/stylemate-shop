"""Routes for customer accounts, order history and reviews."""

from flask import Blueprint, g, jsonify, session

from ..services import accounts, catalog, reviews
from .helpers import current_customer, current_tenant, customer_required, error, json_body

bp = Blueprint("account", __name__, url_prefix="/api")


@bp.post("/account/register")
def register():
    body = json_body()
    customer = accounts.register(current_tenant(), body.get("name"), body.get("email"),
                                 body.get("password"), body.get("phone"))
    session["customer_id"] = customer.id
    return jsonify({"customer": customer.to_dict()}), 201


@bp.post("/account/login")
def login():
    body = json_body()
    customer = accounts.authenticate(current_tenant(), body.get("email"), body.get("password"))
    if customer is None:
        return error("Wrong email or password.", 401)
    session["customer_id"] = customer.id
    return jsonify({"customer": customer.to_dict()})


@bp.post("/account/logout")
def logout():
    session.pop("customer_id", None)  # leaves an owner login in the same browser alone
    return jsonify({"ok": True})


@bp.get("/account/me")
def me():
    """Who is logged in. Answers 200 with null for a guest, so the site can ask on every page load."""
    customer = current_customer()
    return jsonify({"customer": customer.to_dict() if customer else None})


@bp.get("/account/orders")
@customer_required
def my_orders():
    return jsonify([order.to_dict() for order in accounts.order_history(g.customer)])


@bp.get("/products/<code>/reviews")
def product_reviews(code: str):
    product = catalog.get_product(current_tenant(), code)
    return jsonify(reviews.product_reviews(product, current_customer()))


@bp.post("/products/<code>/reviews")
@customer_required
def add_review(code: str):
    body = json_body()
    product = catalog.get_product(current_tenant(), code)
    reviews.save_review(g.customer, product, body.get("rating"), body.get("comment"))
    return jsonify(reviews.product_reviews(product, g.customer)), 201
