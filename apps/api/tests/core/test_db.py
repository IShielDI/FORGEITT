import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core import db


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


def test_engine_uses_configured_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example:5432/x")
    db.get_settings.cache_clear()
    db.get_engine.cache_clear()
    try:
        engine = db.get_engine()
        assert engine.url.host == "db.example"
        assert engine.url.database == "x"
    finally:
        db.get_settings.cache_clear()
        db.get_engine.cache_clear()
