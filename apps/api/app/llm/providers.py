"""One model interface. Claude is the real provider (tests use their own stand-in under tests/support)."""

from dataclasses import dataclass, field

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
