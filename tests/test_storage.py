"""Unit tests for SQLite Local CrawlStorage Repository."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
    DriveLabel,
    DriveLabelField,
    DrivePermission,
)
from app.indexer.storage import CrawlStorage


def test_storage_init_and_tables(tmp_path: Path) -> None:
    """Test initializing storage creates database file and tables."""
    db_file = tmp_path / "test_crawl.db"
    storage = CrawlStorage(db_path=db_file)

    assert db_file.exists()
    assert storage.count_files() == 0
    assert storage.get_watermark() is None


def test_storage_watermark_crud(tmp_path: Path) -> None:
    """Test setting, retrieving, and updating watermark timestamps."""
    storage = CrawlStorage(db_path=tmp_path / "watermark.db")
    assert storage.get_watermark() is None

    wm1 = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
    storage.set_watermark(wm1)

    read_wm1 = storage.get_watermark()
    assert read_wm1 == wm1

    wm2 = datetime(2026, 8, 28, 15, 30, 0, tzinfo=timezone.utc)
    storage.set_watermark(wm2)

    read_wm2 = storage.get_watermark()
    assert read_wm2 == wm2


def test_storage_upsert_and_get_file(tmp_path: Path) -> None:
    """Test storing and reading back a complete DriveFileMetadata entity."""
    storage = CrawlStorage(db_path=tmp_path / "files.db")

    field = DriveLabelField(id="fld_proj", values=["Falcon"], display_value="Falcon")
    label = DriveLabel(id="lbl_gov", fields={"fld_proj": field})
    perm = DrivePermission(id="p1", role="owner", type="user", email_address="lead@co.com")

    file = DriveFileMetadata(
        id="doc_falcon_01",
        name="Project Falcon Master Plan",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        modified_time=datetime(2026, 8, 27, 10, 0, 0, tzinfo=timezone.utc),
        created_time=datetime(2026, 8, 20, 8, 0, 0, tzinfo=timezone.utc),
        owners=["lead@co.com"],
        last_modifying_user="editor@co.com",
        shared=True,
        web_view_link="https://docs.google.com/document/d/doc_falcon_01",
        icon_link="https://drive.google.com/icon.png",
        size_bytes=4096,
        parents=["folder_root"],
        drive_id="shared_drive_99",
        sharing_status="domain",
        permissions=[perm],
        labels=[label],
        project_tags=["Falcon"],
        content_snippet="Falcon launch architecture overview...",
        export_status="success",
    )

    storage.upsert_file(file)

    retrieved = storage.get_file("doc_falcon_01")
    assert retrieved is not None
    assert retrieved.id == "doc_falcon_01"
    assert retrieved.name == "Project Falcon Master Plan"
    assert retrieved.mime_type == GOOGLE_DOC_MIME_TYPE
    assert retrieved.modified_time == datetime(2026, 8, 27, 10, 0, 0, tzinfo=timezone.utc)
    assert retrieved.owners == ["lead@co.com"]
    assert retrieved.last_modifying_user == "editor@co.com"
    assert retrieved.sharing_status == "domain"
    assert len(retrieved.permissions) == 1
    assert retrieved.permissions[0].email_address == "lead@co.com"
    assert retrieved.project_tags == ["Falcon"]
    assert retrieved.content_snippet == "Falcon launch architecture overview..."
    assert retrieved.export_status == "success"


def test_storage_upsert_conflict_update(tmp_path: Path) -> None:
    """Test that upserting with same ID updates row in place without duplicating."""
    storage = CrawlStorage(db_path=tmp_path / "upsert.db")

    f1 = DriveFileMetadata(
        id="file_1",
        name="Version 1",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        content_snippet="Old content",
    )
    storage.upsert_file(f1)
    assert storage.count_files() == 1

    f1_updated = DriveFileMetadata(
        id="file_1",
        name="Version 2",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        content_snippet="New updated content",
    )
    storage.upsert_file(f1_updated)

    assert storage.count_files() == 1
    stored = storage.get_file("file_1")
    assert stored is not None
    assert stored.name == "Version 2"
    assert stored.content_snippet == "New updated content"


def test_storage_list_files_pagination(tmp_path: Path) -> None:
    """Test listing and paginating files from SQLite storage."""
    storage = CrawlStorage(db_path=tmp_path / "pagination.db")

    files = [
        DriveFileMetadata(
            id=f"doc_{i:02d}",
            name=f"Doc {i}",
            mime_type=GOOGLE_DOC_MIME_TYPE,
            modified_time=datetime(2026, 8, 10 + i, 0, 0, tzinfo=timezone.utc),
        )
        for i in range(5)
    ]
    storage.upsert_files(files)

    assert storage.count_files() == 5

    page1 = storage.list_files(limit=2, offset=0)
    assert len(page1) == 2
    # Ordered by modified_time DESC (doc_04, doc_03)
    assert page1[0].id == "doc_04"
    assert page1[1].id == "doc_03"

    page2 = storage.list_files(limit=2, offset=2)
    assert len(page2) == 2
    assert page2[0].id == "doc_02"
    assert page2[1].id == "doc_01"


def test_storage_get_all_file_ids_and_delete(tmp_path: Path) -> None:
    """Test retrieving set of file IDs and batch deleting stale records."""
    storage = CrawlStorage(db_path=tmp_path / "delete.db")

    files = [
        DriveFileMetadata(id="f1", name="Doc 1", mime_type=GOOGLE_DOC_MIME_TYPE),
        DriveFileMetadata(id="f2", name="Doc 2", mime_type=GOOGLE_DOC_MIME_TYPE),
        DriveFileMetadata(id="f3", name="Sheet 1", mime_type=GOOGLE_SHEET_MIME_TYPE),
    ]
    storage.upsert_files(files)

    ids = storage.get_all_file_ids()
    assert ids == {"f1", "f2", "f3"}

    deleted_count = storage.delete_files(["f1", "f3"])
    assert deleted_count == 2
    assert storage.count_files() == 1
    assert storage.get_all_file_ids() == {"f2"}
    assert storage.get_file("f1") is None
