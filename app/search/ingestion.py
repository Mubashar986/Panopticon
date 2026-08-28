"""Search ingestion engine for syncing SQLite crawl records into Meilisearch."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

from app.indexer.models import DriveFileMetadata
from app.indexer.storage import CrawlStorage, get_crawl_storage
from app.search.client import PanopticonSearchClient, get_search_client
from app.search.exceptions import IndexConfigurationError, SearchConnectionError, SearchError
from app.search.models import IngestionResult, SearchDocument

logger = logging.getLogger("panopticon.search.ingestion")


class SearchIngestionEngine:
    """Engine responsible for batch transformation and ingestion from SQLite into Meilisearch."""

    def __init__(
        self,
        search_client: PanopticonSearchClient | None = None,
        storage: CrawlStorage | None = None,
        batch_size: int = 100,
    ) -> None:
        self.search_client = search_client or get_search_client()
        self.storage = storage or get_crawl_storage()
        self.batch_size = max(1, batch_size)

    def _chunk_list(self, items: list[Any], chunk_size: int) -> list[list[Any]]:
        """Split a list into chunks of fixed size."""
        return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]

    def ingest_documents(
        self,
        documents: Sequence[DriveFileMetadata | SearchDocument | dict[str, Any]],
        index_name: str | None = None,
        wait_for_tasks: bool = True,
    ) -> IngestionResult:
        """Transform and batch-upsert documents into the Meilisearch index.

        Args:
            documents: Sequence of DriveFileMetadata entities, SearchDocument models, or dicts.
            index_name: Optional target index UID override.
            wait_for_tasks: Whether to poll and await task completion synchronously.

        Returns:
            IngestionResult metrics model.
        """
        start_time = time.perf_counter()
        target_uid = index_name or self.search_client.index_name

        if not documents:
            logger.info("No documents provided for ingestion into '%s'.", target_uid)
            return IngestionResult(
                indexed_count=0,
                deleted_count=0,
                total_stored=0,
                batch_count=0,
                duration_seconds=time.perf_counter() - start_time,
            )

        # 1. Transform all incoming records to serializable dictionaries
        serialized_docs: list[dict[str, Any]] = []
        for doc in documents:
            if isinstance(doc, DriveFileMetadata):
                search_doc = SearchDocument.from_drive_metadata(doc)
                serialized_docs.append(search_doc.to_meili_dict())
            elif isinstance(doc, SearchDocument):
                serialized_docs.append(doc.to_meili_dict())
            elif isinstance(doc, dict):
                serialized_docs.append(doc)
            else:
                logger.warning("Skipping unsupported document type: %s", type(doc))

        # 2. Ensure schema is configured on the index
        self.search_client.configure_schema(target_uid)
        index = self.search_client.ensure_index(target_uid, primary_key="id")
        raw_client = self.search_client.raw_client

        # 3. Batch chunking and upload
        chunks = self._chunk_list(serialized_docs, self.batch_size)
        task_uids: list[int] = []

        logger.info(
            "Uploading %d documents to index '%s' in %d batches (batch_size=%d)...",
            len(serialized_docs),
            target_uid,
            len(chunks),
            self.batch_size,
        )

        try:
            for idx, chunk in enumerate(chunks, start=1):
                task = index.add_documents(chunk, primary_key="id")
                task_uid = (
                    task.task_uid if hasattr(task, "task_uid") else task.get("taskUid")
                )
                if task_uid is not None:
                    task_uids.append(task_uid)
                logger.debug("Submitted batch %d/%d (task_uid=%s)", idx, len(chunks), task_uid)

            # 4. Await task completion if requested
            if wait_for_tasks and task_uids:
                for task_uid in task_uids:
                    task_result = raw_client.wait_for_task(task_uid)
                    status = (
                        getattr(task_result, "status", None)
                        or (task_result.get("status") if isinstance(task_result, dict) else None)
                    )
                    if status == "failed":
                        error = (
                            getattr(task_result, "error", None)
                            or (task_result.get("error") if isinstance(task_result, dict) else "Unknown error")
                        )
                        raise IndexConfigurationError(
                            f"Meilisearch indexing task {task_uid} failed: {error}"
                        )

            stats = self.search_client.get_stats(target_uid)
            duration = time.perf_counter() - start_time

            logger.info(
                "Ingestion complete: %d documents indexed into '%s' in %.2fs (Total in index: %d).",
                len(serialized_docs),
                target_uid,
                duration,
                stats.number_of_documents,
            )

            return IngestionResult(
                indexed_count=len(serialized_docs),
                deleted_count=0,
                total_stored=stats.number_of_documents,
                batch_count=len(chunks),
                duration_seconds=round(duration, 3),
            )

        except (IndexConfigurationError, SearchConnectionError, SearchError):
            raise
        except Exception as exc:
            err_str = str(exc).lower()
            if "connection refused" in err_str or "communicationerror" in type(exc).__name__.lower():
                raise SearchConnectionError(
                    f"Cannot connect to Meilisearch at {self.search_client.url}: {exc}"
                ) from exc
            raise SearchError(f"Error during document ingestion: {exc}") from exc

    def delete_documents_by_ids(
        self,
        file_ids: Sequence[str],
        index_name: str | None = None,
        wait_for_task: bool = True,
    ) -> int:
        """Delete documents from Meilisearch by file IDs.

        Args:
            file_ids: List of document IDs to delete.
            index_name: Optional index UID override.
            wait_for_task: Whether to await completion synchronously.

        Returns:
            Number of document IDs requested for deletion.
        """
        if not file_ids:
            return 0

        target_uid = index_name or self.search_client.index_name
        try:
            index = self.search_client.ensure_index(target_uid, primary_key="id")
            logger.info("Deleting %d documents from index '%s'...", len(file_ids), target_uid)
            task = index.delete_documents(list(file_ids))

            task_uid = (
                task.task_uid if hasattr(task, "task_uid") else task.get("taskUid")
            )
            if wait_for_task and task_uid is not None:
                self.search_client.raw_client.wait_for_task(task_uid)

            return len(file_ids)
        except Exception as exc:
            err_str = str(exc).lower()
            if "connection refused" in err_str or "communicationerror" in type(exc).__name__.lower():
                raise SearchConnectionError(
                    f"Cannot connect to Meilisearch at {self.search_client.url}: {exc}"
                ) from exc
            raise SearchError(f"Failed deleting documents from '{target_uid}': {exc}") from exc

    def sync_from_storage(
        self,
        storage: CrawlStorage | None = None,
        index_name: str | None = None,
        full_refresh: bool = False,
        purge_deleted: bool = True,
    ) -> IngestionResult:
        """Synchronize stored Google Drive files from SQLite into Meilisearch.

        Args:
            storage: Optional CrawlStorage instance. Defaults to self.storage.
            index_name: Optional target index UID override.
            full_refresh: Whether this is a full rebuild.
            purge_deleted: Whether to detect and remove deleted files from Meilisearch.

        Returns:
            IngestionResult summarizing indexed and deleted counts.
        """
        start_time = time.perf_counter()
        active_storage = storage or self.storage
        target_uid = index_name or self.search_client.index_name

        # 1. Fetch all active files from local SQLite database
        all_stored_files = active_storage.list_files()
        active_file_ids = {f.id for f in all_stored_files}

        # 2. Ingest all active documents in batches
        ingest_res = self.ingest_documents(
            documents=all_stored_files,
            index_name=target_uid,
            wait_for_tasks=True,
        )

        deleted_count = 0
        # 3. Ghost deletion detection (Product Constraint 10)
        if purge_deleted and active_file_ids:
            try:
                # Retrieve currently indexed document IDs in Meilisearch
                index = self.search_client.ensure_index(target_uid, primary_key="id")
                # Meilisearch get_documents returns up to limit
                doc_batch = index.get_documents({"fields": ["id"], "limit": 10000})
                results = doc_batch.results if hasattr(doc_batch, "results") else doc_batch.get("results", [])
                
                indexed_ids = {
                    doc.id if hasattr(doc, "id") else doc.get("id")
                    for doc in results
                    if (hasattr(doc, "id") and doc.id) or (isinstance(doc, dict) and doc.get("id"))
                }

                # Find IDs present in Meilisearch but missing from SQLite storage
                orphaned_ids = list(indexed_ids - active_file_ids)
                if orphaned_ids:
                    logger.info(
                        "Found %d orphaned/deleted documents in search index; purging...",
                        len(orphaned_ids),
                    )
                    deleted_count = self.delete_documents_by_ids(
                        orphaned_ids, index_name=target_uid, wait_for_task=True
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not execute ghost document purge: %s", e)

        stats = self.search_client.get_stats(target_uid)
        total_duration = time.perf_counter() - start_time

        return IngestionResult(
            indexed_count=ingest_res.indexed_count,
            deleted_count=deleted_count,
            total_stored=stats.number_of_documents,
            batch_count=ingest_res.batch_count,
            duration_seconds=round(total_duration, 3),
            is_full_sync=full_refresh,
        )
