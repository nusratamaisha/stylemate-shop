"""Reads every setting from environment variables, in one place."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
DATA_DIR = REPO_DIR / "data"


def settings_from_env() -> dict:
    """Return Flask config values, read when the app is created (after .env is loaded)."""
    env = os.environ.get
    return {
        "SECRET_KEY": env("SECRET_KEY") or "dev-only-secret-change-me",
        "SQLALCHEMY_DATABASE_URI": env("DATABASE_URL") or f"sqlite:///{BACKEND_DIR / 'stylemate.db'}",
        "MAIRA_BASE_URL": env("MAIRA_BASE_URL", "https://api.recommender.gigalogy.com"),
        "CHORUS_BASE_URL": env("CHORUS_BASE_URL", "https://api.maira.gigalogy.com/chorus"),
        "MAIRA_PROJECT_KEY": env("MAIRA_PROJECT_KEY", ""),
        "MAIRA_API_KEY": env("MAIRA_API_KEY", ""),
        "SHOP_SLUG": env("SHOP_SLUG", "house-of-m"),
        "UNANSWERED_SCORE_THRESHOLD": float(env("UNANSWERED_SCORE_THRESHOLD", "30")),
        "CONTACT_MESSAGES_PER_DAY": int(env("CONTACT_MESSAGES_PER_DAY", "5")),  # per visitor; 0 = no limit
        "PREVIEWS_PER_DAY": int(env("PREVIEWS_PER_DAY", "20")),  # each picture costs money
        "IMAGES_DIR": str(DATA_DIR / "images"),
        "UPLOADS_DIR": str(BACKEND_DIR / "uploads"),  # customers' reference pictures; never committed
        "REFERENCE_PICTURES_PER_DAY": int(env("REFERENCE_PICTURES_PER_DAY", "20")),
        "MAX_CONTENT_LENGTH": 5 * 1024 * 1024,  # uploads (CSV, voice) up to 5 MB
        "SESSION_COOKIE_SAMESITE": "Lax",
    }
