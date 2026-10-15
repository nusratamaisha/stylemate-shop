"""StyleMate backend. create_app() builds the Flask app and wires everything together.

This is the only place that decides which Maira, Chorus and recommender clients the app uses.
Tests pass in fake clients instead, so they never call the real APIs.
"""

from dotenv import load_dotenv
from flask import Flask

from .api import register_api
from .api.helpers import Services
from .cli import register_cli
from .clients import ChorusClient, MairaClient, RecommenderClient
from .config import BACKEND_DIR, settings_from_env
from .extensions import db
from .services.catalog import CatalogImporter
from .services.chat import ChatService
from .services.help import HelpPublisher
from .services.preview import PreviewService
from .services.recommendations import RecommendationService


def create_app(config: dict | None = None, *, maira=None, chorus=None, recommender=None) -> Flask:
    config = config or {}
    if not config.get("TESTING"):
        load_dotenv(BACKEND_DIR / ".env")

    app = Flask(__name__)
    app.config.from_mapping(settings_from_env())
    app.config.update(config)

    db.init_app(app)

    keys = (app.config["MAIRA_PROJECT_KEY"], app.config["MAIRA_API_KEY"])
    maira = maira or MairaClient(app.config["MAIRA_BASE_URL"], *keys)
    chorus = chorus or ChorusClient(app.config["CHORUS_BASE_URL"], *keys)
    # Same server and keys as Maira (api.recommender.gigalogy.com)
    recommender = recommender or RecommenderClient(app.config["MAIRA_BASE_URL"], *keys, timeout=10.0)
    app.extensions["stylemate"] = Services(
        chat=ChatService(maira, app.config["UNANSWERED_SCORE_THRESHOLD"]),
        chorus=chorus,
        catalog_importer=CatalogImporter(maira),
        preview=PreviewService(maira, app.config["IMAGES_DIR"]),
        help_publisher=HelpPublisher(maira),
        recommender=recommender,
        recommendations=RecommendationService(recommender),
    )

    register_api(app)
    register_cli(app)

    with app.app_context():
        db.create_all()

    return app
