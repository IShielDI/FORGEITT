"""Stage 6: LLMClient with the mock, structured output retry, adapters over mocked HTTP, credits."""

import json

import httpx
import pytest
from pydantic import BaseModel

from app.core import config
from app.core.db import ex, q, q1
from app.llm import client as llm
from app.llm import prompts
from app.llm.providers import MockChat, OllamaChat, OpenAICompatChat
from app.services import credits
from tests.integration.test_platform import ids


class Item(BaseModel):
    kind: str
    text: str


def test_plain_completion_with_mock_writes_ledger_row(api, room):
    riya = ids(api, room)["riya"]
    c = llm.LLMClient(MockChat(["hello"]), room, riya, "observer")

    res = c.complete([{"role": "user", "content": "hi"}])

    assert res.text == "hello" and res.provider == "mock"
    row = q1("SELECT * FROM ledger WHERE room_id=? AND agent='observer'", (room,))
    assert row["member_id"] == riya and row["model"] == "mock" and row["cost"] == 0


def test_structured_output_valid_first_time(api, room):
    c = llm.LLMClient(MockChat(['Sure: {"kind": "decision", "text": "Use SQLite"}']), room)

    res = c.complete([{"role": "user", "content": "x"}], schema=Item)

    assert res.data == Item(kind="decision", text="Use SQLite")
    assert len(res.usage) == 1


def test_one_retry_on_invalid_json(api, room):
    mock = MockChat(["not json", '{"kind": "requirement", "text": "Login"}'])
    res = llm.LLMClient(mock, room).complete([{"role": "user", "content": "x"}], schema=Item)

    assert res.data.kind == "requirement" and len(mock.calls) == 2
    assert "not valid" in mock.calls[1]["messages"][-1]["content"]


def test_invalid_twice_raises(api, room):
    mock = MockChat(["nope", '{"kind": 1}'])
    with pytest.raises(llm.StructuredOutputError):
        llm.LLMClient(mock, room).complete([{"role": "user", "content": "x"}], schema=Item)
    assert len(mock.calls) == 2  # exactly one retry


def test_hard_stop_when_budget_is_used_up(api, room, monkeypatch):
    kriti = ids(api, room)["kriti"]  # contributed 0
    paid = MockChat(["x"])
    paid.name = "claude"  # behave like a paid provider for the budget check
    paid.model = "claude-sonnet-5-5"

    with pytest.raises(credits.BudgetExceededError):
        llm.LLMClient(paid, room, kriti).complete([{"role": "user", "content": "x"}])
    assert paid.calls == []  # stopped before any call


def test_checkpoints_are_announced(api, room):
    aman = ids(api, room)["aman"]  # $1 budget
    for _ in range(19):  # $0.05 per call: each checkpoint is crossed by its own call
        credits.charge(room, aman, "planner", "claude", "claude-sonnet-5-5", 0, 5_000, "c")

    thresholds = [
        r["threshold"]
        for r in q(
            "SELECT threshold FROM checkpoints WHERE room_id=? AND member_id=?", (room, aman)
        )
    ]
    assert {70, 80, 90} <= set(thresholds)
    announced = q("SELECT data FROM events WHERE room_id=? AND kind='budget'", (room,))
    assert len(announced) == 3


def test_provider_is_chosen_by_setting_and_workspace_allow_list(api, room, monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    assert llm.get_client(room).provider.name == "mock"

    ex("UPDATE rooms SET allowed_providers=? WHERE id=?", (json.dumps(["claude"]), room))
    with pytest.raises(llm.LLMError):
        llm.get_client(room)


def test_providers_endpoint(api, room):
    assert api.put(f"/api/rooms/{room}/providers", json={"allowed": ["gpt"]}).status_code == 400
    assert api.put(f"/api/rooms/{room}/providers", json={"allowed": ["mock", "claude"]}).json() == {
        "allowed": ["claude", "mock"]
    }
    assert api.get(f"/api/rooms/{room}/providers").json()["allowed"] == ["claude", "mock"]


def test_openai_compatible_adapter_over_mocked_http():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = (
            str(request.url),
            request.headers["authorization"],
            json.loads(request.content),
        )
        return httpx.Response(
            200,
            json={
                "id": "c1",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            },
        )

    p = OpenAICompatChat(
        "https://api.example/v1",
        "k-123",
        "deepseek-chat",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    text, usage, call_id = p.chat("be brief", [{"role": "user", "content": "hi"}], 50)

    assert (text, usage.input, usage.output, call_id) == ("ok", 7, 2, "c1")
    assert (
        seen["url"] == "https://api.example/v1/chat/completions" and seen["auth"] == "Bearer k-123"
    )
    assert seen["body"]["messages"][0] == {"role": "system", "content": "be brief"}


def test_ollama_adapter_over_mocked_http():
    def handler(request):
        return httpx.Response(
            200, json={"message": {"content": "local"}, "prompt_eval_count": 3, "eval_count": 1}
        )

    p = OllamaChat(
        "http://localhost:11434",
        "llama3",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert p.chat(None, [{"role": "user", "content": "x"}], 10)[0] == "local"


def test_http_errors_become_llm_errors(api, room):
    def handler(request):
        return httpx.Response(500, json={})

    p = OpenAICompatChat(
        "https://api.example/v1",
        "k",
        "m",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(llm.LLMError):
        llm.LLMClient(p).complete([{"role": "user", "content": "x"}])


def test_prompt_registry_reads_versioned_files():
    p = prompts.load("observer")
    assert p.version and p.text and p.tag.startswith("observer@v")
    with pytest.raises(KeyError):
        prompts.load("nope")
