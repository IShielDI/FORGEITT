from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core import db
from tests.conftest import sqlite_url


def test_sqlite_connections_enable_foreign_keys_and_wal(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"


def test_engine_creates_missing_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "forgeit.db"
    engine = db.create_db_engine(sqlite_url(target))
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()

    assert target.exists()


def test_get_db_yields_working_session_and_closes_it(
    db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = sessionmaker(bind=db_engine)
    monkeypatch.setattr(db, "get_sessionmaker", lambda: factory)
    closed: list[Session] = []
    original_close = Session.close

    def tracking_close(self: Session) -> None:
        closed.append(self)
        original_close(self)

    monkeypatch.setattr(Session, "close", tracking_close)

    gen = db.get_db()
    session = next(gen)
    assert session.execute(text("SELECT 1")).scalar_one() == 1
    gen.close()

    assert closed == [session]


def test_engine_uses_configured_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", sqlite_url(tmp_path / "configured.db"))
    db.get_settings.cache_clear()
    db.get_engine.cache_clear()
    try:
        assert db.get_engine().url.database == (tmp_path / "configured.db").as_posix()
    finally:
        db.get_engine().dispose()
        db.get_settings.cache_clear()
        db.get_engine.cache_clear()
