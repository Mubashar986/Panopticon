"""CLI script to initialize and inspect Panopticon Meilisearch index schema."""

import json
import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.search.client import get_search_client
from app.search.schema import configure_index_schema, get_index_schema


def main() -> int:
    client = get_search_client()
    print("=" * 60)
    print("Panopticon Meilisearch Schema Initializer")
    print("=" * 60)
    print(f"Target Host: {client.url}")
    print(f"Index Name:  {client.index_name}")

    health = client.check_health()
    if not health.is_available:
        print("\n[ERROR] Meilisearch is OFFLINE. Cannot apply index schema.")
        print(f"Details: {health.error_message}")
        print("\nPlease start Meilisearch first:")
        print("  .\\bin\\meilisearch.exe --db-path ./data/meili_data --master-key masterKey_panopticon_local_dev --no-analytics")
        print("=" * 60)
        return 1

    print("\n[1/2] Connecting to index and applying schema settings...")
    try:
        updated_settings = configure_index_schema(client)
        print("[SUCCESS] Schema settings applied successfully!")
        
        print("\n[2/2] Active Index Schema Summary:")
        print(f"  • Searchable: {json.dumps(updated_settings.get('searchableAttributes', []))}")
        print(f"  • Filterable: {json.dumps(updated_settings.get('filterableAttributes', []))}")
        print(f"  • Sortable:   {json.dumps(updated_settings.get('sortableAttributes', []))}")
        print(f"  • Ranking:    {json.dumps(updated_settings.get('rankingRules', []))}")
        print("=" * 60)
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Failed to apply schema: {exc}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
