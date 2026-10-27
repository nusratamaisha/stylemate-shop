"""Customer accounts: signing up, logging in, the details they save, and their own order history."""

import json

from ..errors import UserInputError
from ..extensions import db
from ..models import Customer, Order, Tenant
from .pricing import DELIVERY_AREAS, MADE_TO_MEASURE_SIZE, clean_measurements

MIN_PASSWORD_LENGTH = 6


def register(tenant: Tenant, name, email, password, phone="") -> Customer:
    name, email, phone = str(name or "").strip(), _clean_email(email), str(phone or "").strip()
    password = str(password or "")
    if not name:
        raise UserInputError("Please tell us your name.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise UserInputError("Please enter a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise UserInputError(f"Your password needs at least {MIN_PASSWORD_LENGTH} characters.")
    if _find(tenant, email):
        raise UserInputError("An account with that email already exists. Please log in.")

    customer = Customer(tenant_id=tenant.id, name=name[:120], email=email[:200], phone=phone[:40])
    customer.set_password(password)
    db.session.add(customer)
    db.session.commit()
    return customer


def authenticate(tenant: Tenant, email, password) -> Customer | None:
    """The customer if the email and password match, otherwise None."""
    customer = _find(tenant, _clean_email(email))
    if customer is None or not customer.check_password(str(password or "")):
        return None
    return customer


def remember_details(customer: Customer, order: Order, measured: dict[str, int] | None) -> None:
    """After an order the customer agreed to remember, keep what they typed for next time.
    Contact and delivery details fill in checkout; the size and measurements are what the
    product page and, later, recommendations start from. The transaction ID is never kept.
    The caller commits, so this is saved with the order or not at all.
    """
    customer.phone = order.phone
    customer.address = order.address
    customer.delivery_area = order.delivery_area
    customer.payment_method = order.payment_method
    ready_made = [line.size for line in order.items if line.size != MADE_TO_MEASURE_SIZE]
    if ready_made:
        customer.preferred_size = ready_made[-1]
    if measured:
        customer.measurements = json.dumps(measured)


def update_details(customer: Customer, details: dict) -> Customer:
    """The customer changes or clears what is saved, from their account page. Only the fields sent change."""
    details = details if isinstance(details, dict) else {}
    if "name" in details:
        name = str(details["name"] or "").strip()
        if not name:
            raise UserInputError("Please tell us your name.")
        customer.name = name[:120]
    if "phone" in details:
        customer.phone = str(details["phone"] or "").strip()[:40]
    if "address" in details:
        customer.address = str(details["address"] or "").strip()[:500]
    if "delivery_area" in details:
        area = str(details["delivery_area"] or "")
        if area and area not in DELIVERY_AREAS:
            raise UserInputError("Please choose inside or outside Dhaka.")
        customer.delivery_area = area
    if "payment_method" in details:
        method = str(details["payment_method"] or "")
        if method and method not in Order.PAYMENT_METHODS:
            raise UserInputError("Please choose a way to pay.")
        customer.payment_method = method
    if "preferred_size" in details:
        customer.preferred_size = str(details["preferred_size"] or "").strip()[:20]
    if "measurements" in details:  # empty clears them; otherwise checked like an order's
        numbers = clean_measurements(details["measurements"], require_all=False) if details["measurements"] else {}
        customer.measurements = json.dumps(numbers) if numbers else ""
    db.session.commit()
    return customer


def order_history(customer: Customer) -> list[dict]:
    """The customer's own orders, newest first, each with the customer's own order number."""
    orders = db.session.scalars(
        db.select(Order).where(Order.tenant_id == customer.tenant_id, Order.customer_id == customer.id)
        .order_by(Order.id)
    ).all()
    numbered = [{**order.to_dict(), "customer_order_number": number} for number, order in enumerate(orders, start=1)]
    return numbered[::-1]


def order_number(order: Order) -> int | None:
    """Which of the customer's orders this is: their first is 1, their second 2. None for a guest order.

    Every customer counts from 1. The shop-wide ID (order.id) stays as the reference the owner
    uses, because "order 2" alone would mean a different order for every customer.
    """
    if order.customer_id is None:
        return None
    return db.session.scalar(
        db.select(db.func.count(Order.id)).where(Order.customer_id == order.customer_id, Order.id <= order.id)
    )


def _find(tenant: Tenant, email: str) -> Customer | None:
    return db.session.scalar(
        db.select(Customer).where(Customer.tenant_id == tenant.id, Customer.email == email)
    )


def _clean_email(email) -> str:
    return str(email or "").strip().lower()
