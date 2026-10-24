"""LLM_PROVIDER=auto: the observer and planner use a model someone can actually use."""

import pytest

from app.core import config
from app.core.db import q1
from app.llm import client
from app.services import ledger


def _owner(room):
    return q1("SELECT id FROM members WHERE room_id=? AND is_owner=1", (room,))["id"]


def test_nothing_set_up_gives_a_plain_message(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {})
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    with pytest.raises(client.LLMError, match="Models tab"):
        client.auto_choice(room, None)


def test_a_demo_key_is_used_in_catalog_order(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"openrouter": "sk-or-x", "groq": "gsk_x"})
    provider, model = client.auto_choice(room, None)
    assert provider == "groq" and model == "openai/gpt-oss-120b"  # groq is listed before openrouter


def test_background_jobs_use_the_owners_own_key(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {})
    ledger.add_key(_owner(room), "gemini", "plain", "AIzaOwnerKey")
    assert client.auto_choice(room, None)[0] == "gemini"


def test_claude_is_the_fallback_and_get_client_builds_it(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {})
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-house")
    monkeypatch.setattr(config, "LLM_PROVIDER", "auto")
    client.use_provider(None)
    c = client.get_client(room, label="observer")
    assert c.provider.name == "claude" and c.provider.model == config.DEFAULT_MODEL
