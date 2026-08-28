# ADR-0001: Selection of Meilisearch as Local Typo-Tolerant Search Engine

**Status:** Accepted  
**Date:** 2026-08-27  
**Decision Type:** ADR (Architecture Decision Record)  
**Authors:** Principal Systems Architect  
**Task Association:** Epic 3 / Task 3.1 — Stand up a local Meilisearch instance  

---

## 1. Context & Problem Statement

Panopticon indexes Google Docs and Google Sheets filenames, project label tags, and extracted text snippets. Users search for project names (e.g. "Project Falcon", "Alpha-Phase-2") and expect:
1. Fast, typo-tolerant search results (e.g., searching "Falcn" or "Palcon" surfaces "Project Falcon").
2. Hybrid ranking where governed Google Drive Labels match first, followed by title matches, and finally full-text content matches.
3. Lightweight local execution without heavy infrastructure overhead on a developer laptop.
4. Clean separation of search indexing from storage and backend routing (Non-Negotiable Product Constraint 3 & 7).

We must choose a search engine technology that satisfies local developer ergonomics, zero-cloud dependency for local search, typo tolerance, and fast response times (<20ms).

---

## 2. Decision

We choose **Meilisearch** as the search engine for Panopticon.

1. **Local Daemon / Container:** Runs locally as a standalone binary or Docker container (`localhost:7700`) with zero external cloud dependencies.
2. **Python Client Integration:** Communicates via the official `meilisearch-python` SDK encapsulated inside an adapter layer (`app/indexer/` & `app/search/`).
3. **Index Structure:** A single primary index `panopticon_files` with preconfigured searchable attributes (`name`, `labels`, `content_snippet`, `owner`), filterable attributes (`mime_type`, `sharing_status`, `labels`), and custom ranking rules favoring label matches.
4. **Typo Tolerance:** Built-in Damerau-Levenshtein distance typo tolerance out-of-the-box.

---

## 3. Evaluated Alternatives

### Option A: Meilisearch (SELECTED)
- **Score:** 82/85
- **Pros:** Ultra-fast instant search (Rust-based); first-class typo tolerance; simple REST/SDK API; lightweight memory footprint (<50MB idle); zero schema complexity.
- **Cons:** In-memory + LMDB storage model requires index rebuilding if data format changes drastically; not designed for heavy distributed clusters (not needed for local/mid-size index).

### Option B: SQLite FTS5 + Levenshtein Extension
- **Score:** 68/85
- **Pros:** Single-file database; already used for crawl state; zero extra daemon process.
- **Cons:** FTS5 BM25 lacks native typo tolerance without custom spell-checking triggers or complex trie/trigram extensions; ranking configuration is manual and complex.

### Option C: Elasticsearch / OpenSearch
- **Score:** 52/85
- **Pros:** Industry standard enterprise search; highly configurable analyzers and tokenizers.
- **Cons:** Heavy JVM resource footprint (>1GB RAM); steep operational and configuration curve; excessive for single-laptop / small-team project search tool.

### Option D: PostgreSQL + `pg_trgm`
- **Score:** 65/85
- **Pros:** Solid trigram fuzzy matching; relational data integrity.
- **Cons:** Requires running a full Postgres server; slower fuzzy ranking on large text corpora than dedicated search engines.

---

## 4. Consequences & Guarantees

### Positive Consequences
- **Instant Typo Tolerance:** Users typing misspellings or partial names find documents instantly without custom fuzzy query algorithms.
- **Custom Ranking Rules:** Drive Labels are weighted above title and content effortlessly via `rankingRules`.
- **Architectural Seam:** Search queries execute exclusively against local Meilisearch index with zero Google Drive API calls at search time (Constraint 3).

### Negative Consequences / Trade-offs
- Requires running a local Meilisearch process (or docker container) alongside FastAPI backend.
- Python indexer needs to synchronize SQLite crawl records to Meilisearch index via batch upsert.

---

## 5. Compliance with Mandatory Product Constraints

- **Constraint 2 (Pointer / Snippet Index):** COMPLIANT. Meilisearch only stores document metadata, tags, and 500-char snippets.
- **Constraint 3 (Search against local index only):** COMPLIANT. Meilisearch handles all search queries locally.
- **Constraint 7 (Adapter Pattern Isolation):** COMPLIANT. Meilisearch client calls are isolated within dedicated adapter modules.
- **Constraint 9 (No Secrets in Index):** COMPLIANT. Document records contain public metadata and snippets only, no credentials.

---

```yaml
adr_id: ADR-0001
title: "Selection of Meilisearch as Local Typo-Tolerant Search Engine"
decision_level: "Architecture"
status: accepted
date: "2026-08-27"
depends_on: []
supersedes: []
gates:
  - id: 1
    result: pass
    evidence: "Meilisearch operates purely as an index pointer"
  - id: 7
    result: pass
    evidence: "Crawled content sanitized before indexing"
  - id: 10
    result: pass
    evidence: "Isolated behind adapter interface"
recommended_option: "Option A: Meilisearch"
priority_tier_used_for_tiebreak: "Scalability / Performance / MVP fit"
open_assumptions: []
```
