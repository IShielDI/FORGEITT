from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import REPO_ROOT, Settings, resolve_sqlite_url

# The test session sets some of these (see tests/conftest.py); clear them to test real defaults.
ENV_VARS = (
    "LLM_PROVIDER",
    "VERIFICATION_PROFILE",
    "DATABASE_URL",
    "HOUSE_CAP_PERSON_USD",
    "PLATFORM_STATE",
    "PLATFORM_DATA",
    "REQUIRE_AUTH",
    "MIRROR_PUBLIC_URL",
    "PUBLIC_TUNNEL_URL",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "mock"
    assert settings.verification_profile == "fast"
    assert settings.require_auth is True
    assert settings.agent_image == "forgeit-agent:latest"
    assert settings.platform_state == REPO_ROOT / "data" / "state"
    assert settings.database_url == f"sqlite:///{(REPO_ROOT / 'data/state/forgeit.db').as_posix()}"
    assert settings.git_storage_path == REPO_ROOT / "data" / "git"


def test_state_folder_is_a_sibling_of_workspace_data() -> None:
    # The database and encryption key must never sit inside or above the agents' workspaces.
    settings = Settings(_env_file=None)
    data, state = settings.git_storage_path, settings.platform_state

    assert state != data
    assert data not in state.parents
    assert state not in data.parents


def test_database_follows_platform_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLATFORM_STATE", str(tmp_path))

    assert (
        Settings(_env_file=None).database_url == f"sqlite:///{(tmp_path / 'forgeit.db').as_posix()}"
    )


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("VERIFICATION_PROFILE", "strict")
    monkeypatch.setenv("HOUSE_CAP_PERSON_USD", "2.5")
    monkeypatch.setenv("REQUIRE_AUTH", "0")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "claude"
    assert settings.verification_profile == "strict"
    assert settings.house_cap_person_usd == 2.5
    assert settings.require_auth is False
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "test-key"


def test_referee_era_names_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIRROR_PUBLIC_URL", "https://preview.example")
    monkeypatch.setenv("AGENT_MODEL", "claude-haiku-5-5")

    settings = Settings(_env_file=None)

    assert settings.public_tunnel_url == "https://preview.example"
    assert settings.llm_model == "claude-haiku-5-5"


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
    [("LLM_PROVIDER", "gemini"), ("VERIFICATION_PROFILE", "light"), ("AGENT_SANDBOX", "vm")],
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
