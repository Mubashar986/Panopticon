"""Interactive CLI tool to test queries, typos, filters, and ranking in Panopticon."""

import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.search.client import get_search_client
from app.search.service import get_search_service


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Panopticon Search CLI: Test fuzzy typo search and ranking."
    )
    parser.add_argument(
        "-q", "--query", default="Falcn", help="Search query string (e.g., 'Falcn', 'Budget')"
    )
    parser.add_argument(
        "-t",
        "--file-type",
        choices=["document", "spreadsheet", "other"],
        default=None,
        help="Filter by categorical file type",
    )
    parser.add_argument(
        "--tag", default=None, help="Filter by exact project tag (e.g., 'Falcon')"
    )
    parser.add_argument(
        "-s",
        "--sharing",
        choices=["private", "shared", "domain"],
        default=None,
        help="Filter by sharing status",
    )
    parser.add_argument(
        "-l", "--limit", type=int, default=10, help="Maximum number of hits to display"
    )

    args = parser.parse_args()

    client = get_search_client()
    health = client.check_health()
    if not health.is_available:
        print("[ERROR] Meilisearch is offline. Start it using:")
        print("  .\\bin\\meilisearch.exe --db-path ./data/meili_data --master-key masterKey_panopticon_local_dev --no-analytics")
        return 1

    service = get_search_service(client)

    print("=" * 70)
    print(f"Panopticon Search: Query='{args.query}' | Filter Type={args.file_type} | Tag={args.tag}")
    print("=" * 70)

    try:
        res = service.search(
            query=args.query,
            file_type=args.file_type,
            project_tag=args.tag,
            sharing_status=args.sharing,
            limit=args.limit,
        )

        print(f"Found {res.total_hits} hits in {res.processing_time_ms}ms (Showing top {len(res.hits)}):\n")

        if not res.hits:
            print("  [No results found]")
            print("=" * 70)
            return 0

        for i, hit in enumerate(res.hits, 1):
            badge = f"[{hit.matched_via.upper()}:{hit.confidence.upper()}]"
            tags_str = f" Tags: {hit.project_tags}" if hit.project_tags else ""
            print(f"{i:2d}. {hit.name} {badge} ({hit.file_type}){tags_str}")
            print(f"    Owner: {hit.primary_owner} | Modified: {hit.modified_time or 'Unknown'}")
            if hit.highlighted_snippet:
                snippet_clean = (
                    hit.highlighted_snippet.replace("<em>", ">>")
                    .replace("</em>", "<<")
                    .replace("\ufeff", "")
                    .strip()
                )
                print(f"    Snippet: \"{snippet_clean}\"")
            elif hit.content_snippet:
                clean_content = hit.content_snippet[:80].replace("\ufeff", "")
                print(f"    Snippet: \"{clean_content}...\"")
            if hit.web_view_link:
                print(f"    Link: {hit.web_view_link}")
            print("-" * 70)

        # Facet summary
        if res.facet_distribution:
            print("\nFacets Summary:")
            for facet_name, counts in res.facet_distribution.items():
                if counts:
                    print(f"  • {facet_name}: {counts}")

        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"[ERROR] Search failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
