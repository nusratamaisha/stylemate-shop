from stylemate.cli import _upsert_owner
from stylemate.extensions import db
from stylemate.models import Tenant, User

from .conftest import OWNER_EMAIL


def test_seed_moves_an_existing_owner_to_the_seeded_shop(tenant):
    old_shop = Tenant(slug="old-shop", name="Old shop")
    db.session.add(old_shop)
    db.session.commit()
    owner = db.session.scalar(db.select(User).where(User.email == OWNER_EMAIL))
    owner.tenant_id = old_shop.id
    db.session.commit()

    _upsert_owner(tenant, OWNER_EMAIL, "new-password")

    assert owner.tenant_id == tenant.id
