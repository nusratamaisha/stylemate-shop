"""Registers the routes and turns errors into JSON, in one place for the whole API."""

from flask import Flask

from ..errors import RateLimitError, ServiceUnavailableError, ShopNotSetUpError, UserInputError
from . import account, owner, shop
from .helpers import error


def register_api(app: Flask) -> None:
    app.register_blueprint(shop.bp)
    app.register_blueprint(owner.bp)
    app.register_blueprint(account.bp)

    @app.errorhandler(UserInputError)
    def handle_user_input(exc):
        return error(str(exc), 400)

    @app.errorhandler(RateLimitError)
    def handle_rate_limit(exc):
        return error(str(exc), 429)

    @app.errorhandler(ServiceUnavailableError)
    def handle_service_unavailable(exc):
        app.logger.warning("External service problem: %s", exc)
        return error("The assistant is busy right now. Please try again in a moment.", 502)

    @app.errorhandler(ShopNotSetUpError)
    def handle_missing_shop(exc):
        return error(str(exc), 503)

    @app.errorhandler(413)
    def handle_too_large(_exc):
        return error("That file is too large (5 MB maximum).", 413)
