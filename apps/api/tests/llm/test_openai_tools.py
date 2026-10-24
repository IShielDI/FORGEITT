"""The OpenAI-compatible tool adapter the coding agents use on free providers."""

import json

import httpx
import pytest

from app.llm.providers import (
    OpenAIToolProvider,
    ProviderError,
    from_openai_message,
    to_openai_messages,
)

HISTORY = [
    {"role": "user", "content": "TASK: add a test"},
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Looking."},
            {"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls"}},
        ],
    },
    {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "app\n", "is_error": False},
        ],
    },
]


def test_history_is_translated_to_openai_messages():
    out = to_openai_messages("be careful", HISTORY)

    assert out[0] == {"role": "system", "content": "be careful"}
    assert out[1] == {"role": "user", "content": "TASK: add a test"}
    call = out[2]["tool_calls"][0]
    assert out[2]["content"] == "Looking."
    assert call["id"] == "t1" and call["function"]["name"] == "bash"
    assert json.loads(call["function"]["arguments"]) == {"command": "ls"}
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "content": "app\n"}


def test_failed_tool_results_are_marked():
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "x", "content": "boom", "is_error": True}
            ],
        }
    ]
    assert to_openai_messages(None, msgs)[0]["content"] == "ERROR: boom"


def test_reply_becomes_runner_blocks_and_bad_arguments_do_not_crash():
    blocks = from_openai_message(
        {
            "content": "done",
            "tool_calls": [
                {"id": "c1", "function": {"name": "bash", "arguments": '{"command": "pytest"}'}},
                {"function": {"name": "bash", "arguments": "{not json"}},
            ],
        }
    )
    assert blocks[0] == {"type": "text", "text": "done"}
    assert blocks[1]["input"] == {"command": "pytest"} and blocks[1]["id"] == "c1"
    assert blocks[2]["input"] == {} and blocks[2]["id"].startswith("call_")


def _provider(handler):
    return OpenAIToolProvider(
        "https://free.example/v1",
        "gsk_secret",
        "m",
        "groq",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_complete_sends_tools_and_reads_usage():
    seen = {}

    def handler(req):
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        msg = {
            "content": None,
            "tool_calls": [{"id": "a", "function": {"name": "bash", "arguments": "{}"}}],
        }
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "choices": [{"message": msg, "finish_reason": "tool_calls"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    reply = _provider(handler).complete("sys", HISTORY, 256)

    assert seen["auth"] == "Bearer gsk_secret"
    assert {t["function"]["name"] for t in seen["body"]["tools"]} >= {
        "bash",
        "str_replace_based_edit_tool",
    }
    assert reply.content[0]["type"] == "tool_use"
    assert (reply.usage.input, reply.usage.output, reply.call_id) == (12, 3, "r1")


def test_rate_limits_are_retryable_and_errors_never_echo_the_key():
    def handler(req):
        return httpx.Response(429, json={"error": {"message": "slow down"}})

    with pytest.raises(ProviderError) as e:
        _provider(handler).complete("sys", HISTORY, 256)
    assert e.value.retryable and "slow down" in str(e.value)
    assert "gsk_secret" not in str(e.value)


def test_bad_request_is_not_retryable():
    with pytest.raises(ProviderError) as e:
        _provider(lambda req: httpx.Response(400, json={"error": "bad model"})).complete(
            "s", HISTORY, 9
        )
    assert not e.value.retryable


def test_gemini_thought_signatures_survive_the_round_trip():
    sig = {"google": {"thought_signature": "abc123"}}
    blocks = from_openai_message(
        {
            "tool_calls": [
                {"id": "c1", "function": {"name": "bash", "arguments": "{}"}, "extra_content": sig}
            ]
        }
    )
    assert blocks[0]["extra_content"] == sig

    out = to_openai_messages(None, [{"role": "assistant", "content": blocks}])
    assert out[0]["tool_calls"][0]["extra_content"] == sig


def test_gemini_list_shaped_errors_are_read():
    def handler(req):
        return httpx.Response(
            400, json=[{"error": {"code": 400, "message": "missing thought_signature"}}]
        )

    with pytest.raises(ProviderError, match="missing thought_signature"):
        _provider(handler).complete("s", HISTORY, 9)


def test_claude_never_receives_other_providers_fields():
    from app.llm.providers import _anthropic_only

    msgs = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "a",
                    "name": "bash",
                    "input": {},
                    "extra_content": {"x": 1},
                }
            ],
        }
    ]
    assert "extra_content" not in _anthropic_only(msgs)[0]["content"][0]
    assert "extra_content" in msgs[0]["content"][0]  # the stored history is left as it was


def test_a_rate_limited_model_falls_back_to_the_next_one_and_stays_there():
    tried = []

    def handler(req):
        model = json.loads(req.content)["model"]
        tried.append(model)
        if model == "busy":
            return httpx.Response(429, json=[{"error": {"message": "quota"}}])
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}], "usage": {}})

    p = OpenAIToolProvider(
        "https://free.example/v1",
        "k",
        "busy",
        "gemini",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        fallbacks=["busy", "spare"],
    )
    p.complete("s", HISTORY, 9)
    p.complete("s", HISTORY, 9)

    assert tried == ["busy", "spare", "spare"] and p.model == "spare"


def test_when_every_model_is_busy_the_error_is_retryable():
    p = OpenAIToolProvider(
        "https://free.example/v1",
        "k",
        "a",
        "gemini",
        http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503, json={}))),
        fallbacks=["b"],
    )
    with pytest.raises(ProviderError) as e:
        p.complete("s", HISTORY, 9)
    assert e.value.retryable
