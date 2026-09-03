# Master Roadmap & WBS Tracking
## Panopticon — Google Docs/Sheets Project-Name Search Tool

**Master WBS Location:** [roadmap_wbs.md](file:///c:/Users/Mubashar/Desktop/Panopticon/roadmap_wbs.md)

---

## Active Task Matrix

### Epic 1: Foundation & Dual Swappable Auth
* [x] **Task 1.1:** Set up Python project skeleton `[COMPLETED]`
* [x] **Task 1.2:** Build dual Drive auth providers (Personal OAuth + Domain-Wide Delegation Factory) `[COMPLETED]`
* [x] **Task 1.3:** Smoke-test: list files via the auth provider `[COMPLETED]`

### Epic 2: Indexer Core
* [x] **Task 2.1:** Build the Drive crawl function `[COMPLETED]`
* [x] **Task 2.2:** Implement corrected Label query + tag extraction `[COMPLETED]`
* [x] **Task 2.3:** Implement content export with 10MB cap handling `[COMPLETED]`
* [x] **Task 2.4:** Fetch and attach permissions + owner/editor metadata `[COMPLETED]`
* [x] **Task 2.5:** Persist crawl output + add incremental run logic `[COMPLETED]`

### Epic 3: Search Index Integration
* [x] **Task 3.1:** Stand up a local Meilisearch instance `[COMPLETED]`
* [x] **Task 3.2:** Define the index schema `[COMPLETED]`
* [x] **Task 3.3:** Build the ingestion script `[COMPLETED]`
* [x] **Task 3.4:** Configure ranking + typo tolerance, test fuzzy queries `[COMPLETED]`

### Epic 4: Backend API
* [x] **Task 4.1:** Set up FastAPI project skeleton `[COMPLETED]`
* [x] **Task 4.2:** Build `GET /api/search` `[COMPLETED]`
* [x] **Task 4.3:** Add a pluggable API auth stub (deferred real auth) `[COMPLETED]`
* [x] **Task 4.4:** Add Background Drive Sync & Ingestion API Endpoints (`POST /api/sync`, `GET /api/sync/status`, `POST /api/sync/reindex`) `[COMPLETED]`
* [x] **Task 4.5:** Auto-Managed Engine Subprocess Supervisor & Binary Bootstrap `[COMPLETED]`
* [x] **Task 4.6:** Server- & UI-Managed Google Drive Authentication Setup `[COMPLETED]`

### Epic 5: Dashboard (React)
* [ ] **Task 5.1:** Scaffold the React app & Design System Foundation
* [ ] **Task 5.2:** Build the search bar (debounced input + tag filter dropdown)
* [ ] **Task 5.3:** Build the results list (with badges & export links)
* [ ] **Task 5.4:** Build header sync controls & live progress drawer
* [ ] **Task 5.5:** Build Google Drive auth & credentials settings drawer
* [ ] **Task 5.6:** Add system diagnostics pill & polish states

### Epic 6: Hardening & Handoff
* [ ] **Task 6.1:** End-to-end verification pass
* [ ] **Task 6.2:** Prep demo for lead — interim scope vs. eventual domain-wide plan
