"""Shared fixtures. DB tests run against a real Postgres test database migrated with Alembic.

Set TEST_DATABASE_URL to point elsewhere. If the database is unreachable, DB tests are skipped
locally but fail when REQUIRE_DB=1 (as in CI), so a missing database never passes silently.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://app:app@localhost:5432/collab_test"


def get_test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def _ensure_database_exists(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def db_url() -> str:
    url = get_test_database_url()
    try:
        _ensure_database_exists(url)
    except OperationalError as exc:
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail(f"Test database required but unreachable: {exc}")
        pytest.skip("Test database unreachable; run `docker compose up -d db`.")
    return url


@pytest.fixture(scope="session")
def db_engine(db_url: str) -> Iterator[Engine]:
    """Engine for a test database rebuilt from migrations once per session."""
    cfg = alembic_config(db_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Session inside an outer transaction that is rolled back after each test."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
