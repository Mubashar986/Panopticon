"""Pytest global fixtures and test configuration."""

import pytest
from app.core.config import Settings, get_settings


@pytest.fixture
def test_settings() -> Settings:
    """Return fresh settings instance for tests."""
    get_settings.cache_clear()
    return get_settings()
