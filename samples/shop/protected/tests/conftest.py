import os, tempfile, pytest

@pytest.fixture()
def client():
    d = tempfile.mkdtemp()
    os.environ["DB_PATH"] = os.path.join(d, "t.db")
    from fastapi.testclient import TestClient
    from app import db
    import app.main as m
    db.init()
    with TestClient(m.app) as c:
        yield c
