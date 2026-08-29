# Epic 5: React Dashboard — Developer & Agent Implementation Instructions

---

## 1. Objective & Scope

You are tasked with building the **Panopticon React Dashboard (Epic 5)**. Panopticon is an ultra-fast, typo-tolerant document discovery and project navigation engine for **Google Workspace (Google Docs and Google Sheets)**.

The frontend is a local-first **React 19 + TypeScript + Vite** single-page application running on `http://localhost:5173`. It connects to the FastAPI backend running on `http://localhost:8000`.

### Key Reference Documents
- 📋 **PRD & Product Vision:** [`docs/PRD.md`](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/PRD.md)
- 🏛️ **System Architecture & Data Flows:** [`docs/SYSTEM_DESIGN.md`](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/SYSTEM_DESIGN.md)
- 🔌 **Backend REST API Contract:** [`docs/API_DOCUMENTATION.md`](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/API_DOCUMENTATION.md)
- 🎨 **Design Tokens & Design System:** [`design-system/tokens.json`](file:///c:/Users/Mubashar/Desktop/Panopticon/design-system/tokens.json) & [`design-system/DESIGN_SYSTEM.md`](file:///c:/Users/Mubashar/Desktop/Panopticon/design-system/DESIGN_SYSTEM.md)
- 🧭 **The Muses Protocol:** [`docs/muses/THE_MUSES_GUIDE.md`](file:///c:/Users/Mubashar/Desktop/Panopticon/docs/muses/THE_MUSES_GUIDE.md)

---

## 2. Non-Negotiable Rules & The Muses Protocol

You must strictly execute frontend tasks according to **The Muses Protocol** (`Picasso` ➔ `Escher` ➔ `Vermeer`):

1. **100% Token Discipline (Vermeer):**
   - **Zero raw hex codes** (`#2563EB`) and **zero arbitrary pixel values** (`p-[17px]`, `m-[23px]`).
   - Use CSS token variables from `src/styles/tokens.css` or semantic Tailwind classes (e.g., `bg-[var(--color-bg-surface)]`, `text-[var(--color-text-primary)]`, `p-[var(--space-4)]`, `rounded-[var(--radius-md)]`).
2. **Real Backend Data Contract (Escher):**
   - Use typed interfaces from `src/types/api.ts`.
   - Never invent mock fields that do not exist on the backend. If a feature needs a field the backend doesn't supply, log it to `design-system/backend-requirements.md`.
3. **The 6 Interactive Component States (Vermeer):**
   - Every interactive element (buttons, inputs, cards, pills) must implement all 6 states: `default, hover, active, focus, disabled, loading`.
4. **The 10 Usability Heuristics:**
   - Search input must be debounced (250ms).
   - Async requests must render loading skeletons/spinners (<150ms).
   - Empty states must provide sample clickable query prompts (Heuristic #10).
   - Error messages must provide plain-language explanations with actionable recovery buttons (Heuristic #9).

---

## 3. Target Component Architecture & File Tree

Organize `frontend/src/` into the following component structure:

```
frontend/src/
├── components/
│   ├── Header.tsx                    # App header with title, sync button & status pill
│   ├── SystemStatusPill.tsx          # Live Meilisearch & doc count indicator
│   │
│   ├── search/
│   │   ├── SearchBar.tsx             # Debounced search input + mode toggle
│   │   ├── ModeSelector.tsx          # Fuzzy / Tag / Exact mode tabs
│   │   ├── FilterBar.tsx             # Facet filter pills (Type, Sharing, Owner, Tag)
│   │   └── TagFilterDropdown.tsx     # Google Drive Label project tags dropdown
│   │
│   ├── results/
│   │   ├── ResultsList.tsx           # Container for result cards & pagination
│   │   ├── ResultCard.tsx            # Single document hit card with match badges
│   │   ├── MatchBadge.tsx            # [TAG:HIGH], [TITLE:HIGH], [CONTENT:MEDIUM]
│   │   ├── SharingBadge.tsx          # [Private], [Shared], [Domain]
│   │   ├── ExportMenu.tsx            # Dropdown for direct exports (PDF, DOCX, XLSX, CSV)
│   │   ├── StaleBadge.tsx            # 90+ day untouched document warning badge
│   │   └── EmptyState.tsx            # Empty results guide with suggested prompts
│   │
│   ├── sync/
│   │   ├── SyncControls.tsx          # "Sync Now" button & last-synced timestamp
│   │   └── SyncProgressDrawer.tsx    # Slide-over showing live crawl/export/index phases
│   │
│   ├── settings/
│   │   ├── SettingsDrawer.tsx        # Slide-over modal for Drive auth & credentials
│   │   ├── AuthStatusCard.tsx        # Active mode (OAuth vs DWD) and token validity
│   │   ├── OAuthConnectButton.tsx    # Popup Google consent launcher
│   │   └── CredentialUploader.tsx    # Drag-and-drop upload for JSON credentials
│   │
│   └── common/
│       ├── LoadingSkeleton.tsx       # Shimmer skeletons for card loading
│       └── ErrorBanner.tsx           # Plain-language error banners with retry action
│
├── hooks/
│   ├── useSearch.ts                  # Debounced query hook (GET /api/search)
│   ├── useSync.ts                    # Sync polling hook (POST /api/sync, GET /api/sync/status)
│   ├── useAuth.ts                    # Auth state hook (GET /api/auth/config, POST /api/auth/config)
│   └── useSystemStatus.ts            # System health polling hook (GET /api/system/status)
│
├── styles/
│   └── tokens.css                    # CSS variables mapped from tokens.json
├── types/
│   └── api.ts                        # TypeScript contracts matching FastAPI Pydantic models
├── App.tsx                           # Main app shell & layout coordinator
└── main.tsx                          # React entrypoint
```

---

## 4. Task-by-Task Implementation Specifications

### 🎯 Task 5.2: Search Bar & Filter Controls
* **Files:** `src/components/search/SearchBar.tsx`, `ModeSelector.tsx`, `FilterBar.tsx`
* **Backend Endpoint:** `GET /api/search`
* **Requirements:**
  1. Controlled text input debounced at **250ms**.
  2. Mode selector toggle:
     - `"fuzzy"`: Typo-tolerant search (default).
     - `"tag"`: Prioritizes / filters by Google Drive Workspace labels.
     - `"exact"`: Encloses query in strict phrase matching.
  3. Keyboard shortcuts:
     - Pressing `/` or `Cmd/Ctrl + K` immediately focuses the search input.
     - Pressing `Escape` clears the query and blurs the input.
  4. Quick filter pills:
     - Category filter (`All`, `Documents`, `Spreadsheets`).
     - Sharing scope filter (`All`, `Domain-wide`, `Shared`, `Private`).
     - Dynamic Project Tag dropdown populated from `facet_distribution.project_tags`.
  5. Clear query (`✕`) button appears when query is non-empty.

---

### 🎯 Task 5.3: Results List, Document Cards & Export Links
* **Files:** `src/components/results/ResultsList.tsx`, `ResultCard.tsx`, `MatchBadge.tsx`, `ExportMenu.tsx`
* **Backend Contract:** `SearchItemResponse` from `GET /api/search`
* **Requirements:**
  1. Renders list of matching cards with processing time & total hit count header (e.g. *"Found 14 documents in 12ms"*).
  2. Highlighted text rendering:
     - Render `highlighted_name` with `<mark>` tag styling (contrasting background token).
     - Render `highlighted_snippet` preview text (truncate to 2-3 lines with CSS line-clamp).
  3. Badges:
     - **Match Attribution Badge:**
       - `[TAG:HIGH]`: Purple badge (`var(--color-tag-match)`) when matched via Google Drive Label.
       - `[TITLE:HIGH]`: Blue badge when matched via file title.
       - `[CONTENT:MEDIUM]`: Gray badge when matched via body snippet.
     - **Sharing Scope Badge:**
       - `[Domain]`: Emerald/green badge.
       - `[Shared]`: Blue badge.
       - `[Private]`: Amber badge.
     - **Staleness Badge:** Displays subtle warning pill if `modified_time` is >90 days ago.
  4. Actions per card:
     - **"View in Drive" Button:** Opens `view_url` in a new tab (`target="_blank" rel="noopener noreferrer"`).
     - **Export Dropdown:** Direct download links for `pdf`, `docx`, `xlsx`, `csv` generated from `export_links`.
  5. Owner & Metadata:
     - Displays `owner` email and relative time (`"Modified 2 days ago"`).

---

### 🎯 Task 5.4: Header Sync Controls & Live Progress Drawer
* **Files:** `src/components/sync/SyncControls.tsx`, `SyncProgressDrawer.tsx`, `src/hooks/useSync.ts`
* **Backend Endpoints:** `POST /api/sync`, `GET /api/sync/status`, `POST /api/sync/reindex`
* **Requirements:**
  1. Header **"Sync Now"** button:
     - Triggers `POST /api/sync` (`full_refresh=false`).
     - Disabled with spinning loader while `is_syncing === true`.
     - Displays last sync time badge (e.g. *"Synced 5m ago"*).
  2. Slide-over / Drawer for live progress:
     - Polls `GET /api/sync/status` every **1000ms** while syncing (every 10s when idle).
     - Displays active phase step with visual breadcrumbs:
       `crawling` ➔ `exporting` ➔ `updating_sqlite` ➔ `indexing_meilisearch` ➔ `idle`.
     - Displays live `progress_message` string (e.g. *"Exporting text content (File 14 of 42)..."*).
     - Displays last sync summary metrics: `added`, `updated`, `deleted`, `duration_seconds`.
  3. Action to trigger local re-indexing without calling Google Drive (`POST /api/sync/reindex`).
  4. Conflict handling: Catches HTTP 409 and informs user gracefully.

---

### 🎯 Task 5.5: Google Drive Auth & Credentials Settings Drawer
* **Files:** `src/components/settings/SettingsDrawer.tsx`, `AuthStatusCard.tsx`, `CredentialUploader.tsx`, `src/hooks/useAuth.ts`
* **Backend Endpoints:** `GET /api/auth/config`, `POST /api/auth/config`, `POST /api/auth/oauth/start`, `POST /api/auth/credentials/upload`
* **Requirements:**
  1. Settings drawer opened via gear icon (⚙️) in header.
  2. **Active Mode Display & Switcher:**
     - Toggle between **"Personal OAuth"** and **"Workspace Service Account (DWD)"**.
     - Submitting sends `POST /api/auth/config`.
  3. **Personal OAuth Connection Flow:**
     - Status card indicates if `token.json` is valid or expired.
     - **"Connect Google Account"** button calls `POST /api/auth/oauth/start`, gets `authorization_url`, and opens a 600x700 browser popup window.
     - Sets up `window.addEventListener("message", ...)` to capture `PANOPTICON_OAUTH_SUCCESS`, closes popup, and refreshes auth status immediately.
  4. **Credential Upload Section:**
     - Drag-and-drop or file input for `credentials.json` (OAuth) or `service_account.json` (Service Account).
     - Uploads file as multipart form-data to `POST /api/auth/credentials/upload`.
     - Displays success toast/banner upon upload.

---

### 🎯 Task 5.6: System Diagnostics & Polish States
* **Files:** `src/components/SystemStatusPill.tsx`, `src/components/common/LoadingSkeleton.tsx`, `EmptyState.tsx`, `ErrorBanner.tsx`
* **Backend Endpoints:** `GET /api/system/status`, `GET /health`
* **Requirements:**
  1. **System Health Status Pill:**
     - Green pulsating dot when `meilisearch_connected === true`.
     - Displays total indexed documents count (e.g. *"55 docs indexed"*).
     - Red/Amber dot when engine is degraded or offline.
  2. **Loading Skeletons:**
     - Animated pulse shimmer cards rendered when query is in flight.
  3. **Rich Empty States (Heuristic #10):**
     - When search has 0 results: *"No documents found matching '{query}'"*.
     - Provides clickable suggestion pills: *"Try searching for 'Falcon' or 'RFC'"*.
     - Shows button to clear filters or trigger a Drive sync.
  4. **Error Recovery Banners (Heuristic #9):**
     - Translates HTTP 503 (Meilisearch down) into plain language with a retry button.
     - Translates network errors into helpful troubleshooting instructions.

---

## 5. Verification & Acceptance Checklist

Before submitting code, verify all of the following:

- [ ] **Typo Query Test:** Searching `"Falcn"` or `"SmartTrde"` successfully returns matching files with `<mark>` highlight tags.
- [ ] **Direct View Link:** Clicking `"View in Drive"` opens the actual Google Doc/Sheet in a new browser tab.
- [ ] **Direct Export Links:** Clicking `"PDF"`, `"DOCX"`, or `"CSV"` initiates download from Google's export endpoints.
- [ ] **Live Sync Flow:** Clicking `"Sync Now"` triggers `POST /api/sync`, opens drawer, polls live status, and updates document count on completion.
- [ ] **OAuth Consent Flow:** Clicking `"Connect Google Account"` opens popup, accepts consent, receives postMessage, and turns status badge green.
- [ ] **Zero Raw Styles Audit:** Running `grep -rnE "#[0-9a-fA-F]{3,8}" frontend/src/` returns 0 hits (all colors use CSS variables).
- [ ] **All 6 States Present:** Buttons and cards properly show default, hover, active, focus, disabled, and loading states.
- [ ] **Keyboard Navigation:** `/` focuses search bar; `Escape` clears query.
