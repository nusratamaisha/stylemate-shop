"""The shopping assistant: asks Maira, finds the products it mentioned, and logs the turn.

It can also start an order. The assistant only *proposes* one, by ending its answer
with a marker line; Flask checks every part against the database before the
website acts on it. The AI explains, Flask decides.
"""

import re
from dataclasses import dataclass, field

from ..errors import UserInputError
from ..extensions import db
from ..models import ChatTurn, Product, Tenant
from . import pricing
from .catalog import list_products
from .sizes import sleeve_word

MAX_QUESTION_LENGTH = 500
MAX_PRODUCT_CARDS = 3
MAX_ORDER_QUANTITY = 10
# The line the Maira profile is told to write as soon as a customer wants to order, e.g.
# [ORDER product_id=SR-002; size=S; colour=; quantity=1]. Size and colour may be empty:
# the chat asks for whatever is missing (ChatOrder.to_dict() says what can be chosen).
ORDER_MARKER = re.compile(r"\[ORDER\b([^\]]*)\]", re.IGNORECASE)
# The line it writes when a customer describes a piece made for them, e.g.
# [CUSTOMIZE product_id=SR-002; sleeves=Sleeveless; bust=38; sleeve_length=; length=36]
CUSTOMIZE_MARKER = re.compile(r"\[CUSTOMIZE\b([^\]]*)\]", re.IGNORECASE)
# A customer asking to order, in English, Banglish or Bangla. Used only when the assistant
# forgot its order line, so a clear "I want to order it" still starts the order.
ORDER_WORDS = re.compile(r"\b(order|buy|purchase|checkout|kinbo|kinte|nibo|nebo)\b|অর্ডার|কিনব|নেব", re.IGNORECASE)
SIZE_IN_TEXT = re.compile(r"\bsize\s*([a-z0-9]+)\b", re.IGNORECASE)


@dataclass
class ChatOrder:
    """An order the customer started in the chat, checked against the catalogue.

    `size` and `colour` are the shop's own spelling, or "" when the chat still has to ask.
    to_dict() lists what the customer can choose, so the chat asks only real choices.
    """

    product: Product
    size: str
    colour: str
    quantity: int
    changes: list[dict] = field(default_factory=list)  # option groups for a customizable piece (pricing.options_for)

    def to_dict(self) -> dict:
        return {
            "product": self.product.to_dict(),
            "size": self.size,
            "colour": self.colour,
            "quantity": self.quantity,
            "unit_price_bdt": self.product.price_bdt,  # shown in the bag; checkout recalculates it anyway
            "sizes": self.product.size_list,
            "colours": self.product.colour_list,
            "changes": self.changes,
        }


@dataclass
class ChatCustomize:
    """A made-for-you piece the customer described in the chat. The product page finishes it and shows the price."""

    product: Product
    sleeves: str  # the label of a sleeve option this piece offers, or ""
    measurements: dict[str, int]  # whichever of bust, waist, sleeve length and length the customer has given

    def to_dict(self) -> dict:
        return {"product": self.product.to_dict(), "sleeves": self.sleeves, "measurements": self.measurements}


@dataclass
class ChatReply:
    answer: str
    session_id: str
    products: list[Product]
    answered: bool
    order: ChatOrder | None = None  # set when the website should take the customer to checkout
    customize: ChatCustomize | None = None  # set when the product page should open with their changes filled in

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "session_id": self.session_id,
            "products": [product.to_dict() for product in self.products],
            "answered": self.answered,
            "order": self.order.to_dict() if self.order else None,
            "customize": self.customize.to_dict() if self.customize else None,
        }


class ChatService:
    def __init__(self, maira, unanswered_threshold: float):
        self._maira = maira  # anything with an ask() method: the real client or a test fake
        self._threshold = unanswered_threshold

    def reply(self, tenant: Tenant, visitor_id: str, question: str,
              session_id: str | None = None, via_voice: bool = False) -> ChatReply:
        question = (question or "").strip()
        if not question:
            raise UserInputError("Please type a question.")
        if len(question) > MAX_QUESTION_LENGTH:
            raise UserInputError(f"Please keep questions under {MAX_QUESTION_LENGTH} characters.")

        result = self._maira.ask(
            user_id=visitor_id,
            query=question,
            profile_id=tenant.maira_profile_id,
            session_id=session_id,
        )
        answered = is_answered(result.top_score, self._threshold)
        catalogue = list_products(tenant)
        answer, order = read_order(tenant, catalogue, result.text)
        answer, customize = read_customize(tenant, catalogue, answer)
        products = mentioned_products(catalogue, answer)
        if order is None and customize is None:
            order = order_from_question(tenant, question, products)

        db.session.add(ChatTurn(
            tenant_id=tenant.id,
            visitor_id=visitor_id,
            session_id=result.session_id,
            question=question,
            answer=answer,
            top_score=result.top_score,
            answered=answered,
            via_voice=via_voice,
        ))
        db.session.commit()

        return ChatReply(answer=answer, session_id=result.session_id,
                         products=products, answered=answered, order=order, customize=customize)


def read_order(tenant: Tenant, products: list[Product], answer: str) -> tuple[str, ChatOrder | None]:
    """Take the order marker out of the assistant's answer and check it.

    Returns the answer the customer should see and the order, if the shop can sell it.
    The marker is never shown. A size or colour the piece doesn't come in is simply
    left empty, so the chat asks for it. An unknown or sold-out product starts no
    order, and the answer says why instead.
    """
    match = ORDER_MARKER.search(answer)
    if not match:
        return answer, None
    text = ORDER_MARKER.sub("", answer).strip()
    try:
        return text, _check_order(tenant, products, _marker_fields(match.group(1)))
    except UserInputError as problem:
        return f"{text}\n\nI couldn't start that order: {problem}".strip(), None


def order_from_question(tenant: Tenant, question: str, mentioned: list[Product]) -> ChatOrder | None:
    """A safety net for when the assistant didn't write its order line.

    If the customer clearly asked to order and the answer is about exactly one product,
    start the order for that product anyway; the chat asks for the rest. Without this,
    a model that keeps asking "Would you like it in Yellow?" never lets the customer order.
    """
    if len(mentioned) != 1 or not ORDER_WORDS.search(question):
        return None
    size = SIZE_IN_TEXT.search(question)
    try:
        return _check_order(tenant, mentioned, {"product_id": mentioned[0].code, "size": size.group(1) if size else ""})
    except UserInputError:
        return None  # sold out: the assistant's own answer already says so


def read_customize(tenant: Tenant, products: list[Product], answer: str) -> tuple[str, ChatCustomize | None]:
    """Take the customize marker out of the answer and keep only what the shop can really make.

    No price is worked out here. The product page opens with these choices filled in,
    and pricing.py prices them there, where the customer can see and change everything.
    """
    match = CUSTOMIZE_MARKER.search(answer)
    if not match:
        return answer, None
    text = CUSTOMIZE_MARKER.sub("", answer).strip()
    fields = _marker_fields(match.group(1))
    code = fields.get("product_id", "").lower()
    product = next((item for item in products if item.code.lower() == code), None)
    if product is None:
        return text, None
    if not product.customizable:
        return f"{text}\n\n{product.name} can't be customized, but you can order it in its standard sizes.".strip(), None

    # A sleeve this piece offers (not one it already has), in the shop's own words
    wanted = sleeve_word(fields.get("sleeves", ""))
    offered = [option["label"] for group in pricing.options_for(tenant, product)
               if group["group"] == pricing.SLEEVE_GROUP for option in group["options"]]
    sleeves = next((label for label in offered if wanted and sleeve_word(label) == wanted), "")

    measurements = {}
    for name in pricing.MEASUREMENTS:
        try:  # one unreadable number shouldn't lose the others
            measurements.update(pricing.clean_measurements({name: fields.get(name) or fields.get(f"{name}_inches")},
                                                           require_all=False))
        except UserInputError:
            pass
    if not sleeves and not measurements:
        return text, None
    return text, ChatCustomize(product=product, sleeves=sleeves, measurements=measurements)


def _marker_fields(body: str) -> dict[str, str]:
    """ "product_id=SR-002; size=S" becomes {"product_id": "SR-002", "size": "S"}. """
    pairs = (part.split("=", 1) for part in body.split(";") if "=" in part)
    return {key.strip().lower(): value.strip() for key, value in pairs}


def _check_order(tenant: Tenant, products: list[Product], fields: dict[str, str]) -> ChatOrder:
    code = fields.get("product_id", "").lower()
    product = next((item for item in products if item.code.lower() == code), None)
    if product is None:
        raise UserInputError("I couldn't find that product.")
    # A piece with only one size or one colour needs no question about it
    size = _matching(product.size_list, fields.get("size", "")) or _only(product.size_list)
    colour = _matching(product.colour_list, fields.get("colour") or fields.get("color", "")) or _only(product.colour_list)
    try:
        quantity = int(fields.get("quantity") or 1)
    except ValueError:
        quantity = 1
    quantity = max(1, min(MAX_ORDER_QUANTITY, quantity))
    if product.stock < quantity:
        left = "is out of stock" if product.stock == 0 else f"has only {product.stock} left"
        raise UserInputError(f"{product.name} {left}.")
    return ChatOrder(product=product, size=size, colour=colour, quantity=quantity, changes=_chat_changes(tenant, product))


def _chat_changes(tenant: Tenant, product: Product) -> list[dict]:
    """The changes the chat can offer: the product page's menu without made to measure,
    which needs measurement boxes and stays on the product page (rule 8)."""
    if not product.customizable:
        return []
    groups = [{**group, "options": [option for option in group["options"] if not option["needs_measurements"]]}
              for group in pricing.options_for(tenant, product)]
    return [group for group in groups if group["options"]]


def _only(choices: list[str]) -> str:
    return choices[0] if len(choices) == 1 else ""


def _matching(choices: list[str], wanted: str) -> str:
    """The shop's own spelling of a size or colour ("emerald" finds "Emerald"), or "" if it isn't offered."""
    wanted = wanted.strip().lower()
    return next((choice for choice in choices if choice.lower() == wanted), "")


def is_answered(top_score: float | None, threshold: float) -> bool:
    """Did the shop's data contain a good match for the question?

    In testing, a question about a real product scored about 42; a question about
    something the shop doesn't sell (shoes) scored under 24. A low top score means
    the answer probably wasn't in the data, so the owner should see the question.
    """
    return top_score is not None and top_score >= threshold


def mentioned_products(products: list[Product], answer: str) -> list[Product]:
    """Products whose full name appears in the answer, in the order they're mentioned."""
    text = _normalise(answer)
    found = []
    for product in products:
        position = text.find(_normalise(product.name))
        if position >= 0:
            found.append((position, product))
    found.sort(key=lambda pair: pair[0])
    return [product for _, product in found[:MAX_PRODUCT_CARDS]]


def _normalise(text: str) -> str:
    """Lowercase and drop Markdown and punctuation, so "**Kaya Linen Co-ord Set**" matches."""
    text = re.sub(r"[*_`]", "", text.lower())
    return re.sub(r"\s+", " ", text)
