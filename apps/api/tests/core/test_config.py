import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_without_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("VERIFICATION_PROFILE", raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "mock"
    assert settings.verification_profile == "light"
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("VERIFICATION_PROFILE", "strict")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "groq"
    assert settings.verification_profile == "strict"
    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value() == "test-key"


def test_secrets_are_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "super-secret-value")

    settings = Settings(_env_file=None)

    assert "super-secret-value" not in repr(settings)


def test_rejects_unknown_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "not-a-provider")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
