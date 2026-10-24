"""Shared fixtures. DB tests use temporary SQLite files built by the real Alembic migrations.

The schema is migrated once per session into a template file; each test gets its own copy,
so tests are isolated without relying on SQLite savepoint quirks.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.db import create_db_engine

API_ROOT = Path(__file__).resolve().parents[1]


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database file at migration head, built once per test session."""
    path = tmp_path_factory.mktemp("db") / "template.db"
    command.upgrade(alembic_config(sqlite_url(path)), "head")
    return path


@pytest.fixture
def db_path(migrated_template: Path, tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    shutil.copyfile(migrated_template, path)
    return path


@pytest.fixture
def db_url(db_path: Path) -> str:
    return sqlite_url(db_path)


@pytest.fixture
def db_engine(db_url: str) -> Iterator[Engine]:
    engine = create_db_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    session = Session(bind=db_engine, autoflush=False)
    try:
        yield session
    finally:
        session.close()
