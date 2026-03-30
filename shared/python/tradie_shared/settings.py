from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_messaging_service_sid: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    paddle_api_key: str | None = None
    paddle_webhook_secret: str | None = None
    app_encryption_key: str
    app_hash_key: str
    sentry_dsn: str | None = None
    web_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    default_account_timezone: str = "Australia/Brisbane"
    job_poll_interval_seconds: int = 2
    job_lock_ttl_seconds: int = 300
    watchdog_interval_seconds: int = 30
    default_duplicate_window_minutes: int = 240
    lead_capture_rate_limit_per_minute: int = 10
    auth_rate_limit_per_minute: int = 5
    webhook_rate_limit_per_minute: int = 100
    api_rate_limit_per_minute: int = 60
    manual_action_rate_limit_per_minute: int = 10
    lead_payload_max_length: int = Field(default=2_000, ge=500, le=10_000)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
