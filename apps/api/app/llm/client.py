"""Platform LLMClient: `complete(messages, schema=None)` over one provider adapter (TRD section 6).

- Provider and model come from settings (LLM_PROVIDER, LLM_MODEL); swapping needs no code change.
- Each workspace may restrict which providers it allows.
- Structured output is validated with Pydantic, with one retry on invalid JSON.
- Every call is charged to the credits ledger. Prompts and keys are never logged.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from app.core import config
from app.core.db import q1
from app.llm.providers import (
    ClaudeChat,
    MockChat,
    OllamaChat,
    OpenAICompatChat,
    ProviderError,
    Usage,
)
from app.services import credits, ledger

DEFAULT_MAX_TOKENS = 1500
PROVIDERS = ("claude", "openai_compatible", "ollama", "mock")


class ChatProvider(Protocol):
    name: str
    model: str

    def chat(
        self, system: str | None, messages: list[dict[str, Any]], max_tokens: int
    ) -> tuple[str, Usage, str]: ...


class LLMError(Exception):
    pass


class StructuredOutputError(LLMError):
    pass


@dataclass
class LLMResult:
    text: str
    data: BaseModel | None = None
    provider: str = ""
    model: str = ""
    prompt_version: str | None = None
    usage: list[Usage] = field(default_factory=list)


def allowed_providers(room_id: int | None) -> list[str]:
    row = q1("SELECT allowed_providers FROM rooms WHERE id=?", (room_id,)) if room_id else None
    raw = row["allowed_providers"] if row else None
    return list(PROVIDERS) if not raw else [p for p in json.loads(raw) if p in PROVIDERS]


def _extract_json(text: str) -> Any:
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    return json.loads(m.group(0))


class LLMClient:
    def __init__(
        self,
        provider: ChatProvider,
        room_id: int | None = None,
        member_id: int | None = None,
        label: str = "platform",
    ) -> None:
        self.provider, self.room_id, self.member_id, self.label = (
            provider,
            room_id,
            member_id,
            label,
        )

    def _call(
        self, system: str | None, messages: list[dict[str, Any]], max_tokens: int
    ) -> tuple[str, Usage]:
        if self.room_id is not None:
            credits.ensure_budget(self.room_id, self.member_id, self.provider.name)
        try:
            text, usage, call_id = self.provider.chat(system, messages, max_tokens)
        except ProviderError as e:
            raise LLMError(f"{self.provider.name} call failed: {e}") from e
        if self.room_id is not None:
            credits.charge(
                self.room_id,
                self.member_id,
                self.label,
                self.provider.name,
                self.provider.model,
                usage.input,
                usage.output,
                call_id,
            )
        return text, usage

    def complete(
        self,
        messages: list[dict[str, Any]],
        schema: type[BaseModel] | None = None,
        system: str | None = None,
        prompt_version: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResult:
        sys_prompt = system
        if schema is not None:
            shape = json.dumps(schema.model_json_schema())
            instruction = f"Reply with ONLY a JSON value matching this JSON schema:\n{shape}"
            sys_prompt = f"{system or ''}\n\n{instruction}".strip()
        text, usage = self._call(sys_prompt, messages, max_tokens)
        result = LLMResult(
            text, None, self.provider.name, self.provider.model, prompt_version, [usage]
        )
        if schema is None:
            return result
        try:
            result.data = schema.model_validate(_extract_json(text))
            return result
        except (ValueError, ValidationError) as first:
            retry = [
                *messages,
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": (
                        f"That reply was not valid ({str(first)[:300]}). "
                        "Reply again with ONLY valid JSON."
                    ),
                },
            ]
            text, usage = self._call(sys_prompt, retry, max_tokens)
            result.text, result.usage = text, [*result.usage, usage]
            try:
                result.data = schema.model_validate(_extract_json(text))
            except (ValueError, ValidationError) as second:
                raise StructuredOutputError(
                    f"invalid structured output after one retry: {str(second)[:300]}"
                ) from second
            return result


def make_provider(provider: str, model: str, member_id: int | None = None) -> ChatProvider:
    if provider == "mock":
        return MockChat()
    if provider == "claude":
        key = (ledger.get_secret(member_id) if member_id else None) or config.ANTHROPIC_API_KEY
        if not key:
            raise LLMError(
                "no Claude key: connect your key in the workspace or set ANTHROPIC_API_KEY"
            )
        return ClaudeChat(key, model)
    if provider == "openai_compatible":
        if not (config.OPENAI_COMPAT_BASE_URL and config.OPENAI_COMPAT_API_KEY):
            raise LLMError("set OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_API_KEY")
        return OpenAICompatChat(config.OPENAI_COMPAT_BASE_URL, config.OPENAI_COMPAT_API_KEY, model)
    if provider == "ollama":
        return OllamaChat(config.OLLAMA_BASE_URL, model)
    raise LLMError(f"unknown provider {provider!r}")


# Tests (and offline rehearsals) can install a shared mock so services pick it up.
_override: ChatProvider | None = None


def use_provider(provider: ChatProvider | None) -> None:
    global _override
    _override = provider


def get_client(
    room_id: int | None,
    member_id: int | None = None,
    label: str = "platform",
    provider: str | None = None,
) -> LLMClient:
    if _override is not None:
        return LLMClient(_override, room_id, member_id, label)
    name = provider or config.LLM_PROVIDER
    if room_id is not None and name not in allowed_providers(room_id):
        raise LLMError(f"provider {name!r} is not allowed in this workspace")
    return LLMClient(
        make_provider(name, config.DEFAULT_MODEL, member_id), room_id, member_id, label
    )
