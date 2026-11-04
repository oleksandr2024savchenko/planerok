from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

TIMEZONE = ZoneInfo("Europe/Vienna")
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    webapp_url: str = "https://example.com"

    database_url: str = "postgresql+asyncpg://planer:planer@localhost:5432/planer"
    redis_url: str | None = "redis://localhost:6379/0"

    cors_origins: str = "http://localhost:3000"

    gemini_api_key: str | None = None
    # gemini-2.5-flash is rejected for new AI Studio keys (AQ.*).
    gemini_model: str = "gemini-3.6-flash"

    # Google Calendar. Either a service-account JSON file, or an OAuth client + refresh token.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_refresh_token: str | None = None
    google_service_account_file: str | None = None
    google_impersonate_email: str | None = None
    google_calendar_id: str = "primary"
    # Telegram user that owns events imported from Google (falls back to DEV_USER_ID).
    google_owner_user_id: int | None = None
    # Public HTTPS URL of POST /webhooks/google-calendar (required for push).
    google_webhook_url: str | None = None
    google_channel_token: str | None = None
    google_oauth_redirect_uri: str | None = None

    dev_user_id: int | None = None
    init_data_ttl_seconds: int = 24 * 60 * 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def scheduler_database_url(self) -> str:
        # APScheduler 3.x job store is synchronous, so it needs a sync driver.
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
