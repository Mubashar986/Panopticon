"""Unit tests for Google Drive Permissions Parsing and Sharing Status Classification."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.indexer.crawler import DriveCrawler
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    DrivePermission,
)
from app.indexer.permissions import PermissionClassifier


def test_parse_permissions_empty_and_none() -> None:
    """Test parse_permissions safely returns empty list on None or invalid input."""
    assert PermissionClassifier.parse_permissions(None) == []
    assert PermissionClassifier.parse_permissions([]) == []
    assert PermissionClassifier.parse_permissions(["not_a_dict"]) == []  # type: ignore[arg-type,list-item]


def test_parse_permissions_full_payload() -> None:
    """Test parsing structured permissions from Google Drive API."""
    raw: list[dict[str, Any]] = [
        {
            "id": "perm_user_1",
            "role": "owner",
            "type": "user",
            "emailAddress": "lead@company.com\x00",
            "displayName": "Team Lead",
        },
        {
            "id": "perm_domain_1",
            "role": "reader",
            "type": "domain",
            "domain": "company.com",
            "allowFileDiscovery": True,
        },
    ]

    perms = PermissionClassifier.parse_permissions(raw)
    assert len(perms) == 2

    # Check user perm
    p1 = perms[0]
    assert p1.id == "perm_user_1"
    assert p1.role == "owner"
    assert p1.type == "user"
    assert p1.email_address == "lead@company.com"  # Sanitized null byte
    assert p1.display_name == "Team Lead"

    # Check domain perm
    p2 = perms[1]
    assert p2.id == "perm_domain_1"
    assert p2.role == "reader"
    assert p2.type == "domain"
    assert p2.domain == "company.com"
    assert p2.allow_file_discovery is True


def test_classify_sharing_status_anyone() -> None:
    """Test public web visibility classification."""
    perms = [
        DrivePermission(id="p1", role="reader", type="anyone"),
    ]
    status = PermissionClassifier.classify_sharing_status(shared=True, permissions=perms)
    assert status == "anyone"


def test_classify_sharing_status_domain() -> None:
    """Test organization domain-wide visibility classification."""
    perms = [
        DrivePermission(id="p1", role="owner", type="user", email_address="owner@co.com"),
        DrivePermission(id="p2", role="reader", type="domain", domain="company.com"),
    ]
    status = PermissionClassifier.classify_sharing_status(shared=True, permissions=perms)
    assert status == "domain"


def test_classify_sharing_status_shared_team() -> None:
    """Test team shared file visibility classification."""
    perms = [
        DrivePermission(id="p1", role="owner", type="user", email_address="owner@co.com"),
        DrivePermission(id="p2", role="writer", type="user", email_address="dev@co.com"),
    ]
    status = PermissionClassifier.classify_sharing_status(shared=True, permissions=perms)
    assert status == "shared"


def test_classify_sharing_status_private() -> None:
    """Test private single-owner visibility classification."""
    perms = [
        DrivePermission(id="p1", role="owner", type="user", email_address="owner@co.com"),
    ]
    status = PermissionClassifier.classify_sharing_status(shared=False, permissions=perms)
    assert status == "private"


def test_classify_sharing_status_shared_drive() -> None:
    """Test Shared Drive files automatically inherit 'shared' status."""
    status = PermissionClassifier.classify_sharing_status(
        shared=False,
        permissions=[],
        drive_id="0AJ_shared_drive_123",
    )
    assert status == "shared"


def test_classify_sharing_status_hierarchy_anyone_over_domain() -> None:
    """Test that public link access ('anyone') takes precedence over 'domain'."""
    perms = [
        DrivePermission(id="p1", role="reader", type="domain", domain="co.com"),
        DrivePermission(id="p2", role="reader", type="anyone"),
    ]
    status = PermissionClassifier.classify_sharing_status(shared=True, permissions=perms)
    assert status == "anyone"


def test_crawler_integration_with_permissions() -> None:
    """Test DriveCrawler populating permissions and sharing_status across files."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().list.return_value = mock_req

    mock_req.execute.return_value = {
        "files": [
            {
                "id": "file_public",
                "name": "Public Whitepaper",
                "mimeType": GOOGLE_DOC_MIME_TYPE,
                "shared": True,
                "permissions": [{"id": "p1", "role": "reader", "type": "anyone"}],
            },
            {
                "id": "file_domain",
                "name": "Company Policy",
                "mimeType": GOOGLE_DOC_MIME_TYPE,
                "shared": True,
                "permissions": [{"id": "p2", "role": "reader", "type": "domain", "domain": "org.com"}],
            },
            {
                "id": "file_private",
                "name": "Personal Scratchpad",
                "mimeType": GOOGLE_DOC_MIME_TYPE,
                "shared": False,
                "permissions": [{"id": "p3", "role": "owner", "type": "user", "emailAddress": "me@org.com"}],
            },
        ],
        "nextPageToken": None,
    }

    crawler = DriveCrawler(service=mock_service)
    results = crawler.crawl_all()

    assert len(results) == 3

    assert results[0].id == "file_public"
    assert results[0].sharing_status == "anyone"
    assert len(results[0].permissions) == 1

    assert results[1].id == "file_domain"
    assert results[1].sharing_status == "domain"

    assert results[2].id == "file_private"
    assert results[2].sharing_status == "private"
