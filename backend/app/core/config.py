"""Application settings, sourced from environment variables via pydantic-settings."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, loaded from environment / `.env` file.

    Every value used by the app must be declared here — never read `os.environ`
    directly elsewhere in the codebase.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ---
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_v1_prefix: str = "/api/v1"
    enable_scheduler: bool = True  # disabled in tests via APP_ENV=test override below

    # --- Database ---
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "sportedge"
    postgres_user: str = "sportedge"
    postgres_password: str = "sportedge"

    # --- Auth (used from step 5 onwards) ---
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 120
    jwt_refresh_token_ttl_days: int = 14

    # --- Default user (seeded on first migration, step 2) ---
    default_user_email: str = "you@example.com"
    default_user_password: str = "change-on-first-login"
    default_starting_bankroll: Decimal = Field(default=Decimal("1000.00"))

    # --- Betfair ---
    betfair_default_commission_pct: Decimal = Field(default=Decimal("5.00"))

    # --- Obsidian (step 14b) ---
    obsidian_default_vault: str = "/vault"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL using asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """Sync SQLAlchemy URL — used by Alembic migrations."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
