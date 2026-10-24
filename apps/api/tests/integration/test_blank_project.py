"""Blank-project mode: the first human-approved bootstrap becomes the locked original."""

import json

import pytest

from app.core.db import q, q1
from app.services import agent_runner, gitops, memory, orchestrator
from tests.support.plans import APP, E, bootstrap_plan
from tests.support.scripted import ScriptedProvider


@pytest.fixture()
def blank(api):
    rid = api.post(
        "/api/rooms",
        json={
            "name": "blank",
            "template": "blank",
            "members": [{"name": "riya", "contribution": 5}],
        },
    ).json()["id"]
    return rid


def _boot(rid, plan=None):
    r = agent_runner.run_task(
        rid,
        "riya-agent",
        "Build a hello service",
        provider=plan or bootstrap_plan(),
        summary="Bootstrap",
        bootstrap=True,
    )
    return orchestrator.submit_change(rid, r["change_id"])


def test_blank_room_starts_empty_and_refuses_normal_work(api, blank):
    assert q1("SELECT mode,bootstrapped FROM rooms WHERE id=?", (blank,)) == {
        "mode": "blank",
        "bootstrapped": 0,
    }
    assert (
        api.post(f"/api/rooms/{blank}/agents/riya-agent/run", json={"task": "x"}).status_code == 409
    )
    assert api.get(f"/api/rooms/{blank}/holdout").json() == []


def test_bootstrap_needs_human_review_then_becomes_the_original(api, blank):
    ch = _boot(blank)
    assert ch["status"] == "bootstrap_review" and ch["verdict"] == "needs_human_review"
    orchestrator.approve(blank, [ch["id"]], "riya")
    assert q1("SELECT bootstrapped FROM rooms WHERE id=?", (blank,))["bootstrapped"] == 1
    assert (gitops.original(blank) / "protected/tests/test_hello.py").exists() and (
        gitops.original(blank) / "app/main.py"
    ).exists()


def test_bootstrap_cannot_touch_platform_owned_files(api, blank):
    bad = bootstrap_plan(
        extra=[
            [
                (
                    "tool",
                    E,
                    {
                        "command": "create",
                        "path": "protected/pytest.ini",
                        "file_text": "[pytest]\n",
                    },
                )
            ]
        ]
    )
    ch = _boot(blank, bad)
    assert ch["status"] == "rejected_firewall"


def test_bootstrap_without_tests_is_not_accepted(api, blank):
    only_app = ScriptedProvider(
        [
            [("tool", E, {"command": "create", "path": "app/main.py", "file_text": APP})],
            [("text", "done")],
        ]
    )
    ch = _boot(blank, only_app)
    assert ch["status"] == "tests_failed"


def test_after_bootstrap_tests_are_locked_and_verified_by_them(api, blank, monkeypatch):
    orchestrator.approve(blank, [_boot(blank)["id"]], "riya")
    # a later agent tries to weaken the now-locked test: blocked
    weaken = ScriptedProvider(
        [
            [
                (
                    "tool",
                    E,
                    {
                        "command": "str_replace",
                        "path": "protected/tests/test_hello.py",
                        "old_str": "Hello, Ana!",
                        "new_str": "",
                    },
                )
            ],
            [
                (
                    "tool",
                    E,
                    {
                        "command": "str_replace",
                        "path": "app/main.py",
                        "old_str": "'world'",
                        "new_str": "'there'",
                    },
                )
            ],
            [("text", "changed default name")],
        ]
    )
    r = agent_runner.run_task(
        blank, "riya-agent", "rename default", provider=weaken, summary="rename"
    )
    ch = orchestrator.submit_change(blank, r["change_id"])
    assert any(
        "test_hello" in a["path"] for a in q("SELECT path FROM attempts WHERE room_id=?", (blank,))
    )
    assert (
        ch["status"] == "tests_failed"
    )  # the locked test still says 'Hello, world!' for the default
    assert q1("SELECT 1 x FROM changes WHERE id=? AND status='merged'", (ch["id"],)) is None


def test_no_journey_means_tests_only_and_it_says_so(api, blank):
    orchestrator.approve(blank, [_boot(blank)["id"]], "riya")
    ok = ScriptedProvider(
        [
            [
                (
                    "tool",
                    E,
                    {
                        "command": "str_replace",
                        "path": "app/main.py",
                        "old_str": "def health(): return {'ok': True}",
                        "new_str": "def health(): return {'ok': True}  # fine",
                    },
                )
            ],
            [("text", "comment")],
        ]
    )
    ch = orchestrator.submit_change(
        blank,
        agent_runner.run_task(blank, "riya-agent", "tidy", provider=ok, summary="tidy")[
            "change_id"
        ],
    )
    assert ch["status"] == "passed" and ch["verdict"] == "tests_only"
    assert json.loads(ch["evidence"])["referee"]["verdict"] == "not_run"


def test_journey_goes_to_the_referee_queue(api, blank):
    orchestrator.approve(blank, [_boot(blank)["id"]], "riya")
    assert (
        api.put(
            f"/api/rooms/{blank}/journey",
            json={
                "goal": "Open the site and read the greeting for {email}",
                "success_text": "Hello",
                "db_check": "DELETE FROM x",
            },
        ).status_code
        == 400
    )
    assert (
        api.put(
            f"/api/rooms/{blank}/journey",
            json={"goal": "Open /api/hello and read the greeting", "success_text": "Hello"},
        ).status_code
        == 200
    )
    ok = ScriptedProvider(
        [
            [
                (
                    "tool",
                    E,
                    {
                        "command": "str_replace",
                        "path": "app/main.py",
                        "old_str": "def health(): return {'ok': True}",
                        "new_str": "def health(): return {'ok': True}  # fine",
                    },
                )
            ],
            [("text", "comment")],
        ]
    )
    ch = orchestrator.submit_change(
        blank,
        agent_runner.run_task(blank, "riya-agent", "tidy", provider=ok, summary="tidy")[
            "change_id"
        ],
    )
    assert ch["status"] == "ready"
    assert api.get(f"/api/rooms/{blank}/journey").json()["success_text"] == "Hello"


def test_human_hidden_test_runs_in_the_mirror_and_is_not_served(api, blank):
    orchestrator.approve(blank, [_boot(blank)["id"]], "riya")
    hidden = "def test_hello_unicode(client):\n    assert client.get('/api/hello', params={'name': 'Zoë'}).json()['message'] == 'Hello, Zoë!'\n"
    assert (
        api.post(
            f"/api/rooms/{blank}/holdout", json={"filename": "../evil.py", "content": hidden}
        ).status_code
        == 400
    )
    assert (
        api.post(
            f"/api/rooms/{blank}/holdout",
            json={"filename": "test_hidden_unicode.py", "content": hidden},
        ).status_code
        == 200
    )
    assert (
        api.get(f"/api/rooms/{blank}/holdout").json() == []
    )  # a draft does not run until approved
    approve = api.post(f"/api/rooms/{blank}/holdout/test_hidden_unicode.py/approve")
    assert approve.status_code == 200 and "Zo" not in approve.text  # names only, never the source
    assert api.get(f"/api/rooms/{blank}/holdout").json() == ["test_hidden_unicode.py"]
    # a change that hard-codes the visible answers is caught by the hidden test (borrowing the project's locked fixtures)
    cheat = ScriptedProvider(
        [
            [
                (
                    "tool",
                    E,
                    {
                        "command": "create",
                        "path": "app/main.py",
                        "file_text": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/api/health')\ndef health(): return {'ok': True}\n"
                        "@app.get('/api/hello')\ndef hello(name: str = 'world'): return {'message': 'Hello, Ana!' if name == 'Ana' else 'Hello, world!'}\n",
                    },
                )
            ],
            [("text", "optimised")],
        ]
    )
    ch = orchestrator.submit_change(
        blank,
        agent_runner.run_task(blank, "riya-agent", "optimise", provider=cheat, summary="opt")[
            "change_id"
        ],
    )
    names = [t["name"] for t in json.loads(ch["evidence"])["tests"]["tests"] if not t["passed"]]
    assert ch["status"] == "tests_failed" and any("unicode" in n for n in names)


def test_memory_never_holds_journey_or_hidden_tests(api, blank):
    api.put(f"/api/rooms/{blank}/journey", json={"goal": "secret journey text"})
    text = " ".join(m["content"] for m in memory.listing(blank)).lower()
    assert "secret journey" not in text
