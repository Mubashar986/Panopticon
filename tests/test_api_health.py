"""Unit and integration tests for FastAPI health check and system diagnostic endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.deps import get_search_client_dep
from app.search.models import IndexStats, MeiliHealthStatus


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    app = create_app()
    return TestClient(app)


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify GET /health returns 200 OK and expected diagnostic metadata."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "Panopticon"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert data["auth_mode"] in ("oauth", "service_account")
    assert "x-process-time-ms" in response.headers


def test_system_status_healthy_meilisearch(client: TestClient) -> None:
    """Verify GET /api/system/status reports 'healthy' when Meilisearch is reachable."""
    mock_search_client = MagicMock()
    mock_search_client.health_check.return_value = MeiliHealthStatus(
        is_available=True,
        status="available",
        host="http://localhost:7700",
        version="1.6.2",
    )
    mock_search_client.get_index_stats.return_value = IndexStats(
        index_uid="panopticon_docs",
        is_indexing=False,
        number_of_documents=42,
        field_distribution={"name": 42, "content_snippet": 40},
    )

    client.app.dependency_overrides[get_search_client_dep] = lambda: mock_search_client
    try:
        response = client.get("/api/system/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["meilisearch_connected"] is True
        assert data["meilisearch_health"] == "available"
        assert data["document_count"] == 42
        assert data["is_indexing"] is False
        assert data["details"]["meilisearch_version"] == "1.6.2"
        assert data["details"]["index_stats"]["number_of_documents"] == 42
    finally:
        client.app.dependency_overrides.clear()


def test_system_status_degraded_when_meilisearch_unreachable(client: TestClient) -> None:
    """Verify GET /api/system/status returns 200 with 'degraded' status if Meilisearch is down."""
    mock_search_client = MagicMock()
    mock_search_client.health_check.return_value = MeiliHealthStatus(
        is_available=False,
        status="unreachable",
        host="http://localhost:7700",
        version=None,
        error_message="Connection refused",
    )

    client.app.dependency_overrides[get_search_client_dep] = lambda: mock_search_client
    try:
        response = client.get("/api/system/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "degraded"
        assert data["meilisearch_connected"] is False
        assert "Connection refused" in data["meilisearch_health"]
        assert data["document_count"] == 0
    finally:
        client.app.dependency_overrides.clear()


def test_cors_headers_response(client: TestClient) -> None:
    """Verify CORS headers are returned for preflight requests from allowed origins."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/search", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
