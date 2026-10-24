"""Database access (SQLite, WAL mode, foreign keys on).

Two layers over the same file:
- SQLAlchemy engine/session (`get_engine`, `get_db`) used by Alembic and newer code.
- Small `q`/`q1`/`ex` helpers over sqlite3 used by the platform services.
The schema is owned by Alembic migrations; `init()` applies them.
"""

import sqlite3
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

SQLITE_BUSY_TIMEOUT_MS = 5000
API_ROOT = Path(__file__).resolve().parents[2]


def _apply_sqlite_pragmas(dbapi_connection: Any, _record: Any = None) -> None:
    """Enforce foreign keys and WAL on every new SQLite connection (both default off)."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def sqlite_path(url: str) -> Path | None:
    """File path of a SQLite URL, or None for other databases / in-memory."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or parsed.database in (None, "", ":memory:"):
        return None
    return Path(parsed.database)


def create_db_engine(url: str) -> Engine:
    """Create an engine; for SQLite files, make the parent directory and set pragmas."""
    if make_url(url).get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)

    path = sqlite_path(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _apply_sqlite_pragmas)
    return engine


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide engine, created lazily from settings."""
    return create_db_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session and always close it."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------
def init(url: str | None = None) -> None:
    """Create or upgrade the schema by running the Alembic migrations to head."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", (url or get_settings().database_url).replace("%", "%%"))
    cfg.attributes["configure_logging"] = False
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Lightweight query helpers for the platform services
# ---------------------------------------------------------------------------
def _db_file() -> Path:
    path = sqlite_path(get_settings().database_url)
    if path is None:
        raise RuntimeError("the platform services need a SQLite file DATABASE_URL")
    return path


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_db_file(), timeout=30)
    c.row_factory = sqlite3.Row
    _apply_sqlite_pragmas(c)
    return c


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    c = _conn()
    try:
        yield c
        c.commit()
    finally:
        c.close()


def q(sql: str, args: Sequence[Any] | dict[str, Any] = ()) -> list[dict[str, Any]]:
    with tx() as c:
        return [dict(r) for r in c.execute(sql, args)]


def q1(sql: str, args: Sequence[Any] | dict[str, Any] = ()) -> dict[str, Any] | None:
    rows = q(sql, args)
    return rows[0] if rows else None


def ex(sql: str, args: Sequence[Any] | dict[str, Any] = ()) -> int:
    with tx() as c:
        return c.execute(sql, args).lastrowid or 0


def now() -> float:
    return time.time()
