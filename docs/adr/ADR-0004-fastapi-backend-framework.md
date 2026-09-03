# ADR-0004: Selection of FastAPI as Backend API Framework & Pluggable Dependency Architecture

**Status:** Accepted  
**Date:** 2026-08-29  
**Decision Type:** ADR (Architecture Decision Record)  
**Authors:** Principal Systems Architect  
**Task Association:** Epic 4 / Task 4.1 — Set up FastAPI project skeleton & Task 4.2/4.3  

---

## 1. Context & Problem Statement

Panopticon requires a local backend API service to:
1. Expose high-performance, low-latency REST endpoints (e.g. `GET /api/search`, `GET /health`, `GET /api/system/status`) for the React dashboard frontend.
2. Query the local Meilisearch search index without blocking the server event loop and return structured, validated JSON responses conforming strictly to documented schemas.
3. Provide a pluggable authentication seam (`app/api/deps.py`) that operates as a transparent no-op for local developer iteration while enabling seamless future substitution of team OAuth/JWT/Session verification with zero route handler modifications.
4. Enforce strict type safety and schema contracts via Pydantic v2 data models matching search engine models.
5. Provide automatic OpenAPI documentation (`/docs` and `/redoc`) to facilitate frontend contract verification.

We must select and standardize the Python backend web framework and its structural architecture.

---

## 2. Decision

We choose **FastAPI** (with `uvicorn` ASGI server and Pydantic v2) as the backend API framework for Panopticon.

### Key Architectural Commitments:
1. **Modular Directory Topology:**
   - `app/api/app.py`: FastAPI application factory `create_app()` with lifespan context manager, CORS middleware, global exception handlers, and structured logging.
   - `app/api/routes/health.py`: Liveness (`/health`) and system diagnostics (`/api/system/status`) endpoints.
   - `app/api/routes/search.py`: Search query execution (`GET /api/search`) with facet filtering and pagination.
   - `app/api/deps.py`: Dependency injection providers for `SearchService`, `PanopticonSearchClient`, and pluggable `get_current_user` auth seam.
   - `app/api/schemas/`: Public request/response API contracts decoupling internal storage/search models from public HTTP wire formats.
2. **Lifespan Management:** Use ASGI async `lifespan` context manager on the FastAPI app to initialize and verify Meilisearch client connectivity on startup and cleanly terminate connection pools on shutdown.
3. **Pluggable Auth Seam:** The `get_current_user` dependency defaults to returning a local developer identity (`LocalDevUser`), isolating route handlers completely from auth implementation details (Constraint 6 & 7).
4. **CORS & Security:** Configured CORS middleware supporting local Vite dev server (`http://localhost:5173`) and local production assets.

---

## 3. Evaluated Alternatives

### Option A: FastAPI + Uvicorn + Pydantic v2 (SELECTED)
- **Description:** Modern, high-performance async Python web framework based on Starlette and Pydantic v2 with native ASGI support and type hint reflection.
- **Score:** 83/85
- **Pros:** Native async I/O; first-class Pydantic v2 integration; dependency injection system for modular auth and service lifecycle; automatic OpenAPI/Swagger documentation; negligible routing overhead (<1ms).
- **Cons:** Requires understanding ASGI asynchronous concurrency patterns; request validation schemas must be strictly defined.
- **Gate 6/10 Compliance:** PASS (Dependency injection provides clean decoupling of auth and core domain logic).

### Option B: Flask + Marshmallow / Flask-RESTful
- **Description:** Traditional WSGI microframework using synchronous execution and extensions for schema validation.
- **Score:** 66/85
- **Pros:** Mature ecosystem; simple synchronous mental model; widely understood.
- **Cons:** Synchronous WSGI model blocks threads during search queries; requires disparate third-party extensions for OpenAPI generation, schema validation, and dependency injection; slower JSON serialization than Pydantic v2.
- **Gate 10 Compliance:** PASS.

### Option C: Django REST Framework (DRF) / Django Ninja
- **Description:** Full-featured web framework with ORM, admin panel, authentication, and REST framework.
- **Score:** 54/85
- **Pros:** Batteries-included; built-in auth and permissions.
- **Cons:** Heavy architectural footprint; tightly coupled to Django ORM and settings; excessive complexity for a lightweight local search tool indexing Docs/Sheets.
- **Gate 10 Compliance:** PASS.

### Option D: Litestar (formerly Starlite)
- **Description:** High-performance async ASGI framework with controller-based routing and DTO support.
- **Score:** 74/85
- **Pros:** Excellent performance, strong typing, clean architecture.
- **Cons:** Smaller community ecosystem and fewer third-party integrations than FastAPI; steeper learning curve for team members.
- **Gate 10 Compliance:** PASS.

---

## 4. Evaluation Matrix against 17 Quality Controls

| Quality Control | Option A (FastAPI) | Option B (Flask) | Option C (Django) | Option D (Litestar) |
|---|---|---|---|---|
| 1. PRD Alignment | **5** (Direct match) | 3 (Adequate) | 2 (Overweight) | 4 (Good) |
| 2. Correctness | **5** (Pydantic v2 validation) | 4 (Manual schemas) | 4 (DRF serializers) | 5 (DTO typing) |
| 3. Security | **5** (Pluggable dependency seam) | 4 (Middleware) | 5 (Django security) | 5 (Guards) |
| 4. Privacy | **5** (No token leakage) | 5 (Compliant) | 5 (Compliant) | 5 (Compliant) |
| 5. Maintainability | **5** (Modular router layout) | 3 (Fragmented plugins) | 3 (Monolithic) | 4 (Controller layout) |
| 6. Scalability | **5** (Async ASGI concurrency) | 3 (WSGI thread-bound) | 3 (WSGI thread-bound) | 5 (Async ASGI) |
| 7. Performance | **5** (Fastest Python routing) | 3 (Standard WSGI) | 2 (Heavy stack) | 5 (Ultra-fast) |
| 8. Reliability | **5** (Proven in production) | 5 (Battle-tested) | 5 (Battle-tested) | 4 (Newer) |
| 9. Data Integrity | **5** (Strict response models) | 4 (Marshmallow) | 4 (DRF) | 5 (DTOs) |
| 10. Explainability | **5** (Auto `/docs` OpenAPI UI) | 3 (Manual docs) | 4 (Swagger plugin) | 5 (OpenAPI) |
| 11. Auditability | **5** (Structured request logging)| 4 (Flask logs) | 4 (Django logs) | 5 (Structured) |
| 12. Extensibility | **5** (Dependency injection) | 4 (Hooks/signals) | 4 (Middleware) | 5 (DI plugins) |
| 13. AI Safety | **5** (N/A — strict sanitization) | 5 (N/A) | 5 (N/A) | 5 (N/A) |
| 14. MVP Fit | **5** (Zero boilerplates to run) | 4 (Simple) | 2 (Complex migrations)| 4 (Moderate) |
| 15. Cost | **5** (Free / MIT) | 5 (Free / BSD) | 5 (Free / BSD) | 5 (Free / MIT) |
| 16. Implementation Effort | **4** (Low effort, high clarity) | 4 (Low effort) | 2 (High overhead) | 3 (Moderate) |
| 17. Risk | **4** (Minimal risk) | 3 (Schema drift risk) | 3 (Coupling risk) | 3 (Ecosystem risk) |
| **Total Score (out of 85)** | **83 / 85** | **66 / 85** | **54 / 85** | **74 / 85** |

---

## 5. Mandatory Product Constraints Compliance

- **Constraint 2 (Pointer / Snippet Index):** COMPLIANT. API schemas only transmit titles, snippet excerpts, matched labels, and URLs.
- **Constraint 3 (Search against local index only):** COMPLIANT. Search endpoints communicate with local Meilisearch via `SearchService` with zero Google Drive API calls.
- **Constraint 6 (Pluggable API Auth Seam):** COMPLIANT. `get_current_user` in `app/api/deps.py` provides a clean dependency injection seam that can be swapped without touching routes.
- **Constraint 7 (Adapter Pattern & Domain Isolation):** COMPLIANT. API routes rely on `SearchService` interface; Meilisearch SDK specifics are never imported into router modules.
- **Constraint 9 (No Secrets Exposed):** COMPLIANT. Response schemas explicitly omit tokens, refresh tokens, and internal credentials.

---

## 6. Blueprint & Implementation Mapping

```text
app/
├── api/
│   ├── __init__.py           # Package export for create_app
│   ├── app.py                # FastAPI factory, lifespan, CORS, middleware
│   ├── deps.py               # Dependency injection: search service, auth seam
│   ├── routes/
│   │   ├── __init__.py       # Router aggregator
│   │   ├── health.py         # GET /health, GET /api/system/status
│   │   └── search.py         # GET /api/search
│   └── schemas/
│       ├── __init__.py
│       ├── health.py         # Health & diagnostic response models
│       └── search.py         # Search query params and result response models
```

---

```yaml
adr_id: ADR-0004
title: "Selection of FastAPI as Backend API Framework & Pluggable Dependency Architecture"
decision_level: "Architecture"
status: accepted
date: "2026-08-29"
depends_on: [ADR-0001, ADR-0002, ADR-0003]
supersedes: []
gates:
  - id: 6
    result: pass
    evidence: "Pluggable auth seam via FastAPI dependency injection"
  - id: 7
    result: pass
    evidence: "Input validation and untrusted text sanitization via Pydantic"
  - id: 10
    result: pass
    evidence: "Search engine internals isolated behind SearchService interface"
recommended_option: "Option A: FastAPI + Uvicorn + Pydantic v2"
priority_tier_used_for_tiebreak: "PRD alignment / MVP fit / Maintainability & Extensibility"
open_assumptions: []
```
