"""CLI script to ingest all stored Google Drive files from SQLite into Meilisearch."""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.indexer.chunker import TextChunker
from app.indexer.embeddings import get_embedding_provider
from app.indexer.storage import get_crawl_storage
from app.search.client import get_search_client
from app.search.ingestion import SearchIngestionEngine
from app.search.schema import CHUNK_INDEX_NAME


def main() -> int:
    client = get_search_client()
    storage = get_crawl_storage()
    embedding_provider = get_embedding_provider()

    print("=" * 60)
    print("Panopticon SQLite -> Meilisearch Dual-Index Ingestion Pipeline")
    print("=" * 60)
    print(f"Target Host:        {client.url}")
    print(f"Docs Index:         {client.index_name}")
    print(f"Chunks Index:       {CHUNK_INDEX_NAME}")
    print(f"SQLite Database:    {storage.db_path}")
    print(f"Embedding Provider: {embedding_provider.__class__.__name__} (dim={embedding_provider.dimension})")

    # Check server health
    health = client.check_health()
    if not health.is_available:
        print("\n[ERROR] Meilisearch is OFFLINE. Cannot run ingestion.")
        print(f"Details: {health.error_message}")
        print("\nPlease start Meilisearch:")
        print("  .\\bin\\meilisearch.exe --db-path ./data/meili_data --master-key masterKey_panopticon_local_dev --no-analytics")
        print("=" * 60)
        return 1

    # Enable vector store feature
    print("\nAsserting Meilisearch vector store capability...")
    client.enable_vector_store()

    file_count = storage.count_files()
    chunk_count = storage.count_chunks()
    print(f"\nDiscovered {file_count} active files and {chunk_count} chunks in SQLite storage.")
    if file_count == 0:
        print("[INFO] Storage is currently empty. Run crawler first:")
        print("  python scripts/smoke_test_sync.py")
        print("=" * 60)
        return 0

    # Ensure all files have baseline chunks generated
    chunker = TextChunker()
    files = storage.list_files()
    missing_chunks_count = 0

    for f in files:
        existing = storage.get_chunks_for_file(f.id)
        if not existing:
            # Use content_snippet or fallback text
            text = f.content_snippet or f"{f.name} Google Drive document."
            chunks = chunker.chunk_document(content_text=text, file_id=f.id, file_name=f.name)
            if chunks:
                texts = [c.content_text for c in chunks]
                embeddings = embedding_provider.embed_texts(texts)
                enriched = [
                    c.model_copy(update={"embedding": emb})
                    for c, emb in zip(chunks, embeddings)
                ]
                storage.save_chunks(enriched)
                missing_chunks_count += len(enriched)

    if missing_chunks_count > 0:
        print(f"Bootstrapped {missing_chunks_count} missing semantic chunks into SQLite.")

    total_chunks = storage.count_chunks()
    print(f"Total chunks ready for vector indexing: {total_chunks}")

    print("\nStarting batch dual-index ingestion...")
    engine = SearchIngestionEngine(
        search_client=client,
        storage=storage,
        batch_size=100,
        embedding_provider=embedding_provider,
    )

    try:
        result = engine.sync_from_storage(purge_deleted=True, sync_chunks=True)
        doc_stats = client.get_stats(client.index_name)
        chunk_stats = client.get_stats(CHUNK_INDEX_NAME)

        print("\n[SUCCESS] Ingestion and vector synchronization complete!")
        print(f"  • Documents Upserted:    {result.indexed_count}")
        print(f"  • Document Batches:      {result.batch_count}")
        print(f"  • Deleted/Purged:        {result.deleted_count}")
        print(f"  • Total Docs in Index:   {doc_stats.number_of_documents}")
        print(f"  • Total Chunks in Index: {chunk_stats.number_of_documents}")
        print(f"  • Elapsed Duration:      {result.duration_seconds}s")
        print("=" * 60)
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Ingestion failed: {exc}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
