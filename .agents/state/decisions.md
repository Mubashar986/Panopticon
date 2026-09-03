# Durable Architectural & Engineering Decisions — Panopticon

This file records all formally accepted architectural and technical decisions governing the Panopticon project.

Full decision records live in `docs/adr/`. This file is the human-readable summary of **accepted** decisions only.

---

### [ADR-0001](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/adr/ADR-0001-meilisearch-selection.md): Selection of Meilisearch as Local Search Engine
- **Decision:** Adopt local Meilisearch engine (`localhost:7700`) for typo-tolerant instant search, custom ranking rules, and fast facet filtering.
- **Constraints Enforced:** Local-only search execution, pointer-only snippet index, isolated behind `PanopticonSearchClient` and `SearchService`.

### [ADR-0002](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/adr/ADR-0002-google-drive-auth-provider.md): Dual Drive Auth Providers (Personal OAuth + Domain-Wide Delegation Factory)
- **Decision:** Implement `DriveAuthProvider` interface with `PersonalOAuthProvider` and `DomainWideDelegationProvider` switched dynamically via `DRIVE_AUTH_MODE`.
- **Constraints Enforced:** Zero OAuth details in crawler/indexer, seamless team handoff without code rewrites.

### [ADR-0003](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/adr/ADR-0003-persistence-layer-crawl-state.md): Selection of SQLite for Crawl State & Watermarks
- **Decision:** Use local SQLite database (`data/crawl_state.db`) for tracking crawled file metadata and incremental watermarks.
- **Constraints Enforced:** Zero ghost entries, atomic transactions, lightweight single-file storage.

### [ADR-0004](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/adr/ADR-0004-fastapi-backend-framework.md): Selection of FastAPI as Backend API Framework & Pluggable Auth Architecture
- **Decision:** Use FastAPI with async ASGI lifespan, Pydantic v2 validation schemas, and pluggable dependency injection auth seam (`app/api/deps.py`).
- **Constraints Enforced:** Decoupled route handlers, local no-op auth seam for rapid iteration, strict type safety, zero Drive calls on search.
