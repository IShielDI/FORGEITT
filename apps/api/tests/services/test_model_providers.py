"""Which providers a member can use, their free keys, live model lists and zero-cost metering."""

import httpx
import pytest

from app.core import config
from app.core.db import q1
from app.services import agent_runner, ledger, model_providers


def _member(room, name="riya"):
    return q1("SELECT id FROM members WHERE room_id=? AND name=?", (room, name))["id"]


def _by_id(rows):
    return {r["id"]: r for r in rows}


def test_without_keys_only_a_running_ollama_is_ready(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {})
    monkeypatch.setattr(model_providers, "ollama_up", lambda: False)
    assert not any(r["ready"] for r in model_providers.overview(_member(room)))

    monkeypatch.setattr(model_providers, "ollama_up", lambda: True)
    rows = _by_id(model_providers.overview(_member(room)))

    assert rows["anthropic"]["free"] is False and not rows["anthropic"]["ready"]
    assert rows["ollama"]["source"] == "local"
    assert not rows["groq"]["ready"] and rows["groq"]["models"][0].startswith("groq:")


def test_a_demo_key_makes_a_provider_ready_for_everyone(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"gemini": "AIzaDemo"})
    rows = _by_id(model_providers.overview(_member(room, "aman")))

    assert rows["gemini"]["source"] == "demo" and rows["gemini"]["key_last4"] is None


def test_own_key_wins_over_the_demo_key_and_is_stored_encrypted(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"groq": "gsk_demo_key"})
    mid = _member(room)
    assert model_providers.save_key(mid, "groq", "  gsk_mine_123456  ") == "3456"

    row = q1(
        "SELECT secret_enc FROM keys WHERE member_id=? AND provider='groq' AND status='active'",
        (mid,),
    )
    assert "gsk_mine" not in str(row["secret_enc"])
    assert ledger.free_key(mid, "groq") == "gsk_mine_123456"
    assert _by_id(model_providers.overview(mid))["groq"]["source"] == "yours"

    model_providers.remove_key(mid, "groq")
    assert ledger.free_key(mid, "groq") == "gsk_demo_key"


def test_wrong_keys_are_refused(api, room):
    with pytest.raises(model_providers.ProviderKeyError):
        model_providers.save_key(_member(room), "openrouter", "gsk_not_openrouter")


def test_live_models_keeps_only_free_openrouter_models(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"openrouter": "sk-or-demo"})
    listing = {"data": [{"id": "a/b:free"}, {"id": "a/paid"}, {"id": "c/d:free"}]}
    http = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=listing))
    )

    assert model_providers.live_models(_member(room), "openrouter", http=http) == [
        "openrouter:a/b:free",
        "openrouter:c/d:free",
    ]


def test_live_models_strips_gemini_prefix_and_reports_refusals(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"gemini": "AIzaDemo"})
    ok = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"data": [{"id": "models/gemini-x"}]})
        )
    )
    assert model_providers.live_models(_member(room), "gemini", http=ok) == ["gemini:gemini-x"]

    denied = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(401, json={})))
    with pytest.raises(model_providers.ProviderKeyError, match="401"):
        model_providers.live_models(_member(room), "gemini", http=denied)


def test_runner_needs_a_key_for_free_providers_except_local_ollama(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {})
    mid = _member(room, "kriti")

    assert agent_runner.free_provider("groq:llama-3.3-70b-versatile", mid) is None
    assert "Groq" in agent_runner.no_key_message("groq:x")
    local = agent_runner.free_provider("ollama:qwen2.5-coder:7b", mid)
    assert local is not None and local.model == "qwen2.5-coder:7b" and local.api_key == ""

    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"groq": "gsk_demo"})
    p = agent_runner.free_provider("groq:llama-3.3-70b-versatile", mid)
    assert p is not None and p.base_url == "https://api.groq.com/openai/v1"


def test_free_calls_cost_nothing_and_cross_no_checkpoint(api, room):
    mid = _member(room, "kriti")  # contributed $0: any paid call would be at 100%
    res = ledger.record_call(room, mid, "kriti-agent", "groq:m", "c1", 5000, 900, 0, 0, None)

    assert res["cost"] == 0 and res["checkpoint"] is None
    assert q1("SELECT tin FROM ledger WHERE call_id='c1'")["tin"] == 5000
