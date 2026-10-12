"""Daily limits per visitor, for actions that cost money or could be used to spam.

One mechanism for every limited action (DRY): contact messages and picture previews
both call use(). A visitor is recognised by a hash of their IP address. The visitor
ID kept in the browser is not used, because anyone can clear it and start again.
"""

from datetime import timedelta

from ..errors import RateLimitError
from ..extensions import db
from ..models import RateLimitEvent, Tenant, utc_now

WINDOW = timedelta(hours=24)


def use(tenant: Tenant, action: str, sender_key: str, limit: int, message: str) -> None:
    """Count one use of the action, or raise RateLimitError if this sender has reached the limit.

    A limit of 0 switches the limit off.
    """
    if limit <= 0:
        return
    since = utc_now() - WINDOW
    # Old rows are no longer needed for counting, so remove them as we go.
    db.session.execute(db.delete(RateLimitEvent).where(RateLimitEvent.created_at < since))
    used = db.session.scalar(
        db.select(db.func.count(RateLimitEvent.id)).where(
            RateLimitEvent.tenant_id == tenant.id,
            RateLimitEvent.action == action,
            RateLimitEvent.sender_key == sender_key,
            RateLimitEvent.created_at >= since,
        )
    )
    if used >= limit:
        db.session.commit()
        raise RateLimitError(message)
    db.session.add(RateLimitEvent(tenant_id=tenant.id, action=action, sender_key=sender_key))
    db.session.commit()
