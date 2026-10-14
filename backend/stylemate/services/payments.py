"""How an order is paid: cash on delivery, or money sent to the shop's bKash, Nagad or Rocket number.

There is no payment gateway here, and no money moves through this app. The customer
sends the money in their own wallet app, then types the transaction ID (TrxID) from
the wallet's confirmation message at checkout. The owner compares it with the wallet's
history and marks the order as paid. Many small online shops in Bangladesh work this way.

A real gateway needs a merchant account with each provider. If the shop gets one,
only this module changes: check_payment() would ask the provider instead of trusting
the customer's TrxID until the owner has looked.
"""

import re

from ..errors import UserInputError
from ..extensions import db
from ..models import Order, Tenant

CASH = "cash_on_delivery"
TRANSACTION_ID = re.compile(r"^[A-Z0-9]{6,20}$")  # bKash and Rocket use 10 characters, Nagad 8


def wallet_numbers(tenant: Tenant) -> dict[str, str]:
    """The wallets this shop accepts, as {method: number}. A wallet without a number isn't offered."""
    numbers = {"bkash": tenant.bkash_number, "nagad": tenant.nagad_number, "rocket": tenant.rocket_number}
    return {method: number for method, number in numbers.items() if number}


def payment_options(tenant: Tenant) -> list[dict]:
    """The ways to pay, for the checkout page. `number` is where to send the money (empty for cash)."""
    numbers = {CASH: "", **wallet_numbers(tenant)}
    return [{"method": method, "label": Order.PAYMENT_METHODS[method], "number": number}
            for method, number in numbers.items()]


def check_payment(tenant: Tenant, payment) -> tuple[str, str, str]:
    """Check what the customer chose at checkout. Returns (method, transaction ID, status).

    Cash is "unpaid" until the parcel is handed over. A wallet payment is "to_check":
    the customer says they sent the money, and the owner still has to see it arrive.
    """
    payment = payment if isinstance(payment, dict) else {}
    method = str(payment.get("method") or CASH)  # an order without a choice is paid on delivery
    if method == CASH:
        return CASH, "", "unpaid"
    if method not in wallet_numbers(tenant):
        raise UserInputError("Please choose how you would like to pay.")

    label = Order.PAYMENT_METHODS[method]
    reference = re.sub(r"\s+", "", str(payment.get("transaction_id") or "")).upper()
    if not TRANSACTION_ID.match(reference):
        raise UserInputError(f"Please enter the transaction ID (TrxID) from your {label} message. "
                             "It has letters and numbers only.")
    used = db.session.scalar(
        db.select(Order.id).where(Order.tenant_id == tenant.id, Order.payment_reference == reference)
    )
    if used:  # one payment can't pay for two orders
        raise UserInputError("That transaction ID was already used for another order. Please check it.")
    return method, reference, "to_check"


def set_payment_status(tenant: Tenant, order_id: int, status: str) -> Order:
    """The owner records what happened to the money: unpaid, to check, or paid."""
    if status not in Order.PAYMENT_STATUSES:
        raise UserInputError(f"Payment status must be one of: {', '.join(Order.PAYMENT_STATUSES)}.")
    order = db.session.scalar(db.select(Order).where(Order.tenant_id == tenant.id, Order.id == order_id))
    if order is None:
        raise UserInputError("No order with that ID.")
    order.payment_status = status
    db.session.commit()
    return order
