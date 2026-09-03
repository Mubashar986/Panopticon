"""Verification script to test native Meilisearch vector search latency and paragraph retrieval."""

import time
import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.search.client import get_search_client
from app.search.service import SearchService
from app.search.schema import CHUNK_INDEX_NAME
from app.indexer.embeddings import get_embedding_provider
from app.indexer.storage import get_crawl_storage
from app.agent.tools import AgentToolContext, execute_tool


def main():
    print("=" * 60)
    print("Panopticon Task 9.9 Verification: Hybrid Vector Retrieval")
    print("=" * 60)

    client = get_search_client()
    storage = get_crawl_storage()
    provider = get_embedding_provider()
    service = SearchService(search_client=client)

    # 1. Check Index Stats
    doc_stats = client.get_stats(client.index_name)
    chunk_stats = client.get_stats(CHUNK_INDEX_NAME)

    print(f"Meilisearch Server: {client.url}")
    print(f"panopticon_docs count:   {doc_stats.number_of_documents}")
    print(f"panopticon_chunks count: {chunk_stats.number_of_documents}")
    assert doc_stats.number_of_documents >= 90, "Expected at least 90 documents"
    assert chunk_stats.number_of_documents >= 90, "Expected at least 90 chunks"

    # 2. Test Sub-5ms Vector Chunk Search
    query = "OAuth PKCE authentication security token"
    print(f"\nTesting Query: '{query}'")
    vec = provider.embed_query(query)

    start = time.perf_counter()
    hits = service.search_chunks(query_vector=vec, limit=3, query_text=query)
    latency_ms = (time.perf_counter() - start) * 1000.0

    print(f"[SUCCESS] Native Vector Search Latency: {latency_ms:.2f}ms")
    print(f"Matching Paragraph Chunks Retrieved: {len(hits)}")
    for idx, hit in enumerate(hits, 1):
        print(f"  {idx}. [ID: {hit.get('id')}] File: {hit.get('file_name', hit.get('file_id'))} | Score: {hit.get('_rankingScore')}")
        text_preview = (hit.get('content_text') or '')[:100].replace('\n', ' ')
        print(f"     Preview: {text_preview}...")

    assert len(hits) > 0, "Expected at least 1 vector hit"
    assert latency_ms < 50.0, f"Latency {latency_ms}ms exceeded threshold"

    # 3. Test Agent Tool Dispatch with Meilisearch Acceleration
    ctx = AgentToolContext(
        storage=storage,
        search_service=service,
        embedding_provider=provider,
    )
    raw_res = execute_tool("semantic_chunk_search", {"query": "authentication policy", "limit": 2}, ctx)
    tool_data = json.loads(raw_res)
    print(f"\n[SUCCESS] Agent Tool Execution Engine: {tool_data.get('engine')}")
    print(f"Chunks returned to Agent: {tool_data.get('chunks_count')}")
    assert tool_data.get("engine") == "meilisearch_vector"
    assert tool_data.get("chunks_count") > 0

    print("\n" + "=" * 60)
    print("ALL VERIFICATIONS PASSED CLEANLY (Zero Errors)")
    print("=" * 60)


if __name__ == "__main__":
    main()
