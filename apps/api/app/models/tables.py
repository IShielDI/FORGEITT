"""Platform schema (SQLAlchemy Core). Alembic migrations are generated from this metadata.

The services query these tables with plain SQL through `app.core.db`. A "room" is a workspace.
Timestamps are Unix epoch seconds (REAL). See docs/TRD.md section 3 for how these map to the
TRD entities.
"""

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.schema import SchemaItem

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _id() -> Column[int]:
    return Column("id", Integer, primary_key=True, autoincrement=True)


def _room() -> Column[int]:
    """Owning workspace; indexed on every room-scoped table."""
    return Column("room_id", Integer, index=True)


def _table(name: str, *cols: SchemaItem) -> Table:
    return Table(name, metadata, *cols, sqlite_autoincrement=True)


rooms = _table(
    "rooms",
    _id(),
    Column("name", Text),
    Column("created", Float),
    Column("mode", Text, server_default=text("'sample'")),  # "sample" (demo shop) or "blank"
    Column("slug", Text),  # display label only; never a credential and never used to join
    Column("bootstrapped", Integer, server_default=text("1")),
)

members = _table(
    "members",
    _id(),
    _room(),
    Column("name", Text),
    Column("email", Text),
    Column("token_hash", Text),  # SHA-256 of the login token; the raw token is shown once
    Column("is_owner", Integer, server_default=text("0")),
    Column("role", Text, server_default=text("'member'")),  # owner | member | viewer (read-only)
)

invites = _table(
    "invites",
    _id(),
    _room(),
    Column("token_hash", Text, unique=True),  # only the hash is stored; the link is shown once
    Column("role", Text, server_default=text("'member'")),
    Column("email", Text),
    Column("created_by", Integer),
    Column("created", Float),
    Column("expires", Float),
    Column("used_at", Float),
    Column("used_by", Integer),
)

keys = Table(
    "keys",
    metadata,
    _id(),
    Column("member_id", Integer, index=True),
    Column("provider", Text),
    Column("key_type", Text),
    Column("secret_enc", Text),  # Fernet-encrypted; never returned to any screen
    Column("last4", Text),
    Column("status", Text, server_default=text("'active'")),
    sqlite_autoincrement=True,
)

contributions = _table(
    "contributions", _id(), _room(), Column("member_id", Integer), Column("amount", Float)
)

prices = Table(
    "prices",
    metadata,
    Column("model", Text, primary_key=True),
    Column("input", Float),
    Column("cache_read", Float),
    Column("cache_write", Float),
    Column("output", Float),
)

ledger = _table(
    "ledger",
    _id(),
    _room(),
    Column("member_id", Integer),
    Column("agent", Text),
    Column("model", Text),
    Column("call_id", Text),
    Column("tin", Integer),
    Column("tout", Integer),
    Column("tcr", Integer),
    Column("tcw", Integer),
    Column("cost", Float),
    Column("loan_id", Integer),
    Column("ts", Float),
)

requests = _table(
    "requests",
    _id(),
    _room(),
    Column("requester", Integer),
    Column("target", Integer),
    Column("asked", Float),
    Column("funded", Float, server_default=text("0")),
    Column("status", Text, server_default=text("'open'")),
    Column("expires", Float),
    Column("checkpoint_id", Integer),
)

loans = _table(
    "loans",
    _id(),
    _room(),
    Column("lender", Integer),
    Column("borrower", Integer),
    Column("cap", Float),
    Column("used", Float, server_default=text("0")),
    Column("returned", Float, server_default=text("0")),
    Column("expires", Float),
    Column("status", Text, server_default=text("'active'")),
    Column("request_id", Integer),
)

checkpoints = _table(
    "checkpoints",
    _id(),
    _room(),
    Column("member_id", Integer),
    Column("agent", Text),
    Column("threshold", Integer),
    Column("state", Text),
    Column("ts", Float),
)

attempts = _table(
    "attempts",
    _id(),
    _room(),
    Column("agent", Text),
    Column("action", Text),
    Column("path", Text),
    Column("ts", Float),
)

memory = _table(
    "memory",
    _id(),
    _room(),
    Column("kind", Text),
    Column("part", Text),
    Column("author", Text),
    Column("content", Text),
    Column("ts", Float),
    Column("expires", Float),
    Column("flagged", Integer, server_default=text("0")),
)

parts = _table(
    "parts",
    _id(),
    _room(),
    Column("name", Text),
    Column("owner", Text),
    Column("paths", Text),
    Column("depends_on", Text),
)

changes = _table(
    "changes",
    _id(),
    _room(),
    Column("agent", Text),
    Column("member_id", Integer),
    Column("branch", Text),
    Column("summary", Text),
    Column("status", Text),
    Column("model", Text),
    Column("steps", Integer, server_default=text("0")),
    Column("created", Float),
    Column("evidence", Text),  # JSON: tests, referee verdict, routing, diff
    Column("verdict", Text),
    Column("ready_at", Float),
    Column("kind", Text, server_default=text("'normal'")),  # "normal" or "bootstrap"
)

merges = _table(
    "merges",
    _id(),
    _room(),
    Column("change_ids", Text),
    Column("snapshot", Text),  # tag to restore on undo
    Column("approver", Text),
    Column("ts", Float),
    Column("undone", Integer, server_default=text("0")),
)

agents = _table(
    "agents",
    _id(),
    _room(),
    Column("name", Text),
    Column("member_id", Integer),
    Column("part", Text),
    Column("model", Text),
    Column("backup_model", Text),
    Column("using_backup", Integer, server_default=text("0")),
    Column("status", Text, server_default=text("'idle'")),
    Column("note", Text),
    Column("steps", Integer, server_default=text("0")),
    Column("stop_requested", Integer, server_default=text("0")),
    Column("role", Text),
)

agent_catalog = _table(
    "agent_catalog",
    _id(),
    _room(),
    Column("key", Text),
    Column("label", Text),
    Column("description", Text),
    Column("role_prompt", Text),
    Column("model", Text),
    Column("part", Text),
    UniqueConstraint("room_id", "key"),
)

events = Table(
    "events",
    metadata,
    _id(),
    Column("room_id", Integer),
    Column("agent", Text),
    Column("kind", Text),
    Column("data", Text),  # never contains keys or hidden tests
    Column("ts", Float),
    Index("ix_events_room_id_id", "room_id", "id"),
    sqlite_autoincrement=True,
)

referee_runs = _table(
    "referee_runs",
    _id(),
    _room(),
    Column("ts", Float),
    Column("runner", Text),
    Column("steps", Integer),
)

ROOM_SCOPED = sorted(t.name for t in metadata.sorted_tables if "room_id" in t.c)
