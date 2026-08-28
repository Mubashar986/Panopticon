"""Unit tests for Google Drive Content Exporter and 10MB Cap Handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import httplib2
from googleapiclient.errors import HttpError

from app.indexer.exporter import ContentExporter
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
)


def _make_http_error(status: int, reason: str = "Error", content: str = "") -> HttpError:
    """Construct a mock HttpError with specified status, reason, and body."""
    response = httplib2.Response({"status": status, "reason": reason})
    response.status = status
    response.reason = reason
    return HttpError(resp=response, content=content.encode("utf-8"))


def test_get_target_export_mime() -> None:
    """Test mapping Google Workspace MIME types to plain text formats."""
    exporter = ContentExporter(service=MagicMock())
    assert exporter.get_target_export_mime(GOOGLE_DOC_MIME_TYPE) == "text/plain"
    assert exporter.get_target_export_mime(GOOGLE_SHEET_MIME_TYPE) == "text/csv"
    assert exporter.get_target_export_mime("application/pdf") is None
    assert exporter.get_target_export_mime("image/png") is None


def test_export_file_content_doc_success() -> None:
    """Test exporting a normal-size Google Doc to text/plain."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    mock_req.execute.return_value = b"Project Falcon Kickoff Notes\nThis is a test document."

    exporter = ContentExporter(service=mock_service)
    result = exporter.export_file_content(
        file_id="doc_123",
        mime_type=GOOGLE_DOC_MIME_TYPE,
    )

    assert result.status == "success"
    assert result.file_id == "doc_123"
    assert result.content_text == "Project Falcon Kickoff Notes\nThis is a test document."
    assert result.snippet == "Project Falcon Kickoff Notes This is a test document."
    assert result.size_bytes == len(b"Project Falcon Kickoff Notes\nThis is a test document.")

    mock_service.files().export_media.assert_called_once_with(
        fileId="doc_123",
        mimeType="text/plain",
    )


def test_export_file_content_sheet_success() -> None:
    """Test exporting a normal-size Google Sheet to text/csv."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    mock_req.execute.return_value = b"Project,Budget,Owner\nFalcon,50000,lead@company.com"

    exporter = ContentExporter(service=mock_service)
    result = exporter.export_file_content(
        file_id="sheet_456",
        mime_type=GOOGLE_SHEET_MIME_TYPE,
    )

    assert result.status == "success"
    assert result.file_id == "sheet_456"
    assert "Falcon,50000" in (result.content_text or "")
    mock_service.files().export_media.assert_called_once_with(
        fileId="sheet_456",
        mimeType="text/csv",
    )


def test_export_file_content_unsupported_mime() -> None:
    """Test that binary/unsupported MIME types are skipped without API calls."""
    mock_service = MagicMock()
    exporter = ContentExporter(service=mock_service)

    result = exporter.export_file_content(
        file_id="pdf_789",
        mime_type="application/pdf",
    )

    assert result.status == "skipped_unsupported_mime"
    assert result.snippet is None
    mock_service.files().export_media.assert_not_called()


def test_export_file_content_oversized_403_export_limit() -> None:
    """Test catching Google Drive 10MB conversion limit 403 exportSizeLimitExceeded."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    mock_req.execute.side_effect = _make_http_error(
        403,
        reason="exportSizeLimitExceeded",
        content="This file is too large to be exported.",
    )

    exporter = ContentExporter(service=mock_service)
    result = exporter.export_file_content(
        file_id="giant_sheet_999",
        mime_type=GOOGLE_SHEET_MIME_TYPE,
    )

    assert result.status == "oversized_metadata_only"
    assert result.snippet == "[Oversized file: indexed by metadata only]"
    assert result.content_text is None


def test_export_file_content_oversized_payload_bytes() -> None:
    """Test catching byte payload exceeding max_export_bytes threshold."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    # 2MB payload when limit is set to 1MB
    mock_req.execute.return_value = b"X" * (2 * 1024 * 1024)

    exporter = ContentExporter(
        service=mock_service,
        max_export_bytes=1024 * 1024,  # 1MB cap for test
    )
    result = exporter.export_file_content(
        file_id="large_doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
    )

    assert result.status == "oversized_metadata_only"
    assert result.snippet == "[Oversized file: indexed by metadata only]"
    assert result.size_bytes == 2 * 1024 * 1024


def test_export_file_content_permission_denied() -> None:
    """Test catching standard HTTP 403 forbidden error."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    mock_req.execute.side_effect = _make_http_error(
        403,
        reason="Forbidden",
        content="The caller does not have permission.",
    )

    exporter = ContentExporter(service=mock_service)
    result = exporter.export_file_content(
        file_id="private_doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
    )

    assert result.status == "failed_metadata_only"
    assert "Forbidden" in (result.error_message or "")


def test_export_file_content_sanitizes_null_bytes() -> None:
    """Test that null bytes and control characters are stripped from exported content."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    mock_req.execute.return_value = b"Project\x00_Falcon\x08_Report\x1f"

    exporter = ContentExporter(service=mock_service)
    result = exporter.export_file_content(
        file_id="dirty_doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
    )

    assert result.status == "success"
    assert result.content_text == "Project_Falcon_Report"
    assert result.snippet == "Project_Falcon_Report"


def test_export_file_content_snippet_bounding() -> None:
    """Test that search snippet is bounded to max_snippet_chars."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    # 1000 characters of text
    long_text = "A" * 1000
    mock_req.execute.return_value = long_text.encode("utf-8")

    exporter = ContentExporter(
        service=mock_service,
        max_snippet_chars=50,
    )
    result = exporter.export_file_content(
        file_id="long_doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
    )

    assert result.status == "success"
    assert len(result.content_text or "") == 1000
    assert len(result.snippet or "") == 50
    assert result.snippet == "A" * 50


def test_export_and_attach() -> None:
    """Test export_and_attach updating DriveFileMetadata."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().export_media.return_value = mock_req
    mock_req.execute.return_value = b"Executive Summary: Falcon launch is ready."

    exporter = ContentExporter(service=mock_service)
    meta = DriveFileMetadata(
        id="meta_1",
        name="Falcon Executive Summary",
        mime_type=GOOGLE_DOC_MIME_TYPE,
    )

    updated_meta = exporter.export_and_attach(meta)

    assert updated_meta.id == "meta_1"
    assert updated_meta.export_status == "success"
    assert updated_meta.content_snippet == "Executive Summary: Falcon launch is ready."
