"""platform schema: rooms, members, agents, changes, ledger, referee (TRD section 3)

Revision ID: 0001
Revises:
Create Date: 2026-10-24 16:28:24.457519
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# USD per million tokens (input, cache read, 5-minute cache write, output), from Anthropic's
# pricing page, checked 2026-10-19. Haiku 5.5 uses its higher (>100k prompt) tier so the meter
# never under-counts. Prices change: re-check before relying on them.
PRICE_COLUMNS = ("model", "input", "cache_read", "cache_write", "output")
PRICES = [
    ("claude-sonnet-5-5", 2.0, 0.10, 2.50, 10.0),
    ("claude-haiku-5-5", 0.50, 0.05, 0.625, 2.50),
    ("claude-opus-5-5", 4.0, 0.20, 5.0, 20.0),
    ("claude-fable-5-1", 10.0, 0.25, 12.50, 50.0),
]


def upgrade() -> None:
    op.create_table(
        "agent_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("role_prompt", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("part", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_catalog")),
        sa.UniqueConstraint("room_id", "key", name=op.f("uq_agent_catalog_room_id_key")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("agent_catalog", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_agent_catalog_room_id"), ["room_id"], unique=False)

    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("part", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("backup_model", sa.Text(), nullable=True),
        sa.Column("using_backup", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'idle'"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("steps", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("stop_requested", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("role", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_agents_room_id"), ["room_id"], unique=False)

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attempts")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_attempts_room_id"), ["room_id"], unique=False)

    op.create_table(
        "changes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("branch", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("steps", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column("ready_at", sa.Float(), nullable=True),
        sa.Column("kind", sa.Text(), server_default=sa.text("'normal'"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_changes")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("changes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_changes_room_id"), ["room_id"], unique=False)

    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("threshold", sa.Integer(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_checkpoints")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("checkpoints", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_checkpoints_room_id"), ["room_id"], unique=False)

    op.create_table(
        "contributions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contributions")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("contributions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_contributions_room_id"), ["room_id"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("data", sa.Text(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index("ix_events_room_id_id", ["room_id", "id"], unique=False)

    op.create_table(
        "keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("key_type", sa.Text(), nullable=True),
        sa.Column("secret_enc", sa.Text(), nullable=True),
        sa.Column("last4", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keys")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("keys", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_keys_member_id"), ["member_id"], unique=False)

    op.create_table(
        "ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("call_id", sa.Text(), nullable=True),
        sa.Column("tin", sa.Integer(), nullable=True),
        sa.Column("tout", sa.Integer(), nullable=True),
        sa.Column("tcr", sa.Integer(), nullable=True),
        sa.Column("tcw", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("loan_id", sa.Integer(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ledger")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ledger_room_id"), ["room_id"], unique=False)

    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("lender", sa.Integer(), nullable=True),
        sa.Column("borrower", sa.Integer(), nullable=True),
        sa.Column("cap", sa.Float(), nullable=True),
        sa.Column("used", sa.Float(), server_default=sa.text("0"), nullable=True),
        sa.Column("returned", sa.Float(), server_default=sa.text("0"), nullable=True),
        sa.Column("expires", sa.Float(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=True),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loans")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("loans", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_loans_room_id"), ["room_id"], unique=False)

    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("token_hash", sa.Text(), nullable=True),
        sa.Column("is_owner", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_members_room_id"), ["room_id"], unique=False)

    op.create_table(
        "memory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("part", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.Column("expires", sa.Float(), nullable=True),
        sa.Column("flagged", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("memory", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_memory_room_id"), ["room_id"], unique=False)

    op.create_table(
        "merges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("change_ids", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("approver", sa.Text(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.Column("undone", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_merges")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("merges", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_merges_room_id"), ["room_id"], unique=False)

    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("paths", sa.Text(), nullable=True),
        sa.Column("depends_on", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parts")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("parts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_parts_room_id"), ["room_id"], unique=False)

    op.create_table(
        "prices",
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input", sa.Float(), nullable=True),
        sa.Column("cache_read", sa.Float(), nullable=True),
        sa.Column("cache_write", sa.Float(), nullable=True),
        sa.Column("output", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("model", name=op.f("pk_prices")),
    )
    prices = sa.table("prices", *(sa.column(c) for c in PRICE_COLUMNS))
    op.bulk_insert(prices, [dict(zip(PRICE_COLUMNS, row, strict=True)) for row in PRICES])
    op.create_table(
        "referee_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.Column("runner", sa.Text(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referee_runs")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("referee_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_referee_runs_room_id"), ["room_id"], unique=False)

    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("requester", sa.Integer(), nullable=True),
        sa.Column("target", sa.Integer(), nullable=True),
        sa.Column("asked", sa.Float(), nullable=True),
        sa.Column("funded", sa.Float(), server_default=sa.text("0"), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'"), nullable=True),
        sa.Column("expires", sa.Float(), nullable=True),
        sa.Column("checkpoint_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requests")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_requests_room_id"), ["room_id"], unique=False)

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.Column("mode", sa.Text(), server_default=sa.text("'sample'"), nullable=True),
        sa.Column("bootstrapped", sa.Integer(), server_default=sa.text("1"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
        sqlite_autoincrement=True,
    )


def downgrade() -> None:
    op.drop_table("rooms")
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_requests_room_id"))

    op.drop_table("requests")
    with op.batch_alter_table("referee_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_referee_runs_room_id"))

    op.drop_table("referee_runs")
    op.drop_table("prices")
    with op.batch_alter_table("parts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_parts_room_id"))

    op.drop_table("parts")
    with op.batch_alter_table("merges", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_merges_room_id"))

    op.drop_table("merges")
    with op.batch_alter_table("memory", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_memory_room_id"))

    op.drop_table("memory")
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_members_room_id"))

    op.drop_table("members")
    with op.batch_alter_table("loans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_loans_room_id"))

    op.drop_table("loans")
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ledger_room_id"))

    op.drop_table("ledger")
    with op.batch_alter_table("keys", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_keys_member_id"))

    op.drop_table("keys")
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index("ix_events_room_id_id")

    op.drop_table("events")
    with op.batch_alter_table("contributions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contributions_room_id"))

    op.drop_table("contributions")
    with op.batch_alter_table("checkpoints", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checkpoints_room_id"))

    op.drop_table("checkpoints")
    with op.batch_alter_table("changes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_changes_room_id"))

    op.drop_table("changes")
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_attempts_room_id"))

    op.drop_table("attempts")
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agents_room_id"))

    op.drop_table("agents")
    with op.batch_alter_table("agent_catalog", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_catalog_room_id"))

    op.drop_table("agent_catalog")
