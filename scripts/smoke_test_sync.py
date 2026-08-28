"""Smoke test script for IncrementalSyncEngine and SQLite Storage."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.auth.factory import get_auth_provider
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.indexer.crawler import DriveCrawler
from app.indexer.exporter import ContentExporter
from app.indexer.storage import CrawlStorage
from app.indexer.sync import IncrementalSyncEngine

logger = get_logger("panopticon.scripts.smoke_sync")


def main() -> int:
    """Execute live bootstrap sync followed by an incremental sync run."""
    if sys.stdout.encoding != "utf-8" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    print("\n" + "=" * 65)
    print(" [PANOPTICON] Incremental Sync & SQLite Storage Live Smoke Test")
    print("=" * 65 + "\n")

    try:
        provider = get_auth_provider()
        print(f"[*] Active Auth Provider: {provider.__class__.__name__}")
        print(f"[*] SQLite Database Path: {settings.crawl_database_path}")

        storage = CrawlStorage(db_path=settings.crawl_database_path)
        crawler = DriveCrawler(provider=provider)
        exporter = ContentExporter(provider=provider)

        sync_engine = IncrementalSyncEngine(
            crawler=crawler,
            exporter=exporter,
            storage=storage,
        )

        # -------------------------------------------------------------
        # RUN 1: Full Bootstrap Sync
        # -------------------------------------------------------------
        print("\n" + "-" * 50)
        print(" [PHASE 1] Executing Initial Bootstrap Sync (full_refresh=True)...")
        print("-" * 50)

        res1 = sync_engine.run_sync(full_refresh=True, export_content=True, page_size=50)

        print(f" * Sync Mode:       {'FULL BOOTSTRAP' if res1.is_full_refresh else 'INCREMENTAL'}")
        print(f" * Added Files:     {res1.added_count}")
        print(f" * Updated Files:   {res1.updated_count}")
        print(f" * Deleted Files:   {res1.deleted_count}")
        print(f" * Total in SQLite: {res1.total_stored}")
        print(f" * Duration:        {res1.duration_seconds:.3f}s")
        print(f" * New Watermark:   {res1.new_watermark.isoformat()}")

        # -------------------------------------------------------------
        # RUN 2: Immediate Incremental Delta Sync
        # -------------------------------------------------------------
        print("\n" + "-" * 50)
        print(" [PHASE 2] Executing Immediate Incremental Delta Sync...")
        print("-" * 50)

        res2 = sync_engine.run_sync(full_refresh=False, export_content=True, page_size=50)

        print(f" * Sync Mode:       {'FULL BOOTSTRAP' if res2.is_full_refresh else 'INCREMENTAL DELTA'}")
        print(f" * Watermark Used:  {res2.watermark_used.isoformat() if res2.watermark_used else 'None'}")
        print(f" * Added Files:     {res2.added_count}")
        print(f" * Updated Files:   {res2.updated_count}")
        print(f" * Deleted Files:   {res2.deleted_count}")
        print(f" * Unchanged Files: {res2.unchanged_count}")
        print(f" * Total in SQLite: {res2.total_stored}")
        print(f" * Duration:        {res2.duration_seconds:.3f}s")

        # -------------------------------------------------------------
        # Storage Record Sample Inspection
        # -------------------------------------------------------------
        print("\n" + "-" * 50)
        print(" [SAMPLE] Inspecting Top 5 Records from SQLite Storage:")
        print("-" * 50)
        sample_files = storage.list_files(limit=5)
        for idx, f in enumerate(sample_files, start=1):
            type_badge = "[DOC]" if f.is_doc else ("[SHEET]" if f.is_sheet else "[FILE]")
            status_badge = f"[{f.sharing_status.upper()}]"
            snippet_preview = (f.content_snippet or "No snippet")[:60]
            print(f"  {idx}. {type_badge} {status_badge:<9} {f.name}")
            print(f"     Owner: {f.primary_owner} | Snippet: \"{snippet_preview}...\"")

        print("\n" + "=" * 65)
        print(" [SUCCESS] Incremental Sync & Storage Smoke Test Passed!")
        print("=" * 65 + "\n")
        return 0

    except Exception as e:
        print(f"\n[ERROR] Sync Smoke Test Failed: {e}", file=sys.stderr)
        logger.exception("Incremental Sync Smoke Test encountered unhandled error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
