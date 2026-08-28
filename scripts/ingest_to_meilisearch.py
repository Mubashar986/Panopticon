"""CLI script to ingest all stored Google Drive files from SQLite into Meilisearch."""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.indexer.storage import get_crawl_storage
from app.search.client import get_search_client
from app.search.ingestion import SearchIngestionEngine


def main() -> int:
    client = get_search_client()
    storage = get_crawl_storage()

    print("=" * 60)
    print("Panopticon SQLite -> Meilisearch Ingestion Pipeline")
    print("=" * 60)
    print(f"Target Host:     {client.url}")
    print(f"Index Name:      {client.index_name}")
    print(f"SQLite Database: {storage.db_path}")

    # Check server health
    health = client.check_health()
    if not health.is_available:
        print("\n[ERROR] Meilisearch is OFFLINE. Cannot run ingestion.")
        print(f"Details: {health.error_message}")
        print("\nPlease start Meilisearch:")
        print("  .\\bin\\meilisearch.exe --db-path ./data/meili_data --master-key masterKey_panopticon_local_dev --no-analytics")
        print("=" * 60)
        return 1

    file_count = storage.count_files()
    print(f"\nDiscovered {file_count} active documents in SQLite storage.")
    if file_count == 0:
        print("[INFO] Storage is currently empty. Run crawler first:")
        print("  python scripts/smoke_test_sync.py")
        print("=" * 60)
        return 0

    print("Starting batch ingestion...")
    engine = SearchIngestionEngine(search_client=client, storage=storage, batch_size=100)

    try:
        result = engine.sync_from_storage(purge_deleted=True)
        print("\n[SUCCESS] Ingestion and synchronization complete!")
        print(f"  • Documents Upserted: {result.indexed_count}")
        print(f"  • Batches Processed:  {result.batch_count}")
        print(f"  • Deleted/Purged:     {result.deleted_count}")
        print(f"  • Total in Search:    {result.total_stored}")
        print(f"  • Elapsed Duration:   {result.duration_seconds}s")
        print("=" * 60)
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Ingestion failed: {exc}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
