"""Migration checks: fresh database, round trip, re-applying at head, and no model drift."""

from pathlib import Path

from alembic import command
from sqlalchemy import inspect

from app.core.db import create_db_engine
from app.models import metadata
from tests.conftest import alembic_config, sqlite_url


def _user_tables(url: str) -> set[str]:
    engine = create_db_engine(url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_upgrade_creates_a_fresh_database(tmp_path: Path) -> None:
    url = sqlite_url(tmp_path / "nested" / "fresh.db")

    command.upgrade(alembic_config(url), "head")

    assert len(_user_tables(url)) == len(metadata.tables)


def test_upgrade_on_current_schema_is_a_no_op(db_url: str) -> None:
    command.upgrade(alembic_config(db_url), "head")

    assert len(_user_tables(db_url)) == len(metadata.tables)


def test_downgrade_base_then_upgrade_head(db_url: str) -> None:
    cfg = alembic_config(db_url)

    command.downgrade(cfg, "base")
    assert _user_tables(db_url) == set()

    command.upgrade(cfg, "head")
    assert len(_user_tables(db_url)) == len(metadata.tables)


def test_models_match_migrations(db_url: str) -> None:
    # Raises if autogenerate would emit any operation, i.e. models and migrations drifted.
    command.check(alembic_config(db_url))
