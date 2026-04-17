from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stravacoach"
    redis_url: str = "redis://localhost:6379/0"
    strava_client_id: str = "test-client-id"
    strava_client_secret: str = "test-client-secret"
    strava_verify_token: str = "test-verify-token"
    strava_webhook_callback_url: str = "http://localhost:8000/webhook/strava"
    strava_auth_callback_url: str = "http://localhost:8000/auth/callback"
    encryption_key: str = Field(
        default="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    )
    anthropic_api_key: str = ""
    jwt_secret: str = "test-jwt-secret"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""
    enable_llm_debriefs: bool = False

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
