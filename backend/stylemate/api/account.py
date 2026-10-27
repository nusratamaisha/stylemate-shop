"""Routes for customer accounts, order history, chat history and reviews."""

from flask import Blueprint, g, jsonify, session

from ..services import accounts, catalog, chat_history, reviews
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


@bp.patch("/account/details")
@customer_required
def update_details():
    """The customer changes or clears the details saved for checkout."""
    return jsonify({"customer": accounts.update_details(g.customer, json_body()).to_dict()})


@bp.get("/account/orders")
@customer_required
def my_orders():
    return jsonify(accounts.order_history(g.customer))


# --- Chats with the stylist. There is no owner route for any of these (services/chat_history.py) ---

@bp.get("/account/chats/current")
@customer_required
def my_current_chat():
    return jsonify(chat_history.current(g.customer))


@bp.put("/account/chats/current")
@customer_required
def save_my_current_chat():
    """The chat window sends its messages after every change."""
    chat_history.save_current(g.customer, json_body())
    return jsonify({"ok": True})


@bp.post("/account/chats/current/end")
@customer_required
def end_my_current_chat():
    """ "New chat": the chat joins the list of past chats."""
    chat_history.end_current(g.customer)
    return jsonify({"ok": True})


@bp.get("/account/chats")
@customer_required
def my_past_chats():
    return jsonify(chat_history.past_chats(g.customer))


@bp.get("/account/chats/<int:chat_id>")
@customer_required
def my_past_chat(chat_id: int):
    return jsonify(chat_history.past_chat(g.customer, chat_id))


@bp.delete("/account/chats/<int:chat_id>")
@customer_required
def delete_my_past_chat(chat_id: int):
    chat_history.delete_past_chat(g.customer, chat_id)
    return jsonify({"ok": True})


@bp.post("/account/chats/<int:chat_id>/resume")
@customer_required
def resume_my_past_chat(chat_id: int):
    """ "Continue this chat": it becomes the current chat again, and the window shows what this returns."""
    return jsonify(chat_history.resume_past_chat(g.customer, chat_id))


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
