import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.db import get_session
from app.main import app


def migration_config(connection):
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture(scope="session")
def migrated_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; real PostgreSQL tests run in CI")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not parsed.database.endswith(
        "_test"
    ):
        pytest.fail(
            "TEST_DATABASE_URL must be PostgreSQL with a dedicated *_test database"
        )
    engine = create_engine(url)
    with engine.begin() as connection:
        command.upgrade(migration_config(connection), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def session(migrated_engine):
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
