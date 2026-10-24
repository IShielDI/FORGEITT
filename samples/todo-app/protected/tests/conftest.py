import os
import tempfile

import pytest


@pytest.fixture()
def client():
    os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
    from fastapi.testclient import TestClient

    import app.main as m
    from app import db

    db.init()
    with TestClient(m.app) as c:
        yield c
