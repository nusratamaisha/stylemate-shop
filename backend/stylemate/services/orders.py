"""Checkout and the custom order queue.

Prices sent by the browser are ignored: every price is recalculated here, so a
customer can't change what they pay by editing the page.
"""

from datetime import date, timedelta

from ..errors import UserInputError
from ..extensions import db
from ..models import Customer, Order, OrderItem, Product, Tenant
from .accounts import remember_details
from .catalog import get_product
from .payments import check_payment
from .uploads import picture_exists
from .pricing import MADE_TO_MEASURE_SIZE, clean_measurements, measurements_text, quote_for, shipping_charge

MAX_QUANTITY = 10


def place_order(tenant: Tenant, customer: dict, items: list[dict], account: Customer | None = None,
                uploads_dir: str = "", payment: dict | None = None, source: str = "website",
                remember: bool = False) -> Order:
    """Check and save an order. `account` is the logged-in customer, or None for a guest checkout.

    `source` says where the customer confirmed it: "website" (the checkout page) or "chat".
    Both go through exactly the same checks, so a chat order is priced and stocked like any other.
    `remember`: the logged-in customer ticked "save my details", so they're filled in next time.
    """
    if source not in Order.SOURCES:
        raise UserInputError("Unknown order source.")
    customer = customer or {}
    name, phone, address = (str(customer.get(key) or "").strip() for key in ("name", "phone", "address"))
    if not (name and phone and address):
        raise UserInputError("Please fill in your name, phone number and address.")
    if not items:
        raise UserInputError("Your cart is empty.")
    area = str(customer.get("delivery_area") or "")
    shipping = shipping_charge(tenant, area)  # the customer picks the area; Flask sets the charge
    method, reference, payment_status = check_payment(tenant, payment)

    order = Order(tenant_id=tenant.id, customer_id=account.id if account else None,
                  customer_name=name, phone=phone, address=address,
                  delivery_area=area, shipping_bdt=shipping, total_bdt=0,
                  payment_method=method, payment_reference=reference, payment_status=payment_status,
                  source=source)
    for item in items:
        order.items.append(_build_item(tenant, item, uploads_dir))
    _take_from_stock(order.items)
    order.total_bdt = sum(line.unit_price_bdt * line.quantity for line in order.items) + shipping

    if account and remember:
        measured = next((clean_measurements(item.get("measurements")) for item, line in zip(items, order.items)
                         if line.size == MADE_TO_MEASURE_SIZE), None)
        remember_details(account, order, measured)

    db.session.add(order)
    db.session.commit()
    return order


def _build_item(tenant: Tenant, item: dict, uploads_dir: str = "") -> OrderItem:
    product = get_product(tenant, str(item.get("product_code") or ""))
    size, colour = str(item.get("size") or ""), str(item.get("colour") or "")
    quote = quote_for(tenant, product, item.get("option_ids") or [], item.get("measurements"))
    details = quote.details
    if quote.needs_measurements:
        # Cut to the customer's body, so there is no S, M or L to choose
        size = MADE_TO_MEASURE_SIZE
        details += f"; Measurements: {measurements_text(clean_measurements(item.get('measurements')))}"
    elif size not in product.size_list:
        raise UserInputError(f"{product.name} doesn't come in size {size or '(none chosen)'}.")
    if colour not in product.colour_list:
        raise UserInputError(f"{product.name} doesn't come in {colour or '(no colour chosen)'}.")

    try:
        quantity = int(item.get("quantity") or 1)
    except (TypeError, ValueError):
        raise UserInputError("Quantity must be a number.") from None
    if not 1 <= quantity <= MAX_QUANTITY:
        raise UserInputError(f"Quantity must be between 1 and {MAX_QUANTITY}.")

    # Custom pieces are made to order; ready-made pieces need stock (checked for the whole order in _take_from_stock).

    # A reference picture only goes with a made-to-order piece, and only if it really was uploaded here
    picture = str(item.get("reference_image") or "")
    if not (quote.is_custom and picture_exists(uploads_dir, picture)):
        picture = ""

    return OrderItem(
        tenant_id=tenant.id,
        product=product,
        size=size,
        colour=colour,
        quantity=quantity,
        unit_price_bdt=quote.total_bdt,
        is_custom=quote.is_custom,
        custom_details=details,
        notes=str(item.get("notes") or "").strip()[:500],
        reference_image=picture,
        ready_by=date.today() + timedelta(days=quote.ready_in_days) if quote.is_custom else None,
    )


def _take_from_stock(lines: list[OrderItem]) -> None:
    """Lower the stock of every ready-made piece in the order, or refuse the order.

    Stock is kept per product, so two lines of the same piece (say, one in each colour)
    are added up first. Made-to-order lines are sewn for the customer and use no stock.
    Nothing is saved until place_order() commits, so a refused order changes nothing.
    """
    wanted: dict[Product, int] = {}
    for line in lines:
        if not line.is_custom:
            wanted[line.product] = wanted.get(line.product, 0) + line.quantity
    for product, quantity in wanted.items():
        if product.stock == 0:
            raise UserInputError(f"Sorry, {product.name} is out of stock.")
        if product.stock < quantity:
            raise UserInputError(f"Sorry, only {product.stock} of {product.name} left in stock.")
    for product, quantity in wanted.items():
        product.stock -= quantity


def custom_order_queue(tenant: Tenant, status: str | None = None) -> list[OrderItem]:
    query = (db.select(OrderItem)
             .where(OrderItem.tenant_id == tenant.id, OrderItem.is_custom.is_(True))
             .order_by(OrderItem.id.desc()))
    if status:
        query = query.where(OrderItem.status == status)
    return db.session.scalars(query).all()


def all_orders(tenant: Tenant) -> list[dict]:
    """Every order of the shop, ready-made and made to order, newest first, with who it is for."""
    orders = db.session.scalars(
        db.select(Order).where(Order.tenant_id == tenant.id).order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    return [{
        **order.to_dict(),
        "customer_name": order.customer_name,
        "phone": order.phone,
        "address": order.address,
        "has_account": order.customer_id is not None,
    } for order in orders]


def sales_summary(tenant: Tenant) -> dict:
    """The numbers an owner checks first: how many orders, how much money, what sells."""
    orders = db.session.scalars(db.select(Order).where(Order.tenant_id == tenant.id)).all()
    lines = [line for order in orders for line in order.items]
    sold: dict[str, int] = {}
    for line in lines:
        sold[line.product.name] = sold.get(line.product.name, 0) + line.quantity
    best = sorted(sold.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    goods = sum(order.total_bdt - order.shipping_bdt for order in orders)
    return {
        "order_count": len(orders),
        "pieces_sold": sum(line.quantity for line in lines),
        "custom_pieces": sum(line.quantity for line in lines if line.is_custom),
        "sales_bdt": goods,  # what customers paid for the clothes
        "delivery_bdt": sum(order.shipping_bdt for order in orders),  # collected for delivery, not income
        "average_order_bdt": round(goods / len(orders)) if orders else 0,
        "to_ship": sum(1 for line in lines if line.status != "shipped"),
        "payments_to_check": sum(1 for order in orders if order.payment_status == "to_check"),
        "chat_orders": sum(1 for order in orders if order.source == "chat"),  # what the assistant sold
        "best_sellers": [{"name": name, "quantity": quantity} for name, quantity in best],
    }


def update_item_status(tenant: Tenant, item_id: int, status: str) -> OrderItem:
    """Move one order line along: new, in production, shipped. Works for ready-made and custom lines.
    Only forward, as OrderItem.NEXT_STATUSES allows; asking for the status it already has changes nothing."""
    if status not in OrderItem.STATUSES:
        raise UserInputError(f"Status must be one of: {', '.join(OrderItem.STATUSES)}.")
    item = db.session.scalar(
        db.select(OrderItem).where(OrderItem.tenant_id == tenant.id, OrderItem.id == item_id)
    )
    if item is None:
        raise UserInputError("No order line with that ID.")
    if status == item.status:
        return item  # e.g. a double click
    if status == "in_production" and not item.is_custom:
        raise UserInputError("A ready-made piece is already made, so it can't be in production.")
    if status not in item.next_statuses():
        raise UserInputError(f"This line is already {_label(item.status)}, so it can't go back to {_label(status)}.")
    item.status = status

    db.session.commit()
    return item


def reference_picture_name(tenant: Tenant, item_id: int) -> str:
    """The file name of an order line's reference picture, for this shop's owner only."""
    item = db.session.scalar(
        db.select(OrderItem).where(OrderItem.tenant_id == tenant.id, OrderItem.id == item_id)
    )
    if item is None or not item.reference_image:
        raise UserInputError("That order has no reference picture.")
    return item.reference_image


def _label(status: str) -> str:
    return status.replace("_", " ")  # "in_production" -> "in production"
