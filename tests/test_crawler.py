"""Unit tests for Google Drive Crawler, Models, and Pagination."""

from __future__ import annotations

from unittest.mock import MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError

from app.core.auth.exceptions import (
    DriveConnectionError,
    DrivePermissionDeniedError,
    DriveQuotaExceededError,
    DriveRateLimitError,
    DriveTimeoutError,
)
from app.indexer.crawler import (
    DEFAULT_DOCS_SHEETS_QUERY,
    DriveCrawler,
)
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
    sanitize_string,
)

# --- Helpers & Fixtures ---


def _make_http_error(status: int, reason: str = "Error", content: str = "") -> HttpError:
    """Construct a mock HttpError with specified status, reason, and body."""
    response = httplib2.Response({"status": status, "reason": reason})
    response.status = status
    response.reason = reason
    return HttpError(resp=response, content=content.encode("utf-8"))


# --- Tests for Models & Sanitization ---


def test_sanitize_string() -> None:
    """Test stripping illegal control characters and null bytes."""
    assert sanitize_string(None) is None
    assert sanitize_string("Clean String") == "Clean String"
    assert sanitize_string("Project\x00_Alpha\x08_Beta\x1f") == "Project_Alpha_Beta"
    assert sanitize_string("   Padded Title   ") == "Padded Title"


def test_drive_file_metadata_properties() -> None:
    """Test DriveFileMetadata model validation and computed properties."""
    doc = DriveFileMetadata(
        id="doc_123",
        name="Project Plan\x00",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        owners=["lead@company.com"],
        shared=True,
    )
    assert doc.id == "doc_123"
    assert doc.name == "Project Plan"
    assert doc.is_doc is True
    assert doc.is_sheet is False
    assert doc.primary_owner == "lead@company.com"

    sheet = DriveFileMetadata(
        id="sheet_456",
        name="Budget 2026",
        mime_type=GOOGLE_SHEET_MIME_TYPE,
        owners=[],
        shared=False,
    )
    assert sheet.is_doc is False
    assert sheet.is_sheet is True
    assert sheet.primary_owner == "Shared Drive / Organization"


def test_drive_file_metadata_dict_owners_and_parents() -> None:
    """Test parsing owners list containing Google API dict objects."""
    raw_owners = [
        {"emailAddress": "alice@company.com", "displayName": "Alice Admin"},
        {"displayName": "Bob Builder"},
    ]
    meta = DriveFileMetadata(
        id="file_789",
        name="Architecture Spec",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        owners=raw_owners,  # type: ignore[arg-type]
        parents=["folder_root", "folder_sub"],
    )
    assert meta.owners == ["alice@company.com", "Bob Builder"]
    assert meta.parents == ["folder_root", "folder_sub"]


# --- Tests for DriveCrawler ---


def test_crawler_page_size_validation() -> None:
    """Test page_size boundary validation."""
    mock_service = MagicMock()
    crawler = DriveCrawler(service=mock_service)

    with pytest.raises(ValueError, match="page_size must be between 1 and 1000"):
        list(crawler.crawl_files(page_size=0))

    with pytest.raises(ValueError, match="page_size must be between 1 and 1000"):
        list(crawler.crawl_files(page_size=1001))


def test_crawler_single_page_docs_and_sheets() -> None:
    """Test crawling a single page containing Docs and Sheets."""
    mock_service = MagicMock()
    mock_list_req = MagicMock()
    mock_service.files().list.return_value = mock_list_req

    mock_list_req.execute.return_value = {
        "files": [
            {
                "id": "doc_1",
                "name": "Sprint 10 Planning",
                "mimeType": GOOGLE_DOC_MIME_TYPE,
                "modifiedTime": "2026-08-20T10:00:00Z",
                "owners": [{"emailAddress": "dev1@company.com"}],
                "webViewLink": "https://docs.google.com/document/d/doc_1/edit",
            },
            {
                "id": "sheet_2",
                "name": "Q3 Revenue Model",
                "mimeType": GOOGLE_SHEET_MIME_TYPE,
                "modifiedTime": "2026-08-21T14:30:00Z",
                "owners": [{"emailAddress": "finance@company.com"}],
                "webViewLink": "https://docs.google.com/spreadsheets/d/sheet_2/edit",
            },
        ],
        "nextPageToken": None,
    }

    crawler = DriveCrawler(service=mock_service)
    results = crawler.crawl_all()

    assert len(results) == 2
    assert results[0].id == "doc_1"
    assert results[0].name == "Sprint 10 Planning"
    assert results[0].is_doc is True
    assert results[0].owners == ["dev1@company.com"]

    assert results[1].id == "sheet_2"
    assert results[1].name == "Q3 Revenue Model"
    assert results[1].is_sheet is True
    assert results[1].owners == ["finance@company.com"]

    # Verify query parameters passed to Google API
    mock_service.files().list.assert_called_once_with(
        q=DEFAULT_DOCS_SHEETS_QUERY,
        pageSize=100,
        fields=mock_service.files().list.call_args[1]["fields"],
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="allDrives",
    )


def test_crawler_multi_page_pagination() -> None:
    """Test 3-page cursor-based pagination loop without dropping items."""
    mock_service = MagicMock()
    mock_req_p1 = MagicMock()
    mock_req_p2 = MagicMock()
    mock_req_p3 = MagicMock()

    mock_req_p1.execute.return_value = {
        "files": [{"id": "p1_f1", "name": "Doc 1", "mimeType": GOOGLE_DOC_MIME_TYPE}],
        "nextPageToken": "token_page_2",
    }
    mock_req_p2.execute.return_value = {
        "files": [{"id": "p2_f2", "name": "Sheet 2", "mimeType": GOOGLE_SHEET_MIME_TYPE}],
        "nextPageToken": "token_page_3",
    }
    mock_req_p3.execute.return_value = {
        "files": [{"id": "p3_f3", "name": "Doc 3", "mimeType": GOOGLE_DOC_MIME_TYPE}],
        "nextPageToken": None,
    }

    # Sequence return for files().list(...)
    mock_service.files().list.side_effect = [mock_req_p1, mock_req_p2, mock_req_p3]

    crawler = DriveCrawler(service=mock_service)
    results = crawler.crawl_all(page_size=50)

    assert len(results) == 3
    assert [r.id for r in results] == ["p1_f1", "p2_f2", "p3_f3"]
    assert mock_service.files().list.call_count == 3


def test_crawler_custom_query_and_shared_drives_flags() -> None:
    """Test passing custom query filter and verifying Shared Drives parameters."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.return_value = {"files": [], "nextPageToken": None}
    mock_service.files().list.return_value = mock_req

    custom_query = "name contains 'Project Falcon'"
    crawler = DriveCrawler(service=mock_service)
    results = crawler.crawl_all(query_filter=custom_query, page_size=25)

    assert results == []
    mock_service.files().list.assert_called_once()
    kwargs = mock_service.files().list.call_args[1]
    assert kwargs["q"] == custom_query
    assert kwargs["pageSize"] == 25
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["includeItemsFromAllDrives"] is True
    assert kwargs["corpora"] == "allDrives"


def test_crawler_empty_drive_response() -> None:
    """Test crawling when Drive contains zero matching files."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.return_value = {"files": [], "nextPageToken": None}
    mock_service.files().list.return_value = mock_req

    crawler = DriveCrawler(service=mock_service)
    results = list(crawler.crawl_files())
    assert results == []


def test_crawler_cyclic_token_detection() -> None:
    """Test infinite loop protection if API returns cyclic nextPageToken."""
    mock_service = MagicMock()
    mock_req1 = MagicMock()
    mock_req2 = MagicMock()

    mock_req1.execute.return_value = {
        "files": [{"id": "f1", "name": "File 1", "mimeType": GOOGLE_DOC_MIME_TYPE}],
        "nextPageToken": "cyclic_token_1",
    }
    mock_req2.execute.return_value = {
        "files": [{"id": "f2", "name": "File 2", "mimeType": GOOGLE_DOC_MIME_TYPE}],
        "nextPageToken": "cyclic_token_1",  # Same token repeated
    }
    mock_service.files().list.side_effect = [mock_req1, mock_req2]

    crawler = DriveCrawler(service=mock_service)
    with pytest.raises(RuntimeError, match="Cyclic pagination token detected"):
        crawler.crawl_all()


def test_crawler_max_pages_ceiling() -> None:
    """Test bounding crawl by max_pages parameter."""
    mock_service = MagicMock()
    mock_req1 = MagicMock()
    mock_req2 = MagicMock()
    mock_req1.execute.return_value = {
        "files": [{"id": "f1", "name": "File 1", "mimeType": GOOGLE_DOC_MIME_TYPE}],
        "nextPageToken": "next_token_1",
    }
    mock_req2.execute.return_value = {
        "files": [{"id": "f2", "name": "File 2", "mimeType": GOOGLE_DOC_MIME_TYPE}],
        "nextPageToken": "next_token_2",
    }
    mock_service.files().list.side_effect = [mock_req1, mock_req2]

    crawler = DriveCrawler(service=mock_service)
    results = crawler.crawl_all(max_pages=2)

    assert len(results) == 2
    assert mock_service.files().list.call_count == 2


def test_crawler_rate_limit_error_remapping() -> None:
    """Test remapping HTTP 429 to DriveRateLimitError."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.side_effect = _make_http_error(429, "Too Many Requests", "User rate limit exceeded")
    mock_service.files().list.return_value = mock_req

    crawler = DriveCrawler(service=mock_service)
    with pytest.raises(DriveRateLimitError):
        crawler.crawl_all()


def test_crawler_quota_exceeded_error_remapping() -> None:
    """Test remapping HTTP 403 quota error to DriveQuotaExceededError."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.side_effect = _make_http_error(403, "Forbidden", "Daily Limit Exceeded quota")
    mock_service.files().list.return_value = mock_req

    crawler = DriveCrawler(service=mock_service)
    with pytest.raises(DriveQuotaExceededError):
        crawler.crawl_all()


def test_crawler_permission_denied_remapping() -> None:
    """Test remapping HTTP 403 permission error to DrivePermissionDeniedError."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.side_effect = _make_http_error(403, "Forbidden", "The caller does not have permission")
    mock_service.files().list.return_value = mock_req

    crawler = DriveCrawler(service=mock_service)
    with pytest.raises(DrivePermissionDeniedError):
        crawler.crawl_all()


def test_crawler_crawl_with_stats() -> None:
    """Test crawl_with_stats telemetry data collection."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.return_value = {
        "files": [
            {"id": "doc1", "name": "Doc A", "mimeType": GOOGLE_DOC_MIME_TYPE},
            {"id": "sheet1", "name": "Sheet B", "mimeType": GOOGLE_SHEET_MIME_TYPE},
            {"id": "other1", "name": "File C", "mimeType": "application/pdf"},
        ],
        "nextPageToken": None,
    }
    mock_service.files().list.return_value = mock_req

    crawler = DriveCrawler(service=mock_service)
    files, stats = crawler.crawl_with_stats()

    assert len(files) == 3
    assert stats.files_discovered == 3
    assert stats.docs_count == 1
    assert stats.sheets_count == 1
    assert stats.other_count == 1
    assert stats.duration_seconds >= 0.0
    assert stats.end_time is not None


def test_crawler_socket_timeout_remapping() -> None:
    """Test remapping socket TimeoutError to DriveTimeoutError."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.side_effect = TimeoutError("The read operation timed out")
    mock_service.files().list.return_value = mock_req

    crawler = DriveCrawler(service=mock_service)
    with pytest.raises(DriveTimeoutError):
        crawler.crawl_all()


def test_crawler_connection_error_remapping() -> None:
    """Test remapping ConnectionResetError to DriveConnectionError."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_req.execute.side_effect = ConnectionResetError("Connection reset by peer")
    mock_service.files().list.return_value = mock_req

    crawler = DriveCrawler(service=mock_service)
    with pytest.raises(DriveConnectionError):
        crawler.crawl_all()
