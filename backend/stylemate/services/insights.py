
"""Numbers for the owner dashboard: what customers ask, and what the shop couldn't answer."""

import re
from collections import Counter

from ..extensions import db
from ..models import ChatTurn, Tenant

TOP_N = 8


def owner_insights(tenant: Tenant) -> dict:
    turns = db.session.scalars(
        db.select(ChatTurn).where(ChatTurn.tenant_id == tenant.id).order_by(ChatTurn.created_at.desc())
    ).all()

    total = len(turns)
    unanswered = [turn for turn in turns if not turn.answered]
    return {
        "total_questions": total,
        "unanswered_count": len(unanswered),
        "answer_rate": round(100 * (total - len(unanswered)) / total) if total else None,
        "voice_count": sum(1 for turn in turns if turn.via_voice),
        "top_questions": _most_common(turns),
        "unanswered_questions": _most_common(unanswered),
        "recent": [
            {
                "question": turn.question,
                "answer": turn.answer,
                "answered": turn.answered,
                "via_voice": turn.via_voice,
                "asked_at": turn.created_at.isoformat(),
            }
            for turn in turns[:10]
        ],
    }


def _most_common(turns: list[ChatTurn]) -> list[dict]:
    """Group questions that differ only in case, spacing or punctuation."""
    counts: Counter[str] = Counter()
    example: dict[str, str] = {}
    for turn in turns:
        key = normalise_question(turn.question)
        counts[key] += 1
        example.setdefault(key, turn.question)  # newest wording, since turns are newest first
    return [{"question": example[key], "count": count} for key, count in counts.most_common(TOP_N)]


def normalise_question(question: str) -> str:
    text = re.sub(r"[^\w\s]", "", question.lower())
    return re.sub(r"\s+", " ", text).strip()
