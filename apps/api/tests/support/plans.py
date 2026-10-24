"""Reusable scripted plans for tests."""

from tests.support.scripted import ScriptedProvider

E = "str_replace_based_edit_tool"
CONF = (
    "import os, tempfile, pytest\n@pytest.fixture()\ndef client():\n    os.environ['DB_PATH'] = os.path.join(tempfile.mkdtemp(), 't.db')\n"
    "    from fastapi.testclient import TestClient\n    import app.main as m\n    with TestClient(m.app) as c:\n        yield c\n"
)
TESTS = (
    "def test_health(client):\n    assert client.get('/api/health').json() == {'ok': True}\n"
    "def test_hello(client):\n    assert client.get('/api/hello', params={'name': 'Ana'}).json()['message'] == 'Hello, Ana!'\n"
    "def test_hello_default(client):\n    assert client.get('/api/hello').json()['message'] == 'Hello, world!'\n"
)
APP = (
    "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/api/health')\ndef health(): return {'ok': True}\n"
    "@app.get('/api/hello')\ndef hello(name: str = 'world'): return {'message': f'Hello, {name}!'}\n"
)


def bootstrap_plan(extra=()):
    c = lambda path, text: [("tool", E, {"command": "create", "path": path, "file_text": text})]
    return ScriptedProvider(
        [
            c(
                "protected/contracts/contracts.json",
                '{"hello": "GET /api/hello?name=X returns Hello, X!"}',
            ),
            c("protected/tests/conftest.py", CONF),
            c("protected/tests/test_hello.py", TESTS),
            c("app/main.py", APP),
            *extra,
            [("text", "Handoff: hello service with 3 tests.")],
        ]
    )
