"""Integration and contract tests for GET /api/search endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.deps import get_search_service_dep
from app.search.exceptions import IndexNotFoundError, SearchConnectionError, SearchError
from app.search.models import SearchHit, SearchResult


@pytest.fixture
def mock_search_service() -> MagicMock:
    """Provide a mock SearchService returning standard search results."""
    service = MagicMock()

    sample_doc_hit = SearchHit(
        id="doc_123",
        name="Project Falcon Architecture Plan",
        mime_type="application/vnd.google-apps.document",
        file_type="document",
        primary_owner="lead@company.com",
        owners=["lead@company.com", "arch@company.com"],
        last_modifying_user="arch@company.com",
        modified_time="2026-08-28T14:30:00Z",
        created_time="2026-08-01T09:00:00Z",
        sharing_status="shared",
        project_tags=["Falcon", "Architecture"],
        content_snippet="Comprehensive architecture specification for Falcon initiative...",
        export_status="success",
        web_view_link="https://docs.google.com/document/d/doc_123/edit",
        icon_link="https://ssl.gstatic.com/docs/doc_2023q4.ico",
        size_bytes=15000,
        matched_via="tag",
        confidence="high",
        highlighted_name="Project <em>Falcon</em> Architecture Plan",
        highlighted_snippet="Comprehensive architecture specification for <em>Falcon</em> initiative...",
    )

    sample_sheet_hit = SearchHit(
        id="sheet_456",
        name="Falcon Q3 Budget",
        mime_type="application/vnd.google-apps.spreadsheet",
        file_type="spreadsheet",
        primary_owner="finance@company.com",
        owners=["finance@company.com"],
        sharing_status="private",
        project_tags=["Falcon"],
        content_snippet="Q3 financial allocations and projections for Falcon...",
        web_view_link="https://docs.google.com/spreadsheets/d/sheet_456/edit",
        matched_via="title",
        confidence="medium",
        highlighted_name="<em>Falcon</em> Q3 Budget",
    )

    service.search.return_value = SearchResult(
        query="Falcon",
        hits=[sample_doc_hit, sample_sheet_hit],
        total_hits=2,
        processing_time_ms=1.45,
        limit=20,
        offset=0,
        facet_distribution={
            "file_type": {"document": 1, "spreadsheet": 1},
            "sharing_status": {"shared": 1, "private": 1},
        },
    )

    return service


@pytest.fixture
def client(mock_search_service: MagicMock) -> TestClient:
    """FastAPI TestClient with mock SearchService injected."""
    app = create_app()
    app.dependency_overrides[get_search_service_dep] = lambda: mock_search_service
    return TestClient(app)


def test_search_happy_path(client: TestClient, mock_search_service: MagicMock) -> None:
    """Verify GET /api/search returns 200 OK with correct JSON contract."""
    response = client.get("/api/search?q=Falcon")
    assert response.status_code == 200

    data = response.json()
    assert data["query"] == "Falcon"
    assert data["total_hits"] == 2
    assert len(data["results"]) == 2
    assert data["processing_time_ms"] == 1.45

    # Verify first hit (Doc)
    doc = data["results"][0]
    assert doc["id"] == "doc_123"
    assert doc["name"] == "Project Falcon Architecture Plan"
    assert doc["type"] == "document"
    assert doc["mime_type"] == "application/vnd.google-apps.document"
    assert doc["owner"] == "lead@company.com"
    assert doc["matched_via"] == "tag"
    assert doc["confidence"] == "high"
    assert doc["view_url"] == "https://docs.google.com/document/d/doc_123/edit"
    assert doc["export_links"]["pdf"] == "https://docs.google.com/document/d/doc_123/export?format=pdf"
    assert doc["export_links"]["docx"] == "https://docs.google.com/document/d/doc_123/export?format=docx"
    assert doc["highlighted_name"] == "Project <em>Falcon</em> Architecture Plan"

    # Verify second hit (Sheet)
    sheet = data["results"][1]
    assert sheet["id"] == "sheet_456"
    assert sheet["type"] == "spreadsheet"
    assert sheet["export_links"]["xlsx"] == "https://docs.google.com/spreadsheets/d/sheet_456/export?format=xlsx"


def test_search_facet_filtering(client: TestClient, mock_search_service: MagicMock) -> None:
    """Verify facet query parameters are forwarded to SearchService."""
    response = client.get(
        "/api/search?q=Falcon&file_type=spreadsheet&sharing_status=private&project_tag=Falcon&limit=10&offset=5"
    )
    assert response.status_code == 200

    mock_search_service.search.assert_called_once_with(
        query="Falcon",
        file_type="spreadsheet",
        mime_type=None,
        sharing_status="private",
        project_tag="Falcon",
        primary_owner=None,
        sort_by=None,
        limit=10,
        offset=5,
    )


def test_search_tag_mode(client: TestClient, mock_search_service: MagicMock) -> None:
    """Verify mode='tag' sets effective project_tag."""
    response = client.get("/api/search?q=Falcon&mode=tag")
    assert response.status_code == 200

    mock_search_service.search.assert_called_once_with(
        query="Falcon",
        file_type=None,
        mime_type=None,
        sharing_status=None,
        project_tag="Falcon",
        primary_owner=None,
        sort_by=None,
        limit=50,
        offset=0,
    )


def test_search_blank_query_browsing_allowed(
    client: TestClient, mock_search_service: MagicMock
) -> None:
    """Verify empty or missing 'q' parameter is allowed and defaults to modified_time:desc sort."""
    response = client.get("/api/search")
    assert response.status_code == 200

    mock_search_service.search.assert_called_with(
        query="",
        file_type=None,
        mime_type=None,
        sharing_status=None,
        project_tag=None,
        primary_owner=None,
        sort_by="modified_time:desc",
        limit=50,
        offset=0,
    )

    response_empty = client.get("/api/search?q=")
    assert response_empty.status_code == 200



def test_search_connection_error_returns_503(
    client: TestClient, mock_search_service: MagicMock
) -> None:
    """Verify Meilisearch connectivity failure returns HTTP 503."""
    mock_search_service.search.side_effect = SearchConnectionError("Cannot reach Meilisearch at http://localhost:7700")

    response = client.get("/api/search?q=Falcon")
    assert response.status_code == 503
    data = response.json()
    assert "error" in data["detail"]
    assert data["detail"]["error"] == "search_engine_unavailable"


def test_search_index_not_found_returns_503(
    client: TestClient, mock_search_service: MagicMock
) -> None:
    """Verify missing index raises HTTP 503 with actionable instruction."""
    mock_search_service.search.side_effect = IndexNotFoundError("Index 'panopticon_docs' not found")

    response = client.get("/api/search?q=Falcon")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["error"] == "search_index_not_found"


def test_search_generic_error_returns_500(
    client: TestClient, mock_search_service: MagicMock
) -> None:
    """Verify unexpected SearchError raises HTTP 500."""
    mock_search_service.search.side_effect = SearchError("Corrupted index file")

    response = client.get("/api/search?q=Falcon")
    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error"] == "search_execution_error"
