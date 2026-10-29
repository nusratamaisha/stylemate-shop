import pytest

from stylemate import create_app
from stylemate.cli import DEFAULT_OPTIONS, SHOP, add_default_faq, add_default_size_guide
from pathlib import Path

from stylemate.extensions import db
from stylemate.models import CustomizationOption, Tenant, User
from stylemate.services.catalog import parse_products_csv, save_products

from .fakes import FakeChorus, FakeMaira, FakeRecommender

PRODUCTS_CSV = Path(__file__).parent / "data" / "products.csv"  # a fixed catalogue, separate from the shop's
OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "secret-pass"


@pytest.fixture
def maira():
    return FakeMaira()


@pytest.fixture
def chorus():
    return FakeChorus()


@pytest.fixture
def recommender():
    return FakeRecommender()


@pytest.fixture
def extra_config():
    """Settings a test file adds on top of the defaults below (override this fixture in that file)."""
    return {}


@pytest.fixture
def app(maira, chorus, recommender, tmp_path, extra_config):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",  # in memory, fresh for every test
            "SECRET_KEY": "test",
            "SHOP_SLUG": "stylemate",
            "UNANSWERED_SCORE_THRESHOLD": 30.0,
            "IMAGES_DIR": str(tmp_path),
            "UPLOADS_DIR": str(tmp_path / "uploads"),
            **extra_config,
        },
        maira=maira,
        chorus=chorus,
        recommender=recommender,
    )
    with app.app_context():
        _seed()
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def tenant(app):
    return db.session.scalar(db.select(Tenant))


@pytest.fixture
def owner_client(client):
    response = client.post("/api/owner/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    assert response.status_code == 200
    return client


def option_id(group: str, label: str) -> int:
    return db.session.scalar(
        db.select(CustomizationOption.id).where(CustomizationOption.group == group,
                                                CustomizationOption.label == label)
    )


def _seed():
    tenant = Tenant(**SHOP, maira_profile_id="profile-1", maira_dataset_id="dataset-1",
                    maira_image_profile_id="image-profile-1")
    db.session.add(tenant)
    db.session.commit()
    for position, (group, label, price, days, length_change, measured) in enumerate(DEFAULT_OPTIONS):
        db.session.add(CustomizationOption(tenant_id=tenant.id, group=group, label=label,
                                           extra_price_bdt=price, extra_days=days, length_change_inches=length_change,
                                           needs_measurements=measured, position=position))
    add_default_size_guide(tenant)
    add_default_faq(tenant)
    owner = User(tenant_id=tenant.id, email=OWNER_EMAIL)
    owner.set_password(OWNER_PASSWORD)
    db.session.add(owner)
    db.session.commit()
    save_products(tenant, parse_products_csv(PRODUCTS_CSV.read_bytes()))
