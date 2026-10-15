"""Requests for a StyleMate demo from the public page: how a Facebook shop becomes a customer.

These are StyleMate's own leads, not any shop's data, so they have no tenant. They are
read with `flask demo-requests`; a shop is then set up by hand (`flask seed`, its Maira
profile and dataset) and put on its plan with `flask set-plan`.
"""

from ..errors import UserInputError
from ..extensions import db
from ..models import DemoRequest
from .plans import PLANS

FIELDS = {"shop_name": 120, "owner_name": 120, "phone": 40, "facebook_page": 300, "product_count": 40, "message": 1000}


def save_request(details) -> DemoRequest:
    details = details if isinstance(details, dict) else {}
    clean = {name: str(details.get(name) or "").strip()[:size] for name, size in FIELDS.items()}
    if not (clean["shop_name"] and clean["owner_name"] and clean["phone"]):
        raise UserInputError("Please give your shop's name, your name and a phone number.")
    plan = str(details.get("plan") or "")
    request = DemoRequest(**clean, plan=plan if plan in PLANS else "")
    db.session.add(request)
    db.session.commit()
    return request


def all_requests() -> list[DemoRequest]:
    return db.session.scalars(db.select(DemoRequest).order_by(DemoRequest.id.desc())).all()
