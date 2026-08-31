"""Integration and contract tests for GET /api/documents endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.deps import get_crawl_storage_dep
from app.indexer.models import DriveFileMetadata
from app.indexer.storage import CrawlStorage


@pytest.fixture
def temp_storage(tmp_path: Path) -> CrawlStorage:
    """Provide an isolated temporary SQLite CrawlStorage instance."""
    db_path = tmp_path / "test_crawl_state.db"
    return CrawlStorage(db_path=db_path)


@pytest.fixture
def populated_storage(temp_storage: CrawlStorage) -> CrawlStorage:
    """Populate temporary storage with sample Google Docs and Sheets."""
    docs = [
        DriveFileMetadata(
            id="doc_001",
            name="Project Falcon Technical Architecture",
            mime_type="application/vnd.google-apps.document",
            modified_time=datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc),
            created_time=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            owners=["alex.architect@company.com"],
            last_modifying_user="alex.architect@company.com",
            shared=True,
            sharing_status="domain",
            project_tags=["Falcon", "Architecture"],
            content_snippet="Architecture specification for Project Falcon...",
            export_status="success",
            web_view_link="https://docs.google.com/document/d/doc_001/edit",
            size_bytes=24500,
        ),
        DriveFileMetadata(
            id="sheet_002",
            name="Falcon Q3 Financial Budget",
            mime_type="application/vnd.google-apps.spreadsheet",
            modified_time=datetime(2026, 8, 29, 11, 30, tzinfo=timezone.utc),
            created_time=datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc),
            owners=["finance@company.com"],
            last_modifying_user="finance.lead@company.com",
            shared=False,
            sharing_status="private",
            project_tags=["Falcon", "Budget"],
            content_snippet="Financial allocations and burn projections...",
            export_status="success",
            web_view_link="https://docs.google.com/spreadsheets/d/sheet_002/edit",
            size_bytes=12000,
        ),
        DriveFileMetadata(
            id="doc_003",
            name="SmartTrade Integration Roadmap",
            mime_type="application/vnd.google-apps.document",
            modified_time=datetime(2026, 8, 25, 16, 45, tzinfo=timezone.utc),
            created_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc),
            owners=["samantha.pm@company.com"],
            last_modifying_user="samantha.pm@company.com",
            shared=True,
            sharing_status="shared",
            project_tags=["SmartTrade", "Roadmap"],
            content_snippet="SmartTrade API integration milestones...",
            export_status="success",
            web_view_link="https://docs.google.com/document/d/doc_003/edit",
            size_bytes=35000,
        ),
        DriveFileMetadata(
            id="sheet_004",
            name="SmartTrade Customer Tracking",
            mime_type="application/vnd.google-apps.spreadsheet",
            modified_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            created_time=datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc),
            owners=["sales@company.com"],
            last_modifying_user="jordan.dev@company.com",
            shared=True,
            sharing_status="domain",
            project_tags=["SmartTrade"],
            content_snippet="Customer onboarding telemetry for SmartTrade...",
            export_status="success",
            web_view_link="https://docs.google.com/spreadsheets/d/sheet_004/edit",
            size_bytes=8400,
        ),
        DriveFileMetadata(
            id="other_005",
            name="Uncategorized Archive File",
            mime_type="application/octet-stream",
            modified_time=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
            created_time=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
            owners=["alex.architect@company.com"],
            shared=False,
            sharing_status="private",
            project_tags=[],
            export_status="skipped_unsupported_mime",
            size_bytes=500000,
        ),
    ]
    temp_storage.upsert_files(docs)
    return temp_storage


@pytest.fixture
def client(populated_storage: CrawlStorage) -> TestClient:
    """Create a test client with overridden CrawlStorage dependency."""
    app = create_app()
    app.dependency_overrides[get_crawl_storage_dep] = lambda: populated_storage
    return TestClient(app)


def test_get_documents_empty_db(tmp_path: Path):
    """Verify GET /api/documents handles empty storage gracefully."""
    empty_storage = CrawlStorage(db_path=tmp_path / "empty.db")
    app = create_app()
    app.dependency_overrides[get_crawl_storage_dep] = lambda: empty_storage
    test_client = TestClient(app)

    response = test_client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert data["documents"] == []
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert "processing_time_ms" in data


def test_get_documents_default_listing(client: TestClient):
    """Verify default listing returns all non-trashed records sorted by modified_time descending."""
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()

    assert data["total_count"] == 5
    assert len(data["documents"]) == 5
    # doc_001 was modified latest (Aug 30) -> should be first
    assert data["documents"][0]["id"] == "doc_001"
    assert data["documents"][0]["name"] == "Project Falcon Technical Architecture"
    assert data["documents"][0]["type"] == "document"
    assert data["documents"][0]["export_links"]["pdf"].endswith("/export?format=pdf")
    assert data["documents"][0]["export_links"]["docx"].endswith("/export?format=docx")

    # sheet_002 was modified second latest (Aug 29) -> should be second
    assert data["documents"][1]["id"] == "sheet_002"
    assert data["documents"][1]["type"] == "spreadsheet"
    assert data["documents"][1]["export_links"]["xlsx"].endswith("/export?format=xlsx")
    assert data["documents"][1]["export_links"]["csv"].endswith("/export?format=csv")


def test_get_documents_pagination(client: TestClient):
    """Verify limit and offset pagination slicing."""
    response = client.get("/api/documents?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 5
    assert len(data["documents"]) == 2
    assert data["documents"][0]["id"] == "doc_001"
    assert data["documents"][1]["id"] == "sheet_002"

    # Page 2
    response_page2 = client.get("/api/documents?limit=2&offset=2")
    assert response_page2.status_code == 200
    data2 = response_page2.json()
    assert data2["total_count"] == 5
    assert len(data2["documents"]) == 2
    assert data2["documents"][0]["id"] == "doc_003"
    assert data2["documents"][1]["id"] == "sheet_004"


def test_get_documents_sorting(client: TestClient):
    """Verify sorting options work correctly."""
    # 1. Alphabetical ascending (A -> Z)
    res_alpha = client.get("/api/documents?sort_by=name:asc")
    assert res_alpha.status_code == 200
    names = [doc["name"] for doc in res_alpha.json()["documents"]]
    assert names == sorted(names, key=str.lower)

    # 2. Modified time ascending (oldest first)
    res_time_asc = client.get("/api/documents?sort_by=modified_time:asc")
    assert res_time_asc.status_code == 200
    time_asc_docs = res_time_asc.json()["documents"]
    assert time_asc_docs[0]["id"] == "other_005"  # Aug 10
    assert time_asc_docs[-1]["id"] == "doc_001"   # Aug 30


def test_get_documents_facet_filters(client: TestClient):
    """Verify facet filtering by file_type, sharing_status, project_tag, and owner."""
    # Filter by file_type: document
    res_docs = client.get("/api/documents?file_type=document")
    assert res_docs.status_code == 200
    doc_data = res_docs.json()
    assert doc_data["total_count"] == 2
    assert all(d["type"] == "document" for d in doc_data["documents"])

    # Filter by file_type: spreadsheet
    res_sheets = client.get("/api/documents?file_type=spreadsheet")
    assert res_sheets.status_code == 200
    sheet_data = res_sheets.json()
    assert sheet_data["total_count"] == 2
    assert all(d["type"] == "spreadsheet" for d in sheet_data["documents"])

    # Filter by project_tag: Falcon
    res_tag = client.get("/api/documents?project_tag=Falcon")
    assert res_tag.status_code == 200
    tag_data = res_tag.json()
    assert tag_data["total_count"] == 2
    assert {d["id"] for d in tag_data["documents"]} == {"doc_001", "sheet_002"}

    # Filter by sharing_status: private
    res_private = client.get("/api/documents?sharing_status=private")
    assert res_private.status_code == 200
    priv_data = res_private.json()
    assert priv_data["total_count"] == 2
    assert {d["id"] for d in priv_data["documents"]} == {"sheet_002", "other_005"}

    # Filter by primary_owner: alex.architect
    res_owner = client.get("/api/documents?primary_owner=alex.architect")
    assert res_owner.status_code == 200
    owner_data = res_owner.json()
    assert owner_data["total_count"] == 2
    assert {d["id"] for d in owner_data["documents"]} == {"doc_001", "other_005"}


def test_get_documents_validation_bounds(client: TestClient):
    """Verify FastAPI validation bounds for limit and sort parameters."""
    # Limit < 1
    res_low = client.get("/api/documents?limit=0")
    assert res_low.status_code == 422

    # Limit > 500
    res_high = client.get("/api/documents?limit=501")
    assert res_high.status_code == 422

    # Offset < 0
    res_neg_offset = client.get("/api/documents?offset=-1")
    assert res_neg_offset.status_code == 422

    # Invalid sort_by option
    res_bad_sort = client.get("/api/documents?sort_by=invalid_col:desc")
    assert res_bad_sort.status_code == 422
