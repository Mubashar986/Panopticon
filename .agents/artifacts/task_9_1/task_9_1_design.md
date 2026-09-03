# Stage 2: Codebase Design — Task 9.1: Semantic Text Chunking & Embedding Pipeline

**Task ID:** `9.1`  
**Task Title:** Implement Semantic Text Chunking & Local Embeddings Pipeline  
**Epic:** Epic 9 — Agentic RAG Intelligence & OpenRouter Provider Seam  
**Target Files:**
- `[NEW]` [`app/indexer/chunker.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/chunker.py)
- `[NEW]` [`app/indexer/embeddings.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/embeddings.py)
- `[MODIFY]` [`app/indexer/models.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/models.py)
- `[MODIFY]` [`app/indexer/storage.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/storage.py)
- `[MODIFY]` [`app/indexer/sync.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/sync.py)
- `[MODIFY]` [`app/indexer/__init__.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/__init__.py)
- `[NEW]` [`tests/test_chunker.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/tests/test_chunker.py)
- `[NEW]` [`tests/test_embeddings.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/tests/test_embeddings.py)
**Artifact Version:** 1.0.0  
**Status:** READY FOR IMPLEMENTATION  

---

## 1. Current State Snapshot

Currently, Panopticon stores:
1. `files`: File metadata (ID, title, owner, tags, sharing status).
2. `document_versions`: Full exported text snapshot per revision.
3. `document_diffs`: Unified diff patches and AI change summaries between revisions.

There is no chunk-level indexing or vector representation. When an agent or user asks a specific question about a technical specification, the system has no way to locate the exact paragraphs or compute semantic relevance scores.

---

## 2. Proposed Target Architecture

Task 9.1 introduces the semantic vector backbone:
1. **`TextChunker` Engine (`app/indexer/chunker.py`)**: Slices exported document text into overlapping contextual chunks tagged with document title and section headings.
2. **`EmbeddingProvider` Protocol & Implementations (`app/indexer/embeddings.py`)**: Generates normalized embedding vectors using OpenRouter Cloud or local deterministic hash vectors.
3. **SQLite `document_chunks` Table (`app/indexer/storage.py`)**: Persists chunks with foreign key relationships (`file_id`, `version_id`) and provides cosine similarity search.
4. **`IncrementalSyncEngine` Integration (`app/indexer/sync.py`)**: Automatically triggers chunking and embedding generation on newly ingested or updated documents.

```mermaid
graph TD
    subgraph Pipeline ["Ingestion Pipeline"]
        DriveExporter["DriveExporter (Task 4.1)"]
        SyncEngine["IncrementalSyncEngine (app/indexer/sync.py)"]
    end

    subgraph ChunkAndEmbed ["Chunking & Embedding Subsystem"]
        Chunker["TextChunker (app/indexer/chunker.py)"]
        Embedder["EmbeddingProvider (app/indexer/embeddings.py)"]
    end

    subgraph Storage ["SQLite Storage (app/indexer/storage.py)"]
        ChunksTable[("document_chunks Table")]
        CosineSearch["search_similar_chunks()"]
    end

    DriveExporter -->|raw text| SyncEngine
    SyncEngine --> Chunker
    Chunker -->|List[DocumentChunk]| Embedder
    Embedder -->|Chunks with Vector Embeddings| ChunksTable
    ChunksTable --> CosineSearch
```

---

## 3. File-Level Impact Analysis

### `[MODIFY]` [`app/indexer/models.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/models.py)
- **What changes:** Add `DocumentChunk` domain model:
  ```python
  class DocumentChunk(BaseModel):
      id: str  # chk_<hash/uuid>
      file_id: str
      version_id: str | None = None
      chunk_index: int
      section_heading: str | None = None
      content_text: str
      char_start: int
      char_end: int
      embedding: list[float] | None = None
      created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
  ```

### `[NEW]` [`app/indexer/chunker.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/chunker.py)
- **Purpose:** Pure Python sliding-window chunker with section heading parsing:
  - `TextChunker(chunk_size: int = 1500, overlap: int = 200)`
  - `chunk_document(content_text: str, file_id: str, file_name: str, version_id: str | None) -> list[DocumentChunk]`
  - Detects markdown headers (`#`, `##`, `###`) and uppercase titles.
  - Prepares text with context prefix: `[Document: {file_name} | Section: {heading}]\n\n{text}`.

### `[NEW]` [`app/indexer/embeddings.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/embeddings.py)
- **Purpose:** Pluggable vector embedding engine:
  - `EmbeddingProvider(Protocol)` with `embed_texts(texts) -> list[list[float]]`, `embed_query(query) -> list[float]`, and `dimension: int`.
  - `OpenRouterEmbeddingProvider`: Calls OpenRouter / OpenAI-compatible embedding endpoint via `httpx`.
  - `DeterministicHashEmbeddingProvider`: Fast local term-frequency vectorizer (128-dim, normalized) for 100% offline zero-setup operation.
  - `cosine_similarity(vec1: list[float], vec2: list[float]) -> float` helper.
  - `get_embedding_provider(settings: Settings | None) -> EmbeddingProvider` factory.

### `[MODIFY]` [`app/indexer/storage.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/storage.py)
- **What changes:**
  - Create `document_chunks` table with `ON DELETE CASCADE` foreign keys.
  - Add indices `idx_chunks_file_idx` and `idx_chunks_version`.
  - Add methods:
    - `save_chunks(chunks: list[DocumentChunk]) -> int`
    - `get_chunks_for_file(file_id: str) -> list[DocumentChunk]`
    - `delete_chunks_for_file(file_id: str) -> int`
    - `search_similar_chunks(query_vector: list[float], limit: int = 5, file_id_filter: str | None = None) -> list[tuple[DocumentChunk, float]]`
    - `count_chunks(file_id: str | None = None) -> int`

### `[MODIFY]` [`app/indexer/sync.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/indexer/sync.py)
- **What changes:**
  - Inject `chunker: TextChunker | None = None` and `embedding_provider: EmbeddingProvider | None = None` into `IncrementalSyncEngine`.
  - In `run_sync()`, when `export_content=True` and content text is exported, chunk document, generate embeddings, and persist chunks to SQLite.

---

## 4. Regression Risk Matrix

| Risk ID | Risk Description | Severity | Affected Area | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **R-01** | OpenRouter embedding network timeout | 🟢 Low | `sync.py` / `embeddings.py` | Try/except block falls back to `DeterministicHashEmbeddingProvider` without crashing crawl. |
| **R-02** | Stale chunks when file is re-indexed or modified | 🟢 Low | `storage.py` | `delete_chunks_for_file(file_id)` called before inserting new chunks for that file. |
| **R-03** | Slow cosine similarity on massive chunk counts | 🟢 Low | `storage.py` | Vector dot products pre-filter or limit to relevant documents; Meilisearch vector search seam in Epic 9.3. |

---

## 5. Rollback Plan

### If Changes Are Uncommitted:
```bash
git checkout -- app/indexer/models.py app/indexer/storage.py app/indexer/sync.py app/indexer/__init__.py
rm app/indexer/chunker.py app/indexer/embeddings.py
```

### If Changes Are Committed:
```bash
git revert HEAD --no-edit
pytest tests/
```
