"""Smoke test script for DriveCrawler against real or mock Google Drive API."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.auth.factory import get_auth_provider
from app.core.logging import get_logger
from app.indexer.crawler import DriveCrawler

logger = get_logger("panopticon.scripts.smoke_crawler")


def main() -> int:
    """Run smoke test for DriveCrawler."""
    if sys.stdout.encoding != "utf-8" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("\n" + "=" * 60)
    print(" [PANOPTICON] Google Drive Crawler Live Smoke Test")
    print("=" * 60 + "\n")

    try:
        provider = get_auth_provider()
        print(f"[*] Active Auth Provider: {provider.provider_name}")

        print("[*] Initializing DriveCrawler...")
        crawler = DriveCrawler(provider=provider)

        print("[*] Executing crawl_with_stats (pageSize=50)...")
        files, stats = crawler.crawl_with_stats(page_size=50)

        print("\n" + "-" * 50)
        print(" [SUMMARY] CRAWL TELEMETRY SUMMARY")
        print("-" * 50)
        print(f" * Total Pages Fetched:    {stats.pages_fetched}")
        print(f" * Total Files Discovered: {stats.files_discovered}")
        print(f" * Google Docs Count:      {stats.docs_count}")
        print(f" * Google Sheets Count:    {stats.sheets_count}")
        print(f" * Other Files Count:      {stats.other_count}")
        print(f" * Elapsed Duration:       {stats.duration_seconds:.3f}s")
        print("-" * 50)

        if files:
            print("\n Discovered Files Preview (First 10):")
            for idx, f in enumerate(files[:10], start=1):
                type_badge = "[DOC]" if f.is_doc else ("[SHEET]" if f.is_sheet else "[FILE]")
                print(f"  {idx:2d}. {type_badge} {f.name} (ID: {f.id}, Owner: {f.primary_owner})")
        else:
            print("\n [INFO] No Google Docs or Sheets found matching the query.")

        print("\n[SUCCESS] Google Drive Crawler Smoke Test Completed Successfully!\n")
        return 0

    except Exception as e:
        print(f"\n[ERROR] Crawler Smoke Test Failed: {e}", file=sys.stderr)
        logger.exception("Smoke test failed with error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
