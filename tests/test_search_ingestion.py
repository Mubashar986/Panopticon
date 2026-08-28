"""Unit tests for SearchIngestionEngine, batching, and deletion synchronization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from app.indexer.models import GOOGLE_DOC_MIME_TYPE, GOOGLE_SHEET_MIME_TYPE, DriveFileMetadata
from app.indexer.storage import CrawlStorage
from app.search.exceptions import IndexConfigurationError, SearchConnectionError, SearchError
from app.search.ingestion import IngestionResult, SearchIngestionEngine
from app.search.models import IndexStats
from app.search.schema import SearchDocument


def test_ingest_documents_empty() -> None:
    """Test ingest_documents with empty list returns 0 counts without error."""
    mock_client = MagicMock()
    engine = SearchIngestionEngine(search_client=mock_client)

    result = engine.ingest_documents([])

    assert result.indexed_count == 0
    assert result.batch_count == 0
    assert result.total_stored == 0
    mock_client.ensure_index.assert_not_called()


def test_ingest_documents_batches_chunking() -> None:
    """Test chunking 250 documents into 3 batches (100, 100, 50)."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_task1 = MagicMock(task_uid=1)
    mock_task2 = MagicMock(task_uid=2)
    mock_task3 = MagicMock(task_uid=3)

    mock_task_success = MagicMock(status="succeeded")

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = mock_task_success
    mock_index.add_documents.side_effect = [mock_task1, mock_task2, mock_task3]
    mock_client.get_stats.return_value = IndexStats(
        index_uid="panopticon_docs", number_of_documents=250, is_indexing=False
    )

    engine = SearchIngestionEngine(search_client=mock_client, batch_size=100)

    # Create 250 test files
    files = [
        DriveFileMetadata(
            id=f"file_{i}",
            name=f"Document {i}",
            mime_type=GOOGLE_DOC_MIME_TYPE,
            project_tags=[f"Tag_{i % 5}"],
        )
        for i in range(250)
    ]

    result: IngestionResult = engine.ingest_documents(files)

    assert result.indexed_count == 250
    assert result.batch_count == 3
    assert result.total_stored == 250
    assert mock_index.add_documents.call_count == 3

    # Check batch sizes
    first_batch = mock_index.add_documents.call_args_list[0][0][0]
    second_batch = mock_index.add_documents.call_args_list[1][0][0]
    third_batch = mock_index.add_documents.call_args_list[2][0][0]

    assert len(first_batch) == 100
    assert len(second_batch) == 100
    assert len(third_batch) == 50


def test_sync_from_storage_full(tmp_path: Path) -> None:
    """Test syncing stored records from SQLite into Meilisearch."""
    storage = CrawlStorage(db_path=tmp_path / "test_ingest.db")

    files = [
        DriveFileMetadata(
            id="f1",
            name="Falcon Plan",
            mime_type=GOOGLE_DOC_MIME_TYPE,
            project_tags=["Falcon"],
        ),
        DriveFileMetadata(
            id="f2",
            name="Falcon Budget",
            mime_type=GOOGLE_SHEET_MIME_TYPE,
            project_tags=["Falcon"],
        ),
    ]
    storage.upsert_files(files)

    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_task = MagicMock(task_uid=10)
    mock_task_success = MagicMock(status="succeeded")

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = mock_task_success
    mock_index.add_documents.return_value = mock_task
    mock_index.get_documents.return_value = MagicMock(results=[MagicMock(id="f1"), MagicMock(id="f2")])
    mock_client.get_stats.return_value = IndexStats(
        index_uid="panopticon_docs", number_of_documents=2, is_indexing=False
    )

    engine = SearchIngestionEngine(search_client=mock_client, storage=storage)

    result = engine.sync_from_storage(purge_deleted=True)

    assert result.indexed_count == 2
    assert result.total_stored == 2
    assert result.deleted_count == 0
    mock_index.add_documents.assert_called_once()


def test_sync_from_storage_ghost_deletion_purging(tmp_path: Path) -> None:
    """Test detecting orphaned document IDs in Meilisearch and purging them."""
    storage = CrawlStorage(db_path=tmp_path / "test_purge.db")

    # SQLite only has f1 (f2 was deleted from Drive)
    storage.upsert_file(
        DriveFileMetadata(id="f1", name="Active Doc", mime_type=GOOGLE_DOC_MIME_TYPE)
    )

    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_task_add = MagicMock(task_uid=11)
    mock_task_del = MagicMock(task_uid=12)
    mock_task_success = MagicMock(status="succeeded")

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = mock_task_success
    mock_index.add_documents.return_value = mock_task_add
    mock_index.delete_documents.return_value = mock_task_del

    # Meilisearch currently has f1 and f2 (ghost)
    mock_index.get_documents.return_value = MagicMock(
        results=[MagicMock(id="f1"), MagicMock(id="f2")]
    )
    mock_client.get_stats.return_value = IndexStats(
        index_uid="panopticon_docs", number_of_documents=1, is_indexing=False
    )

    engine = SearchIngestionEngine(search_client=mock_client, storage=storage)

    result = engine.sync_from_storage(purge_deleted=True)

    assert result.indexed_count == 1
    assert result.deleted_count == 1
    mock_index.delete_documents.assert_called_once_with(["f2"])


def test_delete_documents_by_ids() -> None:
    """Test delete_documents_by_ids helper."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_task = MagicMock(task_uid=20)
    mock_task_success = MagicMock(status="succeeded")

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = mock_task_success
    mock_index.delete_documents.return_value = mock_task

    engine = SearchIngestionEngine(search_client=mock_client)

    count = engine.delete_documents_by_ids(["del_1", "del_2"])
    assert count == 2
    mock_index.delete_documents.assert_called_once_with(["del_1", "del_2"])


def test_ingestion_task_failure() -> None:
    """Test raising IndexConfigurationError when an indexing task fails."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_task = MagicMock(task_uid=99)
    mock_task_failed = MagicMock(status="failed", error={"message": "Malformed document"})

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = mock_task_failed
    mock_index.add_documents.return_value = mock_task

    engine = SearchIngestionEngine(search_client=mock_client)
    files = [DriveFileMetadata(id="bad_1", name="Doc", mime_type=GOOGLE_DOC_MIME_TYPE)]

    with pytest.raises(IndexConfigurationError) as exc_info:
        engine.ingest_documents(files)
    assert "Meilisearch indexing task 99 failed" in str(exc_info.value)


def test_ingestion_connection_error() -> None:
    """Test raising SearchConnectionError when Meilisearch connection is refused."""
    mock_client = MagicMock()
    mock_client.configure_schema.side_effect = SearchConnectionError("Connection refused")

    engine = SearchIngestionEngine(search_client=mock_client)
    files = [DriveFileMetadata(id="f1", name="Doc", mime_type=GOOGLE_DOC_MIME_TYPE)]

    with pytest.raises(SearchConnectionError):
        engine.ingest_documents(files)
