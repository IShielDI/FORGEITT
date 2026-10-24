"""Database engine and session handling (SQLite, WAL mode, foreign keys on)."""

import sqlite3
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

SQLITE_BUSY_TIMEOUT_MS = 5000


def _apply_sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
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


def create_db_engine(url: str) -> Engine:
    """Create an engine; for SQLite files, make the parent directory and set pragmas."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)

    if parsed.database and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
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
