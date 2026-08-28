"""Unit tests for IncrementalSyncEngine and High-Watermark Synchronization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
)
from app.indexer.storage import CrawlStorage
from app.indexer.sync import IncrementalSyncEngine


def test_sync_bootstrap_full_crawl(tmp_path: Path) -> None:
    """Test initial sync cycle when no previous watermark exists."""
    storage = CrawlStorage(db_path=tmp_path / "sync_bootstrap.db")

    mock_crawler = MagicMock()
    mock_exporter = MagicMock()

    files = [
        DriveFileMetadata(
            id="doc_1",
            name="First Document",
            mime_type=GOOGLE_DOC_MIME_TYPE,
            modified_time=datetime(2026, 8, 25, 10, 0, 0, tzinfo=timezone.utc),
        ),
        DriveFileMetadata(
            id="sheet_1",
            name="First Sheet",
            mime_type=GOOGLE_SHEET_MIME_TYPE,
            modified_time=datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc),
        ),
    ]

    mock_crawler.crawl_files.return_value = iter(files)
    # Exporter attaches snippet
    mock_exporter.export_and_attach.side_effect = lambda f: f.model_copy(
        update={"content_snippet": f"Snippet for {f.name}", "export_status": "success"}
    )

    sync_engine = IncrementalSyncEngine(
        crawler=mock_crawler,
        exporter=mock_exporter,
        storage=storage,
    )

    result = sync_engine.run_sync(full_refresh=False)

    assert result.is_full_refresh is True
    assert result.added_count == 2
    assert result.updated_count == 0
    assert result.deleted_count == 0
    assert result.total_stored == 2
    assert storage.count_files() == 2
    assert storage.get_watermark() is not None

    # Verify query had no modifiedTime filter
    kwargs = mock_crawler.crawl_files.call_args[1]
    assert "modifiedTime >" not in kwargs["query_filter"]


def test_sync_incremental_with_watermark(tmp_path: Path) -> None:
    """Test incremental sync applying watermark query and updating delta."""
    storage = CrawlStorage(db_path=tmp_path / "sync_incremental.db")

    # Pre-populate storage with 2 files and a watermark
    existing_file = DriveFileMetadata(
        id="doc_1",
        name="Existing Doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        modified_time=datetime(2026, 8, 25, 10, 0, 0, tzinfo=timezone.utc),
    )
    storage.upsert_file(existing_file)

    past_watermark = datetime(2026, 8, 26, 0, 0, 0, tzinfo=timezone.utc)
    storage.set_watermark(past_watermark)

    mock_crawler = MagicMock()
    mock_exporter = MagicMock()

    # Crawler returns only 1 newly modified file
    new_file = DriveFileMetadata(
        id="doc_new",
        name="Newly Added Doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        modified_time=datetime(2026, 8, 27, 14, 0, 0, tzinfo=timezone.utc),
    )

    # First call: active changed files; second call: trashed files (empty)
    mock_crawler.crawl_files.side_effect = [iter([new_file]), iter([])]
    mock_exporter.export_and_attach.side_effect = lambda f: f

    sync_engine = IncrementalSyncEngine(
        crawler=mock_crawler,
        exporter=mock_exporter,
        storage=storage,
    )

    result = sync_engine.run_sync(full_refresh=False)

    assert result.is_full_refresh is False
    assert result.added_count == 1
    assert result.updated_count == 0
    assert result.deleted_count == 0
    assert result.total_stored == 2  # doc_1 + doc_new
    assert storage.count_files() == 2

    # Verify query included watermark
    first_call_kwargs = mock_crawler.crawl_files.call_args_list[0][1]
    assert "modifiedTime > '2026-08-26T00:00:00Z'" in first_call_kwargs["query_filter"]


def test_sync_deletion_detection_on_full_refresh(tmp_path: Path) -> None:
    """Test full refresh detecting deleted files via ID diffing and purging them."""
    storage = CrawlStorage(db_path=tmp_path / "sync_deletion.db")

    # Stored: f1 and f2
    storage.upsert_files(
        [
            DriveFileMetadata(id="f1", name="Active File", mime_type=GOOGLE_DOC_MIME_TYPE),
            DriveFileMetadata(id="f2", name="Deleted File", mime_type=GOOGLE_DOC_MIME_TYPE),
        ]
    )

    mock_crawler = MagicMock()
    mock_exporter = MagicMock()

    # Remote Google Drive only returns f1 (f2 was deleted)
    active_remote = [
        DriveFileMetadata(id="f1", name="Active File", mime_type=GOOGLE_DOC_MIME_TYPE)
    ]
    mock_crawler.crawl_files.return_value = iter(active_remote)
    mock_exporter.export_and_attach.side_effect = lambda f: f

    sync_engine = IncrementalSyncEngine(
        crawler=mock_crawler,
        exporter=mock_exporter,
        storage=storage,
    )

    result = sync_engine.run_sync(full_refresh=True)

    assert result.added_count == 0
    assert result.updated_count == 1
    assert result.deleted_count == 1
    assert result.total_stored == 1
    assert storage.count_files() == 1
    assert storage.get_file("f1") is not None
    assert storage.get_file("f2") is None
