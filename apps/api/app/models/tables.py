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
    Column("allowed_providers", Text),  # JSON list, e.g. ["claude","mock"]; NULL = every provider
    Column("observer_cursor", Integer, server_default=text("0")),  # last chat message observed
    Column("verification_profile", Text),  # fast | standard | strict; NULL = VERIFICATION_PROFILE
    Column(
        "edit_scope", Text, server_default=text("'off'")
    ),  # off | task: edits limited to relevant files
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
    # set for teammates added when the workspace was created: accepting signs in as that member
    Column("member_id", Integer),
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
    Column("source", Text, server_default=text("'own'")),  # own | loan | house (who pays)
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
    Column("task_id", Integer),  # planned task this change implements (stage 13)
    Column("commit_sha", Text),  # head of the change's branch when it was submitted (stage 14)
    Column("handoff", Text),  # JSON handoff summary (stage 14)
    Column(
        "verified_sha", Text
    ),  # branch head the checks ran on; approval is bound to it (stage 18)
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
    Column("candidate_sha", Text),  # JSON {change_id: verified commit} the approval was bound to
    Column("merged_sha", Text),  # main after the merge
    Column("release_tag", Text),  # release/<n>
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

messages = _table(
    "messages",
    _id(),
    _room(),
    Column("member_id", Integer),
    Column("body", Text),  # untrusted chat text: never rendered as HTML, validated before prompts
    Column("ts", Float),
)

spec_items = _table(
    "spec_items",
    _id(),
    _room(),
    Column("kind", Text),  # requirement | decision | suggestion | question
    Column("text", Text),
    Column(
        "status", Text, server_default=text("'proposed'")
    ),  # proposed|confirmed|rejected|superseded
    Column("source_message_ids", Text, server_default=text("'[]'")),  # JSON list of message ids
    Column("confidence", Float),
    Column("version", Integer, server_default=text("1")),
    Column("supersedes_id", Integer),  # previous version of the same item (append-only edits)
    Column("created_by", Integer),  # NULL = proposed by the observer agent
    Column("confirmed_by", Integer),  # always a human
    Column("created", Float),
    Column("decided", Float),
)

# Two spec items that contradict each other (e.g. "add X" then "remove X"). People pick one; if
# everyone who argued agrees it settles itself, otherwise the owner makes the final call.
spec_conflicts = _table(
    "spec_conflicts",
    _id(),
    _room(),
    Column("item_a", Integer),  # the earlier item
    Column("item_b", Integer),  # the later item, which reverses it
    Column("status", Text, server_default=text("'open'")),  # open | resolved
    Column("winner_id", Integer),
    Column("decided_how", Text),  # agreement | owner
    Column("decided_by", Integer),
    Column("created", Float),
    Column("decided", Float),
)

conflict_votes = _table(
    "conflict_votes",
    _id(),
    _room(),
    Column("conflict_id", Integer, index=True),
    Column("member_id", Integer),
    Column("choice", Integer),  # the spec item id this member picked
    Column("created", Float),
    UniqueConstraint("conflict_id", "member_id"),
)

spec_versions = _table(
    "spec_versions",
    _id(),
    _room(),
    Column("version", Integer),
    Column("snapshot", Text),  # JSON: the confirmed items at this version
    Column("created_by", Integer),
    Column("created", Float),
    UniqueConstraint("room_id", "version"),
)

tasks = _table(
    "tasks",
    _id(),
    _room(),
    Column("key", Text),  # short id from the plan, used for dependencies
    Column("title", Text),
    Column("description", Text),
    Column("component", Text),
    Column("depends_on", Text, server_default=text("'[]'")),  # JSON list of task keys
    Column("suggested_owner", Text),
    Column("owner_member_id", Integer),
    Column(
        "status", Text, server_default=text("'proposed'")
    ),  # proposed|approved|in_progress|submitted|done
    Column(
        "spec_item_ids", Text, server_default=text("'[]'")
    ),  # requirements/decisions it implements
    Column("contract_ids", Text, server_default=text("'[]'")),  # pinned contract versions
    Column("plan_version", Integer, server_default=text("1")),
    Column("created", Float),
)

contracts = _table(
    "contracts",
    _id(),
    _room(),
    Column("kind", Text),  # api | schema | type
    Column("name", Text),
    Column("content", Text),
    Column("version", Integer, server_default=text("1")),
    Column("status", Text, server_default=text("'proposed'")),  # proposed|approved|superseded
    Column("spec_item_ids", Text, server_default=text("'[]'")),
    Column("created_by", Integer),
    Column("created", Float),
    UniqueConstraint("room_id", "name", "version"),
)

knowledge_links = Table(
    "knowledge_links",
    metadata,
    _id(),
    _room(),
    Column(
        "src_type", Text
    ),  # requirement|decision|suggestion|question|contract|task|change|commit|failure
    Column("src_id", Text),
    Column("dst_type", Text),
    Column("dst_id", Text),
    Column("relation", Text),
    Column("version", Integer, server_default=text("1")),
    Column("created_by", Integer),
    Column("created", Float),
    Index("ix_knowledge_links_src", "room_id", "src_type", "src_id"),
    Index("ix_knowledge_links_dst", "room_id", "dst_type", "dst_id"),
    sqlite_autoincrement=True,
)

hidden_tests = _table(
    "hidden_tests",
    _id(),
    _room(),
    Column(
        "filename", Text
    ),  # the source lives in the room's holdout folders, never in the database
    Column("author_id", Integer),
    Column("approved_by", Integer),  # must be a different person than the author
    Column("status", Text, server_default=text("'draft'")),  # draft | approved | retired
    Column("created", Float),
    Column("approved_at", Float),
    UniqueConstraint("room_id", "filename"),
)

ROOM_SCOPED = sorted(t.name for t in metadata.sorted_tables if "room_id" in t.c)
