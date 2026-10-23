from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_KEYS = {"", "change-me", "dev-insecure-secret-key"}


def normalize_database_url(url: str) -> str:
    """Render supplies postgres://; SQLAlchemy needs the psycopg 3 driver prefix."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["development", "production", "test"] = "development"
    demo_mode: bool = False
    secret_key: str = "dev-insecure-secret-key"  # noqa: S105 - rejected in production
    database_url: str = "postgresql+psycopg://orthoready:orthoready@localhost:5432/orthoready"
    tz_display: str = "Asia/Tashkent"
    session_timeout_min: int = 15
    decimal_separator: str = ","

    telegram_bot_token: str = ""
    telegram_mode: Literal["webhook", "polling"] = "polling"

    ai_provider: Literal["template", "anthropic"] = "template"
    anthropic_api_key: str = ""
    ai_model: str = ""

    storage_backend: Literal["disabled", "local", "s3"] = "disabled"

    frontend_dist: str = "frontend/dist"
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def effective_storage_backend(self) -> str:
        """Uploads are disabled in demo mode regardless of configuration."""
        return "disabled" if self.demo_mode else self.storage_backend

    def validate_for_web(self) -> None:
        if self.is_production and self.secret_key in _INSECURE_KEYS:
            raise RuntimeError("SECRET_KEY must be set to a strong random value in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
