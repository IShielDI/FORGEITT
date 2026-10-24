"""Shared fixtures.

Before anything from `app` is imported, point the platform at throwaway folders so tests never touch
real data, a real `.env` database, real keys or the real referee. Logins are off by default; tests
that exercise them switch REQUIRE_AUTH on themselves.
"""

import os
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="forgeit-test-state-")
os.environ["PLATFORM_DATA"] = tempfile.mkdtemp(prefix="forgeit-test-data-")
os.environ["PLATFORM_STATE"] = _STATE
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_STATE, 'forgeit.db').as_posix()}"
os.environ["REQUIRE_AUTH"] = "0"
os.environ["LLM_PROVIDER"] = "mock"
for _secret in ("TINYFISH_API_KEY", "ANTHROPIC_API_KEY", "PUBLIC_TUNNEL_URL", "MIRROR_PUBLIC_URL"):
    os.environ.pop(_secret, None)

import shutil  # noqa: E402
from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine  # noqa: E402

from app.core import db as _db  # noqa: E402

_db.init()
# test-only free model for scripted agents
_db.ex("INSERT OR IGNORE INTO prices VALUES(?,?,?,?,?)", ("scripted", 0, 0, 0, 0))

API_ROOT = Path(__file__).resolve().parents[1]


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


# ---------- platform API fixtures ----------
@pytest.fixture(scope="module")
def api() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def room(api: TestClient) -> int:
    members = [
        {"name": "riya", "contribution": 10},
        {"name": "aman", "contribution": 1},
        {"name": "kriti", "contribution": 0},
    ]
    return int(api.post("/api/rooms", json={"name": "t", "members": members}).json()["id"])


# ---------- schema fixtures: separate temporary database files ----------
@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database file at migration head, built once per test session."""
    path = tmp_path_factory.mktemp("db") / "template.db"
    command.upgrade(alembic_config(sqlite_url(path)), "head")
    return path


@pytest.fixture
def db_url(migrated_template: Path, tmp_path: Path) -> str:
    path = tmp_path / "test.db"
    shutil.copyfile(migrated_template, path)
    return sqlite_url(path)


@pytest.fixture
def db_engine(db_url: str) -> Iterator[Engine]:
    engine = _db.create_db_engine(db_url)
    yield engine
    engine.dispose()
