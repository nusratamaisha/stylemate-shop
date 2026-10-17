"""The migrations in backend/migrations/ build exactly the tables models.py describes.

Every other test creates its tables straight from models.py. These build a real database
file from the migrations instead, so a model change without a migration fails here.
"""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect

from stylemate import create_app
from stylemate.extensions import db


@pytest.fixture
def empty_app(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'migrated.db'}"})
    with app.app_context():
        db.drop_all()  # create_app made the tables from models.py; start from nothing instead
        yield app
        db.engine.dispose()


def test_migrations_build_the_same_tables_as_the_models(empty_app):
    upgrade()

    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, db.metadata)

    assert differences == [], f"models.py changed without a migration: run `uv run flask db migrate -m ...`\n{differences}"


def test_migrations_can_be_undone(empty_app):
    upgrade()
    downgrade(revision="base")

    assert inspect(db.engine).get_table_names() == ["alembic_version"]
