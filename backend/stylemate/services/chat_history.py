"""A customer's chats with the stylist: the one they are in now, and the list of past chats.

The chat they are in now is saved after every change, so it's still there after a reload or on
another phone. "New chat" ends it: it joins the past chats, which they can open and read later.
The browser sends the chat as its window shows it (messages, the orders being filled in through
follow-up questions, and Maira's session). Flask only checks its shape and size: nothing in it is
trusted for a price or an order, because checkout and /price-quote work those out again.
Only the customer reads their chats; the owner never sees conversations (services/insights.py).
A guest's chats stay in their own browser (frontend/src/stores/chat.js).
"""

import json

from ..errors import UserInputError
from ..extensions import db
from ..models import ChatConversation, Customer, utc_now

MAX_MESSAGES = 100  # per chat; the browser keeps the newest 100 too
MAX_BYTES = 400_000  # about 100 messages with product cards; stops one account filling the database
MAX_PAST_CHATS = 30  # older ones are deleted when a chat ends
MAX_SESSION_ID = 100
TITLE_LENGTH = 80
EMPTY = {"messages": [], "drafts": {}, "session_id": None}


def current(customer: Customer) -> dict:
    """The chat the customer is in now, or an empty one."""
    row = _open_chat(customer)
    return json.loads(row.content) if row else dict(EMPTY)


def save_current(customer: Customer, data) -> None:
    """Replace the chat they are in now with what their window shows. An empty chat isn't kept."""
    chat = _clean(data)
    row = _open_chat(customer)
    if not chat["messages"]:
        if row:
            db.session.delete(row)
            db.session.commit()
        return
    content = json.dumps(chat, ensure_ascii=False)
    if len(content.encode()) > MAX_BYTES:
        raise UserInputError("This chat is too long to save. Please start a new chat.")
    if row is None:
        row = ChatConversation(tenant_id=customer.tenant_id, customer_id=customer.id)
        db.session.add(row)
    row.title = _title(chat["messages"])
    row.content = content
    db.session.commit()


def end_current(customer: Customer) -> None:
    """ "New chat": the chat they are in now joins their past chats. Only the newest MAX_PAST_CHATS are kept."""
    row = _open_chat(customer)
    if row is None:
        return
    row.ended_at = utc_now()
    db.session.flush()  # so the list below includes the chat just ended
    for old in _past_chats(customer)[MAX_PAST_CHATS:]:
        db.session.delete(old)
    db.session.commit()


def past_chats(customer: Customer) -> list[dict]:
    """The list of past chats, newest first: titles and dates only, not the messages."""
    return [_summary(row) for row in _past_chats(customer)]


def past_chat(customer: Customer, chat_id: int) -> dict:
    return {**_summary(row := _find_past(customer, chat_id)), **json.loads(row.content)}


def delete_past_chat(customer: Customer, chat_id: int) -> None:
    db.session.delete(_find_past(customer, chat_id))
    db.session.commit()


def resume_past_chat(customer: Customer, chat_id: int) -> dict:
    """ "Continue this chat": a past chat becomes the one they are in now, and the one they were in
    joins the past chats. One leaves the list and one joins it, so MAX_PAST_CHATS still holds."""
    row = _find_past(customer, chat_id)  # refuses another customer's chat, like reading it does
    open_now = _open_chat(customer)
    if open_now:
        open_now.ended_at = utc_now()
    row.ended_at = None
    db.session.commit()  # both in one commit, so there's never a moment with two open chats
    return json.loads(row.content)



def _clean(data) -> dict:
    data = data if isinstance(data, dict) else {}
    messages = data.get("messages") or []
    drafts = data.get("drafts") or {}
    session_id = data.get("session_id") or None
    if (not isinstance(messages, list) or not all(isinstance(message, dict) for message in messages)
            or not isinstance(drafts, dict) or not isinstance(session_id, (str, type(None)))):
        raise UserInputError("That chat couldn't be read.")
    if len(messages) > MAX_MESSAGES:
        raise UserInputError(f"Only the last {MAX_MESSAGES} chat messages can be saved.")
    return {"messages": messages, "drafts": drafts, "session_id": session_id[:MAX_SESSION_ID] if session_id else None}


def _title(messages: list[dict]) -> str:
    first = next((str(message.get("text") or "") for message in messages if message.get("role") == "customer"), "")
    first = " ".join(first.split())
    return (first[:TITLE_LENGTH - 1] + "…" if len(first) > TITLE_LENGTH else first) or "Chat with the stylist"


def _summary(row: ChatConversation) -> dict:
    return {"id": row.id, "title": row.title, "started_at": row.created_at.isoformat(),
            "ended_at": row.ended_at.isoformat()}


def _mine(customer: Customer):
    """Every query here goes through this: the shop's rows, and only this customer's."""
    return db.select(ChatConversation).where(ChatConversation.tenant_id == customer.tenant_id,
                                             ChatConversation.customer_id == customer.id)


def _open_chat(customer: Customer) -> ChatConversation | None:
    return db.session.scalar(_mine(customer).where(ChatConversation.ended_at.is_(None)))


def _past_chats(customer: Customer) -> list[ChatConversation]:
    return list(db.session.scalars(_mine(customer).where(ChatConversation.ended_at.is_not(None))
                                   .order_by(ChatConversation.ended_at.desc(), ChatConversation.id.desc())))


def _find_past(customer: Customer, chat_id: int) -> ChatConversation:
    row = db.session.scalar(_mine(customer).where(ChatConversation.id == chat_id,
                                                  ChatConversation.ended_at.is_not(None)))
    if row is None:
        raise UserInputError("That chat isn't in your history.")  # also when it's someone else's
    return row
