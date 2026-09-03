# ADR-0006: Selection of Semantic Text Chunking Strategy & Embedding Provider Architecture

**Status:** Proposed (Pending Acceptance)  
**Date:** 2026-09-01  
**Decision Type:** ADR (Architecture Decision Record)  
**Authors:** Principal Systems Architect & Lead QA/SRE  
**Task Association:** Epic 9 / Task 9.1 — Semantic Text Chunking & Local Embeddings Pipeline  

---

## 1. Context & Problem Statement

In Epic 8, Panopticon established full-text document versioning, text diff generation, and AI semantic change summaries. However, searching for answers across document bodies (e.g. *"What is mentioned about authentication across all SmartTrade project documents?"*) requires granular semantic retrieval rather than only file-level title/tag search.

Full Google Docs can span 10 to 100+ pages. Directly feeding entire document texts into LLM prompts exceeds token context windows and induces hallucinations. To enable accurate retrieval-augmented generation (RAG) in Epic 9, Panopticon requires:
1. **Semantic Text Chunking:** Splitting raw document text into overlapping contextual passages (e.g., 300–500 tokens / 1,500 characters) preserving section headings and document metadata anchors.
2. **Embedding Generation Strategy:** Generating dense vector representations for each chunk to allow cosine similarity semantic search.
3. **Zero-Setup & Dependency Compliance (Constraint 6 & 11, Rule 3):** Must preserve zero-setup local execution without requiring mandatory GPU hardware, mandatory paid API keys, or unapproved heavy dependencies.

---

## 2. Decision

We choose a **Sliding-Window Semantic Text Chunker** implemented with Python standard library primitives, paired with a swappable **`EmbeddingProvider` Interface** supporting both:
1. **`OpenRouterEmbeddingProvider` (Cloud Default via existing `httpx`):** Uses the existing `OPENROUTER_API_KEY` to generate high-dimensional embeddings (e.g. `text-embedding-3-small` or `baai/bge-large-en-v1.5`) with zero new pip packages.
2. **`DeterministicHashEmbeddingProvider` (Offline Zero-Setup Fallback):** Generates normalized term-frequency vectors locally without any external network calls or pip installs, ensuring 100% testability and offline operation.
3. **Optional `FastEmbedProvider`:** A pluggable seam ready for local ONNX inference (`fastembed` / `BAAI/bge-small-en-v1.5`) when local neural inference is explicitly enabled.

### Key Architectural Commitments:

1. **`TextChunker` Domain Engine (`app/indexer/chunker.py`):**
   - Implements sentence/paragraph-aware sliding window chunking with configurable `chunk_size` (default 1,500 chars / ~350 words) and `overlap` (default 200 chars / ~50 words).
   - Detects markdown headers (`#`, `##`, `###`, uppercase section titles) and prepends a metadata anchor:
     `[Document: {file_name} | Section: {heading}]` to each chunk so isolated chunks retain global document context.
   - Computes character start/end offsets (`char_start`, `char_end`) and sequential `chunk_index`.

2. **Decoupled `EmbeddingProvider` Protocol (`app/indexer/embeddings.py`):**
   ```python
   class EmbeddingProvider(Protocol):
       def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
       def embed_query(self, query: str) -> list[float]: ...
       @property
       def dimension(self) -> int: ...
   ```
   - Core indexing and search logic never calls vendor embedding APIs directly (Constraint 7).

3. **SQLite Relational Persistence for Chunks (`app/indexer/storage.py`):**
   - New table `document_chunks`:
     - `id TEXT PRIMARY KEY` (`chk_{uuid}`)
     - `file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE`
     - `version_id TEXT REFERENCES document_versions(id) ON DELETE CASCADE`
     - `chunk_index INTEGER NOT NULL`
     - `section_heading TEXT`
     - `content_text TEXT NOT NULL`
     - `char_start INTEGER NOT NULL`
     - `char_end INTEGER NOT NULL`
     - `embedding_json TEXT` (JSON-serialized float array)
     - `created_at TIMESTAMP NOT NULL`
   - B-Tree indices on `(file_id, chunk_index)` and `version_id` for $O(\log N)$ joins and cascaded deletions.

---

## 3. Evaluated Alternatives

### Option A: Standard Library Chunker + Dual Cloud/Hash Embedding Seam (SELECTED)
- **Description:** Pure Python sliding-window chunker + `httpx` OpenRouter embedding client with deterministic local fallback.
- **Score:** 90/100
- **Pros:** Zero new pip dependencies required; uses existing `httpx` and `OPENROUTER_API_KEY`; 100% offline fallback; full compliance with Rule 3 and Constraint 11.
- **Cons:** Cloud embeddings require network connectivity (mitigated by deterministic local fallback).

### Option B: Mandatory `sentence-transformers` / `torch`
- **Description:** Install PyTorch (~2GB download) and run local HuggingFace embedding models.
- **Score:** 45/100
- **Pros:** High quality local embeddings.
- **Cons (REJECTED):** Violates Rule 3; installs gigabytes of C++ / PyTorch binaries; causes significant installation friction on Windows workstations.

### Option C: `langchain` / `llama-index` Monolithic Framework
- **Description:** Pull in LangChain or LlamaIndex for chunking and vector storage.
- **Score:** 40/100
- **Pros:** Ready-made abstractions.
- **Cons (REJECTED):** Massive dependency bloat (100+ sub-dependencies); high cognitive complexity; leaky abstractions violating Panopticon architectural principles.

---

## 4. Consequences & Migration Impact

- **Positive:**
  - Fast, modular chunking with global document context prepended to every chunk.
  - Zero new pip dependencies added to `pyproject.toml`.
  - Full relational consistency in SQLite with cascading deletes when files are deleted from Google Drive.
- **Negative / Risks:**
  - Cosine similarity across large collections in pure Python/SQLite can be slower than dedicated vector databases for $>100,000$ chunks (sufficient for thousands of enterprise docs; Meilisearch vector integration can be added seamlessly via the same `EmbeddingProvider` seam).

---

## 5. Compliance with Project Constraints

| Constraint | Compliance Status | Rationale |
|---|---|---|
| **Constraint 2** (Index/Pointer Constraint) | ✅ PASS | Chunks store extracted text for semantic retrieval and link directly to Google Drive URLs. |
| **Constraint 6 / 11** (Zero-Setup Guarantee) | ✅ PASS | Does not require mandatory GPU or paid credentials; includes local deterministic embedding provider. |
| **Constraint 7** (Vendor Isolation) | ✅ PASS | Abstracted behind `EmbeddingProvider` protocol. |
| **Constraint 10** (Safe Incremental Sync) | ✅ PASS | Foreign keys with `ON DELETE CASCADE` ensure stale chunks are purged when documents are removed or re-indexed. |
| **Rule 3** (Zero Silent Dependency Ingestion) | ✅ PASS | Zero new external libraries introduced; leverages existing `httpx` and standard library. |
