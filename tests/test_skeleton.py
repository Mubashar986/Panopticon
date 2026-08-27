"""Smoke verification tests for Panopticon skeleton."""

import pytest
from app import __version__
from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.main import get_app_info, main


def test_package_metadata():
    """Verify package version and naming."""
    assert __version__ == "0.1.0"


def test_settings_defaults(test_settings: Settings):
    """Verify default configuration values."""
    assert test_settings.APP_NAME == "Panopticon"
    assert test_settings.APP_VERSION == "0.1.0"
    assert test_settings.DRIVE_AUTH_MODE in ("oauth", "service_account")
    assert test_settings.MEILI_HOST.startswith("http")
    assert test_settings.MEILI_INDEX_NAME == "panopticon_docs"


def test_logging_setup():
    """Verify logger creation and structured setup."""
    setup_logging("DEBUG")
    logger = get_logger("test.logger")
    assert logger is not None
    assert logger.name == "test.logger"


def test_app_info_diagnostic():
    """Verify diagnostic metadata dictionary."""
    info = get_app_info()
    assert info["app_name"] == "Panopticon"
    assert info["version"] == "0.1.0"
    assert "auth_mode" in info
    assert "meili_host" in info


def test_main_entrypoint(monkeypatch):
    """Verify main function executes with 0 exit code."""
    result = main()
    assert result == 0
