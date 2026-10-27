"""Numbers for the owner's Insights tab: how the business is going (what to restock, what not to,
what sells and how) and what the chat shows (what customers want that the shop doesn't sell).

The chat conversations themselves are not shown to the owner, only these summaries."""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from ..extensions import db
from ..models import ChatTurn, Order, OrderItem, Product, Review, Tenant

TOP_N = 8

# Business insights (Oct 20). One place for the rules, so they are easy to explain and change.
RECENT_DAYS = 30  # "recent sales" means the last 30 days
RESTOCK_WITHIN_DAYS = 14  # restock when the stock left lasts two weeks or less at the recent pace
FIT_MIN_LINES = 3  # a piece needs a few orders before its made-to-measure share means anything
FIT_SHARE = 0.5  # half or more of its orders made to measure: the standard sizes may not fit


# What customers ask for that the shop can't answer, grouped into topics the owner can act on.
# First match wins, so the more specific topics come first. Keywords are whole words or phrases.
MISSING_TOPICS = [
    ("Bigger sizes", ["xxl", "2xl", "3xl", "4xl", "xxxl", "plus size", "big size", "bigger size", "large size"]),
    ("Smaller sizes", ["xxs", "petite", "small size", "smaller size"]),
    ("Children's clothes", ["kid", "kids", "child", "children", "baby", "babies"]),
    ("Men's clothes", ["men", "mens", "man", "gents", "male", "panjabi", "punjabi", "boys"]),
    ("Shoes and bags", ["shoe", "shoes", "sandal", "sandals", "heels", "slipper", "slippers", "bag", "bags", "purse"]),
    ("Jewellery", ["jewellery", "jewelry", "earring", "earrings", "necklace", "bangle", "bangles", "ring", "rings"]),
    ("Sarees", ["saree", "sarees", "sari", "saris"]),
    ("Salwar kameez and three-piece", ["salwar", "kameez", "three piece", "3 piece", "3piece", "threepiece"]),
    ("Hijabs, scarves and dupattas", ["hijab", "hijabs", "scarf", "scarves", "dupatta", "orna"]),
    ("Delivery abroad", ["abroad", "international", "overseas", "outside bangladesh", "usa", "uk", "canada"]),
    ("Discounts and offers", ["discount", "discounts", "offer", "offers", "sale", "coupon", "promo", "cheaper"]),
    ("Returns and exchanges", ["return", "returns", "exchange", "refund"]),
    ("Card or instalment payment", ["card", "visa", "mastercard", "emi", "instalment", "installment"]),
]
OTHER_TOPIC = "Other"
EXAMPLES_PER_TOPIC = 3


def chat_insights(tenant: Tenant, order_count: int) -> dict:
    """From the chat, only what the owner can act on: whether it sells, and what customers want
    that the shop doesn't sell. No conversation is sent, only counts and a few example questions."""
    turns = db.session.scalars(
        db.select(ChatTurn).where(ChatTurn.tenant_id == tenant.id).order_by(ChatTurn.created_at.desc())
    ).all()
    total = len(turns)
    unanswered = [turn for turn in turns if not turn.answered]
    chat_orders = db.session.scalar(  # orders the customer confirmed in the stylist chat (Order.source)
        db.select(db.func.count(Order.id)).where(Order.tenant_id == tenant.id, Order.source == "chat"))
    return {
        "total_questions": total,
        "answer_rate": round(100 * (total - len(unanswered)) / total) if total else None,
        "voice_count": sum(1 for turn in turns if turn.via_voice),
        "order_count": order_count,
        "chat_orders": chat_orders,
        "missing": missing_topics([turn.question for turn in unanswered]),
    }


def missing_topics(questions: list[str]) -> list[dict]:
    """Group unanswered questions by topic, biggest first, with a few example wordings (newest first)."""
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for question in questions:
        topic = topic_of(question)
        counts[topic] += 1
        wording = question.strip()
        readable = len(normalise_question(wording)) >= 3  # "." or "ok" counts, but isn't worth showing
        if readable and len(examples[topic]) < EXAMPLES_PER_TOPIC and wording not in examples[topic]:
            examples[topic].append(wording)
    ranked = sorted(counts.items(), key=lambda pair: (pair[0] == OTHER_TOPIC, -pair[1]))  # "Other" always last
    return [{"topic": topic, "count": count, "examples": examples[topic]} for topic, count in ranked]


def topic_of(question: str) -> str:
    text = f" {normalise_question(question)} "
    for topic, keywords in MISSING_TOPICS:
        if any(f" {keyword} " in text for keyword in keywords):
            return topic
    return OTHER_TOPIC


def normalise_question(question: str) -> str:
    """Lower case, no punctuation, single spaces: "Do you have XXL?!" becomes "do you have xxl"."""
    text = re.sub(r"[^\w\s]", "", question.lower())
    return re.sub(r"\s+", " ", text).strip()


def business_insights(tenant: Tenant, now: datetime | None = None) -> dict:
    """What the owner should act on, from the shop's own orders, stock and reviews.

    Stock is kept per product (not per size), so restocking advice is per product;
    the best sellers say which size and colour sell most, so the right ones are restocked.
    `now` is passed in by tests, so the 30-day window doesn't depend on today's date.
    """
    now = _utc(now or datetime.now(timezone.utc))
    since = now - timedelta(days=RECENT_DAYS)
    products = db.session.scalars(db.select(Product).where(Product.tenant_id == tenant.id)).all()
    lines = db.session.execute(
        db.select(OrderItem, Order.created_at).join(Order).where(OrderItem.tenant_id == tenant.id)
    ).all()
    ratings = _ratings(tenant)

    recent_ready = Counter()  # ready-made pieces sold in the last 30 days: the pace stock runs out at
    sold, revenue = Counter(), Counter()
    sizes, colours = defaultdict(Counter), defaultdict(Counter)
    line_count, custom_count = Counter(), Counter()
    last_sold: dict[int, datetime] = {}
    for line, ordered_at in lines:
        ordered_at = _utc(ordered_at)
        product_id = line.product_id
        sold[product_id] += line.quantity
        revenue[product_id] += line.unit_price_bdt * line.quantity
        sizes[product_id][line.size] += line.quantity
        colours[product_id][line.colour] += line.quantity
        line_count[product_id] += 1
        custom_count[product_id] += line.is_custom
        last_sold[product_id] = max(last_sold.get(product_id, ordered_at), ordered_at)
        if not line.is_custom and ordered_at >= since:  # made-to-order pieces are sewn and use no stock
            recent_ready[product_id] += line.quantity

    first_order = min((_utc(at) for _, at in lines), default=None)

    def card(product: Product) -> dict:
        return {"code": product.code, "name": product.name, "stock": product.stock,
                "image_url": product.image_url, "colours": product.colour_list, **ratings.get(product.id, {})}

    restock = []
    for product in products:
        pace = recent_ready[product.id] / RECENT_DAYS  # pieces a day
        if not pace:
            continue
        days_left = int(product.stock / pace)
        if days_left <= RESTOCK_WITHIN_DAYS:
            restock.append({**card(product), "sold_recently": recent_ready[product.id], "days_left": days_left})
    restock.sort(key=lambda item: (item["days_left"], -item["sold_recently"]))

    slow = [{**card(product), "sold_total": sold[product.id],
             "last_sold": last_sold[product.id].isoformat() if product.id in last_sold else None}
            for product in products if product.stock > 0 and not recent_ready[product.id]]
    slow.sort(key=lambda item: (-item["stock"], item["sold_total"]))

    by_id = {product.id: product for product in products}
    best = [{**card(by_id[product_id]), "sold": quantity, "revenue_bdt": revenue[product_id],
             "top_size": sizes[product_id].most_common(1)[0][0],
             "top_colour": colours[product_id].most_common(1)[0][0]}
            for product_id, quantity in sold.most_common(5) if product_id in by_id]

    fit = [{**card(by_id[product_id]), "orders": count, "made_to_measure": custom_count[product_id],
            "share": round(100 * custom_count[product_id] / count), "sizes": by_id[product_id].size_list}
           for product_id, count in line_count.items()
           if product_id in by_id and count >= FIT_MIN_LINES and custom_count[product_id] / count >= FIT_SHARE]
    fit.sort(key=lambda item: -item["share"])

    return {
        "recent_days": RECENT_DAYS,
        "days_of_orders": (now - first_order).days if first_order else 0,
        "restock": restock,
        "slow": slow[:TOP_N],
        "best_sellers": best,
        "made_to_measure": fit,
        "trend": _trend(tenant, now),
        "chat": chat_insights(tenant, order_count=len({line.order_id for line, _ in lines})),
    }


def _trend(tenant: Tenant, now: datetime) -> dict:
    """This calendar month so far against the whole of last month."""
    this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_start = (this_start - timedelta(days=1)).replace(day=1)
    orders = db.session.scalars(db.select(Order).where(Order.tenant_id == tenant.id,
                                                       Order.created_at >= last_start)).all()
    questions = db.session.scalars(db.select(ChatTurn.created_at).where(ChatTurn.tenant_id == tenant.id,
                                                                        ChatTurn.created_at >= last_start)).all()

    def month(start: datetime, end: datetime) -> dict:
        chosen = [order for order in orders if start <= _utc(order.created_at) < end]
        return {"sales_bdt": sum(order.total_bdt - order.shipping_bdt for order in chosen),
                "orders": len(chosen),
                "pieces": sum(line.quantity for order in chosen for line in order.items),
                "questions": sum(1 for at in questions if start <= _utc(at) < end)}

    return {"this_month": month(this_start, now + timedelta(seconds=1)), "last_month": month(last_start, this_start),
            "this_month_name": this_start.strftime("%B"), "last_month_name": last_start.strftime("%B")}


def _ratings(tenant: Tenant) -> dict[int, dict]:
    rows = db.session.execute(
        db.select(Review.product_id, db.func.avg(Review.rating), db.func.count(Review.id))
        .where(Review.tenant_id == tenant.id).group_by(Review.product_id)
    ).all()
    return {product_id: {"rating": round(float(average), 1), "reviews": count} for product_id, average, count in rows}


def _utc(moment: datetime) -> datetime:
    """SQLite gives back dates without a time zone; they were saved in UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
