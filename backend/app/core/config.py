"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Application ---
    app_name: str = "Ahmedabad Startup Jobs API"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: list[str] | str = Field(default="http://localhost:3000")

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ahmedabad_jobs"
    sync_database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ahmedabad_jobs"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Security ---
    secret_key: str = "change-me-in-production-please-32-chars-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    refresh_token_expire_days: int = 30
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # --- Ingestion ---
    user_agent: str = (
        "Mozilla/5.0 (compatible; AhmedabadStartupJobsBot/1.0; +https://ahmedabadstartupjobs.com/bot)"
    )
    http_timeout: float = 25.0
    http_max_concurrency: int = 8
    respect_robots_txt: bool = True
    max_jobs_per_source_run: int = 500
    job_stale_after_days: int = 14
    job_expire_after_days: int = 45

    # --- AI ---
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ai_enabled: bool = False

    # --- Email notifications ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str = "alerts@ahmedabadstartupjobs.com"
    email_enabled: bool = False

    # --- Frontend ---
    frontend_base_url: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
