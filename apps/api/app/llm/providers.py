"""One model interface. Claude is the first provider; free OpenAI-compatible providers (app/llm/catalog.py)
share one adapter. Tests use their own stand-in under tests/support."""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

TOOLS = [
    {"type": "bash_20250124", "name": "bash"},
    {"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"},
    {
        "name": "file_contract_change_request",
        "description": "Ask the owner to change a protected test or contract. Use this instead of editing protected files when a test or contract looks wrong.",
        "input_schema": {
            "type": "object",
            "properties": {"proposal": {"type": "string"}},
            "required": ["proposal"],
        },
    },
]


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0


@dataclass
class Reply:
    content: list  # blocks as plain dicts: {type:text,text} | {type:tool_use,id,name,input}
    usage: Usage = field(default_factory=Usage)
    call_id: str = ""
    stop_reason: str = ""


class ProviderError(Exception):
    def __init__(self, msg, retryable=False):
        super().__init__(msg)
        self.retryable = retryable


def _anthropic_only(messages: list[dict]) -> list[dict]:
    """Drop fields other providers add to tool calls (e.g. Gemini's signature) if a run switches
    to Claude midway, e.g. onto a Claude backup model; Anthropic rejects unknown block fields."""
    out = []
    for m in messages:
        if isinstance(m["content"], list):
            blocks = [{k: v for k, v in b.items() if k != "extra_content"} for b in m["content"]]
            m = {**m, "content": blocks}
        out.append(m)
    return out


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key, model):
        import anthropic

        self.client, self.model = anthropic.Anthropic(api_key=api_key), model

    def complete(self, system, messages, max_tokens):
        import anthropic

        try:
            r = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=_anthropic_only(messages),
                tools=TOOLS,
            )
        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        ) as e:
            raise ProviderError(str(e), retryable=True)  # includes 429 and overloaded (529)
        except anthropic.APIStatusError as e:
            raise ProviderError(
                f"{e.status_code}: {e.message}",
                retryable=e.status_code in (429, 500, 502, 503, 529),
            )
        u = r.usage
        blocks = [b.model_dump(exclude_none=True) for b in r.content]
        return Reply(
            blocks,
            Usage(
                u.input_tokens,
                u.output_tokens,
                getattr(u, "cache_read_input_tokens", 0) or 0,
                getattr(u, "cache_creation_input_tokens", 0) or 0,
            ),
            r.id,
            r.stop_reason,
        )


# The same tools in OpenAI function-calling form, for the free providers.
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in your workspace (no network). Returns stdout and stderr.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace_based_edit_tool",
            "description": (
                "View, create or edit files in your workspace. view: show a file (or list a folder); "
                "create: write file_text to path; str_replace: replace old_str (must match exactly once) "
                "with new_str; insert: put insert_text after line insert_line."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["view", "create", "str_replace", "insert"],
                    },
                    "path": {"type": "string"},
                    "file_text": {"type": "string"},
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"},
                    "insert_line": {"type": "integer"},
                    "insert_text": {"type": "string"},
                    "view_range": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["command", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TOOLS[2]["name"],
            "description": TOOLS[2]["description"],
            "parameters": TOOLS[2]["input_schema"],
        },
    },
]


def to_openai_messages(system: str | None, messages: list[dict]) -> list[dict]:
    """The runner keeps its history in Anthropic block form; translate it for an OpenAI-style API."""
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
            continue
        if m["role"] == "assistant":
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {})},
                    **({"extra_content": b["extra_content"]} if b.get("extra_content") else {}),
                }
                for b in content
                if b.get("type") == "tool_use"
            ]
            msg: dict = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
            continue
        for b in content:  # user turn: tool results (and any plain text)
            if b.get("type") == "tool_result":
                body = str(b.get("content", ""))
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": b["tool_use_id"],
                        "content": ("ERROR: " + body) if b.get("is_error") else body,
                    }
                )
            elif b.get("type") == "text":
                out.append({"role": "user", "content": b.get("text", "")})
    return out


def from_openai_message(msg: dict) -> list[dict]:
    """An OpenAI assistant message as Anthropic-style blocks (what the runner understands)."""
    blocks: list[dict] = []
    if msg.get("content"):
        blocks.append({"type": "text", "text": msg["content"]})
    for c in msg.get("tool_calls") or []:
        fn = c.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        block = {
            "type": "tool_use",
            "id": c.get("id") or f"call_{uuid.uuid4().hex[:12]}",
            "name": fn.get("name", ""),
            "input": args if isinstance(args, dict) else {},
        }
        if c.get("extra_content"):  # Gemini 3's thought signature: must be sent back next turn
            block["extra_content"] = c["extra_content"]
        blocks.append(block)
    return blocks


FALLBACK_STATUSES = (429, 503)  # quota used up or model overloaded: another model may still work


def post_with_fallback(
    http: Any, url: str, headers: dict, body: dict, models: list[str]
) -> tuple[Any, str]:
    """POST, moving to the next model when one is rate-limited or overloaded (free tiers have a
    separate quota per model). Returns the last response and the model that produced it."""
    r = None
    for model in models:
        r = http.post(url, headers=headers, json={**body, "model": model})
        if r.status_code not in FALLBACK_STATUSES:
            return r, model
    return r, models[-1]


class OpenAIToolProvider:
    """Coding-agent calls (with tools) to any OpenAI-compatible API: the free providers and Ollama."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        name: str,
        http: Any = None,
        fallbacks: list[str] | None = None,
    ):
        import httpx

        self.base_url, self.api_key, self.model, self.name = (
            base_url.rstrip("/"),
            api_key,
            model,
            name,
        )
        self.fallbacks = [m for m in (fallbacks or []) if m != model]
        self.http = http or httpx.Client(timeout=180)

    def complete(self, system, messages, max_tokens):
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {
            "messages": to_openai_messages(system, messages),
            "tools": OPENAI_TOOLS,
            "max_tokens": max_tokens,
        }
        try:
            r, used = post_with_fallback(
                self.http,
                f"{self.base_url}/chat/completions",
                headers,
                body,
                [self.model, *self.fallbacks],
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name}: {type(e).__name__}", retryable=True)
        self.model = used  # stay on the model that answered for the rest of the run
        if r.status_code >= 400:
            raise ProviderError(
                f"{self.name} HTTP {r.status_code}: {_error_detail(r)}",
                retryable=r.status_code in (408, 429, 500, 502, 503, 504),
            )
        d = r.json()
        choice = (d.get("choices") or [{}])[0]
        u = d.get("usage") or {}
        return Reply(
            from_openai_message(choice.get("message") or {}),
            Usage(u.get("prompt_tokens", 0) or 0, u.get("completion_tokens", 0) or 0),
            d.get("id", "") or "",
            choice.get("finish_reason", "") or "",
        )


def _error_detail(r: Any) -> str:
    """The provider's own error message (never the request, which holds the key in a header)."""
    try:
        body = r.json()
        if isinstance(body, list) and body:  # Gemini wraps its error in a list
            body = body[0]
        err = body.get("error")
        msg = err.get("message") if isinstance(err, dict) else err
        return str(msg or "")[:200]
    except (ValueError, AttributeError):
        return ""


# ---------------------------------------------------------------------------
# Plain chat adapters for the platform LLMClient (observer, planner, handoff).
# Each returns (text, Usage, call_id). The sandbox harness above shares this module and the ledger.
# ---------------------------------------------------------------------------
class ClaudeChat:
    name = "claude"

    def __init__(self, api_key: str, model: str, client: Any = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        self.client, self.model = client, model

    def chat(self, system, messages, max_tokens):
        import anthropic

        try:
            r = self.client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system or "", messages=messages
            )
        except anthropic.APIError as e:
            raise ProviderError(str(e), retryable=isinstance(e, anthropic.RateLimitError))
        text = "".join(getattr(b, "text", "") for b in r.content)
        u = r.usage
        return text, Usage(u.input_tokens, u.output_tokens), r.id


class OpenAICompatChat:
    """One adapter for OpenAI-compatible APIs (DeepSeek, OpenAI, Gemini's OpenAI endpoint)."""

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        http: Any = None,
        fallbacks: list[str] | None = None,
    ) -> None:
        import httpx

        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.fallbacks = [m for m in (fallbacks or []) if m != model]
        self.http = http or httpx.Client(timeout=120)

    def chat(self, system, messages, max_tokens):
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        r, self.model = post_with_fallback(
            self.http,
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            {"messages": msgs, "max_tokens": max_tokens},
            [self.model, *self.fallbacks],
        )
        if r.status_code >= 400:
            raise ProviderError(
                f"HTTP {r.status_code}: {_error_detail(r)}",
                retryable=r.status_code in (429, 500, 502, 503),
            )
        d = r.json()
        u = d.get("usage") or {}
        return (
            d["choices"][0]["message"]["content"] or "",
            Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0)),
            d.get("id", ""),
        )


class OllamaChat:
    name = "ollama"

    def __init__(self, base_url: str, model: str, http: Any = None) -> None:
        import httpx

        self.base_url, self.model = base_url.rstrip("/"), model
        self.http = http or httpx.Client(timeout=300)

    def chat(self, system, messages, max_tokens):
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        r = self.http.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": msgs,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code}", retryable=r.status_code >= 500)
        d = r.json()
        return (
            d["message"]["content"],
            Usage(d.get("prompt_eval_count", 0), d.get("eval_count", 0)),
            "",
        )


class MockChat:
    """Deterministic provider for tests and offline development. Replies come from a queue of
    canned answers (strings or callables taking the messages); with nothing queued it echoes."""

    name = "mock"
    model = "mock"

    def __init__(self, replies: list[Any] | None = None) -> None:
        self.replies = list(replies or [])
        self.calls = []

    def chat(self, system, messages, max_tokens):
        self.calls.append({"system": system, "messages": messages})
        if self.replies:
            r = self.replies.pop(0)
            text = r(messages) if callable(r) else r
        else:
            text = "mock: " + str(messages[-1]["content"])[:200]
        return text, Usage(len(str(messages)) // 4, len(text) // 4), f"mock-{len(self.calls)}"
