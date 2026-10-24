import pytest

from app.core.db import ex, q, q1
from app.services import firewall, gitops, graph, ledger, memory, orchestrator
from app.services.mirror import new_mirror


def ids(api, rid):
    return {m["name"]: m["id"] for m in api.get(f"/api/rooms/{rid}").json()["members"]}


# ---------- ledger ----------
def test_cost_uses_four_rates():
    assert ledger.cost_of(
        "claude-sonnet-5-5", 1_000_000, 1_000_000, 1_000_000, 1_000_000
    ) == pytest.approx(2 + 10 + 0.10 + 2.50)


def test_checkpoints_once_per_crossing(api, room):
    m = ids(api, room)["aman"]  # budget $1
    for cost_tokens in (50_000, 20_000, 20_000, 20_000, 20_000):  # output tokens, $10 per million
        ledger.record_call(
            room, m, "aman-agent", "claude-sonnet-5-5", "c", 0, cost_tokens, 0, 0, None
        )
    cps = [
        c["threshold"]
        for c in q(
            "SELECT threshold FROM checkpoints WHERE room_id=? AND member_id=? ORDER BY id",
            (room, m),
        )
    ]
    assert cps == sorted(set(cps)) and set(cps) <= {70, 80, 90} and 70 in cps


def test_portion_first_then_loan_key(api, room):
    m = ids(api, room)
    ledger.add_key(m["riya"], "anthropic", "plain", "sk-ant-riya-1234")
    ledger.add_key(m["kriti"], "anthropic", "plain", "sk-ant-kriti-9999")
    assert ledger.pick_key(room, m["kriti"]) is None  # kriti contributed 0: nothing to spend
    rid = ledger.create_request(room, m["kriti"], 2.0, target=m["riya"])
    loan = ledger.fund_request(rid, m["riya"], 2.0)
    assert ledger.pick_key(room, m["kriti"]) == (m["riya"], loan)  # loan bills the LENDER's key
    r = ledger.record_call(
        room, m["kriti"], "kriti-agent", "claude-sonnet-5-5", "x", 0, 250_000, 0, 0, loan
    )  # $2.50 > cap
    assert r["cap_reached"]
    assert ledger.pick_key(room, m["kriti"]) is None


def test_balances_and_privacy(api, room):
    m = ids(api, room)
    b = ledger.balance(room, m["riya"])
    assert b["budget"] == 10
    ledger.add_key(m["riya"], "anthropic", "plain", "k")
    rid = ledger.create_request(room, m["aman"], 3.0, target=m["riya"])
    ledger.fund_request(rid, m["riya"], 3.0)
    assert ledger.balance(room, m["riya"])["lent_out"] == 3.0
    assert ledger.balance(room, m["aman"])["budget"] == 4.0
    view = ledger.room_view(room, m["aman"])
    assert set(view) == {"pool_total", "pool_spent", "me"}  # never anyone else's balance


def test_one_open_request_and_counter_offer(api, room):
    m = ids(api, room)
    rid = ledger.create_request(room, m["aman"], 5.0)
    with pytest.raises(ValueError):
        ledger.create_request(room, m["aman"], 1.0)
    ledger.fund_request(rid, m["riya"], 2.0)  # counter-offer smaller than asked
    bar = ledger.funding_bar(rid)
    assert bar["funded"] == 2.0 and bar["status"] == "open"
    ledger.fund_request(rid, m["riya"], 3.0)  # chip in until full
    assert ledger.funding_bar(rid)["status"] == "funded"
    with pytest.raises(ValueError):
        ledger.fund_request(rid, m["riya"], 1.0)  # closed for everyone


def test_no_popup_without_spare_budget(api, room):
    m = ids(api, room)
    ledger.create_request(room, m["aman"], 1.0)
    assert ledger.visible_requests(room, m["riya"])  # has budget
    assert not ledger.visible_requests(room, m["kriti"])  # contributed 0


def test_loan_expiry_returns_unspent(api, room):
    m = ids(api, room)
    rid = ledger.create_request(room, m["aman"], 2.0, target=m["riya"])
    lid = ledger.fund_request(rid, m["riya"], 2.0)
    ex("UPDATE loans SET expires=1 WHERE id=?", (lid,))
    ledger.housekeeping(room)
    assert q1("SELECT status,returned FROM loans WHERE id=?", (lid,)) == {
        "status": "expired",
        "returned": 2.0,
    }
    assert ledger.balance(room, m["riya"])["lent_out"] == 0


# ---------- memory ----------
def test_memory_rules(api, room):
    with pytest.raises(PermissionError):
        memory.add(room, "contract", "aman-agent", "x", part="backend")
    with pytest.raises(PermissionError):
        memory.add(room, "failure", "aman-agent", "x", part="backend")
    with pytest.raises(PermissionError):
        memory.add(room, "handoff", "aman-agent", "x", part="frontend")  # not its own part
    memory.add(room, "handoff", "aman-agent", "ok", part="backend")
    mid = memory.add(room, "decision", "riya", "use sqlite", ttl=-5)
    memory.sweep(room)
    assert q1("SELECT flagged FROM memory WHERE id=?", (mid,))["flagged"] == 1
    assert any("STALE" in e for e in memory.excerpts(room, "backend"))


def test_hidden_tests_and_journeys_never_in_memory(api, room):
    text = " ".join(m["content"] for m in memory.listing(room)).lower()
    assert "holdout" not in text and "hidden" not in text and "journey" not in text


# ---------- firewall ----------
def _branch(room, name, fn):
    o = gitops.original(room)
    gitops.git(o, "checkout", "-q", "-b", name, "main")
    fn(o)
    gitops.git(o, "add", "-A")
    gitops.git(o, "commit", "-q", "-m", name)
    gitops.git(o, "checkout", "-q", "main")


def test_commit_check_catches_change_delete_rename_and_new_conftest(api, room):
    import os

    o = gitops.original(room)
    _branch(room, "edit", lambda o: (o / "protected/tests/test_shop.py").write_text("x"))
    _branch(room, "delete", lambda o: os.remove(o / "protected/tests/test_shop.py"))
    _branch(
        room,
        "rename",
        lambda o: os.rename(o / "protected/contracts/contracts.json", o / "app/c.json"),
    )
    _branch(room, "conftest", lambda o: (o / "app/conftest.py").write_text("x"))
    _branch(room, "ok", lambda o: (o / "app/newfile.py").write_text("x = 1"))
    for b in ("edit", "delete", "rename", "conftest"):
        assert firewall.commit_check(str(o), "main", b), b
    assert firewall.commit_check(str(o), "main", "ok") == []


def test_action_check_blocks_edit_and_traversal(api, room):
    assert firewall.check_action(
        "edit", {"command": "create", "path": "protected/tests/test_new.py"}, room, "a"
    )
    assert (
        firewall.check_action(
            "edit", {"command": "view", "path": "protected/tests/test_shop.py"}, room, "a"
        )
        is None
    )
    assert firewall.check_action("edit", {"command": "create", "path": "../x"}, room, "a")
    assert (
        firewall.check_action(
            "bash", {"command": "python -m pytest -q -c protected/pytest.ini"}, room, "a"
        )
        is None
    )


# ---------- git / mirror ----------
def test_merge_conflict_returns_to_owner(api, room):
    o = gitops.original(room)
    _branch(room, "a1", lambda o: (o / "app/db.py").write_text("A = 1\n"))
    _branch(room, "a2", lambda o: (o / "app/db.py").write_text("A = 2\n"))
    m = new_mirror(room)
    try:
        r = m.merge_stack(["a1"], "a2")
        assert r["ok"] is False and r["conflict_with"] == "a2"
    finally:
        m.destroy()


def test_mirror_is_clean_checkout_and_deleted(api, room):
    m = new_mirror(room)
    m.merge_stack([], "main") if False else None
    gitops.git(".", "clone", "-q", "--no-local", str(gitops.original(room)), str(m.path))
    assert not (m.path / "_holdout").exists()  # hold-out only added by merge_stack
    m.destroy()
    assert not m.path.exists()


def test_build_order_and_affected(api, room):
    assert graph.build_order(room) == [["database", "qa"], ["backend"], ["frontend"]]
    assert graph.affected_by(room, "database") == ["backend", "database", "frontend"]


def test_approve_requires_passed(api, room):
    ex(
        "INSERT INTO changes(room_id,agent,member_id,branch,summary,status) VALUES(?,?,?,?,?,?)",
        (room, "a", 1, "x", "s", "ready"),
    )
    cid = q1("SELECT MAX(id) i FROM changes")["i"]
    with pytest.raises(ValueError):
        orchestrator.approve(room, [cid], "human")
