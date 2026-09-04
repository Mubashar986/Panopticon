"""Unit tests for Dossiers relational schema and repository methods in CrawlStorage."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.indexer.models import (
    DriveFileMetadata,
    GOOGLE_DOC_MIME_TYPE,
)
from app.indexer.storage import CrawlStorage


def _create_sample_file(file_id: str, name: str) -> DriveFileMetadata:
    """Helper to generate a mock DriveFileMetadata."""
    return DriveFileMetadata(
        id=file_id,
        name=name,
        mime_type=GOOGLE_DOC_MIME_TYPE,
        created_time=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
        modified_time=datetime(2026, 8, 25, 14, 30, 0, tzinfo=timezone.utc),
        owners=["author@company.com"],
        last_modifying_user="editor@company.com",
        shared=True,
        web_view_link=f"https://docs.google.com/document/d/{file_id}/view",
        sharing_status="domain",
        project_tags=["Falcon"],
        content_snippet="Test document excerpt snippet.",
    )


def test_dossier_create_and_get(tmp_path: Path) -> None:
    """Test creating a dossier, automatic slug creation, admin membership, and retrieval."""
    storage = CrawlStorage(db_path=tmp_path / "dossiers.db")

    dossier = storage.create_dossier(
        name="Project Falcon Launch",
        description="Falcon initiative primary documents",
        color="#2563EB",
        icon="rocket",
        created_by="lead@company.com",
    )

    assert dossier.id.startswith("dos_")
    assert dossier.name == "Project Falcon Launch"
    assert dossier.slug == "project-falcon-launch"
    assert dossier.description == "Falcon initiative primary documents"
    assert dossier.color == "#2563EB"
    assert dossier.icon == "rocket"
    assert dossier.status == "active"
    assert dossier.created_by == "lead@company.com"

    # Retrieve by ID
    fetched = storage.get_dossier(dossier.id)
    assert fetched is not None
    assert fetched.id == dossier.id
    assert fetched.name == dossier.name

    # Retrieve by slug
    by_slug = storage.get_dossier_by_slug("project-falcon-launch")
    assert by_slug is not None
    assert by_slug.id == dossier.id

    # Verify auto-created admin member
    members = storage.list_dossier_members(dossier.id)
    assert len(members) == 1
    assert members[0].user_email == "lead@company.com"
    assert members[0].role == "admin"


def test_dossier_slug_collision_resolution(tmp_path: Path) -> None:
    """Test that creating dossiers with identical names automatically dedupes slugs."""
    storage = CrawlStorage(db_path=tmp_path / "slug_test.db")

    d1 = storage.create_dossier(name="Q4 Strategy")
    d2 = storage.create_dossier(name="Q4 Strategy")
    d3 = storage.create_dossier(name="Q4 Strategy")

    assert d1.slug == "q4-strategy"
    assert d2.slug == "q4-strategy-2"
    assert d3.slug == "q4-strategy-3"


def test_dossier_list_with_aggregations(tmp_path: Path) -> None:
    """Test listing dossiers with item and member count aggregations, status filtering, and sorting."""
    storage = CrawlStorage(db_path=tmp_path / "list_test.db")

    # Seed files
    storage.upsert_file(_create_sample_file("doc_1", "Doc One"))
    storage.upsert_file(_create_sample_file("doc_2", "Doc Two"))
    storage.upsert_file(_create_sample_file("doc_3", "Doc Three"))

    # Create dossiers
    d1 = storage.create_dossier(
        name="Alpha Project",
        created_by="alpha@company.com",
        initial_file_ids=["doc_1", "doc_2"],
    )
    d2 = storage.create_dossier(
        name="Beta Project",
        status="archived",
        created_by="beta@company.com",
        initial_file_ids=["doc_3"],
    )

    # Add extra member to Alpha
    storage.add_dossier_member(d1.id, "viewer@company.com", role="viewer")

    # List all
    all_dossiers, total = storage.list_dossiers()
    assert total == 2
    assert len(all_dossiers) == 2

    alpha_summary = next(d for d in all_dossiers if d.id == d1.id)
    assert alpha_summary.item_count == 2
    assert alpha_summary.member_count == 2

    beta_summary = next(d for d in all_dossiers if d.id == d2.id)
    assert beta_summary.item_count == 1
    assert beta_summary.member_count == 1

    # Filter by active
    active_dossiers, active_total = storage.list_dossiers(status="active")
    assert active_total == 1
    assert active_dossiers[0].id == d1.id

    # Filter by archived
    archived_dossiers, arch_total = storage.list_dossiers(status="archived")
    assert arch_total == 1
    assert archived_dossiers[0].id == d2.id


def test_dossier_update(tmp_path: Path) -> None:
    """Test updating dossier metadata and status."""
    storage = CrawlStorage(db_path=tmp_path / "update_test.db")

    dossier = storage.create_dossier(name="Initial Name", description="Old desc")

    updated = storage.update_dossier(
        dossier.id,
        name="Revised Name",
        description="New desc",
        color="#10B981",
        icon="briefcase",
        status="archived",
    )

    assert updated is not None
    assert updated.name == "Revised Name"
    assert updated.description == "New desc"
    assert updated.color == "#10B981"
    assert updated.icon == "briefcase"
    assert updated.status == "archived"
    assert updated.updated_at >= dossier.updated_at


def test_dossier_delete_cascade_and_file_preservation(tmp_path: Path) -> None:
    """Test deleting a dossier deletes its items/members via CASCADE but PRESERVES file_records."""
    storage = CrawlStorage(db_path=tmp_path / "cascade_test.db")

    # Seed file
    storage.upsert_file(_create_sample_file("preserved_file", "Preserved Document"))

    dossier = storage.create_dossier(
        name="Temporary Project",
        created_by="temp@company.com",
        initial_file_ids=["preserved_file"],
    )

    # Add extra member
    storage.add_dossier_member(dossier.id, "collab@company.com", role="editor")

    # Verify associations exist
    files, count = storage.list_dossier_items(dossier.id)
    assert count == 1
    assert files[0].id == "preserved_file"

    members = storage.list_dossier_members(dossier.id)
    assert len(members) == 2

    # Delete dossier
    deleted = storage.delete_dossier(dossier.id)
    assert deleted is True

    # Dossier and its links should be gone
    assert storage.get_dossier(dossier.id) is None
    files_after, count_after = storage.list_dossier_items(dossier.id)
    assert count_after == 0
    members_after = storage.list_dossier_members(dossier.id)
    assert len(members_after) == 0

    # Underlying Google Drive file MUST still exist in file_records
    persisted_file = storage.get_file("preserved_file")
    assert persisted_file is not None
    assert persisted_file.name == "Preserved Document"


def test_dossier_items_management(tmp_path: Path) -> None:
    """Test adding, listing, and removing files from a dossier."""
    storage = CrawlStorage(db_path=tmp_path / "items_test.db")

    storage.upsert_file(_create_sample_file("f1", "File 1"))
    storage.upsert_file(_create_sample_file("f2", "File 2"))

    dossier = storage.create_dossier(name="Items Project")

    # Add items
    added = storage.add_dossier_items(dossier.id, ["f1", "f2"], added_by="admin@company.com")
    assert added == 2

    # Idempotent re-add should not duplicate
    re_added = storage.add_dossier_items(dossier.id, ["f1", "f2"])
    assert re_added == 0

    files, total = storage.list_dossier_items(dossier.id)
    assert total == 2
    assert len(files) == 2

    # Remove one item
    removed = storage.remove_dossier_item(dossier.id, "f1")
    assert removed is True

    files_remaining, total_remaining = storage.list_dossier_items(dossier.id)
    assert total_remaining == 1
    assert files_remaining[0].id == "f2"


def test_dossier_members_management(tmp_path: Path) -> None:
    """Test adding, role updating, listing, and removing dossier members."""
    storage = CrawlStorage(db_path=tmp_path / "members_test.db")

    dossier = storage.create_dossier(name="Team Project")

    # Add member as viewer
    m1 = storage.add_dossier_member(dossier.id, "alice@company.com", role="viewer")
    assert m1.role == "viewer"
    assert m1.user_email == "alice@company.com"

    # Update role to editor
    m1_updated = storage.add_dossier_member(dossier.id, "alice@company.com", role="editor")
    assert m1_updated.role == "editor"

    members = storage.list_dossier_members(dossier.id)
    assert len(members) == 1
    assert members[0].role == "editor"

    # Remove member
    removed = storage.remove_dossier_member(dossier.id, "alice@company.com")
    assert removed is True
    assert len(storage.list_dossier_members(dossier.id)) == 0
