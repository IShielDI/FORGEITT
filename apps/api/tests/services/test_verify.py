"""Stages 15-17 and 19-20: check evidence, profiles, contract conformance, routing confidence."""

import json
from pathlib import Path

import pytest

from app.core.db import ex, q1
from app.services import agent_runner, gitops, mirror, orchestrator, security, verify
from tests.support import scenarios


def _change(room, agent, task, scenario):
    r = agent_runner.run_task(
        room, agent, task, provider=scenarios.SCENARIOS[scenario](), summary=task
    )
    return orchestrator.submit_change(room, r["change_id"])


def _checks(change):
    return {c["name"]: c for c in json.loads(change["evidence"])["tests"]["checks"]}


def test_every_check_records_command_exit_code_duration_and_log(api, room):
    ch = _change(room, "riya-agent", "Tidy the cart page", "ui_bug")
    checks = _checks(ch)

    assert {
        "build",
        "locked_tests",
        "hidden_tests",
        "lint",
        "contract",
        "secret_scan",
        "dependency_scan",
    } <= set(checks)
    for c in checks.values():
        assert {"command", "exit_code", "duration_ms", "status", "log_path"} <= set(c)
        assert Path(c["log_path"]).exists()
    assert checks["build"]["exit_code"] == 0 and checks["locked_tests"]["status"] == "passed"
    assert checks["contract"]["status"] == "skipped"  # no approved API contract in this room


def test_hidden_test_failure_fails_the_verdict_without_showing_source(api, room):
    ch = _change(room, "aman-agent", "Simplify the checkout total", "bug")
    checks = _checks(ch)

    assert ch["status"] == "tests_failed"
    assert checks["hidden_tests"]["exit_code"] != 0 and checks["hidden_tests"]["status"] == "failed"
    log = Path(checks["hidden_tests"]["log_path"]).read_text()
    assert "hidden tests passed" in log and "def test_" not in log and "client.post" not in log


def test_routing_reports_confidence_and_alternates(api, room):
    ch = _change(room, "aman-agent", "Simplify the checkout total", "bug")
    routed = json.loads(ch["evidence"])["routed"]

    assert routed["part"] == "backend" and 0 < routed["confidence"] < 1
    assert routed["triage"] is False and routed["assigned_to"] == routed["owner"]
    assert "frontend" in routed["alternates"]


def test_contract_check_fails_when_a_pinned_path_is_missing(api, room):
    ex(
        "INSERT INTO contracts(room_id,kind,name,content,version,status) "
        "VALUES(?,?,?,?,1,'approved')",
        (
            room,
            "api",
            "shop",
            json.dumps({"paths": {"/checkout": {"post": {}}, "/api/refunds": {"post": {}}}}),
        ),
    )
    ch = _change(room, "riya-agent", "Tidy the cart page", "ui_bug")
    c = _checks(ch)["contract"]

    assert c["status"] == "failed" and "POST /api/refunds" in Path(c["log_path"]).read_text()
    assert ch["status"] == "tests_failed"


def test_fast_profile_skips_the_referee_and_extra_checks(api, room):
    ex("UPDATE rooms SET verification_profile='fast' WHERE id=?", (room,))
    ch = _change(room, "riya-agent", "Tidy the cart page", "ui_bug")

    assert ch["status"] == "passed" and ch["verdict"] == "tests_only"
    assert set(_checks(ch)) == {"build", "locked_tests", "hidden_tests"}
    assert json.loads(ch["evidence"])["referee"]["verdict"] == "not_run"


def test_strict_profile_never_merges_an_inconclusive_change(api, room):
    ex("UPDATE rooms SET verification_profile='strict' WHERE id=?", (room,))
    ex(
        "INSERT INTO changes(room_id,agent,member_id,branch,summary,status) VALUES(?,?,?,?,?,?)",
        (room, "a", 1, "main", "s", "inconclusive"),
    )
    cid = q1("SELECT MAX(id) i FROM changes")["i"]
    with pytest.raises(ValueError):
        orchestrator.approve(room, [cid], "human", allow_inconclusive=True)


def test_stale_commit_cannot_be_merged_and_merges_are_tagged(api, room):
    ex("UPDATE rooms SET verification_profile='fast' WHERE id=?", (room,))
    ch = _change(room, "riya-agent", "Tidy the cart page", "ui_bug")
    o = gitops.original(room)
    # someone moves the branch after it was verified
    gitops.git(o, "checkout", "-q", ch["branch"])
    (o / "app/extra.py").write_text("x = 1\n")
    gitops.git(o, "add", "-A")
    gitops.git(o, "commit", "-q", "-m", "late edit")
    gitops.git(o, "checkout", "-q", "main")

    with pytest.raises(ValueError, match="stale"):
        orchestrator.approve(room, [ch["id"]], "riya")

    gitops.git(o, "branch", "-f", ch["branch"], ch["verified_sha"])
    res = orchestrator.approve(room, [ch["id"]], "riya")
    merge = q1("SELECT * FROM merges WHERE id=?", (res["merge_id"],))
    assert merge["release_tag"] == "release/1" and json.loads(merge["candidate_sha"]) == {
        str(ch["id"]): ch["verified_sha"]
    }
    assert merge["merged_sha"] == gitops.git(o, "rev-parse", "main").stdout.strip()


def test_secret_scan_finds_keys_without_logging_them(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "settings.py").write_text(
        'KEY = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAA"\n'
    )
    (tmp_path / "app" / "ok.py").write_text('password = "pw"\n')

    hits = security.find_secrets(tmp_path)

    assert hits == ["app/settings.py:1: Anthropic API key"]
    assert "AAAA" not in "".join(hits)


def test_profiles_only_change_checks_never_approval():
    assert set(verify.PROFILES) == {"fast", "standard", "strict"}
    assert (
        "secret_scan" not in verify.PROFILES["fast"]
        and "secret_scan" in verify.PROFILES["standard"]
    )


def test_mirror_container_command_has_no_network_or_keys(api, room, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leak")
    m = mirror.Mirror(room, tmp_path)
    a = m.docker_args(["python", "-m", "pytest"])

    assert a[a.index("--network") + 1] == "none" and "--cap-drop" in a and "--memory" in a
    assert not any("leak" in x or "ANTHROPIC" in x for x in a)
    assert a[-3:] == ["python", "-m", "pytest"]
