"""The shop's size guide: what body each size fits, and how long each kind of sleeve is.

Like customization options, the guide is rows in the database, not code, so each
shop has its own and can change it without a developer.
"""

import re

from ..extensions import db
from ..models import SizeGuideRow, SleeveLength, Tenant


def size_guide(tenant: Tenant) -> dict:
    sizes = db.session.scalars(
        db.select(SizeGuideRow).where(SizeGuideRow.tenant_id == tenant.id).order_by(SizeGuideRow.position)
    ).all()
    sleeves = db.session.scalars(
        db.select(SleeveLength).where(SleeveLength.tenant_id == tenant.id).order_by(SleeveLength.position)
    ).all()
    return {"sizes": [row.to_dict() for row in sizes], "sleeves": [row.to_dict() for row in sleeves]}


def sleeve_lengths(tenant: Tenant) -> dict[str, int]:
    """Sleeve lengths by sleeve word, e.g. {"short": 7, "full": 23}."""
    return {sleeve_word(row["name"]): row["length_inches"] for row in size_guide(tenant)["sleeves"]}


def sleeve_word(text: str) -> str:
    """ "Short sleeves" and "short" both become "short", so labels, products and the guide can be compared. """
    return re.sub(r"\s*sleeves?$", "", text.strip().lower())
