import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.search.client import get_search_client


def main() -> int:
    client = get_search_client()
    print("=" * 60)
    print("Panopticon Meilisearch Health Diagnostic")
    print("=" * 60)
    print(f"Target Host: {client.url}")
    print(f"Index Name:  {client.index_name}")

    health = client.check_health()
    if health.is_available:
        print("\n[SUCCESS] Meilisearch is ONLINE and Healthy!")
        print(f"Status:   {health.status}")
        print(f"Version:  {health.version or 'N/A'}")
        print("=" * 60)
        return 0
    else:
        print("\n[WARNING] Meilisearch is OFFLINE or Unreachable.")
        print(f"Details:  {health.error_message}")
        print("\nTo start Meilisearch locally:")
        print("Option A (Docker):")
        print("  docker run -d -p 7700:7700 -e MEILI_NO_ANALYTICS=true -v meili_data:/meili_data getmeili/meilisearch:v1.12")
        print("\nOption B (Standalone Binary):")
        print("  python scripts/download_meilisearch.py")
        print(f"  .\\bin\\meilisearch.exe --db-path ./data/meili_data --master-key {client.api_key or 'devMasterKey'} --no-analytics")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
