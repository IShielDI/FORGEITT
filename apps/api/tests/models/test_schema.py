"""Structural checks on the migrated database (stage 2 acceptance criteria)."""

import pytest
from sqlalchemy import Engine, inspect, text

from app.models import Base

EXPECTED_TABLES = {
    "users",
    "workspaces",
    "members",
    "invites",
    "messages",
    "spec_items",
    "spec_versions",
    "contracts",
    "tasks",
    "knowledge_links",
    "submissions",
    "integration_runs",
    "check_results",
    "hidden_tests",
    "referee_runs",
    "failures",
    "approvals",
    "credit_ledger",
    "jobs",
}

WORKSPACE_SCOPED = {
    "members",
    "invites",
    "messages",
    "spec_items",
    "spec_versions",
    "contracts",
    "tasks",
    "knowledge_links",
    "integration_runs",
    "hidden_tests",
    "credit_ledger",
}


def test_all_core_tables_exist(db_engine: Engine) -> None:
    tables = set(inspect(db_engine).get_table_names()) - {"alembic_version"}

    assert tables == EXPECTED_TABLES


def test_models_cover_exactly_the_core_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_every_table_has_string_uuid_pk_and_timestamps(db_engine: Engine, table: str) -> None:
    inspector = inspect(db_engine)
    columns = {c["name"]: c for c in inspector.get_columns(table)}

    assert inspector.get_pk_constraint(table)["constrained_columns"] == ["id"]
    assert str(columns["id"]["type"]) == "VARCHAR(36)"
    assert {"created_at", "updated_at"} <= columns.keys()


def test_workspace_scoped_tables_index_and_cascade_workspace_id(db_engine: Engine) -> None:
    inspector = inspect(db_engine)
    scoped = {
        t
        for t in EXPECTED_TABLES
        if "workspace_id" in {c["name"] for c in inspector.get_columns(t)}
    }

    assert scoped == WORKSPACE_SCOPED
    for table in scoped:
        indexed = [
            ix for ix in inspector.get_indexes(table) if ix["column_names"] == ["workspace_id"]
        ]
        assert indexed, f"{table}.workspace_id has no index"
        fks = [
            fk
            for fk in inspector.get_foreign_keys(table)
            if fk["constrained_columns"] == ["workspace_id"]
        ]
        assert fks and fks[0]["referred_table"] == "workspaces"
        assert fks[0]["options"].get("ondelete") == "CASCADE"


def test_expected_unique_constraints(db_engine: Engine) -> None:
    inspector = inspect(db_engine)

    def uniques(table: str) -> list[list[str]]:
        return [u["column_names"] for u in inspector.get_unique_constraints(table)]

    assert ["email"] in uniques("users")
    assert ["workspace_id", "user_id"] in uniques("members")
    assert ["token_hash"] in uniques("members")
    assert ["token_hash"] in uniques("invites")
    assert ["workspace_id", "version"] in uniques("spec_versions")
    assert ["workspace_id", "name", "version"] in uniques("contracts")


def test_slug_is_not_unique_and_there_is_no_room_code(db_engine: Engine) -> None:
    # TRD R14: the slug is a display label, never an identifier anyone can join with.
    inspector = inspect(db_engine)
    columns = {c["name"] for c in inspector.get_columns("workspaces")}

    assert "room_code" not in columns
    assert ["slug"] not in [
        u["column_names"] for u in inspector.get_unique_constraints("workspaces")
    ]


def test_enum_values_are_enforced_by_check_constraints(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        schema = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE name = 'referee_runs'")
        ).scalar_one()

    assert "CONSTRAINT ck_referee_runs_referee_verdict CHECK" in schema
    assert "'not_run'" in schema
