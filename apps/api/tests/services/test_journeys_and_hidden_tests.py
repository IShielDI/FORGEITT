"""Stages 21-22: journeys drafted from requirements and the hidden-test workflow."""

import json

import pytest

from app.llm.client import LLMClient
from app.llm.providers import MockChat
from app.services import hidden_tests, journeys, referee
from tests.integration.test_platform import ids
from tests.support.planning import approved_spec


def test_journey_draft_is_not_used_until_a_human_approves(api, room):
    spec_ids = approved_spec(room)
    reply = {
        "goal": "Open the home page, sign up with {email}, add a Notebook and check out.",
        "success_text": "Order placed",
        "db_check": "SELECT 1 FROM orders WHERE email = :email",
        "source_spec_ids": [spec_ids["login"], 99999],
    }

    d = journeys.draft(room, LLMClient(MockChat([json.dumps(reply)]), room))

    assert d["status"] == "draft" and d["source_spec_ids"] == [spec_ids["login"]]
    assert referee.load_journey(room) is None  # the referee never sees a draft
    saved = journeys.approve(room, {"success_text": "Order placed!"})
    assert referee.load_journey(room)["success_text"] == "Order placed!" == saved["success_text"]
    assert journeys.load_draft(room) is None


def test_journey_draft_with_an_unsafe_db_check_is_refused_on_approval(api, room):
    approved_spec(room)
    bad = {
        "goal": "Open the site and sign up with {email} please.",
        "db_check": "DELETE FROM orders",
    }
    journeys.draft(room, LLMClient(MockChat([json.dumps(bad)]), room))
    with pytest.raises(ValueError):
        journeys.approve(room)


def test_journey_needs_confirmed_requirements(api, room):
    with pytest.raises(ValueError):
        journeys.draft(room, LLMClient(MockChat(["{}"]), room))


def test_hidden_test_draft_needs_a_second_person(api, room):
    m = ids(api, room)
    hidden_tests.submit(
        room, m["aman"], "test_hidden_extra.py", "def test_total():\n    assert True\n"
    )

    assert not (hidden_tests.holdout_dir(room) / "test_hidden_extra.py").exists()  # not live yet
    with pytest.raises(hidden_tests.HiddenTestError):
        hidden_tests.approve(room, "test_hidden_extra.py", m["aman"])
    info = hidden_tests.approve(room, "test_hidden_extra.py", m["riya"])

    assert info == {
        "filename": "test_hidden_extra.py",
        "status": "approved",
        "author_id": m["aman"],
        "approved_by": m["riya"],
        "tests": ["test_total"],
    }
    assert (hidden_tests.holdout_dir(room) / "test_hidden_extra.py").exists()


def test_hidden_test_listing_never_contains_source(api, room):
    hidden_tests.submit(room, 1, "test_secret.py", "def test_a():\n    assert compute(2) == 42\n")
    text = json.dumps(hidden_tests.listing(room))
    assert "compute" not in text and "42" not in text and "test_a" in text


def test_retire_removes_a_hidden_test(api, room):
    m = ids(api, room)
    hidden_tests.submit(room, m["aman"], "test_old.py", "def test_x():\n    pass\n")
    hidden_tests.approve(room, "test_old.py", m["riya"])
    assert hidden_tests.retire(room, "test_old.py")["status"] == "retired"
    assert not (hidden_tests.holdout_dir(room) / "test_old.py").exists()


@pytest.mark.parametrize("name", ["../evil.py", "evil.py", "test_x.sh", "test_a b.py"])
def test_bad_file_names_are_refused(api, room, name):
    with pytest.raises(hidden_tests.HiddenTestError):
        hidden_tests.submit(room, 1, name, "x = 1\n")
