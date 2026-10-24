"""Migration round-trip: upgrade head, downgrade base, and models match the migrated schema."""

from sqlalchemy import Engine, inspect, text

from alembic import command
from tests.conftest import alembic_config


def _user_tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def _enum_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(text("SELECT count(*) FROM pg_type WHERE typtype = 'e'")).scalar_one()
        )


def test_downgrade_base_then_upgrade_head(db_engine: Engine, db_url: str) -> None:
    cfg = alembic_config(db_url)
    try:
        command.downgrade(cfg, "base")
        assert _user_tables(db_engine) == set()
        assert _enum_count(db_engine) == 0
    finally:
        command.upgrade(cfg, "head")

    assert len(_user_tables(db_engine)) == 15
    assert _enum_count(db_engine) == 15


def test_models_match_migrations(db_engine: Engine, db_url: str) -> None:
    # Raises if autogenerate would emit any operation, i.e. models and migrations drifted.
    command.check(alembic_config(db_url))
