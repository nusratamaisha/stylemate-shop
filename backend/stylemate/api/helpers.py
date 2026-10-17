"""Small helpers every route uses: finding the shop, the logged-in owner, and the services."""

import hashlib
from dataclasses import dataclass
from functools import wraps

from flask import current_app, g, jsonify, request, session

from ..errors import ShopNotSetUpError
from ..extensions import db
from ..models import Customer, Tenant, User


@dataclass
class Services:
    """Objects built once in create_app() and shared by all requests."""

    chat: object
    chorus: object
    catalog_importer: object
    preview: object
    help_publisher: object
    recommender: object  # the Gigalogy recommender client, for `flask sync-recommender`
    recommendations: object


def services() -> Services:
    return current_app.extensions["stylemate"]


def current_tenant() -> Tenant:
    """The shop this storefront belongs to.

    Today it comes from the SHOP_SLUG setting. To serve many shops from one
    deployment, only this function changes (for example, read the subdomain).
    """
    if "tenant" not in g:
        slug = current_app.config["SHOP_SLUG"]
        tenant = db.session.scalar(db.select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            raise ShopNotSetUpError(f"Shop '{slug}' isn't set up yet. Run: uv run flask --app stylemate seed")
        g.tenant = tenant
    return g.tenant


def sender_key() -> str:
    """Recognises a visitor for daily limits without storing their IP address.

    Behind a proxy (nginx in Docker), request.remote_addr is the visitor's address only
    when PROXY_COUNT is set: create_app() then reads it from X-Forwarded-For.
    """
    secret = current_app.config["SECRET_KEY"]
    return hashlib.sha256(f"{secret}:{request.remote_addr}".encode()).hexdigest()


def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def error(message: str, status: int):
    return jsonify({"error": message}), status


def current_customer() -> Customer | None:
    """The logged-in customer of this shop, or None for a guest.

    Customers and owners use different session keys ("customer_id" and "user_id"),
    so one kind of login never counts as the other.
    """
    customer_id = session.get("customer_id")
    customer = db.session.get(Customer, customer_id) if customer_id else None
    if customer is None or customer.tenant_id != current_tenant().id:
        return None
    return customer


def customer_required(view):
    """Allow the route only for a logged-in customer."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        customer = current_customer()
        if customer is None:
            return error("Please log in to your account.", 401)
        g.customer = customer
        return view(*args, **kwargs)

    return wrapper


def owner_required(view):
    """Allow the route only for a logged-in owner, and use the owner's shop."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        if user is None:
            return error("Please log in.", 401)
        g.user = user
        g.tenant = user.tenant
        return view(*args, **kwargs)

    return wrapper
