"""Central Application Settings & Environment Configuration."""

from functools import lru_cache
from pathlib import Path
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
    MEILI_NO_ANALYTICS: bool = True

    # API Server Config
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Local Persistence
    CRAWL_DB_PATH: str = "data/crawl_state.db"

    # Auto-Sync Background Scheduler
    AUTO_SYNC_ENABLED: bool = True
    AUTO_SYNC_INTERVAL_SECONDS: int = 30

    # OpenRouter AI Semantic Change Summarizer
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"


    @property
    def credentials_path(self) -> Path:
        """Resolved Path to OAuth client secrets file."""
        return Path(self.GOOGLE_CLIENT_SECRETS_FILE).resolve()

    @property
    def token_cache_path(self) -> Path:
        """Resolved Path to OAuth token cache file."""
        return Path(self.GOOGLE_TOKEN_CACHE_FILE).resolve()

    @property
    def service_account_path(self) -> Path:
        """Resolved Path to Service Account JSON key file."""
        return Path(self.GOOGLE_SERVICE_ACCOUNT_FILE).resolve()

    @property
    def crawl_database_path(self) -> Path:
        """Resolved Path to local SQLite crawl state database."""
        return Path(self.CRAWL_DB_PATH).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
