"""Settings read from the environment."""

from stylemate.config import settings_from_env


def test_login_cookie_is_allowed_on_plain_http_by_default(monkeypatch):
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    assert settings_from_env()["SESSION_COOKIE_SECURE"] is False


def test_login_cookie_is_https_only_when_switched_on(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    assert settings_from_env()["SESSION_COOKIE_SECURE"] is True
