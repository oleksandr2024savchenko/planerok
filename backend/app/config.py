from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

TIMEZONE = ZoneInfo("Europe/Vienna")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    webapp_url: str = "https://example.com"

    database_url: str = "postgresql+asyncpg://planer:planer@localhost:5432/planer"
    redis_url: str | None = "redis://localhost:6379/0"

    cors_origins: str = "http://localhost:3000"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"

    # Google Calendar. Either a service-account JSON file, or an OAuth client + refresh token.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_refresh_token: str | None = None
    google_service_account_file: str | None = None
    google_impersonate_email: str | None = None
    google_calendar_id: str = "primary"
    # Calendar of the second allowed Telegram user. Share it with the service account.
    google_partner_calendar_id: str | None = None
    # Telegram user that owns events imported from Google (falls back to DEV_USER_ID).
    google_owner_user_id: int | None = None
    # Public HTTPS URL of POST /webhooks/google-calendar (required for push).
    google_webhook_url: str | None = None
    google_channel_token: str | None = None
    google_oauth_redirect_uri: str | None = None

    dev_user_id: int | None = None

    # "Додовбувач": high-priority tasks are re-sent until done, except during quiet hours.
    nag_interval_minutes: int = 5
    nag_quiet_start_hour: int = 23
    nag_quiet_end_hour: int = 8
    nag_give_up_days: int = 3
    init_data_ttl_seconds: int = 24 * 60 * 60
    # Comma-separated Telegram user ids allowed to use the bot and the API.
    allowed_telegram_ids: str = ""

    @property
    def GOOGLE_SERVICE_ACCOUNT_FILE(self) -> str | None:
        return self.google_service_account_file

    @property
    def GOOGLE_CALENDAR_ID(self) -> str:
        return self.google_calendar_id

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_telegram_id_list(self) -> list[int]:
        ids: list[int] = []
        for raw in self.allowed_telegram_ids.split(","):
            item = raw.strip()
            if not item:
                continue
            ids.append(int(item))
        return ids

    def allows(self, telegram_id: int) -> bool:
        allowed = self.allowed_telegram_id_list
        return bool(allowed) and telegram_id in allowed

    @property
    def scheduler_database_url(self) -> str:
        # APScheduler 3.x job store is synchronous, so it needs a sync driver.
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
