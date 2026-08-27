"""Unit tests for Google Drive client construction and smoke-test utilities."""

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.core.auth import (
    DriveAuthProvider,
    DrivePermissionDeniedError,
    DriveQuotaExceededError,
    DriveRateLimitError,
    build_drive_service,
)
from scripts.smoke_test_drive import format_mime_type, format_timestamp, run_smoke_test


def test_build_drive_service_success():
    """Verify build_drive_service initializes resource with credentials."""
    mock_provider = MagicMock(spec=DriveAuthProvider)
    mock_provider.provider_name = "MockProvider"
    mock_creds = MagicMock()
    mock_provider.get_credentials.return_value = mock_creds

    with patch("app.core.auth.client.build") as mock_build:
        mock_resource = MagicMock()
        mock_build.return_value = mock_resource

        service = build_drive_service(mock_provider)
        mock_provider.get_credentials.assert_called_once()
        mock_build.assert_called_once_with(
            "drive", "v3", credentials=mock_creds, cache_discovery=False
        )
        assert service == mock_resource


def test_build_drive_service_rate_limit_error():
    """Verify HTTP 429 or rate limit error maps to DriveRateLimitError."""
    mock_provider = MagicMock(spec=DriveAuthProvider)
    mock_resp = Response({"status": "429"})
    mock_provider.get_credentials.side_effect = HttpError(
        resp=mock_resp, content=b"userRateLimitExceeded"
    )

    with pytest.raises(DriveRateLimitError) as exc_info:
        build_drive_service(mock_provider)

    assert "rate limit reached" in str(exc_info.value).lower()


def test_build_drive_service_quota_error():
    """Verify HTTP 403 quota exceeded maps to DriveQuotaExceededError."""
    mock_provider = MagicMock(spec=DriveAuthProvider)
    mock_resp = Response({"status": "403"})
    mock_provider.get_credentials.side_effect = HttpError(
        resp=mock_resp, content=b"quotaExceeded"
    )

    with pytest.raises(DriveQuotaExceededError) as exc_info:
        build_drive_service(mock_provider)

    assert "quota exhausted" in str(exc_info.value).lower()


def test_build_drive_service_permission_denied_error():
    """Verify HTTP 403 permission error maps to DrivePermissionDeniedError."""
    mock_provider = MagicMock(spec=DriveAuthProvider)
    mock_resp = Response({"status": "403"})
    mock_provider.get_credentials.side_effect = HttpError(
        resp=mock_resp, content=b"insufficientPermissions"
    )

    with pytest.raises(DrivePermissionDeniedError) as exc_info:
        build_drive_service(mock_provider)

    assert "permission denied" in str(exc_info.value).lower()


def test_format_mime_type():
    """Verify MIME type formatting for Google Docs and binary types."""
    assert format_mime_type("application/vnd.google-apps.document") == "Google Doc"
    assert format_mime_type("application/vnd.google-apps.spreadsheet") == "Google Sheet"
    assert format_mime_type("application/pdf") == "PDF Document"
    assert format_mime_type("image/png") == "PNG"


def test_format_timestamp():
    """Verify ISO timestamp formatting."""
    assert format_timestamp(None) == "N/A"
    assert format_timestamp("2026-08-27T10:15:30.000Z") == "2026-08-27 10:15"


def test_run_smoke_test_with_mock_files(monkeypatch):
    """Verify run_smoke_test executes query and parses file response."""
    mock_service = MagicMock()
    mock_files_resource = MagicMock()
    mock_list_req = MagicMock()

    mock_files_resource.list.return_value = mock_list_req
    mock_list_req.execute.return_value = {
        "files": [
            {
                "id": "file_123",
                "name": "Q3 Financial Plan",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "modifiedTime": "2026-08-25T14:30:00Z",
            }
        ]
    }
    mock_service.files.return_value = mock_files_resource

    with patch("scripts.smoke_test_drive.build_drive_service", return_value=mock_service):
        exit_code = run_smoke_test(page_size=5)
        assert exit_code == 0
        mock_files_resource.list.assert_called_once()
