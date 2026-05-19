from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Zoe Personal Assistant"
    app_env: str = "local"
    app_base_url: str = "http://localhost:8000"
    timezone: str = "Asia/Jerusalem"
    default_language: str = "auto"

    database_url: str = "sqlite:///./zoe.db"
    token_store: str = "file"
    secret_key: str = Field(default="change-me-before-deploy", min_length=8)
    token_encryption_key: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    primary_whatsapp_to: str | None = None

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/google/oauth/callback"

    daily_brief_time: str = "07:45"
    sunday_finance_brief_time: str = "08:30"

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
