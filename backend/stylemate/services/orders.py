"""Checkout and the custom order queue.

Prices sent by the browser are ignored: every price is recalculated here, so a
customer can't change what they pay by editing the page.
"""

from datetime import date, timedelta

from ..errors import UserInputError
from ..extensions import db
from ..models import Customer, Order, OrderItem, Tenant
from .catalog import get_product
from .pricing import quote_for, shipping_charge

MAX_QUANTITY = 10


def place_order(tenant: Tenant, customer: dict, items: list[dict], account: Customer | None = None) -> Order:
    """Check and save an order. `account` is the logged-in customer, or None for a guest checkout."""
    customer = customer or {}
    name, phone, address = (str(customer.get(key) or "").strip() for key in ("name", "phone", "address"))
    if not (name and phone and address):
        raise UserInputError("Please fill in your name, phone number and address.")
    if not items:
        raise UserInputError("Your cart is empty.")
    area = str(customer.get("delivery_area") or "")
    shipping = shipping_charge(tenant, area)  # the customer picks the area; Flask sets the charge

    order = Order(tenant_id=tenant.id, customer_id=account.id if account else None,
                  customer_name=name, phone=phone, address=address,
                  delivery_area=area, shipping_bdt=shipping, total_bdt=0)
    for item in items:
        order.items.append(_build_item(tenant, item))
    order.total_bdt = sum(line.unit_price_bdt * line.quantity for line in order.items) + shipping

    db.session.add(order)
    db.session.commit()
    return order


def _build_item(tenant: Tenant, item: dict) -> OrderItem:
    product = get_product(tenant, str(item.get("product_code") or ""))
    size, colour = str(item.get("size") or ""), str(item.get("colour") or "")
    if size not in product.size_list:
        raise UserInputError(f"{product.name} doesn't come in size {size or '(none chosen)'}.")
    if colour not in product.colour_list:
        raise UserInputError(f"{product.name} doesn't come in {colour or '(no colour chosen)'}.")

    try:
        quantity = int(item.get("quantity") or 1)
    except (TypeError, ValueError):
        raise UserInputError("Quantity must be a number.") from None
    if not 1 <= quantity <= MAX_QUANTITY:
        raise UserInputError(f"Quantity must be between 1 and {MAX_QUANTITY}.")

    quote = quote_for(tenant, product, item.get("option_ids") or [])
    # Custom pieces are made to order; ready-made pieces need stock.
    if not quote.is_custom and product.stock < quantity:
        raise UserInputError(f"Sorry, {product.name} is out of stock.")

    return OrderItem(
        tenant_id=tenant.id,
        product=product,
        size=size,
        colour=colour,
        quantity=quantity,
        unit_price_bdt=quote.total_bdt,
        is_custom=quote.is_custom,
        custom_details=quote.details,
        notes=str(item.get("notes") or "").strip()[:500],
        ready_by=date.today() + timedelta(days=quote.ready_in_days) if quote.is_custom else None,
    )


def custom_order_queue(tenant: Tenant, status: str | None = None) -> list[OrderItem]:
    query = (db.select(OrderItem)
             .where(OrderItem.tenant_id == tenant.id, OrderItem.is_custom.is_(True))
             .order_by(OrderItem.id.desc()))
    if status:
        query = query.where(OrderItem.status == status)
    return db.session.scalars(query).all()


def update_custom_order_status(tenant: Tenant, item_id: int, status: str) -> OrderItem:
    if status not in OrderItem.STATUSES:
        raise UserInputError(f"Status must be one of: {', '.join(OrderItem.STATUSES)}.")
    item = db.session.scalar(
        db.select(OrderItem).where(OrderItem.tenant_id == tenant.id, OrderItem.id == item_id,
                                   OrderItem.is_custom.is_(True))
    )
    if item is None:
        raise UserInputError("No custom order with that ID.")
    item.status = status
    db.session.commit()
    return item
