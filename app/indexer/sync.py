from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.indexer.chunker import TextChunker
from app.indexer.crawler import DEFAULT_DOCS_SHEETS_QUERY, DriveCrawler
from app.indexer.diff import DiffEngine
from app.indexer.embeddings import EmbeddingProvider, get_embedding_provider
from app.indexer.exporter import ContentExporter
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DocumentDiff,
    DocumentVersion,
    DriveFileMetadata,
    SyncResult,
)
from app.indexer.storage import CrawlStorage
from app.indexer.summarizer import ChangeSummarizer, get_change_summarizer

logger = get_logger("panopticon.indexer.sync")


class IncrementalSyncEngine:
    """Coordinates high-watermark delta crawling, content extraction, and SQLite storage."""

    def __init__(
        self,
        crawler: DriveCrawler | None = None,
        exporter: ContentExporter | None = None,
        storage: CrawlStorage | None = None,
        diff_engine: DiffEngine | None = None,
        summarizer: ChangeSummarizer | None = None,
        chunker: TextChunker | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize IncrementalSyncEngine with injected dependencies.

        Args:
            crawler: Optional DriveCrawler instance.
            exporter: Optional ContentExporter instance.
            storage: Optional CrawlStorage repository instance.
            diff_engine: Optional DiffEngine instance.
            summarizer: Optional ChangeSummarizer instance.
            chunker: Optional TextChunker instance.
            embedding_provider: Optional EmbeddingProvider instance.
        """
        self.crawler = crawler if crawler is not None else DriveCrawler()
        self.exporter = exporter if exporter is not None else ContentExporter()
        self.storage = storage if storage is not None else CrawlStorage()
        self.diff_engine = diff_engine if diff_engine is not None else DiffEngine()
        self.summarizer = summarizer if summarizer is not None else get_change_summarizer()
        self.chunker = chunker if chunker is not None else TextChunker()
        self.embedding_provider = embedding_provider if embedding_provider is not None else get_embedding_provider()

    def run_sync(
        self,
        full_refresh: bool = False,
        export_content: bool = True,
        include_labels: list[str] | str | None = None,
        page_size: int = 100,
    ) -> SyncResult:
        """Execute a full or incremental sync cycle.

        Args:
            full_refresh: If True, ignores previous watermark and crawls all files.
            export_content: If True, exports text snippets from Docs and Sheets.
            include_labels: Optional label IDs to extract from Google Drive.
            page_size: Number of files per API pagination batch.

        Returns:
            SyncResult: Telemetry and metrics for the completed synchronization.
        """
        sync_start_time = datetime.now(timezone.utc)
        watermark_used: datetime | None = None

        if not full_refresh:
            watermark_used = self.storage.get_watermark()

        # Build delta query if watermark exists
        if watermark_used is not None:
            watermark_iso = watermark_used.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            query_filter = f"{DEFAULT_DOCS_SHEETS_QUERY} and modifiedTime > '{watermark_iso}'"
            logger.info("Executing incremental sync with watermark: %s", watermark_iso)
        else:
            query_filter = DEFAULT_DOCS_SHEETS_QUERY
            logger.info("Executing full bootstrap sync (watermark is None or full_refresh=True)")
            if export_content:
                self.bootstrap_baseline_versions(export_content=True)

        stored_ids_before = self.storage.get_all_file_ids()
        active_ids_seen: set[str] = set()

        added_count = 0
        updated_count = 0
        deleted_count = 0
        batch: list[DriveFileMetadata] = []

        # 1. Stream modified or new files
        for raw_file in self.crawler.crawl_files(
            query_filter=query_filter,
            page_size=page_size,
            include_labels=include_labels,
        ):
            file_id = raw_file.id
            active_ids_seen.add(file_id)

            if file_id in stored_ids_before:
                updated_count += 1
            else:
                added_count += 1

            # Extract content, save file record, and handle version snapshots / diffs
            if export_content:
                export_res = self.exporter.export_file_content(raw_file.id, raw_file.mime_type)
                file_to_save = raw_file.model_copy(
                    update={
                        "content_snippet": export_res.snippet,
                        "export_status": export_res.status,
                    }
                )
                self.storage.upsert_file(file_to_save, last_seen_at=sync_start_time)

                if export_res.content_text is not None:
                    new_text = export_res.content_text
                    new_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
                    prev_ver = self.storage.get_latest_version(file_id)

                    if prev_ver is None:
                        saved_ver = self.storage.save_version(
                            DocumentVersion(
                                file_id=file_id,
                                version_number=1,
                                content_hash=new_hash,
                                snapshot_text=new_text,
                                modified_time=raw_file.modified_time,
                                editor=raw_file.last_modifying_user,
                            )
                        )
                        self._generate_and_save_chunks(
                            new_text, file_id, file_to_save.name, saved_ver.id
                        )
                    elif prev_ver.content_hash != new_hash:
                        diff_res = self.diff_engine.compute_diff(
                            prev_ver.snapshot_text,
                            new_text,
                            from_label=f"v{prev_ver.version_number}",
                            to_label=f"v{prev_ver.version_number + 1}",
                        )
                        new_ver = self.storage.save_version(
                            DocumentVersion(
                                file_id=file_id,
                                version_number=prev_ver.version_number + 1,
                                content_hash=new_hash,
                                snapshot_text=new_text,
                                modified_time=raw_file.modified_time,
                                editor=raw_file.last_modifying_user,
                            )
                        )
                        self._generate_and_save_chunks(
                            new_text, file_id, file_to_save.name, new_ver.id
                        )
                        if diff_res.has_changes:
                            ai_summary = self.summarizer.summarize_diff(
                                patch_text=diff_res.patch_text,
                                file_name=file_to_save.name,
                                editor=raw_file.last_modifying_user,
                            )
                            self.storage.save_diff(
                                DocumentDiff(
                                    file_id=file_id,
                                    from_version_id=prev_ver.id,
                                    to_version_id=new_ver.id,
                                    patch_text=diff_res.patch_text,
                                    ai_summary=ai_summary,
                                    lines_added=diff_res.lines_added,
                                    lines_removed=diff_res.lines_removed,
                                )
                            )
            else:
                file_to_save = raw_file
                batch.append(file_to_save)
                if len(batch) >= 50:
                    self.storage.upsert_files(batch, last_seen_at=sync_start_time)
                    batch.clear()

        # Upsert remaining buffer
        if batch:
            self.storage.upsert_files(batch, last_seen_at=sync_start_time)
            batch.clear()

        # 2. Deletion Detection Phase
        deleted_ids_to_purge: set[str] = set()

        if full_refresh or watermark_used is None:
            # On full refresh: any ID previously stored but not seen in active crawl is deleted
            deleted_ids_to_purge = stored_ids_before - active_ids_seen
        else:
            # On incremental run: query Google Drive trash for files trashed since watermark
            trash_query = (
                f"trashed = true and (mimeType = '{GOOGLE_DOC_MIME_TYPE}' or mimeType = '{GOOGLE_SHEET_MIME_TYPE}') "
                f"and modifiedTime > '{watermark_iso}'"
            )
            try:
                for trashed_file in self.crawler.crawl_files(
                    query_filter=trash_query,
                    page_size=page_size,
                ):
                    if trashed_file.id in stored_ids_before:
                        deleted_ids_to_purge.add(trashed_file.id)
            except (ValueError, TypeError, RuntimeError, OSError) as trash_err:
                logger.warning("Could not query trashed files delta: %s", trash_err)

        if deleted_ids_to_purge:
            deleted_count = self.storage.delete_files(deleted_ids_to_purge)
            logger.info("Purged %d deleted/trashed files from local storage", deleted_count)

        # 3. Commit new watermark timestamp
        self.storage.set_watermark(sync_start_time)

        total_stored = self.storage.count_files()
        duration = (datetime.now(timezone.utc) - sync_start_time).total_seconds()
        unchanged_count = max(0, total_stored - added_count - updated_count)

        result = SyncResult(
            added_count=added_count,
            updated_count=updated_count,
            deleted_count=deleted_count,
            unchanged_count=unchanged_count,
            total_stored=total_stored,
            duration_seconds=duration,
            watermark_used=watermark_used,
            new_watermark=sync_start_time,
            is_full_refresh=full_refresh or watermark_used is None,
        )

        logger.info(
            "Sync cycle finished in %.2fs (added=%d, updated=%d, deleted=%d, total=%d)",
            duration,
            added_count,
            updated_count,
            deleted_count,
            total_stored,
        )
        return result

    def _generate_and_save_chunks(
        self,
        content_text: str,
        file_id: str,
        file_name: str,
        version_id: str | None,
    ) -> None:
        """Chunk document text, compute vector embeddings, and persist chunks to storage."""
        try:
            chunks = self.chunker.chunk_document(
                content_text=content_text,
                file_id=file_id,
                file_name=file_name,
                version_id=version_id,
            )
            if chunks:
                texts = [c.content_text for c in chunks]
                embeddings = self.embedding_provider.embed_texts(texts)
                enriched = [
                    c.model_copy(update={"embedding": emb})
                    for c, emb in zip(chunks, embeddings)
                ]
                self.storage.save_chunks(enriched)
                logger.debug("Saved %d semantic chunks for file %s", len(enriched), file_id)
        except Exception as exc:
            logger.warning("Failed to chunk and embed file %s: %s", file_id, exc)

    def bootstrap_baseline_versions(self, export_content: bool = True) -> int:
        """Bootstrap initial v1 version snapshots and chunks for existing unversioned documents.

        Ensures that every tracked document has an initial baseline v1 snapshot in SQLite,
        guaranteeing that subsequent edits (additions, modifications, deletions) reliably
        compute unified diffs and AI change summaries instead of silently saving v1.

        Args:
            export_content: Whether to fetch full plain text via exporter if not already cached.

        Returns:
            int: Number of unversioned documents successfully bootstrapped with baseline v1.
        """
        unversioned_ids = self.storage.get_unversioned_file_ids()
        if not unversioned_ids:
            return 0

        logger.info(
            "Bootstrapping baseline versions for %d unversioned documents...",
            len(unversioned_ids),
        )
        bootstrapped_count = 0

        for fid in unversioned_ids:
            file_record = self.storage.get_file(fid)
            if not file_record:
                continue

            text_to_save: str | None = None
            if export_content:
                try:
                    res = self.exporter.export_file_content(fid, file_record.mime_type)
                    if res.content_text:
                        text_to_save = res.content_text
                except Exception as exc:
                    logger.debug("Content export failed during baseline bootstrap (%s): %s", fid, exc)

            if not text_to_save and file_record.content_snippet:
                text_to_save = file_record.content_snippet

            if text_to_save:
                content_hash = hashlib.sha256(text_to_save.encode("utf-8")).hexdigest()
                saved_ver = self.storage.save_version(
                    DocumentVersion(
                        file_id=fid,
                        version_number=1,
                        content_hash=content_hash,
                        snapshot_text=text_to_save,
                        modified_time=file_record.modified_time,
                        editor=file_record.last_modifying_user,
                    )
                )
                self._generate_and_save_chunks(
                    text_to_save, fid, file_record.name, saved_ver.id
                )
                bootstrapped_count += 1

        logger.info("Successfully bootstrapped %d baseline document versions.", bootstrapped_count)
        return bootstrapped_count


