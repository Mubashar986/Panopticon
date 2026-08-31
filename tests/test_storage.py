"""Unit tests for SQLite Local CrawlStorage Repository."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DocumentDiff,
    DocumentVersion,
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


def test_storage_version_crud_and_history(tmp_path: Path) -> None:
    """Test inserting and retrieving multiple version snapshots for a document."""
    storage = CrawlStorage(db_path=tmp_path / "versions.db")
    file_id = "doc_proj_01"

    # Upsert parent file record first
    storage.upsert_file(
        DriveFileMetadata(
            id=file_id,
            name="Project Spec",
            mime_type=GOOGLE_DOC_MIME_TYPE,
        )
    )

    assert storage.count_versions(file_id) == 0
    assert storage.get_latest_version(file_id) is None

    # Version 1
    v1 = DocumentVersion(
        id="ver_01",
        file_id=file_id,
        version_number=1,
        content_hash="hash_v1_aaa",
        snapshot_text="Initial project overview draft.",
        editor="alice@co.com",
        modified_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
    )
    saved_v1 = storage.save_version(v1)
    assert saved_v1.version_number == 1
    assert saved_v1.char_count == len("Initial project overview draft.")
    assert saved_v1.word_count == 4

    # Version 2
    v2 = DocumentVersion(
        id="ver_02",
        file_id=file_id,
        version_number=2,
        content_hash="hash_v2_bbb",
        snapshot_text="Initial project overview draft. Added architectural diagrams and security checklist.",
        editor="bob@co.com",
        modified_time=datetime(2026, 8, 21, 14, 30, tzinfo=timezone.utc),
    )
    storage.save_version(v2)

    # Version 3
    v3 = DocumentVersion(
        id="ver_03",
        file_id=file_id,
        version_number=3,
        content_hash="hash_v3_ccc",
        snapshot_text="Final signed off project spec with compliance guidelines.",
        editor="charlie@co.com",
        modified_time=datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc),
    )
    storage.save_version(v3)

    assert storage.count_versions(file_id) == 3
    assert storage.count_versions() == 3

    # Latest version check
    latest = storage.get_latest_version(file_id)
    assert latest is not None
    assert latest.id == "ver_03"
    assert latest.version_number == 3
    assert latest.editor == "charlie@co.com"
    assert latest.content_hash == "hash_v3_ccc"

    # Specific version lookup
    lookup_v2 = storage.get_version("ver_02")
    assert lookup_v2 is not None
    assert lookup_v2.id == "ver_02"
    assert lookup_v2.version_number == 2
    assert lookup_v2.editor == "bob@co.com"

    # Full history check (newest first)
    history = storage.get_version_history(file_id)
    assert len(history) == 3
    assert [v.version_number for v in history] == [3, 2, 1]
    assert [v.id for v in history] == ["ver_03", "ver_02", "ver_01"]


def test_storage_auto_version_increment(tmp_path: Path) -> None:
    """Test that version_number <= 0 automatically assigns next monotonic number."""
    storage = CrawlStorage(db_path=tmp_path / "auto_inc.db")
    file_id = "doc_auto"
    storage.upsert_file(
        DriveFileMetadata(id=file_id, name="Auto Doc", mime_type=GOOGLE_DOC_MIME_TYPE)
    )

    v1 = storage.save_version(
        DocumentVersion(
            id="v_a1",
            file_id=file_id,
            version_number=0,  # Should become 1
            content_hash="h1",
            snapshot_text="Text 1",
        )
    )
    assert v1.version_number == 1

    v2 = storage.save_version(
        DocumentVersion(
            id="v_a2",
            file_id=file_id,
            version_number=0,  # Should become 2
            content_hash="h2",
            snapshot_text="Text 2",
        )
    )
    assert v2.version_number == 2


def test_storage_diff_crud_and_lookup(tmp_path: Path) -> None:
    """Test storing and querying document difference records."""
    storage = CrawlStorage(db_path=tmp_path / "diffs.db")
    file_id = "doc_diff_01"
    storage.upsert_file(
        DriveFileMetadata(id=file_id, name="Diff Doc", mime_type=GOOGLE_DOC_MIME_TYPE)
    )

    v1 = storage.save_version(
        DocumentVersion(
            id="v1",
            file_id=file_id,
            version_number=1,
            content_hash="h1",
            snapshot_text="Line 1\nLine 2",
        )
    )
    v2 = storage.save_version(
        DocumentVersion(
            id="v2",
            file_id=file_id,
            version_number=2,
            content_hash="h2",
            snapshot_text="Line 1\nLine 2 updated\nLine 3 added",
        )
    )

    diff = DocumentDiff(
        id="diff_01_02",
        file_id=file_id,
        from_version_id=v1.id,
        to_version_id=v2.id,
        patch_text="@@ -1,2 +1,3 @@\n Line 1\n-Line 2\n+Line 2 updated\n+Line 3 added",
        ai_summary="Updated Line 2 and appended Line 3.",
        lines_added=2,
        lines_removed=1,
    )
    saved_diff = storage.save_diff(diff)
    assert saved_diff.id == "diff_01_02"
    assert storage.count_diffs(file_id) == 1

    diffs = storage.get_diffs(file_id)
    assert len(diffs) == 1
    assert diffs[0].lines_added == 2
    assert diffs[0].lines_removed == 1
    assert diffs[0].ai_summary == "Updated Line 2 and appended Line 3."

    # Direct from->to lookup
    direct = storage.get_diff_between(v1.id, v2.id)
    assert direct is not None
    assert direct.id == "diff_01_02"
    assert direct.patch_text == diff.patch_text

    # Non-existent pair
    assert storage.get_diff_between("v2", "v1") is None


def test_storage_cascade_delete_versions_and_diffs(tmp_path: Path) -> None:
    """Test that deleting a file record automatically cascades and cleans up versions and diffs."""
    storage = CrawlStorage(db_path=tmp_path / "cascade.db")
    file_id = "doc_to_delete"

    storage.upsert_file(
        DriveFileMetadata(id=file_id, name="Temp Doc", mime_type=GOOGLE_DOC_MIME_TYPE)
    )
    v1 = storage.save_version(
        DocumentVersion(
            id="v_del_1",
            file_id=file_id,
            version_number=1,
            content_hash="h1",
            snapshot_text="Snap 1",
        )
    )
    v2 = storage.save_version(
        DocumentVersion(
            id="v_del_2",
            file_id=file_id,
            version_number=2,
            content_hash="h2",
            snapshot_text="Snap 2",
        )
    )
    storage.save_diff(
        DocumentDiff(
            id="d_del_1_2",
            file_id=file_id,
            from_version_id=v1.id,
            to_version_id=v2.id,
            patch_text="patch",
        )
    )

    assert storage.count_versions(file_id) == 2
    assert storage.count_diffs(file_id) == 1

    # Delete parent file
    deleted_count = storage.delete_files([file_id])
    assert deleted_count == 1
    assert storage.get_file(file_id) is None

    # Foreign key cascade check
    assert storage.count_versions(file_id) == 0
    assert storage.count_diffs(file_id) == 0
    assert storage.get_version(v1.id) is None
    assert storage.get_diff_between(v1.id, v2.id) is None


def test_storage_version_pagination(tmp_path: Path) -> None:
    """Test paginating version history."""
    storage = CrawlStorage(db_path=tmp_path / "ver_pagination.db")
    file_id = "doc_paged"
    storage.upsert_file(
        DriveFileMetadata(id=file_id, name="Paged Doc", mime_type=GOOGLE_DOC_MIME_TYPE)
    )

    for i in range(1, 11):
        storage.save_version(
            DocumentVersion(
                id=f"v_p_{i:02d}",
                file_id=file_id,
                version_number=i,
                content_hash=f"hash_{i}",
                snapshot_text=f"Content for version {i}",
            )
        )

    assert storage.count_versions(file_id) == 10

    page1 = storage.get_version_history(file_id, limit=4, offset=0)
    assert len(page1) == 4
    assert [v.version_number for v in page1] == [10, 9, 8, 7]

    page2 = storage.get_version_history(file_id, limit=4, offset=4)
    assert len(page2) == 4
    assert [v.version_number for v in page2] == [6, 5, 4, 3]

    page3 = storage.get_version_history(file_id, limit=4, offset=8)
    assert len(page3) == 2
    assert [v.version_number for v in page3] == [2, 1]

