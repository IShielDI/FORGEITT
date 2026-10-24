"""Application settings loaded from environment variables (and an optional `.env` file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py -> repo root is four levels up.
REPO_ROOT = Path(__file__).resolve().parents[4]

LLMProvider = Literal["gemini", "groq", "openrouter", "ollama", "mock"]
VerificationProfile = Literal["light", "standard", "strict"]


class Settings(BaseSettings):
    """Typed runtime configuration. Secrets are `SecretStr` so they never print in logs."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FORGEITT API"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/collab"

    llm_provider: LLMProvider = "mock"
    llm_model: str = ""
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"

    secret_key: SecretStr = SecretStr("change-me")

    git_storage_path: Path = Path("./data/git")
    artifact_path: Path = Path("./data/artifacts")
    sandbox_image: str = "collab-agent:latest"
    verification_profile: VerificationProfile = "light"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
