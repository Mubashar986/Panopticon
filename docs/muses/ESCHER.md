# Escher — Backend-Aware Frontend Data Wiring

---

## 1. Overview & Purpose

**Escher** ensures frontend components and pages are wired to **REAL backend data, schemas, and endpoints**. It inspects actual API contracts, database schemas, and route handlers before any UI code is written, mirrors backend validation in the browser, and explicitly flags missing backend capabilities in `design-system/backend-requirements.md` instead of silently inventing fake mock data.

### The Problem Escher Solves
Left unchecked, an AI coding agent asked to "build a dashboard" will happily invent plausible-looking fake fields (`user.tier`, `file.total_views`, `doc.ai_summary`) that do not exist on the backend. When a real user tests the UI, the seams tear apart with runtime `undefined` crashes and broken API calls. Escher acts as the rigorous backend-to-frontend seam inspector: **every field must be verified in the backend schema, or explicitly flagged as a gap.**

### The Muses Division of Labor
- **Picasso:** Defines the design tokens once.
- **Escher (This Skill):** Decides *what data flows through components and whether that backend data actually exists*.
- **Vermeer:** Decides *how the component looks and behaves* once the data contract is settled.

---

## 2. The 4-Step Escher Protocol

```
┌─────────────────────────────────────────────────────────────┐
│                    THE ESCHER PROTOCOL                      │
│                                                             │
│  Step 1: Inspect Real Source of Truth (FastAPI / Schemas)   │
│  Step 2: Mirror Field Types, Nullability & Constraints      │
│  Step 3: Detect & Record Backend Gaps in Markdown           │
│  Step 4: Translate Raw Status Codes to Human Error Messages │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Find the Real Backend Contract
Before writing frontend code that touches data, Escher searches for the authoritative source of truth:
1. **OpenAPI / Pydantic Schemas:** Look in `app/api/schemas/` or `openapi.json`.
2. **FastAPI Route Handlers:** Read actual endpoints in `app/api/routes/` to verify HTTP methods, query params, and status codes (200, 202, 400, 409, 503).
3. **Domain Models & Database Tables:** Read SQLite models (`CrawlStorage`) and Meilisearch schemas (`SearchDocument`).
4. **Existing Frontend Types:** Inspect `frontend/src/types/api.ts` to ensure consistency.

*Rule: Never infer a data shape purely from what would look attractive in the UI. Backend reality always takes precedence.*

### Step 2: Build Against the Real Contract, Not a Convenient One
- **Field Name Integrity:** Use the exact property names returned by the API (`last_modifying_user`, `modified_time`, `project_tags`). Never silently rename properties without a documented transform layer.
- **Respect Nullability:** If a field is optional (`string | null`), the UI must handle `null` with fallback text (e.g. `"Unknown Author"` or `"Never modified"`).
- **Distinguish Async States (Heuristic #1):**
  - `loading`: Request in flight ➔ Render animated skeleton or spinner.
  - `empty`: Request succeeded with 0 items ➔ Render empty-state illustration with actionable next steps.
  - `error`: Request failed with 4xx/5xx ➔ Render recovery banner with retry action.
  *Never collapse these three distinct states into one generic empty message.*

### Step 3: When the Backend Doesn't Have What the UI Needs (Gap Protocol)
When building UI reveals that a desired feature requires a field, endpoint, or filter that does not exist in the backend:
1. **Stop & Alert:** Notify the user immediately in the response.
2. **Log to `design-system/backend-requirements.md`:** Write a formal requirement entry using the standardized template.
3. **Mark Temporary Mocks:** If the user agrees to proceed before the backend is updated, create a clearly labeled mock with a `// TODO: backend-requirements.md REQ-X` comment.
4. **Never Leave Unflagged Mocks:** An invisible mock is a production bug waiting to happen.

---

## 3. Backend Requirements Register Template (`backend-requirements-template.md`)

When a backend gap is discovered, Escher appends an entry to `design-system/backend-requirements.md`:

```markdown
## [OPEN] REQ-<sequential-number>: <Short Descriptive Title>

- **Needed for:** <Component or page that depends on this capability>
- **What's missing:** <Endpoint / field / query parameter / computed value — be specific>
- **Expected shape:** <HTTP method + path, or JSON field name + type>
- **Why the UI needs it:** <User-facing behavior blocked without it>
- **Current workaround:** <"None — feature blocked" OR "Temporary mock in place, marked TODO in <file>">
- **Flagged:** <YYYY-MM-DD>
```

### Requirement Status Lifecycle
- `[OPEN]`: Missing from backend; UI is either blocked or running on a tagged temporary mock.
- `[IN PROGRESS]`: Backend development has started.
- `[RESOLVED]`: Backend now provides the endpoint/field. Temporary mock has been purged from frontend code.

---

## 4. Translating Backend Errors (Heuristic #9)

Escher is responsible for converting raw HTTP status codes, socket timeouts, and Pydantic validation errors into the plain-language recovery voice defined in `tokens.json` (`voice.error-style`).

### Error Mapping Matrix

| Backend Event / Code | Raw Error Details | Translated UI Message (User-Facing) | Actionable Recovery Step |
|---|---|---|---|
| **HTTP 503** | `SearchConnectionError: Meilisearch unreachable` | *"Search Engine Offline: Panopticon cannot connect to the local Meilisearch service."* | *"Check if the background engine is running, or trigger auto-start."* |
| **HTTP 503** | `IndexNotFoundError: Index missing` | *"Search Index Not Ready: Documents have not been indexed yet."* | Click *"Sync Now"* button in header to run initial crawl. |
| **HTTP 409** | `SyncInProgressError: Active job active` | *"Sync Already in Progress: Another crawl job is currently running."* | View live progress in the Header Sync Drawer. |
| **HTTP 400** | `Missing Client Secrets: credentials.json missing` | *"Google Credentials Missing: Client secrets file was not found."* | Open *"Settings"* to upload `credentials.json`. |
| **Fetch / Network Error** | `TypeError: Failed to fetch (Port 8000 down)` | *"Backend Disconnected: Cannot reach the Panopticon API server."* | *"Ensure `uvicorn app.api.app:app` is running on port 8000."* |

---

## 5. Handoff to Vermeer

Once Escher has mapped the data types and error boundaries:
1. Pass the typed component props and state variables to **Vermeer**.
2. Vermeer styles the elements strictly using tokens from `tokens.json`.
3. Vermeer attaches all 6 interactive states (`default, hover, active, focus, disabled, loading`).
