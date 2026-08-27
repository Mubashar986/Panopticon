"""Central Application Settings & Environment Configuration."""

from functools import lru_cache
import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration model loaded from environment or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General App Config
    APP_NAME: str = "Panopticon"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"

    # Google Drive Authentication
    DRIVE_AUTH_MODE: Literal["oauth", "service_account"] = "oauth"
    GOOGLE_CLIENT_SECRETS_FILE: str = "credentials.json"
    GOOGLE_TOKEN_CACHE_FILE: str = "token.json"
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "service_account.json"
    GOOGLE_DELEGATED_USER_EMAIL: str | None = None

    # Meilisearch Config
    MEILI_HOST: str = "http://localhost:7700"
    MEILI_MASTER_KEY: str = "masterKey_panopticon_local_dev"
    MEILI_INDEX_NAME: str = "panopticon_docs"

    # API Server Config
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    # Local Persistence
    CRAWL_DB_PATH: str = "data/crawl_state.db"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
