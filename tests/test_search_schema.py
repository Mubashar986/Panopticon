"""Unit tests for SearchDocument transformation, index settings, and schema provisioning."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
)
from app.search.client import PanopticonSearchClient
from app.search.exceptions import IndexConfigurationError, SearchConnectionError
from app.search.schema import (
    INDEX_SETTINGS,
    SearchDocument,
    configure_index_schema,
    get_index_schema,
)


def test_search_document_from_google_doc() -> None:
    """Test transforming a Google Doc metadata entity to SearchDocument."""
    drive_doc = DriveFileMetadata(
        id="doc_123",
        name="Project Falcon Overview",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        modified_time=datetime(2026, 8, 28, 14, 30, 0, tzinfo=timezone.utc),
        created_time=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
        owners=["lead@company.com", "dev@company.com"],
        last_modifying_user="editor@company.com",
        sharing_status="domain",
        project_tags=["Falcon", "Core"],
        content_snippet="Project Falcon Q3 roadmap and deliverables.",
        export_status="success",
        web_view_link="https://docs.google.com/document/d/doc_123",
        icon_link="https://drive.google.com/icon/doc",
        size_bytes=1024,
    )

    doc = SearchDocument.from_drive_metadata(drive_doc)

    assert doc.id == "doc_123"
    assert doc.name == "Project Falcon Overview"
    assert doc.mime_type == GOOGLE_DOC_MIME_TYPE
    assert doc.file_type == "document"
    assert doc.modified_time == "2026-08-28T14:30:00+00:00"
    assert doc.created_time == "2026-08-20T10:00:00+00:00"
    assert doc.primary_owner == "lead@company.com"
    assert doc.owners == ["lead@company.com", "dev@company.com"]
    assert doc.last_modifying_user == "editor@company.com"
    assert doc.sharing_status == "domain"
    assert doc.project_tags == ["Falcon", "Core"]
    assert doc.content_snippet == "Project Falcon Q3 roadmap and deliverables."
    assert doc.export_status == "success"
    assert doc.web_view_link == "https://docs.google.com/document/d/doc_123"


def test_search_document_from_google_sheet() -> None:
    """Test transforming a Google Sheet metadata entity to SearchDocument."""
    drive_sheet = DriveFileMetadata(
        id="sheet_456",
        name="Falcon Budget 2026",
        mime_type=GOOGLE_SHEET_MIME_TYPE,
        modified_time=datetime(2026, 8, 27, 9, 0, 0, tzinfo=timezone.utc),
        owners=[],
        sharing_status="shared",
        project_tags=["Falcon"],
        content_snippet="Q1: $50k | Q2: $60k",
    )

    sheet_doc = SearchDocument.from_drive_metadata(drive_sheet)

    assert sheet_doc.id == "sheet_456"
    assert sheet_doc.name == "Falcon Budget 2026"
    assert sheet_doc.mime_type == GOOGLE_SHEET_MIME_TYPE
    assert sheet_doc.file_type == "spreadsheet"
    assert sheet_doc.primary_owner == "Shared Drive / Organization"
    assert sheet_doc.sharing_status == "shared"
    assert sheet_doc.project_tags == ["Falcon"]


def test_search_document_from_other_file_type() -> None:
    """Test transforming an arbitrary MIME type to SearchDocument."""
    other_file = DriveFileMetadata(
        id="pdf_789",
        name="Specs.pdf",
        mime_type="application/pdf",
        modified_time=None,
        created_time=None,
    )

    other_doc = SearchDocument.from_drive_metadata(other_file)

    assert other_doc.id == "pdf_789"
    assert other_doc.file_type == "other"
    assert other_doc.modified_time is None
    assert other_doc.created_time is None


def test_search_document_to_meili_dict() -> None:
    """Test serializing SearchDocument to JSON dictionary."""
    doc = SearchDocument(
        id="doc_001",
        name="Test",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        file_type="document",
        sharing_status="private",
    )
    data = doc.to_meili_dict()
    assert isinstance(data, dict)
    assert data["id"] == "doc_001"
    assert data["name"] == "Test"
    assert data["file_type"] == "document"
    assert data["project_tags"] == []


def test_index_settings_structure() -> None:
    """Verify canonical INDEX_SETTINGS configuration meets product requirements."""
    # Governed project_tags must be first searchable attribute
    assert INDEX_SETTINGS["searchableAttributes"][0] == "project_tags"
    assert INDEX_SETTINGS["searchableAttributes"][1] == "name"
    assert "content_snippet" in INDEX_SETTINGS["searchableAttributes"]

    # Filterable attributes must include file_type, sharing_status, and tags
    assert "file_type" in INDEX_SETTINGS["filterableAttributes"]
    assert "mime_type" in INDEX_SETTINGS["filterableAttributes"]
    assert "sharing_status" in INDEX_SETTINGS["filterableAttributes"]
    assert "project_tags" in INDEX_SETTINGS["filterableAttributes"]

    # Sortable attributes must include modified_time
    assert "modified_time" in INDEX_SETTINGS["sortableAttributes"]

    # Ranking rules must include words, typo, proximity, attribute, sort, exactness
    assert INDEX_SETTINGS["rankingRules"] == [
        "words",
        "typo",
        "proximity",
        "attribute",
        "sort",
        "exactness",
    ]

    # Typo tolerance enabled with min word sizes
    assert INDEX_SETTINGS["typoTolerance"]["enabled"] is True
    assert INDEX_SETTINGS["typoTolerance"]["minWordSizeForTypos"]["oneTypo"] == 4


def test_configure_index_schema_success() -> None:
    """Test successful schema application awaiting task completion."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_task = MagicMock()
    mock_task.task_uid = 99

    mock_task_result = MagicMock()
    mock_task_result.status = "succeeded"

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = mock_task_result
    mock_index.update_settings.return_value = mock_task
    mock_index.get_settings.return_value = INDEX_SETTINGS

    result = configure_index_schema(mock_client, "panopticon_docs")

    assert result == INDEX_SETTINGS
    mock_client.ensure_index.assert_called_once_with("panopticon_docs", primary_key="id")
    mock_index.update_settings.assert_called_once_with(INDEX_SETTINGS)
    mock_client.raw_client.wait_for_task.assert_called_once_with(99)
    mock_index.get_settings.assert_called_once()


def test_configure_index_schema_task_failure() -> None:
    """Test configure_index_schema raises IndexConfigurationError when task fails."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_task = MagicMock()
    mock_task.task_uid = 100

    mock_task_result = MagicMock()
    mock_task_result.status = "failed"
    mock_task_result.error = {"message": "Invalid ranking rules"}

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = mock_task_result
    mock_index.update_settings.return_value = mock_task

    with pytest.raises(IndexConfigurationError) as exc_info:
        configure_index_schema(mock_client, "panopticon_docs")
    assert "Meilisearch schema update task 100 failed" in str(exc_info.value)


def test_configure_index_schema_connection_error() -> None:
    """Test configure_index_schema raises SearchConnectionError on connection loss."""
    mock_client = MagicMock()
    mock_client.ensure_index.side_effect = Exception("Connection refused on port 7700")

    with pytest.raises(SearchConnectionError) as exc_info:
        configure_index_schema(mock_client, "panopticon_docs")
    assert "Cannot connect to Meilisearch" in str(exc_info.value)


def test_get_index_schema_success() -> None:
    """Test get_index_schema retrieves active settings."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_index.get_settings.return_value = {"searchableAttributes": ["name"]}
    mock_client.raw_client.index.return_value = mock_index

    settings = get_index_schema(mock_client, "panopticon_docs")
    assert settings == {"searchableAttributes": ["name"]}


def test_panopticon_search_client_schema_methods() -> None:
    """Test PanopticonSearchClient configure_schema and get_schema_settings helpers."""
    client = PanopticonSearchClient()

    mock_raw_client = MagicMock()
    mock_index = MagicMock()
    mock_task = MagicMock()
    mock_task.task_uid = 55

    mock_task_result = MagicMock()
    mock_task_result.status = "succeeded"

    mock_raw_client.get_index.return_value = mock_index
    mock_raw_client.index.return_value = mock_index
    mock_raw_client.wait_for_task.return_value = mock_task_result
    mock_index.update_settings.return_value = mock_task
    mock_index.get_settings.return_value = INDEX_SETTINGS

    client._client = mock_raw_client

    updated = client.configure_schema()
    assert updated == INDEX_SETTINGS

    current = client.get_schema_settings()
    assert current == INDEX_SETTINGS
