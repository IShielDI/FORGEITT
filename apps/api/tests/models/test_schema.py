"""Structural checks on the migrated database (stage 2 acceptance criteria)."""

from sqlalchemy import Engine, inspect, text

from app.models import ROOM_SCOPED, metadata

EXPECTED_TABLES = {
    "rooms",
    "members",
    "keys",
    "contributions",
    "prices",
    "ledger",
    "requests",
    "loans",
    "checkpoints",
    "attempts",
    "memory",
    "parts",
    "changes",
    "merges",
    "agents",
    "agent_catalog",
    "events",
    "referee_runs",
    "invites",
    "messages",
    "spec_items",
    "spec_conflicts",
    "conflict_votes",
    "spec_versions",
    "tasks",
    "contracts",
    "knowledge_links",
    "hidden_tests",
}


def test_all_tables_exist(db_engine: Engine) -> None:
    tables = set(inspect(db_engine).get_table_names()) - {"alembic_version", "sqlite_sequence"}

    assert tables == EXPECTED_TABLES


def test_metadata_covers_exactly_the_tables() -> None:
    assert set(metadata.tables) == EXPECTED_TABLES


def test_every_room_scoped_table_indexes_room_id(db_engine: Engine) -> None:
    inspector = inspect(db_engine)

    assert len(ROOM_SCOPED) == 25
    for table in ROOM_SCOPED:
        leading = [ix["column_names"][0] for ix in inspector.get_indexes(table)]
        assert "room_id" in leading, f"{table}.room_id has no index"


def test_catalog_keys_are_unique_per_room(db_engine: Engine) -> None:
    uniques = [
        u["column_names"] for u in inspect(db_engine).get_unique_constraints("agent_catalog")
    ]

    assert ["room_id", "key"] in uniques


def test_prices_are_seeded_for_the_default_models(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        models = set(conn.execute(text("SELECT model FROM prices")).scalars())

    assert {"claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"} <= models


def test_ids_autoincrement(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.execute(text("INSERT INTO rooms(name) VALUES ('a')"))
        conn.execute(text("INSERT INTO rooms(name) VALUES ('b')"))
        ids = list(conn.execute(text("SELECT id FROM rooms ORDER BY id")).scalars())
        defaults = conn.execute(text("SELECT mode, bootstrapped FROM rooms LIMIT 1")).one()

    assert ids == [1, 2]
    assert tuple(defaults) == ("sample", 1)
