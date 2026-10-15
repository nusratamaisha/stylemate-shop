"""StyleMate's monthly plans: what each costs a shop, and what it allows.

The ONE place for plan prices and limits. The public StyleMate page shows them
(GET /api/plans) and the app enforces them, so they can never disagree.

Limits are on what costs money per use: AI chat questions (Maira), voice (Chorus),
picture previews (an image model) and Gigalogy recommendations. Each month starts fresh.
A shop at its limit gets a grace margin (GRACE) so its customers aren't cut off at
once; the owner sees a warning from 80%.

TODO (Maisha): replace the example prices with ones worked out from Gigalogy's price per
call (cost per conversation x margin), then set PRICES_ARE_EXAMPLES = False.
"""

from dataclasses import asdict, dataclass

from ..errors import PlanLimitError, UserInputError
from ..extensions import db
from ..models import PlanUsage, Tenant, utc_now

PRICES_ARE_EXAMPLES = True  # the public page says so while this is True
GRACE = 0.10  # 10% over the limit before it stops
WARN_AT = 0.80  # the owner's dashboard warns from 80% of a limit


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_bdt: int  # per month
    chat_questions: int  # per month, typed or spoken
    voice: bool
    previews: int  # picture previews per month; 0 = not included
    smart_recommendations: bool  # Gigalogy's recommender; without it, the shop's own picks
    products: int  # 0 = unlimited
    pitch: str


PLANS = {
    plan.key: plan for plan in [
        Plan("starter", "Starter", 1500, chat_questions=500, voice=False, previews=0,
             smart_recommendations=False, products=50,
             pitch="For a shop starting out: answers customers day and night."),
        Plan("growth", "Growth", 4000, chat_questions=2000, voice=True, previews=100,
             smart_recommendations=True, products=200,
             pitch="For a busy page: voice questions, previews and smart suggestions."),
        Plan("pro", "Pro", 9000, chat_questions=6000, voice=True, previews=400,
             smart_recommendations=True, products=0,
             pitch="For a large catalogue with many customers."),
    ]
}
DEFAULT_PLAN = "growth"

# What is counted each month, and which plan field limits it
METERED = {"chat": "chat_questions", "preview": "previews"}


def plan_of(tenant: Tenant) -> Plan:
    return PLANS.get(tenant.plan, PLANS[DEFAULT_PLAN])


def public_plans() -> dict:
    """For the public StyleMate page."""
    return {"plans": [asdict(plan) for plan in PLANS.values()], "prices_are_examples": PRICES_ARE_EXAMPLES}


def _month() -> str:
    return utc_now().strftime("%Y-%m")


def used(tenant: Tenant, kind: str) -> int:
    return db.session.scalar(db.select(PlanUsage.count).where(
        PlanUsage.tenant_id == tenant.id, PlanUsage.kind == kind, PlanUsage.month == _month())) or 0


def require(tenant: Tenant, kind: str, message: str) -> None:
    """Raise PlanLimitError if this month's use has passed the limit plus the grace margin.

    Called before the paid call; record() counts it after the call succeeded, so a
    failed call (Maira down) doesn't use up the shop's month.
    """
    limit = getattr(plan_of(tenant), METERED[kind])
    if used(tenant, kind) >= int(limit * (1 + GRACE)):
        raise PlanLimitError(message)


def record(tenant: Tenant, kind: str) -> None:
    row = db.session.scalar(db.select(PlanUsage).where(
        PlanUsage.tenant_id == tenant.id, PlanUsage.kind == kind, PlanUsage.month == _month()))
    if row is None:
        row = PlanUsage(tenant_id=tenant.id, kind=kind, month=_month(), count=0)
        db.session.add(row)
    row.count += 1
    db.session.commit()


def features(tenant: Tenant) -> dict:
    """What the storefront may show: a feature off for this plan, or used up, is hidden."""
    plan = plan_of(tenant)
    previews_left = plan.previews > 0 and used(tenant, "preview") < int(plan.previews * (1 + GRACE))
    return {"voice": plan.voice, "previews": previews_left}


def check_product_count(tenant: Tenant, count: int) -> None:
    plan = plan_of(tenant)
    if plan.products and count > plan.products:
        raise UserInputError(f"Your {plan.name} plan allows up to {plan.products} products, and this file "
                             f"would make {count}. Remove some, or ask about a bigger plan.")


def usage_summary(tenant: Tenant) -> dict:
    """For the owner's dashboard: this month's use of each limit, and whether to warn."""
    plan = plan_of(tenant)
    meters = []
    for kind, field in METERED.items():
        limit = getattr(plan, field)
        if limit:
            count = used(tenant, kind)
            meters.append({"kind": kind, "used": count, "limit": limit,
                           "warn": count >= limit * WARN_AT, "over": count >= limit})
    return {"plan": plan.name, "meters": meters}


def set_plan(tenant: Tenant, key: str) -> Plan:
    if key not in PLANS:
        raise UserInputError(f"Unknown plan. Choose one of: {', '.join(PLANS)}.")
    tenant.plan = key
    db.session.commit()
    return PLANS[key]
