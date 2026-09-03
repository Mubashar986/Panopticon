# Product Requirements Document (PRD) — Panopticon

---

## 1. Executive Summary & Vision

**Panopticon** is an internal, ultra-fast, typo-tolerant document discovery and project navigation engine built specifically for **Google Workspace (Google Docs and Google Sheets)**.

In modern engineering and product organizations, crucial technical knowledge, project specifications, RFCs, tracking spreadsheets, and architecture designs are scattered across hundreds of Google Docs and Google Sheets in personal "My Drive" folders, Shared Drives, and team-shared folders. Traditional Google Drive search fails users due to strict substring matching, lack of typo tolerance for project codenames, inability to prioritize governed metadata (Drive Labels) over raw text matches, and slow search latencies.

Panopticon solves this by acting as a **lightweight, local-first search pointer and discovery layer**. It indexes document titles, owner/editor metadata, governed project label tags, and extracted content snippets into a specialized high-performance search index ([Meilisearch](https://www.meilisearch.com/)), allowing engineers, product managers, and team leads to find any relevant document in under 50ms—even with typos or partial project names.

```
       ┌────────────────────────────────────────────────────────┐
       │                   The User Query                       │
       │     e.g., "Falcn architecture", "SmartTrde sheet"      │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                  PANOPTICON ENGINE                     │
       │   1. Governed Drive Label Project Tags   [HIGH PRIO]   │
       │   2. Exact & Fuzzy Document Titles       [MED-HIGH]    │
       │   3. Typo-Tolerant Snippet Matches       [MEDIUM]      │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │               Instant Document Pointer                 │
       │  • Direct "View in Google Drive" Link                  │
       │  • One-Click Direct Export (PDF, DOCX, XLSX, CSV)      │
       │  • Match Attribution Badge ([TAG:HIGH], etc.)          │
       │  • Owner & Sharing Status (Private / Shared / Domain)  │
       └────────────────────────────────────────────────────────┘
```

---

## 2. Problem Statement & Business Opportunity

### 2.1 The Problem
1. **Typo & Codename Blindness in Native Search:** Project codenames (e.g., *Project Falcon*, *SmartTrade*, *Apollo-V2*) are frequently misspelled in fast queries (`Falcn`, `SmartTrde`, `Apolo`). Native Google Drive search fails or returns irrelevant files.
2. **Scattered Organization:** Documents live in personal drives, team shared drives, or "Shared with me" feeds without a unified catalog.
3. **Governed vs. Ungoverned Chaos:** When organizations use Google Workspace Labels to tag official project artifacts, there is no fast UI to filter or elevate officially tagged documents above accidental word mentions.
4. **Latency & Friction:** Opening Google Drive, waiting for the heavy web interface, and wading through unranked search results wastes hours of engineering time weekly.

### 2.2 What Panopticon Proposes & Delivers
- **Sub-50ms Typo-Tolerant Search:** Powered by local Meilisearch with specialized ranking rules (`words`, `typo`, `proximity`, `attribute`, `sort`, `exactness`).
- **Hybrid Matching Strategy:** Governed Google Drive Labels (structured tags) are given first-tier ranking priority, with fuzzy full-text snippet matching serving as a seamless fallback.
- **Zero-Mirror Security Model:** Panopticon is an *index and pointer*, **not a data warehouse**. Full document contents are never stored in the search index or database. Only titles, metadata, and truncated preview snippets are held.
- **Dual Swappable Authentication:** Frictionless local setup for personal `@gmail.com` accounts via OAuth 2.0 Web flow, with a zero-rewrite runtime switch to Google Workspace Domain-Wide Delegation (Service Account with impersonation) for company-wide deployment.
- **Live Sync & Ingestion Management:** Background crawler with incremental watermarking (`modifiedTime`), 10MB server export cap protection, and real-time status reporting directly to the UI.

---

## 3. Target Personas & Core User Journeys

### 3.1 Target Personas

| Persona | Role | Primary Need | Typical Workflow |
|---|---|---|---|
| **Alex (Staff Engineer / Architect)** | Technical Leadership | Quick access to RFCs, ADRs, and system design docs across projects. | Searches codename with minor typo (`"Orion arch"`); gets tagged RFC doc immediately; clicks one-click PDF export or Drive link. |
| **Samantha (Senior Product Manager)** | Product Operations | Finding tracking sheets, sprint roadmaps, and stakeholder PRDs. | Filters by tag `[Project Alpha]` and document type `Spreadsheet`; inspects last-modified editor. |
| **Jordan (Developer / New Hire)** | Software Engineer | Discovering existing documentation for an unfamiliar service. | Searches fuzzy term; uses match confidence badges (`[TAG:HIGH]`, `[CONTENT:MEDIUM]`) to identify official documentation. |
| **System Operator / Admin** | DevOps / Local Dev | Maintaining the crawler, monitoring engine health, configuring auth. | Uses the Header Sync Drawer and Auth Settings Modal to connect Google Drive, trigger syncs, and verify Meilisearch process status. |

### 3.2 Key User Journeys

#### Journey A: Typo-Tolerant Document Discovery
1. User opens Panopticon React Dashboard (`http://localhost:5173`).
2. Types `"Falcn spec"` into the search input.
3. Debounced query (250ms) hits `GET /api/search?q=Falcn+spec&mode=fuzzy`.
4. Dashboard displays search results in ~15ms:
   - Match 1: *“Project Falcon - Technical Architecture RFC”* (`[TAG:HIGH]`, Owner: `alex@company.com`, Sharing: `domain`).
   - Match 2: *“Falcon Sprint Roadmap Q3”* (`[TITLE:HIGH]`, Type: `spreadsheet`).
5. User clicks `"View in Drive"` to jump straight into Google Docs in a new tab, or clicks `"PDF"` for immediate offline export.

#### Journey B: Triggering Background Synchronization
1. User creates a new Google Doc in Google Drive.
2. User opens Panopticon and clicks **"Sync Now"** in the top navigation bar.
3. Frontend issues `POST /api/sync` (returns `202 Accepted`) and opens the live progress drawer.
4. UI polls `GET /api/sync/status` every 1000ms, displaying live phase transitions:
   `idle` ➔ `crawling` ➔ `exporting` ➔ `updating_sqlite` ➔ `indexing_meilisearch` ➔ `idle`.
5. Sync finishes; document count increments and new files become instantly searchable.

#### Journey C: Onboarding & Authentication Setup
1. New user launches Panopticon for the first time without configured credentials.
2. System status pill indicates auth needs setup.
3. User opens the **Settings Drawer**, uploads `credentials.json`, and clicks **"Connect Google Drive"**.
4. A Google OAuth consent popup opens (`/api/auth/oauth/start`).
5. Upon consent, the popup saves `token.json`, broadcasts `PANOPTICON_OAUTH_SUCCESS` via `window.postMessage`, and closes automatically.
6. The dashboard immediately updates to show a green `"Authenticated"` state.

---

## 4. Product Requirements & Feature Matrix

### 4.1 Feature Breakdown

```
Panopticon Feature Tree
├── 1. Typo-Tolerant Search & Navigation
│   ├── 1.1 Debounced Interactive Search Bar
│   ├── 1.2 Search Modes (Fuzzy, Governed Tag, Exact Match)
│   ├── 1.3 Facet Filtering (Category, Sharing Scope, Owner, Project Tag)
│   ├── 1.4 Match Attribution Badges ([TAG:HIGH], [TITLE:HIGH], [CONTENT:MEDIUM])
│   ├── 1.5 Hit Highlighting (<mark> tags around matched words)
│   └── 1.6 One-Click Direct Export Links (PDF, DOCX, XLSX, CSV)
├── 2. Google Drive Ingestion & Sync Engine
│   ├── 2.1 Full & Incremental Watermark Crawling (modifiedTime)
│   ├── 2.2 Workspace Drive Labels Tag Extraction
│   ├── 2.3 10MB Server-Side Export Cap Graceful Handling
│   ├── 2.4 Deleted & Moved File Detection & Index Purge
│   └── 2.5 Local SQLite ACID Durability Storage (WAL Mode)
├── 3. Engine Process Supervision & Zero-Setup DX
│   ├── 3.1 Automated Meilisearch Binary Download & Validation
│   ├── 3.2 Background Child Process Lifespan Management (Auto-spawn & Graceful Shutdown)
│   └── 3.3 System Health & Index Diagnostics API
└── 4. Dynamic Dual Authentication Management
    ├── 4.1 Personal OAuth 2.0 Web Flow with Popup Receiver
    ├── 4.2 Workspace Domain-Wide Delegation (Service Account with Impersonation)
    ├── 4.3 Runtime Provider Hot-Switching via UI / API
    └── 4.4 In-Browser Credential JSON File Upload
```

### 4.2 Functional Requirements

| ID | Requirement | Priority | Implementation Status |
|---|---|---|---|
| **FR-01** | Support sub-50ms typo-tolerant search over Google Docs & Sheets titles and contents. | Must Have | **Implemented** (Meilisearch + FastAPI) |
| **FR-02** | Prioritize Google Drive Label project tags above full-text content matches in ranking. | Must Have | **Implemented** (Custom Ranking Rules & Match Attribution) |
| **FR-03** | Incremental crawl updates using last-modified timestamps; avoid re-crawling unchanged files. | Must Have | **Implemented** (`CrawlStorage` SQLite watermark) |
| **FR-04** | Detect deleted files in Google Drive and remove them from SQLite and Meilisearch. | Must Have | **Implemented** (`sync_deleted_files` logic) |
| **FR-05** | Graceful fallback when document export exceeds Google's 10MB ceiling (mark metadata-only). | Must Have | **Implemented** (`export_file_content` cap handler) |
| **FR-06** | Sanitize all crawled untrusted external strings against null bytes and control characters. | Must Have | **Implemented** (`sanitize_string` regex) |
| **FR-07** | Expose asynchronous background sync trigger with conflict prevention (HTTP 409). | Must Have | **Implemented** (`/api/sync` + `SyncManager`) |
| **FR-08** | Provide auto-managed Meilisearch binary supervisor on backend startup. | Must Have | **Implemented** (`ProcessSupervisor` in FastAPI lifespan) |
| **FR-09** | Hot-switch between Personal OAuth and Domain-Wide Delegation without code changes. | Must Have | **Implemented** (`/api/auth/config` + `DriveAuthFactory`) |
| **FR-10** | Provide React dashboard with tokenized design system, 6 interaction states, and accessibility. | Must Have | **In Progress** (Design system & Shell complete, components underway) |

---

## 5. Non-Negotiable Product & Architectural Constraints

1. **Drive Auth Abstraction Seam:** Crawler and indexer domain logic must NEVER touch OAuth or Service Account specifics directly. All credential access goes through the `DriveAuthProvider` protocol interface.
2. **Zero-Mirroring Policy:** Panopticon is strictly a pointer index. Full document text must **never** be cached in the SQLite database, stored in Meilisearch, or returned in API responses.
3. **Index-Only Search Execution:** Search requests must NEVER make live Google Drive API calls. All queries execute strictly against the local Meilisearch index.
4. **Untrusted Data Sanitization:** All external titles, snippets, owners, and tags must be sanitized against illegal control characters (`[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`) before entering storage or index.
5. **10MB Drive Export Cap:** File exports must gracefully handle the 10MB Google server-side export limit by tagging the document as `oversized_metadata_only` rather than failing the crawl.
6. **Pluggable API Auth Seam:** The backend API auth dependency (`CurrentUser`) must remain a pluggable dependency (currently a local dev stub, swappable for JWT/OIDC without touching route handlers).
7. **Zero Provider Leakage:** Google Drive API and Meilisearch SDK constructs must not leak into core domain models.
8. **Explicit Crawl Scope:** Personal OAuth mode crawls only files visible to the logged-in principal (My Drive + accessible Shared Drives + Shared with me). Full company discovery is enabled when switching to Domain-Wide Delegation.
9. **Credential Safety:** OAuth tokens, client secrets, and service account keys must NEVER be committed to Git, stored in the search index, or returned in search API responses.
10. **Ghost Entry Purge:** Incremental sync must purge deleted/inaccessible files from both SQLite and Meilisearch to prevent stale ghost results.

---

## 6. Release & Roadmap Phasing

```
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Google Docs & Sheets Local Engine (Current Scope)             │
│ • Local Python Crawler + SQLite State Store                            │
│ • Supervised Local Meilisearch Engine                                  │
│ • FastAPI Backend (/api/search, /api/sync, /api/auth, /api/system)     │
│ • Vite + React + TypeScript Dashboard (Epic 5)                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: Multi-Source Enterprise Connectors (Future Roadmap)           │
│ • Google Drive Real-time Change Webhooks (RFC-0001)                    │
│ • Gmail & Google Chat Message Indexing                                 │
│ • Bitbucket & GitHub Repository / PR Search                            │
│ • Team-wide Multi-tenant Cloud Deployment & SSO Auth                   │
└────────────────────────────────────────────────────────────────────────┘
```
