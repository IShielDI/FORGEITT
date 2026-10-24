"""Application settings loaded from environment variables (and an optional `.env` file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py -> repo root is four levels up.
REPO_ROOT = Path(__file__).resolve().parents[4]

LLMProvider = Literal["claude", "openai_compatible", "ollama", "mock"]
VerificationProfile = Literal["fast", "standard", "strict"]

SQLITE_PREFIX = "sqlite:///"


def resolve_sqlite_url(url: str, base: Path = REPO_ROOT) -> str:
    """Make a relative SQLite file path absolute against `base`; leave other URLs untouched."""
    if not url.startswith(SQLITE_PREFIX):
        return url
    path = url.removeprefix(SQLITE_PREFIX)
    if path in ("", ":memory:") or Path(path).is_absolute():
        return url
    return f"{SQLITE_PREFIX}{(base / path).resolve().as_posix()}"


class Settings(BaseSettings):
    """Typed runtime configuration. Secrets are `SecretStr` so they never print in logs.

    Provider keys live only in the backend environment; they are never passed to sandboxes.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "ForgeIt API"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "sqlite:///./data/forgeit.db"
    secret_key: SecretStr = SecretStr("change-me")
    git_storage_path: Path = Path("./data/git")
    artifact_path: Path = Path("./data/artifacts")

    # Providers (Claude first)
    llm_provider: LLMProvider = "mock"
    llm_model: str = ""
    anthropic_api_key: SecretStr | None = None
    openai_compat_base_url: str | None = None
    openai_compat_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Referee
    tinyfish_api_key: SecretStr | None = None
    public_tunnel_url: str | None = None

    # Invites and mail (Gmail SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_app_password: SecretStr | None = None
    invite_ttl_days: int = 7

    # Credits
    house_key_enabled: bool = False
    house_cap_workspace_usd: float | None = None
    house_cap_person_usd: float | None = None

    verification_profile: VerificationProfile = "fast"

    @field_validator("database_url")
    @classmethod
    def _absolute_sqlite_path(cls, value: str) -> str:
        return resolve_sqlite_url(value)

    @field_validator("git_storage_path", "artifact_path")
    @classmethod
    def _absolute_data_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
