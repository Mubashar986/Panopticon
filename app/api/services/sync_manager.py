"""Background Synchronization and Search Ingestion Coordinator."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timezone


from app.api.schemas.sync import (
    ReindexResponse,
    SyncMode,
    SyncPhase,
    SyncStats,
    SyncStatusResponse,
    SyncTriggerResponse,
)
from app.api.services.event_bus import get_sync_event_bus
from app.core.auth.factory import get_auth_provider
from app.core.config import get_settings
from app.indexer.crawler import DriveCrawler
from app.indexer.exporter import ContentExporter
from app.indexer.storage import CrawlStorage, get_crawl_storage
from app.indexer.sync import IncrementalSyncEngine
from app.search.client import get_search_client
from app.search.ingestion import SearchIngestionEngine


logger = logging.getLogger("panopticon.api.sync_manager")


class SyncInProgressError(Exception):
    """Raised when a sync trigger is attempted while another sync job is already active."""


class SyncManager:
    """Thread-safe background coordinator managing Google Drive crawl and Meilisearch sync."""

    _instance: SyncManager | None = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_syncing: bool = False
        self._job_id: str | None = None
        self._sync_mode: SyncMode | None = None
        self._current_phase: SyncPhase = "idle"
        self._progress_message: str = "Ready"
        self._started_at: datetime | None = None
        self._duration_seconds: float | None = None
        self._last_stats: SyncStats | None = None
        self._last_error: str | None = None
        self._scheduler_task: asyncio.Task[None] | None = None
        self._scheduler_running: bool = False


    @classmethod
    def get_instance(cls) -> SyncManager:
        """Return the global SyncManager singleton."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_syncing(self) -> bool:
        """Return whether a sync job is actively executing."""
        with self._lock:
            return self._is_syncing

    def get_status(
        self, storage: CrawlStorage | None = None
    ) -> SyncStatusResponse:
        """Return snapshot of current sync state, progress, and database watermark."""
        settings = get_settings()
        store = storage or get_crawl_storage(settings.crawl_database_path)

        with self._lock:
            is_sync = self._is_syncing
            job_id = self._job_id
            mode = self._sync_mode
            phase = self._current_phase
            msg = self._progress_message
            started_dt = self._started_at
            duration = self._duration_seconds
            stats = self._last_stats
            error = self._last_error

        # If actively syncing, calculate elapsed runtime
        if is_sync and started_dt:
            duration = round(
                (datetime.now(timezone.utc) - started_dt).total_seconds(), 2
            )

        # Read last watermark from SQLite
        last_watermark_dt = store.get_watermark()
        last_watermark_str = (
            last_watermark_dt.isoformat() if last_watermark_dt else None
        )

        return SyncStatusResponse(
            is_syncing=is_sync,
            job_id=job_id,
            sync_mode=mode,
            current_phase=phase,
            progress_message=msg,
            started_at=started_dt.isoformat() if started_dt else None,
            duration_seconds=duration,
            last_sync_time=last_watermark_str,
            last_sync_stats=stats,
            last_error=error,
        )

    def trigger_sync(
        self,
        full_refresh: bool = False,
        export_content: bool = True,
        page_size: int = 50,
    ) -> SyncTriggerResponse:
        """Initiate asynchronous Google Drive crawl, storage update, and Meilisearch ingestion.

        Raises:
            SyncInProgressError: If a sync job is already running.
        """
        job_uuid = f"sync_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        mode: SyncMode = "full_refresh" if full_refresh else "incremental"
        now = datetime.now(timezone.utc)

        with self._lock:
            if self._is_syncing:
                raise SyncInProgressError(
                    f"A sync job ({self._job_id}) is currently in progress."
                )

            self._is_syncing = True
            self._job_id = job_uuid
            self._sync_mode = mode
            self._current_phase = "crawling"
            self._progress_message = (
                "Full Google Drive re-crawl initiated..."
                if full_refresh
                else "Checking Google Drive for recent modifications..."
            )
            self._started_at = now
            self._duration_seconds = 0.0
            self._last_error = None

        # Spawn worker in a dedicated OS background thread to ensure zero event loop blocking
        worker_thread = threading.Thread(
            target=self._run_sync_worker,
            args=(job_uuid, mode, full_refresh, export_content, page_size),
            daemon=True,
            name=f"PanopticonSyncWorker-{job_uuid}",
        )
        worker_thread.start()

        mode_desc = "Full re-crawl" if full_refresh else "Incremental sync"
        get_sync_event_bus().publish(
            "sync_started",
            {
                "job_id": job_uuid,
                "sync_mode": mode,
                "full_refresh": full_refresh,
                "message": f"{mode_desc} initiated.",
            },
        )
        return SyncTriggerResponse(
            status="started",
            message=f"{mode_desc} initiated successfully in background.",
            job_id=job_uuid,
            sync_mode=mode,
            started_at=now.isoformat(),
        )

    def trigger_reindex(self) -> ReindexResponse:
        """Re-push all documents stored in SQLite into Meilisearch without calling Google Drive."""
        job_uuid = f"reindex_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)

        with self._lock:
            if self._is_syncing:
                raise SyncInProgressError(
                    f"A job ({self._job_id}) is currently in progress."
                )

            self._is_syncing = True
            self._job_id = job_uuid
            self._sync_mode = "reindex"
            self._current_phase = "indexing_meilisearch"
            self._progress_message = "Re-indexing local SQLite database to Meilisearch..."
            self._started_at = now
            self._duration_seconds = 0.0
            self._last_error = None

        worker_thread = threading.Thread(
            target=self._run_reindex_worker,
            args=(job_uuid,),
            daemon=True,
            name=f"PanopticonReindexWorker-{job_uuid}",
        )
        worker_thread.start()

        get_sync_event_bus().publish(
            "reindex_started",
            {"job_id": job_uuid, "sync_mode": "reindex", "message": "Search re-indexing initiated."},
        )
        return ReindexResponse(
            status="started",
            message="Local search re-indexing initiated in background.",
            job_id=job_uuid,
            started_at=now.isoformat(),
        )

    def _update_progress(self, phase: SyncPhase, message: str) -> None:
        with self._lock:
            self._current_phase = phase
            self._progress_message = message
            job_id = self._job_id
        get_sync_event_bus().publish(
            "sync_progress",
            {"job_id": job_id, "phase": phase, "message": message},
        )

    def _run_sync_worker(
        self,
        job_id: str,
        mode: SyncMode,
        full_refresh: bool,
        export_content: bool,
        page_size: int,
    ) -> None:
        """Internal worker executing the sequential pipeline in background."""
        start_time = time.perf_counter()
        logger.info("Background sync job [%s] started (Mode: %s)", job_id, mode)

        try:
            settings = get_settings()
            provider = get_auth_provider(settings)
            storage = get_crawl_storage(settings.crawl_database_path)
            search_client = get_search_client()

            # Phase 1 & 2: Crawl Google Drive & Export Content
            self._update_progress(
                "crawling", "Connecting to Google Drive and scanning files..."
            )
            crawler = DriveCrawler(provider=provider)
            exporter = ContentExporter(provider=provider)
            sync_engine = IncrementalSyncEngine(
                crawler=crawler,
                exporter=exporter,
                storage=storage,
            )

            self._update_progress(
                "exporting" if export_content else "crawling",
                "Crawling Google Drive and extracting text snippets...",
            )
            drive_res = sync_engine.run_sync(
                full_refresh=full_refresh,
                export_content=export_content,
                page_size=page_size,
            )

            # Phase 3: SQLite update completed by IncrementalSyncEngine
            self._update_progress(
                "updating_sqlite",
                f"SQLite updated: +{drive_res.added_count} added, {drive_res.updated_count} updated.",
            )

            # Phase 4: Push to Meilisearch
            total_indexed = 0
            health = search_client.check_health()
            if health.is_available:
                self._update_progress(
                    "indexing_meilisearch", "Synchronizing documents to Meilisearch search index..."
                )
                ingestion_engine = SearchIngestionEngine(
                    search_client=search_client,
                    storage=storage,
                    batch_size=100,
                )
                ingest_res = ingestion_engine.sync_from_storage(purge_deleted=True)
                total_indexed = ingest_res.total_stored
            else:
                logger.warning(
                    "Meilisearch offline during sync [%s]. Skipping index update.",
                    job_id,
                )

            total_duration = round(time.perf_counter() - start_time, 2)
            final_stats = SyncStats(
                sync_mode=mode,
                added=drive_res.added_count,
                updated=drive_res.updated_count,
                deleted=drive_res.deleted_count,
                unchanged=drive_res.unchanged_count,
                total_stored=drive_res.total_stored,
                total_indexed=total_indexed,
                duration_seconds=total_duration,
            )

            with self._lock:
                self._is_syncing = False
                self._current_phase = "idle"
                self._progress_message = (
                    f"Sync completed successfully in {total_duration:.2f}s."
                )
                self._duration_seconds = total_duration
                self._last_stats = final_stats
                self._last_error = None

            get_sync_event_bus().publish(
                "sync_completed",
                {
                    "job_id": job_id,
                    "sync_mode": mode,
                    "added": drive_res.added_count,
                    "updated": drive_res.updated_count,
                    "deleted": drive_res.deleted_count,
                    "total_stored": drive_res.total_stored,
                    "duration_seconds": total_duration,
                },
            )
            logger.info("Background sync job [%s] finished in %.2fs", job_id, total_duration)

        except Exception as exc:
            total_duration = round(time.perf_counter() - start_time, 2)
            err_msg = str(exc)
            logger.exception("Background sync job [%s] failed", job_id)

            with self._lock:
                self._is_syncing = False
                self._current_phase = "failed"
                self._progress_message = f"Sync failed: {err_msg}"
                self._duration_seconds = total_duration
                self._last_error = err_msg

            get_sync_event_bus().publish(
                "sync_failed",
                {"job_id": job_id, "error": err_msg, "duration_seconds": total_duration},
            )

    def _run_reindex_worker(self, job_id: str) -> None:
        """Internal worker executing SQLite to Meilisearch re-indexing."""
        start_time = time.perf_counter()
        logger.info("Background re-indexing job [%s] started", job_id)

        try:
            settings = get_settings()
            storage = get_crawl_storage(settings.crawl_database_path)
            search_client = get_search_client()

            health = search_client.check_health()
            if not health.is_available:
                raise ConnectionError(
                    f"Meilisearch is unreachable at {search_client.url}: {health.error_message}"
                )

            self._update_progress(
                "indexing_meilisearch", "Pushing all SQLite documents to Meilisearch..."
            )
            ingestion_engine = SearchIngestionEngine(
                search_client=search_client,
                storage=storage,
                batch_size=100,
            )
            ingest_res = ingestion_engine.sync_from_storage(purge_deleted=True)

            total_duration = round(time.perf_counter() - start_time, 2)
            final_stats = SyncStats(
                sync_mode="reindex",
                added=ingest_res.indexed_count,
                updated=0,
                deleted=ingest_res.deleted_count,
                unchanged=0,
                total_stored=ingest_res.total_stored,
                total_indexed=ingest_res.total_stored,
                duration_seconds=total_duration,
            )

            with self._lock:
                self._is_syncing = False
                self._current_phase = "idle"
                self._progress_message = f"Re-indexing completed in {total_duration:.2f}s."
                self._duration_seconds = total_duration
                self._last_stats = final_stats
                self._last_error = None

            get_sync_event_bus().publish(
                "sync_completed",
                {
                    "job_id": job_id,
                    "sync_mode": "reindex",
                    "indexed": ingest_res.indexed_count,
                    "deleted": ingest_res.deleted_count,
                    "total_stored": ingest_res.total_stored,
                    "duration_seconds": total_duration,
                },
            )
            logger.info("Re-indexing job [%s] finished in %.2fs", job_id, total_duration)

        except Exception as exc:
            total_duration = round(time.perf_counter() - start_time, 2)
            err_msg = str(exc)
            logger.exception("Re-indexing job [%s] failed", job_id)

            with self._lock:
                self._is_syncing = False
                self._current_phase = "failed"
                self._progress_message = f"Re-indexing failed: {err_msg}"
                self._duration_seconds = total_duration
                self._last_error = err_msg

            get_sync_event_bus().publish(
                "sync_failed",
                {"job_id": job_id, "error": err_msg, "duration_seconds": total_duration},
            )



    def start_background_scheduler(self, interval_seconds: int = 30) -> None:
        """Start the automated background polling scheduler if not already running."""
        with self._lock:
            if self._scheduler_running:
                return
            self._scheduler_running = True

        try:
            loop = asyncio.get_running_loop()
            self._scheduler_task = loop.create_task(self._scheduler_loop(interval_seconds))
            logger.info("Auto-sync background scheduler task spawned (Interval: %ds)", interval_seconds)
        except RuntimeError:
            logger.warning("No running asyncio event loop found; background scheduler not started.")

    def stop_background_scheduler(self) -> None:
        """Stop the automated background polling scheduler cleanly."""
        with self._lock:
            self._scheduler_running = False
            task = self._scheduler_task
            self._scheduler_task = None

        if task and not task.done():
            task.cancel()
            logger.info("Auto-sync background scheduler task cancelled.")

    async def _scheduler_loop(self, interval_seconds: int) -> None:
        """Background coroutine that periodically checks Google Drive for modifications."""
        logger.info("Auto-sync background loop active (Checking every %ds)", interval_seconds)
        while self._scheduler_running:
            try:
                await asyncio.sleep(interval_seconds)
                if not self._scheduler_running:
                    break

                if not self.is_syncing:
                    settings = get_settings()
                    provider = get_auth_provider(settings)
                    # Only attempt sync if auth credentials are valid
                    if provider.is_authenticated:
                        logger.debug("Auto-sync scheduler checking Google Drive for modifications...")
                        try:
                            self.trigger_sync(full_refresh=False, export_content=True)
                        except SyncInProgressError:
                            pass
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Auto-sync background loop encountered error: %s", exc)
                await asyncio.sleep(10)
        logger.info("Auto-sync background loop terminated.")


def get_sync_manager() -> SyncManager:
    """Return the global SyncManager singleton."""
    return SyncManager.get_instance()

