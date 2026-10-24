"""End-to-end rehearsal with scripted agents (tests only), plus the stage-1 safety checks."""

import json

import pytest

from app.core import config
from app.core.db import q, q1
from app.services import agent_runner, firewall, memory, orchestrator
from app.services.mirror import new_mirror
from tests.support import scenarios


def _run(rid, agent, task, scenario):
    r = agent_runner.run_task(
        rid, agent, task, provider=scenarios.SCENARIOS[scenario](), summary=task
    )
    assert r["change_id"], r
    return orchestrator.submit_change(rid, r["change_id"])


@pytest.fixture()
def team(api, monkeypatch):
    monkeypatch.setattr(
        config, "ALLOW_STANDIN", True
    )  # offline rehearsal only; the stand-in is labelled in every verdict
    return api.post(
        "/api/rooms",
        json={
            "name": "e2e",
            "members": [{"name": n, "contribution": 5} for n in ("riya", "aman", "kriti")],
        },
    ).json()["id"]


def test_full_story_with_scripted_agents(team):
    rid = team
    ch = _run(rid, "aman-agent", "Simplify the checkout total", "bug")
    failed = [
        t["name"]
        for t in json.loads(q1("SELECT evidence FROM changes WHERE id=?", (ch["id"],))["evidence"])[
            "tests"
        ]["tests"]
        if not t["passed"]
    ]
    assert ch["status"] == "tests_failed" and any(
        "total" in f for f in failed
    )  # hidden test caught it
    ch = _run(rid, "riya-agent", "Tidy the cart page", "ui_bug")
    assert ch["status"] == "ready"  # tests cannot see a broken form
    res = orchestrator.run_referee(rid, force=True)
    d = q1("SELECT * FROM changes WHERE id=?", (ch["id"],))
    ev = json.loads(d["evidence"])
    assert (
        d["status"] == "referee_failed"
        and ev["referee"]["runner"] == "local-standin"
        and ev["referee"]["routed"]["part"] == "frontend"
    )
    ch2 = _run(rid, "riya-agent", "Tidy the cart page (retry)", "fix_ui")
    assert any(
        "test_shop" in a["path"] for a in q("SELECT path FROM attempts WHERE room_id=?", (rid,))
    )  # firewall blocked the edit
    cc = memory.listing(rid, "contract-change")
    assert len(cc) == 1
    memory.approve_contract_change(rid, cc[0]["id"], "riya")
    orchestrator.run_referee(rid, force=True)
    d2 = q1("SELECT * FROM changes WHERE id=?", (ch2["id"],))
    assert d2["status"] == "passed"
    m = orchestrator.approve(rid, [ch2["id"]], "kriti")
    assert q1("SELECT status FROM changes WHERE id=?", (ch2["id"],))["status"] == "merged"
    orchestrator.undo(rid, m["merge_id"])
    assert q1("SELECT status FROM changes WHERE id=?", (ch2["id"],))["status"] == "undone"


def test_referee_never_pretends(team, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_STANDIN", False)
    monkeypatch.setattr(config, "TINYFISH_KEY", "")
    ch = _run(team, "riya-agent", "Tidy the cart page", "ui_bug")
    res = orchestrator.run_referee(team, force=True)
    assert res["verdict"] == "not_run" and "TINYFISH_API_KEY" in res["reason"]
    d = q1("SELECT status,evidence FROM changes WHERE id=?", (ch["id"],))
    assert d["status"] == "ready" and json.loads(d["evidence"])["referee"]["verdict"] == "not_run"
    with pytest.raises(ValueError):
        orchestrator.approve(team, [ch["id"]], "human")  # cannot merge without a verdict


def test_key_without_public_address_is_not_run(team, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_STANDIN", False)
    monkeypatch.setattr(config, "TINYFISH_KEY", "k")
    monkeypatch.setattr(config, "MIRROR_PUBLIC_URL", "")
    monkeypatch.setattr("shutil.which", lambda *_: None)
    _run(team, "riya-agent", "Tidy the cart page", "ui_bug")
    assert "public address" in orchestrator.run_referee(team, force=True)["reason"]


# ---------- stage 1: safety ----------
@pytest.mark.parametrize(
    "cmd",
    [
        "cat ../../holdout/test_hidden_checkout.py",
        "cat ../../../../x/secret.key",
        "ls ../..",
        "cat platform.db",
        "python -m pytest ../../holdout",
        "cat /proc/self/environ",
    ],
)
def test_bash_cannot_reach_outside_or_platform_files(api, room, cmd):
    assert firewall.check_action("bash", {"command": cmd}, room, "a")


def test_legit_commands_still_allowed(api, room):
    for cmd in (
        "python -m pytest -q -c protected/pytest.ini 2>&1 | tail -3",
        "ls app && cat app/main.py",
        "python -m pytest -q -k total",
    ):
        assert firewall.check_action("bash", {"command": cmd}, room, "a") is None


def test_state_is_not_inside_data():
    assert (
        config.STATE != config.DATA
        and config.DATA not in config.STATE.parents
        and config.STATE not in config.DATA.parents
    )


def test_real_model_refused_without_a_real_sandbox(team, monkeypatch):
    monkeypatch.setattr(config, "AGENT_SANDBOX", "auto")
    monkeypatch.setattr(config, "ALLOW_UNSAFE_SANDBOX", False)
    monkeypatch.setattr(agent_runner, "_docker_ok", False)
    r = agent_runner.run_task(
        team, "aman-agent", "do something"
    )  # provider=None means a real model
    assert r["status"] == "error" and "Refused" in r["final_text"] and r["steps"] == 0


def test_docker_command_shape(tmp_path):
    a = agent_runner.docker_args(tmp_path, "pytest", bootstrap=False)
    assert "--network" in a and a[a.index("--network") + 1] == "none" and "--cap-drop" in a
    assert any(x.endswith("/work/protected:ro") for x in a)  # locked tests mounted read-only
    assert not any(
        x.endswith(":ro") for x in agent_runner.docker_args(tmp_path, "pytest", bootstrap=True)
    )


def test_mirror_environment_has_no_secrets(api, room, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "TINYFISH_API_KEY", "PLATFORM_SECRET"):
        monkeypatch.setenv(k, "leak")
    env = new_mirror(room).env()
    assert not {"ANTHROPIC_API_KEY", "TINYFISH_API_KEY", "PLATFORM_SECRET"} & set(env)


def test_prices_current():
    assert q1("SELECT 1 x FROM prices WHERE model=?", (config.DEFAULT_MODEL,))
