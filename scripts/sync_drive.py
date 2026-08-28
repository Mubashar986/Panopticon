"""Production CLI script for fast Google Drive incremental sync and search index update."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Configure UTF-8 on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.auth.factory import get_auth_provider
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.indexer.crawler import DriveCrawler
from app.indexer.exporter import ContentExporter
from app.indexer.storage import get_crawl_storage
from app.indexer.sync import IncrementalSyncEngine
from app.search.client import get_search_client
from app.search.ingestion import SearchIngestionEngine

logger = get_logger("panopticon.scripts.sync_drive")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fast Google Drive incremental synchronizer and Meilisearch updater."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Force a full re-crawl of all documents instead of fast incremental delta",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        default=False,
        help="Skip pushing updates to Meilisearch search index",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=50,
        help="API page size for Google Drive pagination",
    )

    args = parser.parse_args()
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    overall_start = time.perf_counter()

    print("=" * 65)
    print(" [PANOPTICON] Google Drive Fast Synchronizer")
    print("=" * 65)

    try:
        # 1. Initialize Auth and Storage
        provider = get_auth_provider()
        storage = get_crawl_storage(settings.crawl_database_path)
        existing_watermark = storage.get_watermark()

        is_incremental = bool(existing_watermark and not args.full)
        mode_label = "FAST INCREMENTAL DELTA" if is_incremental else "FULL BOOTSTRAP RE-CRAWL"

        print(f"[*] Mode:           {mode_label}")
        print(f"[*] Active Auth:    {provider.__class__.__name__}")
        print(f"[*] SQLite DB:      {storage.db_path}")
        if is_incremental and existing_watermark:
            print(f"[*] Last Sync Time: {existing_watermark.isoformat()}")

        # 2. Run Google Drive Sync
        print(f"\n[1/2] Checking Google Drive for changes...")
        crawler = DriveCrawler(provider=provider)
        exporter = ContentExporter(provider=provider)
        sync_engine = IncrementalSyncEngine(
            crawler=crawler,
            exporter=exporter,
            storage=storage,
        )

        drive_res = sync_engine.run_sync(
            full_refresh=not is_incremental,
            export_content=True,
            page_size=args.page_size,
        )

        print(f"[✓] Google Drive Sync Complete in {drive_res.duration_seconds:.2f}s:")
        print(f"    • Added:     {drive_res.added_count}")
        print(f"    • Updated:   {drive_res.updated_count}")
        print(f"    • Deleted:   {drive_res.deleted_count}")
        print(f"    • Unchanged: {drive_res.unchanged_count}")
        print(f"    • Total DB:  {drive_res.total_stored}")

        # 3. Update Meilisearch Index
        if not args.skip_search:
            print(f"\n[2/2] Updating Meilisearch index...")
            search_client = get_search_client()
            health = search_client.check_health()

            if health.is_available:
                ingestion_engine = SearchIngestionEngine(
                    search_client=search_client,
                    storage=storage,
                    batch_size=100,
                )
                ingest_res = ingestion_engine.sync_from_storage(purge_deleted=True)
                print(f"[✓] Meilisearch Updated in {ingest_res.duration_seconds:.2f}s:")
                print(f"    • Indexed:   {ingest_res.indexed_count}")
                print(f"    • Purged:    {ingest_res.deleted_count}")
                print(f"    • Total Searchable: {ingest_res.total_stored}")
            else:
                print(f"[!] Meilisearch is OFFLINE. Skipped search index update.")
                print(f"    (Start it with: .\\bin\\meilisearch.exe --db-path ./data/meili_data)")
        else:
            print(f"\n[2/2] Skipped Meilisearch update (--skip-search).")

        total_duration = time.perf_counter() - overall_start
        print("\n" + "=" * 65)
        print(f" [SUCCESS] Pipeline Finished in {total_duration:.2f}s!")
        print("=" * 65 + "\n")
        return 0

    except Exception as exc:
        print(f"\n[ERROR] Sync failed: {exc}", file=sys.stderr)
        logger.exception("Sync pipeline encountered unhandled error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
