"""The shopping assistant: asks Maira, finds the products it mentioned, and logs the turn.

It can also start an order. The assistant only *proposes* one, by ending its answer
with a marker line; Flask checks every part against the database before the
website acts on it. The AI explains, Flask decides.
"""

import re
from dataclasses import dataclass

from ..errors import UserInputError
from ..extensions import db
from ..models import ChatTurn, Product, Tenant
from .catalog import list_products

MAX_QUESTION_LENGTH = 500
MAX_PRODUCT_CARDS = 3
MAX_ORDER_QUANTITY = 10
# The line the Maira profile is told to write when a customer confirms an order, e.g.
# [ORDER product_id=SR-002; size=S; colour=Dusty Pink; quantity=1]
ORDER_MARKER = re.compile(r"\[ORDER\b([^\]]*)\]", re.IGNORECASE)


@dataclass
class ChatOrder:
    """A ready-made piece the customer agreed to order in the chat, checked against the catalogue."""

    product: Product
    size: str
    colour: str
    quantity: int

    def to_dict(self) -> dict:
        return {
            "product": self.product.to_dict(),
            "size": self.size,
            "colour": self.colour,
            "quantity": self.quantity,
            "unit_price_bdt": self.product.price_bdt,  # shown in the bag; checkout recalculates it anyway
        }


@dataclass
class ChatReply:
    answer: str
    session_id: str
    products: list[Product]
    answered: bool
    order: ChatOrder | None = None  # set when the website should take the customer to checkout

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "session_id": self.session_id,
            "products": [product.to_dict() for product in self.products],
            "answered": self.answered,
            "order": self.order.to_dict() if self.order else None,
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
        answer, order = read_order(catalogue, result.text)
        products = mentioned_products(catalogue, answer)

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
                         products=products, answered=answered, order=order)


def read_order(products: list[Product], answer: str) -> tuple[str, ChatOrder | None]:
    """Take the order marker out of the assistant's answer and check it.

    Returns the answer the customer should see and the order, if it is valid.
    The marker is never shown. If the assistant proposed something the shop can't
    sell (a wrong size, a colour it doesn't come in, more than is in stock), there
    is no order, and the answer says why instead.
    """
    match = ORDER_MARKER.search(answer)
    if not match:
        return answer, None
    text = ORDER_MARKER.sub("", answer).strip()
    try:
        return text, _check_order(products, _marker_fields(match.group(1)))
    except UserInputError as problem:
        return f"{text}\n\nI couldn't start that order: {problem} Please choose on the product's page.".strip(), None


def _marker_fields(body: str) -> dict[str, str]:
    """ "product_id=SR-002; size=S" becomes {"product_id": "SR-002", "size": "S"}. """
    pairs = (part.split("=", 1) for part in body.split(";") if "=" in part)
    return {key.strip().lower(): value.strip() for key, value in pairs}


def _check_order(products: list[Product], fields: dict[str, str]) -> ChatOrder:
    code = fields.get("product_id", "").lower()
    product = next((item for item in products if item.code.lower() == code), None)
    if product is None:
        raise UserInputError("I couldn't find that product.")
    size = _matching(product.size_list, fields.get("size", ""))
    if not size:
        raise UserInputError(f"{product.name} comes in {', '.join(product.size_list)}.")
    colour = _matching(product.colour_list, fields.get("colour") or fields.get("color", ""))
    if not colour:
        raise UserInputError(f"{product.name} comes in {', '.join(product.colour_list)}.")
    try:
        quantity = int(fields.get("quantity") or 1)
    except ValueError:
        quantity = 1
    quantity = max(1, min(MAX_ORDER_QUANTITY, quantity))
    if product.stock < quantity:
        left = "is out of stock" if product.stock == 0 else f"has only {product.stock} left"
        raise UserInputError(f"{product.name} {left}.")
    return ChatOrder(product=product, size=size, colour=colour, quantity=quantity)


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
