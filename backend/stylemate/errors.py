"""Error types shared across the app.

Services raise these; the API turns them into JSON responses in one place
(see api/__init__.py), so no route needs its own try/except.
"""


class UserInputError(ValueError):
    """Something the customer or owner sent is invalid. Shown to them as a 400."""


class RateLimitError(Exception):
    """One visitor has done something too many times today. Shown as a 429."""


class PlanLimitError(RateLimitError):
    """The shop has used its plan's monthly allowance (services/plans.py). Also shown as a 429."""


class ServiceUnavailableError(Exception):
    """Maira or Chorus failed or timed out. Shown as a friendly 502."""


class ShopNotSetUpError(Exception):
    """The shop named in SHOP_SLUG isn't in the database yet (run `flask seed`)."""
