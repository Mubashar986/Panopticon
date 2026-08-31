"""Unit tests for IncrementalSyncEngine and High-Watermark Synchronization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from app.indexer.exporter import ExportResult
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
)
from app.indexer.storage import CrawlStorage
from app.indexer.summarizer import HeuristicSummarizer
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
    # Exporter attaches snippet and content text
    mock_exporter.export_file_content.side_effect = lambda fid, mime: ExportResult(
        file_id=fid,
        status="success",
        snippet=f"Snippet for {fid}",
        content_text=f"Initial full content for {fid}\nSection 1",
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
    mock_exporter.export_file_content.side_effect = lambda fid, mime: ExportResult(
        file_id=fid,
        status="success",
        snippet="snippet",
        content_text="Sample text",
    )

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
    mock_exporter.export_file_content.side_effect = lambda fid, mime: ExportResult(
        file_id=fid,
        status="success",
        snippet="snippet",
        content_text="Sample text",
    )

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


def test_sync_creates_versions_and_diffs_on_content_change(tmp_path: Path) -> None:
    """Test that consecutive sync runs on modified content generate versions and diff records."""
    storage = CrawlStorage(db_path=tmp_path / "sync_diffs.db")
    mock_crawler = MagicMock()
    mock_exporter = MagicMock()

    sync_engine = IncrementalSyncEngine(
        crawler=mock_crawler,
        exporter=mock_exporter,
        storage=storage,
        summarizer=HeuristicSummarizer(),
    )

    doc_id = "doc_diff_test"
    file_v1 = DriveFileMetadata(
        id=doc_id,
        name="Spec Doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        modified_time=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
        last_modifying_user="alice@co.com",
    )

    # 1. First sync cycle: Initial version 1 snapshot created
    mock_crawler.crawl_files.return_value = iter([file_v1])
    mock_exporter.export_file_content.return_value = ExportResult(
        file_id=doc_id,
        status="success",
        snippet="Line 1 preview",
        content_text="Line 1: Spec Overview\nLine 2: Target Arch\n",
    )

    r1 = sync_engine.run_sync(full_refresh=True)
    assert r1.added_count == 1
    assert storage.count_versions(doc_id) == 1
    assert storage.count_diffs(doc_id) == 0

    v1 = storage.get_latest_version(doc_id)
    assert v1 is not None
    assert v1.version_number == 1
    assert v1.editor == "alice@co.com"

    # 2. Second sync cycle: Document modified, Version 2 + Diff created
    file_v2 = file_v1.model_copy(
        update={
            "modified_time": datetime(2026, 8, 22, 14, 0, 0, tzinfo=timezone.utc),
            "last_modifying_user": "bob@co.com",
        }
    )
    mock_crawler.crawl_files.side_effect = [iter([file_v2]), iter([])]
    mock_exporter.export_file_content.return_value = ExportResult(
        file_id=doc_id,
        status="success",
        snippet="Line 1 preview",
        content_text="Line 1: Spec Overview\nLine 2: Target Arch Modified\nLine 3: Extra Section\n",
    )

    r2 = sync_engine.run_sync(full_refresh=False)
    assert r2.updated_count == 1
    assert storage.count_versions(doc_id) == 2
    assert storage.count_diffs(doc_id) == 1

    v2 = storage.get_latest_version(doc_id)
    assert v2 is not None
    assert v2.version_number == 2
    assert v2.editor == "bob@co.com"

    diffs = storage.get_diffs(doc_id)
    assert len(diffs) == 1
    assert diffs[0].from_version_id == v1.id
    assert diffs[0].to_version_id == v2.id
    assert diffs[0].lines_added == 2
    assert diffs[0].lines_removed == 1
    assert "-Line 2: Target Arch" in diffs[0].patch_text
    assert "+Line 2: Target Arch Modified" in diffs[0].patch_text
    assert diffs[0].ai_summary is not None
    assert "modified 'Spec Doc'" in diffs[0].ai_summary


