"""Model providers with a free tier, Cline-style: pick one, paste its free key (or use the demo
key in .env), pick a model. All of them speak the OpenAI chat API, so one adapter serves them all.

A model is referred to as "<provider>:<model>" (e.g. "groq:llama-3.3-70b-versatile"). A bare
name with no known provider prefix is a Claude model (Anthropic key and credits flow).
Keys stay on the platform: calls are made by the backend, never from inside a sandbox.
"""

from dataclasses import dataclass

from app.core import config

ANTHROPIC = "anthropic"


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    label: str
    base_url: str
    signup_url: str
    models: tuple[str, ...]  # suggestions; the live list (list_models) is the source of truth
    key_prefixes: tuple[str, ...] = ()  # empty: any key accepted
    needs_key: bool = True
    note: str = ""


CATALOG: tuple[ProviderInfo, ...] = (
    ProviderInfo(
        "gemini",
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "https://aistudio.google.com/apikey",
        (
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest",
        ),
        ("AIza", "AQ."),  # classic keys and Google's newer "AQ." keys
        note="Free tier from Google AI Studio; rate limited per minute and per day.",
    ),
    ProviderInfo(
        "groq",
        "Groq",
        "https://api.groq.com/openai/v1",
        "https://console.groq.com/keys",
        ("openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3-32b"),
        ("gsk_",),
        note="Free tier; very fast open models.",
    ),
    ProviderInfo(
        "openrouter",
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "https://openrouter.ai/keys",
        ("qwen/qwen3-coder:free", "deepseek/deepseek-chat-v3.1:free", "openai/gpt-oss-20b:free"),
        ("sk-or-",),
        note="Models ending in ':free' cost nothing; the list changes often.",
    ),
    ProviderInfo(
        "cerebras",
        "Cerebras",
        "https://api.cerebras.ai/v1",
        "https://cloud.cerebras.ai",
        ("gpt-oss-120b", "llama-3.3-70b", "qwen-3-32b"),
        ("csk-",),
        note="Free tier; very fast open models.",
    ),
    ProviderInfo(
        "mistral",
        "Mistral",
        "https://api.mistral.ai/v1",
        "https://console.mistral.ai/api-keys",
        ("devstral-small-latest", "codestral-latest", "mistral-small-latest"),
        note="Free 'Experiment' plan.",
    ),
    ProviderInfo(
        "github",
        "GitHub Models",
        "https://models.github.ai/inference",
        "https://github.com/settings/tokens",
        ("openai/gpt-4.1-mini", "openai/gpt-4.1", "deepseek/deepseek-v3-0324"),
        ("ghp_", "github_pat_"),
        note="Free with a GitHub token that has the models scope.",
    ),
    ProviderInfo(
        "ollama",
        "Ollama (on this machine)",
        "",  # filled from OLLAMA_BASE_URL
        "https://ollama.com/download",
        ("qwen2.5-coder:7b", "llama3.1:8b"),
        needs_key=False,
        note="Runs locally, no key; needs `ollama pull <model>` first.",
    ),
)
_BY_ID = {p.id: p for p in CATALOG}
IDS: tuple[str, ...] = tuple(_BY_ID)


def get(pid: str) -> ProviderInfo | None:
    return _BY_ID.get(pid)


def base_url(p: ProviderInfo) -> str:
    return f"{config.OLLAMA_BASE_URL}/v1" if p.id == "ollama" else p.base_url


def split_model(ref: str | None) -> tuple[str, str]:
    """'groq:llama-3.3' -> ('groq', 'llama-3.3'); 'claude-x' -> ('anthropic', 'claude-x')."""
    ref = ref or ""
    head, sep, rest = ref.partition(":")
    if sep and head in _BY_ID and rest:
        return head, rest
    return ANTHROPIC, ref


def is_free(ref: str | None) -> bool:
    return split_model(ref)[0] != ANTHROPIC


def demo_key(pid: str) -> str:
    """A shared free-tier key from .env (e.g. GROQ_API_KEY), so a demo works with no key pasted."""
    return config.FREE_PROVIDER_KEYS.get(pid, "")


def key_problem(pid: str, key: str) -> str | None:
    p = get(pid)
    if p is None:
        return f"unknown provider '{pid}'"
    if not p.needs_key:
        return f"{p.label} does not need a key"
    if len(key) < 8 or any(c.isspace() for c in key):
        return "that does not look like an API key"
    if p.key_prefixes and not key.startswith(p.key_prefixes):
        return f"a {p.label} key starts with {' or '.join(p.key_prefixes)}"
    return None


def suggested_refs() -> list[str]:
    return [f"{p.id}:{m}" for p in CATALOG for m in p.models]
