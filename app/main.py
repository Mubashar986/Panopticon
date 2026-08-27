"""Panopticon Application Main Orchestrator & CLI Entrypoint."""

import sys
from pathlib import Path
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging


def get_app_info() -> dict[str, str]:
    """Return diagnostic application metadata."""
    settings = get_settings()
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "auth_mode": settings.DRIVE_AUTH_MODE,
        "meili_host": settings.MEILI_HOST,
        "meili_index": settings.MEILI_INDEX_NAME,
        "api_endpoint": f"http://{settings.API_HOST}:{settings.API_PORT}",
    }


def main() -> int:
    """Execute main application startup banner and self-check."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger = get_logger("panopticon.main")

    logger.info("Initializing %s v%s...", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Active Drive Auth Mode: [%s]", settings.DRIVE_AUTH_MODE)
    logger.info("Search Engine Endpoint: %s (Index: %s)", settings.MEILI_HOST, settings.MEILI_INDEX_NAME)

    # Ensure local data directory exists
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Local storage directory verified: %s", data_dir.resolve())

    logger.info("%s skeleton is healthy and ready.", settings.APP_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
