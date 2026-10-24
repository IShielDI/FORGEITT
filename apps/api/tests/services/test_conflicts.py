"""Spec conflicts: "add the add-to-cart button" then "remove it" becomes one decision for people
to settle. If everyone who argued agrees it is applied; otherwise the owner makes the final call."""

import json

import pytest

from app.core.db import ex, now, q1
from app.llm.client import LLMClient
from app.llm.providers import MockChat
from app.services import chat, conflicts, observer, spec
from tests.integration.test_platform import ids


def _item(text, sources):
    return {"kind": "requirement", "text": text, "source_message_ids": sources, "confidence": 0.9}


def _add_then_remove(api, room, remover="aman"):
    """riya asks to add the button, then someone else asks to remove it, in one observer batch."""
    m = ids(api, room)
    add = chat.post(room, m["riya"], "Build an add to cart button")["id"]
    rem = chat.post(room, m[remover], "Actually remove the add to cart button")["id"]
    reply = json.dumps(
        {
            "items": [
                _item("Add an add to cart button", [add]),
                {**_item("Remove the add to cart button", [rem]), "replaces_item": 0},
            ]
        }
    )
    a, b = observer.observe(room, LLMClient(MockChat([reply]), room))
    cid = q1("SELECT id FROM spec_conflicts WHERE item_a=? AND item_b=?", (a, b))["id"]
    return a, b, cid, m


def test_a_reversal_in_one_batch_opens_a_conflict_not_two_loose_items(api, room):
    a, b, cid, _ = _add_then_remove(api, room)
    c = conflicts.listing(room)[0]

    assert c["id"] == cid and c["status"] == "open"
    assert c["earlier"]["id"] == a and c["latest"]["id"] == b
    assert c["involved"] == ["aman", "riya"]


def test_items_in_an_open_conflict_cannot_be_confirmed_one_by_one(api, room):
    a, b, _, _ = _add_then_remove(api, room)
    with pytest.raises(spec.SpecError, match="settle the conflict"):
        spec.confirm(a, None)
    with pytest.raises(spec.SpecError, match="settle the conflict"):
        spec.reject(b, None)


def test_when_everyone_who_argued_agrees_it_is_applied(api, room):
    a, b, cid, m = _add_then_remove(api, room)

    first = conflicts.vote(cid, m["riya"], b)
    assert first["status"] == "open"  # aman has not picked yet

    done = conflicts.vote(cid, m["aman"], b)
    assert done["status"] == "resolved" and done["decided_how"] == "agreement"
    assert spec.get(b)["status"] == "confirmed" and spec.get(a)["status"] == "rejected"


def test_a_split_waits_for_the_owner_who_makes_the_final_call(api, room):
    a, b, cid, m = _add_then_remove(api, room)
    conflicts.vote(cid, m["riya"], a)
    split = conflicts.vote(cid, m["aman"], b)
    assert split["status"] == "open"
    assert split["earlier"]["picked_by"] == ["riya"] and split["latest"]["picked_by"] == ["aman"]

    final = conflicts.decide(cid, m["riya"], b)
    assert final["decided_how"] == "owner" and spec.get(b)["status"] == "confirmed"
    with pytest.raises(conflicts.ConflictError):
        conflicts.vote(cid, m["aman"], a)


def test_reversing_a_confirmed_item_supersedes_it_and_flags_the_plan(api, room):
    m = ids(api, room)
    add = chat.post(room, m["riya"], "Build an add to cart button")["id"]
    first = observer.observe(
        room,
        LLMClient(
            MockChat([json.dumps({"items": [_item("Add an add to cart button", [add])]})]), room
        ),
    )[0]
    spec.confirm(first, m["riya"])
    ex(
        "INSERT INTO tasks(room_id,key,title,status,spec_item_ids,created) VALUES(?,?,?,?,?,?)",
        (room, "cart-btn", "Add to cart button", "approved", json.dumps([first]), now()),
    )
    rem = chat.post(room, m["riya"], "Remove the add to cart button")["id"]
    reply = json.dumps(
        {"items": [{**_item("Remove the add to cart button", [rem]), "replaces_id": first}]}
    )
    (second,) = observer.observe(room, LLMClient(MockChat([reply]), room))
    cid = conflicts.listing(room)[0]["id"]

    conflicts.vote(cid, m["riya"], second)  # riya wrote both messages, so her pick settles it

    assert spec.get(first)["status"] == "superseded" and spec.get(second)["status"] == "confirmed"
    assert conflicts.plan_stale(room) == ["cart-btn"]


def test_unrelated_replaces_ids_are_ignored(api, room):
    m = ids(api, room)
    mid = chat.post(room, m["riya"], "Use SQLite")["id"]
    reply = json.dumps({"items": [{**_item("Use SQLite", [mid]), "replaces_id": 999999}]})
    observer.observe(room, LLMClient(MockChat([reply]), room))
    assert conflicts.listing(room) == []


def test_a_stale_task_can_be_dropped_and_no_longer_blocks_a_new_plan(api, room):
    from app.services import planner

    tid = ex(
        "INSERT INTO tasks(room_id,key,title,status,spec_item_ids,created) VALUES(?,?,?,?,?,?)",
        (room, "old", "Old task", "approved", "[]", now()),
    )
    assert planner.drop(tid)["status"] == "dropped"
    with pytest.raises(planner.PlanError):
        planner.drop(tid)  # already out of the plan
    assert not q1(
        "SELECT 1 x FROM tasks WHERE room_id=? AND status NOT IN ('proposed','dropped')", (room,)
    )


def test_the_owner_can_say_both_can_stand(api, room):
    a, b, cid, m = _add_then_remove(api, room)
    done = conflicts.decide(cid, m["riya"], conflicts.BOTH)

    assert done["status"] == "resolved" and done["decided_how"] == "both"
    assert spec.get(a)["status"] == "proposed" and spec.get(b)["status"] == "proposed"
    spec.confirm(a, m["riya"])  # each one can now be confirmed on its own


def test_a_missed_reversal_is_caught_and_confirmed_by_a_focused_check(api, room):
    m = ids(api, room)
    add = chat.post(room, m["riya"], "Build an add to cart button")["id"]
    rem = chat.post(room, m["aman"], "Remove the add to cart button")["id"]
    observer_reply = json.dumps(
        {
            "items": [
                _item("Build an add to cart button", [add]),
                _item("Remove the add to cart button", [rem]),
            ]
        }
    )  # the model forgot replaces_item
    check_reply = json.dumps({"reverses": True})
    observer.observe(room, LLMClient(MockChat([observer_reply, check_reply]), room))

    assert len(conflicts.listing(room)) == 1


def test_two_real_features_are_not_forced_into_a_conflict(api, room):
    m = ids(api, room)
    x = chat.post(room, m["riya"], "Users can add items to the cart")["id"]
    y = chat.post(room, m["aman"], "Users can remove items from the cart")["id"]
    reply = json.dumps(
        {
            "items": [
                _item("Users can add items to the cart", [x]),
                _item("Users can remove items from the cart", [y]),
            ]
        }
    )
    observer.observe(room, LLMClient(MockChat([reply, json.dumps({"reverses": False})]), room))

    assert conflicts.listing(room) == []
