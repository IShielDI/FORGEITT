"""One model interface. Claude is the real provider (tests use their own stand-in under tests/support)."""

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
                messages=messages,
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

    def __init__(self, base_url: str, api_key: str, model: str, http: Any = None) -> None:
        import httpx

        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.http = http or httpx.Client(timeout=120)

    def chat(self, system, messages, max_tokens):
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        r = self.http.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": msgs, "max_tokens": max_tokens},
        )
        if r.status_code >= 400:
            raise ProviderError(
                f"HTTP {r.status_code}", retryable=r.status_code in (429, 500, 502, 503)
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
