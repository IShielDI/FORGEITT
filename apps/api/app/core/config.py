"""Application settings loaded from environment variables (and an optional `.env` file).

`Settings` is the typed source of truth. The module-level constants below it (DATA, STATE,
REQUIRE_AUTH, ...) are what the services read at call time, so tests can monkeypatch them.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py -> repo root is four levels up.
REPO_ROOT = Path(__file__).resolve().parents[4]

LLMProvider = Literal["claude", "openai_compatible", "ollama", "mock"]
VerificationProfile = Literal["fast", "standard", "strict"]
SandboxMode = Literal["auto", "docker", "subprocess"]

SQLITE_PREFIX = "sqlite:///"
DB_FILENAME = "forgeit.db"


def resolve_sqlite_url(url: str, base: Path = REPO_ROOT) -> str:
    """Make a relative SQLite file path absolute against `base`; leave other URLs untouched."""
    if not url.startswith(SQLITE_PREFIX):
        return url
    path = url.removeprefix(SQLITE_PREFIX)
    if path in ("", ":memory:") or Path(path).is_absolute():
        return url
    return f"{SQLITE_PREFIX}{(base / path).resolve().as_posix()}"


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class Settings(BaseSettings):
    """Typed runtime configuration. Secrets are `SecretStr` so they never print in logs.

    Provider keys live only in the backend environment; they are never passed to sandboxes.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "ForgeIt API"
    environment: Literal["development", "test", "production"] = "development"

    # Platform state (database, encryption key) lives in a SIBLING of the workspace data folder,
    # never inside or above the agents' workspaces. DATABASE_URL defaults to <state>/forgeit.db.
    platform_state: Path = Field(
        Path("./data/state"), validation_alias=AliasChoices("PLATFORM_STATE", "platform_state")
    )
    database_url: str = ""
    secret_key: SecretStr = SecretStr("change-me")
    # Rooms: protected originals, per-task clones, evidence, hidden tests, journeys.
    git_storage_path: Path = Field(
        Path("./data/git"),
        validation_alias=AliasChoices("GIT_STORAGE_PATH", "PLATFORM_DATA", "git_storage_path"),
    )
    artifact_path: Path = Path("./data/artifacts")
    sample_project_path: Path = Path("./samples/shop")
    sample_holdout_path: Path = Path("./samples/shop-holdout")
    todo_project_path: Path = Path("./samples/todo-app")
    todo_holdout_path: Path = Path("./samples/todo-app-holdout")

    # Providers (Claude first)
    llm_provider: LLMProvider = "mock"
    llm_model: str = Field(
        "claude-sonnet-5-5", validation_alias=AliasChoices("LLM_MODEL", "AGENT_MODEL", "llm_model")
    )
    anthropic_api_key: SecretStr | None = None
    openai_compat_base_url: str | None = None
    openai_compat_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Referee
    tinyfish_api_key: SecretStr | None = None
    public_tunnel_url: str | None = Field(
        None,
        validation_alias=AliasChoices(
            "PUBLIC_TUNNEL_URL", "MIRROR_PUBLIC_URL", "public_tunnel_url"
        ),
    )
    referee_step_limit: int = 20
    referee_runs_per_hour: int = 10
    # Offline HTTP stand-in for rehearsals/tests only; its results are never a TinyFish verdict.
    referee_standin: bool = False

    # Agents and sandbox
    agent_step_limit: int = 40
    agent_time_limit_s: int = 1800  # wall-clock limit for one agent run
    agent_sandbox: SandboxMode = "auto"
    agent_image: str = "forgeit-agent:latest"
    # Where the mirror runs candidate code: auto (Docker if the image exists) | docker | host
    mirror_sandbox: Literal["auto", "docker", "host"] = "auto"
    mirror_image: str = "forgeit-mirror:latest"
    # Plain subprocess is NOT a security boundary; only for a throwaway machine with no secrets.
    allow_unsafe_sandbox: bool = False
    pile_size: int = 3
    pile_wait_min: int = 20

    # Access
    require_auth: bool = True
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Where people open the web app; invite links point here.
    public_web_url: str = "http://localhost:3000"

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

    @field_validator(
        "platform_state",
        "git_storage_path",
        "artifact_path",
        "sample_project_path",
        "sample_holdout_path",
        "todo_project_path",
        "todo_holdout_path",
    )
    @classmethod
    def _absolute_paths(cls, value: Path) -> Path:
        return _absolute(value)

    @model_validator(mode="after")
    def _default_database_in_state(self) -> "Settings":
        url = (
            self.database_url or f"{SQLITE_PREFIX}{(self.platform_state / DB_FILENAME).as_posix()}"
        )
        self.database_url = resolve_sqlite_url(url)
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()


# ---- constants read by the platform services (monkeypatchable in tests) ----
_settings = get_settings()

DATA: Path = _settings.git_storage_path
STATE: Path = _settings.platform_state
SAMPLE: Path = _settings.sample_project_path
SAMPLE_HOLDOUT: Path = _settings.sample_holdout_path
# starting points a workspace can be created from: (project, its hidden tests)
TEMPLATES: dict[str, tuple[Path, Path]] = {
    "sample": (SAMPLE, SAMPLE_HOLDOUT),
    "todo": (_settings.todo_project_path, _settings.todo_holdout_path),
}
DATA.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)

TINYFISH_KEY: str = (
    _settings.tinyfish_api_key.get_secret_value() if _settings.tinyfish_api_key else ""
)
TINYFISH_BASE = "https://agent.tinyfish.ai"
MIRROR_PUBLIC_URL: str = _settings.public_tunnel_url or ""
STEP_LIMIT: int = _settings.referee_step_limit
RUNS_PER_HOUR: int = _settings.referee_runs_per_hour
AGENT_STEP_LIMIT: int = _settings.agent_step_limit
PILE_SIZE: int = _settings.pile_size
PILE_WAIT_MIN: int = _settings.pile_wait_min
EXTRA_RUNS_CAP = 2
DEFAULT_MODEL: str = _settings.llm_model
AGENT_SANDBOX: str = _settings.agent_sandbox
AGENT_IMAGE: str = _settings.agent_image
ALLOW_UNSAFE_SANDBOX: bool = _settings.allow_unsafe_sandbox
ALLOW_STANDIN: bool = _settings.referee_standin
REQUIRE_AUTH: bool = _settings.require_auth
CORS_ORIGINS: list[str] = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
PUBLIC_WEB_URL: str = _settings.public_web_url.rstrip("/")
INVITE_TTL_DAYS: int = _settings.invite_ttl_days
SMTP_HOST: str = _settings.smtp_host
SMTP_PORT: int = _settings.smtp_port
SMTP_USER: str = _settings.smtp_user or ""
SMTP_APP_PASSWORD: str = (
    _settings.smtp_app_password.get_secret_value() if _settings.smtp_app_password else ""
)
LLM_PROVIDER: str = _settings.llm_provider
ANTHROPIC_API_KEY: str = (
    _settings.anthropic_api_key.get_secret_value() if _settings.anthropic_api_key else ""
)
OPENAI_COMPAT_BASE_URL: str = (_settings.openai_compat_base_url or "").rstrip("/")
OPENAI_COMPAT_API_KEY: str = (
    _settings.openai_compat_api_key.get_secret_value() if _settings.openai_compat_api_key else ""
)
OLLAMA_BASE_URL: str = _settings.ollama_base_url.rstrip("/")
AGENT_TIME_LIMIT_S: int = _settings.agent_time_limit_s
MIRROR_SANDBOX: str = _settings.mirror_sandbox
MIRROR_IMAGE: str = _settings.mirror_image
VERIFICATION_PROFILE: str = _settings.verification_profile
HOUSE_KEY_ENABLED: bool = _settings.house_key_enabled
HOUSE_CAP_WORKSPACE_USD: float | None = _settings.house_cap_workspace_usd
HOUSE_CAP_PERSON_USD: float | None = _settings.house_cap_person_usd
