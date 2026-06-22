"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-secret-change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    PROJECT_NAME: str = "TeamSync"
    ENVIRONMENT: str = "development"  # development | test | production
    API_V1_PREFIX: str = "/api/v1"

    # --- Security / JWT ---
    # IMPORTANT: override SECRET_KEY in production (e.g. `openssl rand -hex 32`).
    SECRET_KEY: str = _DEV_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30

    # --- Database ---
    # Defaults to a local SQLite file so the app runs with zero setup.
    # For Postgres, set DATABASE_URL, e.g.:
    #   postgresql+asyncpg://teamsync:teamsync@localhost:5432/teamsync
    DATABASE_URL: str = "sqlite+aiosqlite:///./teamsync.db"

    # --- Refresh-token cookie ---
    REFRESH_COOKIE_NAME: str = "teamsync_refresh"
    # Default True (HTTPS-only). Set COOKIE_SECURE=false in .env for local HTTP dev.
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"  # lax | strict | none
    COOKIE_DOMAIN: str | None = None

    # --- Frontend / CORS ---
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        # Allow a comma-separated string in the env var.
        if isinstance(v, str) and not v.startswith("["):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _security_checks(self) -> "Settings":
        # C1: reject the dev placeholder key in production.
        if self.ENVIRONMENT == "production" and self.SECRET_KEY == _DEV_SECRET:
            raise ValueError(
                "SECRET_KEY must be overridden in production "
                "(generate one with: openssl rand -hex 32)"
            )
        # L2: SameSite=none requires Secure=true (browsers enforce this too).
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        return self

    @property
    def refresh_cookie_max_age(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
