from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import REPO_ROOT, Settings, resolve_sqlite_url

ENV_VARS = ("LLM_PROVIDER", "VERIFICATION_PROFILE", "DATABASE_URL", "HOUSE_CAP_PERSON_USD")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "mock"
    assert settings.verification_profile == "fast"
    assert settings.invite_ttl_days == 7
    assert settings.house_key_enabled is False
    assert settings.database_url == f"sqlite:///{(REPO_ROOT / 'data/forgeit.db').as_posix()}"
    assert settings.git_storage_path == REPO_ROOT / "data" / "git"


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("VERIFICATION_PROFILE", "strict")
    monkeypatch.setenv("HOUSE_CAP_PERSON_USD", "2.5")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "claude"
    assert settings.verification_profile == "strict"
    assert settings.house_cap_person_usd == 2.5
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "test-key"


def test_empty_optional_values_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env.example ships blank values such as `HOUSE_CAP_PERSON_USD=`.
    monkeypatch.setenv("HOUSE_CAP_PERSON_USD", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    settings = Settings(_env_file=None)

    assert settings.house_cap_person_usd is None
    assert settings.anthropic_api_key is None


def test_secrets_are_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "super-secret-value")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "mail-secret-value")

    text = repr(Settings(_env_file=None))

    assert "super-secret-value" not in text
    assert "mail-secret-value" not in text


@pytest.mark.parametrize(
    ("name", "value"),
    [("LLM_PROVIDER", "gemini"), ("VERIFICATION_PROFILE", "light")],
)
def test_rejects_unknown_choices(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_example_env_file_is_valid() -> None:
    settings = Settings(_env_file=REPO_ROOT / ".env.example")

    assert settings.llm_provider == "mock"
    assert settings.house_cap_workspace_usd is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:///./data/x.db", f"sqlite:///{Path('/base/data/x.db').resolve().as_posix()}"),
        ("sqlite:///:memory:", "sqlite:///:memory:"),
        ("postgresql://u@h/db", "postgresql://u@h/db"),
    ],
)
def test_resolve_sqlite_url(url: str, expected: str) -> None:
    assert resolve_sqlite_url(url, base=Path("/base")) == expected
