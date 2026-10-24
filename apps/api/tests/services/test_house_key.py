"""Stage 25: the optional capped house key."""

import pytest

from app.core import config
from app.services import ledger
from tests.integration.test_platform import ids


@pytest.fixture()
def house(monkeypatch):
    monkeypatch.setattr(config, "HOUSE_KEY_ENABLED", True)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-house-0000")
    monkeypatch.setattr(config, "HOUSE_CAP_WORKSPACE_USD", 1.0)
    monkeypatch.setattr(config, "HOUSE_CAP_PERSON_USD", 0.5)


def test_house_key_is_off_without_both_caps(api, room, house, monkeypatch):
    kriti = ids(api, room)["kriti"]  # contributed 0
    monkeypatch.setattr(config, "HOUSE_CAP_PERSON_USD", None)
    assert ledger.pick_key(room, kriti) is None


def test_house_key_is_the_last_resort_and_never_eats_a_members_portion(api, room, house):
    m = ids(api, room)
    ledger.add_key(m["riya"], "anthropic", "plain", "sk-ant-riya-1111")
    assert ledger.pick_key(room, m["riya"]) == (m["riya"], None)  # own portion first
    assert ledger.pick_key(room, m["kriti"]) == (
        "house",
        None,
    )  # nothing of their own: the house pays

    ledger.record_call(
        room,
        m["kriti"],
        "kriti-agent",
        "claude-sonnet-5-5",
        "c",
        0,
        20_000,
        0,
        0,
        None,
        source="house",
    )
    assert ledger.house_spent(room, m["kriti"]) == pytest.approx(0.2)
    assert (
        ledger.balance(room, m["kriti"])["spent"] == 0
    )  # house usage is not the member's own spend


def test_per_person_and_per_workspace_caps_stop_the_house_key(api, room, house):
    m = ids(api, room)
    ledger.record_call(
        room, m["kriti"], "a", "claude-sonnet-5-5", "c", 0, 50_000, 0, 0, None, source="house"
    )  # $0.50
    assert ledger.pick_key(room, m["kriti"]) is None  # person cap reached
    assert ledger.house_available(room, m["aman"]) is True
    ledger.record_call(
        room, m["aman"], "a", "claude-sonnet-5-5", "c", 0, 49_000, 0, 0, None, source="house"
    )
    assert ledger.house_available(room, m["aman"]) is False  # workspace cap ($1) reached
