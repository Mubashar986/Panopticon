"""Integration tests for LLM settings REST endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.config import get_settings


@pytest.fixture
def client() -> TestClient:
    """Provide TestClient with local development settings."""
    app = create_app()
    return TestClient(app)


def test_get_llm_settings(client: TestClient):
    """Verify GET /api/settings/llm returns masked credentials and recommendations."""
    resp = client.get("/api/settings/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert "model" in data
    assert "base_url" in data
    assert "has_api_key" in data
    assert "recommended_models" in data
    assert len(data["recommended_models"]) > 0

    # Ensure raw secret is never returned
    if data.get("masked_api_key"):
        assert "***" in data["masked_api_key"]


def test_update_llm_settings(client: TestClient):
    """Verify POST /api/settings/llm dynamically updates model and base_url."""
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct",
        "base_url": "https://openrouter.ai/api/v1",
    }
    resp = client.post("/api/settings/llm", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "meta-llama/llama-3.3-70b-instruct"

    # Confirm persistence in subsequent GET
    get_resp = client.get("/api/settings/llm")
    assert get_resp.json()["model"] == "meta-llama/llama-3.3-70b-instruct"


def test_test_llm_connection_success(client: TestClient):
    """Verify POST /api/settings/llm/test succeeds with mocked completion."""
    with patch(
        "app.core.llm.OpenRouterClient.test_connection",
        return_value=(True, 24.5, "Connection successful: pong"),
    ):
        resp = client.post(
            "/api/settings/llm/test",
            json={"model": "deepseek/deepseek-chat"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["latency_ms"] == 24.5
        assert "successful" in data["message"]
        assert data["model_tested"] == "deepseek/deepseek-chat"


def test_test_llm_connection_failure(client: TestClient):
    """Verify POST /api/settings/llm/test returns error details cleanly."""
    with patch(
        "app.core.llm.OpenRouterClient.test_connection",
        return_value=(False, 120.0, "HTTP 401 Unauthorized: Invalid Key"),
    ):
        resp = client.post(
            "/api/settings/llm/test",
            json={"api_key": "invalid-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "401" in data["message"]
