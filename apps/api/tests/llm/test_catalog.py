"""Free-tier provider catalog: model references and key checks."""

from app.core import config
from app.llm import catalog


def test_split_model_reads_the_provider_prefix_and_keeps_the_rest():
    assert catalog.split_model("groq:llama-3.3-70b-versatile") == (
        "groq",
        "llama-3.3-70b-versatile",
    )
    assert catalog.split_model("openrouter:qwen/qwen3-coder:free") == (
        "openrouter",
        "qwen/qwen3-coder:free",
    )
    assert catalog.split_model("ollama:qwen2.5-coder:7b") == ("ollama", "qwen2.5-coder:7b")


def test_a_bare_or_unknown_prefix_is_a_claude_model():
    assert catalog.split_model("claude-sonnet-5-5") == ("anthropic", "claude-sonnet-5-5")
    assert catalog.split_model("acme:model") == ("anthropic", "acme:model")
    assert catalog.split_model("groq:") == ("anthropic", "groq:")
    assert not catalog.is_free("claude-sonnet-5-5")
    assert catalog.is_free("gemini:gemini-2.5-flash")


def test_key_problem_catches_pasting_the_wrong_key():
    assert catalog.key_problem("groq", "gsk_" + "a" * 20) is None
    assert "gsk_" in (catalog.key_problem("groq", "sk-or-" + "a" * 20) or "")
    assert catalog.key_problem("groq", "gsk_ abc def") is not None
    assert catalog.key_problem("ollama", "anything-long") is not None  # local, no key
    assert catalog.key_problem("nope", "x" * 20) is not None
    assert catalog.key_problem("mistral", "m" * 32) is None  # no fixed prefix


def test_demo_keys_come_from_settings(monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"groq": "gsk_demo"})
    assert catalog.demo_key("groq") == "gsk_demo"
    assert catalog.demo_key("gemini") == ""


def test_ollama_uses_the_configured_local_url(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://box:11434")
    assert catalog.base_url(catalog.get("ollama")) == "http://box:11434/v1"
    assert all(ref.split(":", 1)[0] in catalog.IDS for ref in catalog.suggested_refs())


def test_both_google_key_formats_are_accepted():
    assert catalog.key_problem("gemini", "AIza" + "x" * 30) is None
    assert catalog.key_problem("gemini", "AQ.Ab" + "x" * 30) is None
