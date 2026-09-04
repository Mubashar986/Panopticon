# Panopticon
# Agent Operating Contract

This is the top-level operating contract for all AI coding agents working in this workspace. It governs **Panopticon** — a Google Docs/Sheets project-name search tool (Python indexer + Meilisearch + FastAPI + React dashboard) as defined in `roadmap_wbs.md`.

All agent work is controlled by the WBS, stage-gated skills, an accepted-decision registry, explicit evidence, and documented state. Nothing is built on assumption alone — including technology choices.

---

## 1. Core Operating Principles

### 1.1 WBS-first execution

The WBS is the source of truth for **what gets built**.

Agents MUST:
- work from an active WBS leaf task;
- identify the WBS task ID before implementation;
- respect dependencies, scope, and acceptance criteria;
- update the WBS when scope or dependencies materially change;
- never silently expand a task into unrelated work.

If a request is larger than the current leaf task:
```text
STOP → identify scope expansion → update/revise WBS → select appropriate leaf task → resume lifecycle
```

### 1.2 Decision-first execution — the open technology list

The following choices are intentionally left undecided until the architecture phase. **None of these may be chosen inline, silently, or differently between sessions.** An accepted ADR must exist in `docs/adr/` before any of the following is used, imported, or proposed in code:

- search engine technology (Meilisearch confirmed in WBS — formalize via ADR)
- Google Drive authentication strategy (personal OAuth vs. domain-wide delegation)
- persistence layer for crawl state (SQLite, JSON, etc.)
- backend framework (FastAPI confirmed in WBS — formalize via ADR)
- frontend framework (React confirmed in WBS — formalize via ADR)
- API/dashboard authentication mechanism (deferred — currently stubbed)
- deployment platform (local-only for now)
- CSS / component library (Tailwind, Shadcn, etc.)
- Google API client library
- incremental sync / scheduling strategy

If no ADR exists for a decision the current task depends on:
```text
STOP → check docs/adr/ADR-INDEX.md → if PENDING: generate the ADR using docs/adr/ADR-PROMPT-TEMPLATE.md → present to user for acceptance → only then resume implementation
```

### 1.3 Non-negotiable product constraints

These are permanent, drawn directly from the project requirements and WBS, and apply regardless of which WBS task is active. No design, WBS task, or Stage 2 artifact may propose violating one; if a task appears to require it, STOP and escalate.

1. Drive auth must be abstracted behind a swappable provider interface — crawler/indexer code must never touch OAuth specifics directly.
2. The dashboard is a pointer/index — it shows titles, snippets, and links. No full document content is mirrored or cached in the search index or API responses.
3. Search operates against the local Meilisearch index only — no live Google Drive API calls on search requests.
4. Crawled content and metadata must be treated as untrusted input (sanitize before indexing).
5. File exports must handle the 10MB Drive server-side cap gracefully (metadata-only fallback, never crash).
6. API authentication must be a pluggable seam (currently a no-op stub for local use, swappable later).
7. Provider-specific logic (Google API, Meilisearch internals) must not leak into core search/indexing domain logic — use adapter/interface patterns.
8. Crawl scope must be explicitly bounded and documented (personal-account limitations vs. future domain-wide).
9. No OAuth tokens, refresh tokens, or API secrets may be stored in the search index, committed to Git, or exposed via API responses.
10. Incremental sync must be safe — deleted/moved files must be detected and removed from the index, not left as stale ghost entries.

---

## 2. Evidence and Truthfulness

Agents MUST distinguish:
```text
VERIFIED
INFERRED
ASSUMED
UNKNOWN
BLOCKED
```

Rules:
- Never invent test or benchmark results.
- Never claim a fix without verification.
- Never claim a file/function/schema exists without inspecting the repository.
- Inspect complete logs before diagnosing runtime failures.
- When evidence is insufficient, explicitly state that it cannot be confirmed.

Prefer:
```text
Repository evidence + Executed commands/results + Relevant source implementation + Tests/benchmarks + Accepted ADRs
```
over intuition or memory of a different project.

---

## 3. Skill Inventory

| Stage / Skill | Directory | Purpose | Required Artifact |
|---|---|---|---|
| Stage 0: Roadmap & WBS Planner | `.agents/skills/roadmap-wbs-planner/` | Discovery, scope, epics, leaf tasks, dependencies | `roadmap_wbs.md` |
| Stage 1: Concept-to-Code Bridge | `.agents/skills/conceptual-understanding/` | Mental model, architecture, data flow, concept-to-code mapping | `task_X_Y_understanding.md` |
| Architecture / QA: Narrsistic Pluto | `.agents/skills/narrsistic-pluto/` | Principal Architect & Lead QA/SRE analysis, 3–5 web-researched solutions, RCA, blast radius, rollout/rollback matrix | `task_X_Y_architect_analysis.md` |
| Stage 2: Codebase Design | `.agents/skills/codebase-design/` | Impact analysis, file-level design, blast radius, regression risk, rollback | `task_X_Y_design.md` |
| Stage 3: CS Domain Extraction | `.agents/skills/cs-domain-learning/` | First-principles CS/ML/security/infrastructure analysis | `task_X_Y_cs_concepts.md` |
| UI/UX Intake: Picasso | `.agents/skills/picasso/` | Design system intake interview, brand tokens, typography, colors, density | `design-system/tokens.json`<br>`design-system/DESIGN_SYSTEM.md` |
| UI Data Contract: Escher | `.agents/skills/escher/` | Real backend data wiring, API schema inspection, backend gap flagging | `design-system/backend-requirements.md` |
| UI Visual Builder: Vermeer | `.agents/skills/vermeer/` | 100% token enforcement, 10 usability heuristics, 6 interactive states | Tokenized UI components + audit |
| Stage 4: Testing & Verification | `.agents/skills/testing-verification/` | Test matrix, commands, verification, quality audit, completion | `task_X_Y_testing.md` |

Full skill files MUST be loaded only when that stage is being performed.

---

## 4. Mandatory Stage Lifecycle

```text
Backend / Core Tasks:
Stage 0: WBS → Stage 1: Conceptual Understanding → [Narrsistic Pluto] → Stage 2: Design → [Stage 3: CS Domain] → Implementation → Stage 4: Testing

Frontend / UI Dashboard Tasks (The Muses Sequence):
Step 1: Check design-system/tokens.json (If missing → run Picasso)
   ↓
Step 2: Check Real Backend Contract (If data touches backend → run Escher, flag gaps in backend-requirements.md)
   ↓
Step 3: Build Visuals & Interactions (Strictly run Vermeer with tokens + 10 heuristics + 6 interaction states)
   ↓
Step 4: Self-Audit (Grep for raw hex/px codes) → Stage 4: Testing & Verification
```

### 4.1 Triggering Narrsistic Pluto

The agent MUST load `.agents/skills/narrsistic-pluto/` under the following conditions:
1. **Explicit User Triggers:** the user asks to "analyze this task like a principal architect," "give me 3–5 approaches with trade-offs," "do an RCA on this bug," or references "Narrsistic Pluto."
2. **Architectural Evaluation & Comparative Design:** choosing between competing patterns (search ranking strategies, auth provider architecture, incremental sync approaches, index schema design, caching strategy) — Phase 3 of that skill MUST actively search the web for current idioms, library versions, and known caveats.
3. **Deep Defect Diagnostics & Incident RCA:** difficult bugs, regressions, or system failures requiring 5-Whys/Fishbone RCA.

### 4.2 Mandatory Frontend & Design System Standing Rule (The Muses)

Before starting **ANY** frontend/UI task (new page, search bar, result card, modal, or layout):
1. **Step 1 (Check Tokens):** Inspect `design-system/tokens.json`. If not found, **DO NOT INVENT COLORS OR FONTS**. Run `picasso` first to define the design tokens with the user.
2. **Step 2 (Backend Contract Check):** If the component touches data, run `escher` first. Read the actual FastAPI schemas / Meilisearch document shapes. If the frontend needs a field the backend doesn't provide, **NEVER SILENTLY FAKE IT**. Log it in `design-system/backend-requirements.md` and alert the user.
3. **Step 3 (Vermeer Enforcement):** Build the UI strictly from tokens (zero raw hex codes, zero arbitrary px). Implement all 6 interactive states (`default, hover, active, focus, disabled, loading`) and pass the 10-heuristic checklist in `vermeer/SKILL.md`.
4. **Step 4 (Audit):** Scan all created/modified UI files for stray hex codes or un-tokenized px before marking complete.

### 4.3 Stage 3 Triggers (CS Domain Extraction)

Stage 3 (CS Domain Extraction) MUST be used for:
- search ranking and relevance tuning (Meilisearch ranking rules, typo tolerance);
- Google Drive API pagination, auth flows, and label query syntax;
- incremental sync algorithms and watermark strategies;
- architecture changes;
- unfamiliar runtime/framework behavior;
- difficult incidents whose root cause is not understood.

For simple, well-understood mechanical/configuration tasks, Stage 3 may be omitted.

The agent MUST NOT skip a necessary stage merely for speed.

---

## 5. Stage Gates

### Stage 0
Required: WBS task ID; objective; scope/out-of-scope; dependencies; acceptance criteria; learning objective; known risks. No implementation.

### Stage 1
Required: what; why; how; analogy where useful; architecture flow; data flow; cognitive-to-code mapping; relevant framework/domain concepts; actual execution path when source inspection is required; verified vs. inferred behavior.

### Stage: Narrsistic Pluto (Principal Architect & QA/SRE Gate)
Required Artifact: `task_X_Y_architect_analysis.md`. Must include Phase 0 (task intake, assumptions ledger), Phase 1 (topology & semver/blast radius), Phase 2 (RCA, if a bug), Phase 3 (3–5 web-researched approaches with honest rejection reasons), Phase 4/4.5 (QA matrix, rollback triggers, ADR stub). Any technology conclusion from this stage still requires formal acceptance via `docs/adr/ADR-PROMPT-TEMPLATE.md` before it governs implementation.

### Stage 2
Required: current architecture; target architecture; `[NEW]`, `[MODIFY]`, `[DELETE]` files; call/data flow; dependency impact; blast radius; regression risk; rollback plan; test strategy. No code changes.

If implementation reveals a design defect:
```text
STOP → document discovery → re-enter Stage 2 → revise design → obtain required approval → resume
```

### Stage 3
When required, analyze: first principles → mathematics → generic mechanism → framework mechanism → project implementation → integration → failure modes/trade-offs.

### Stage 4
Required: environment checklist; exact test/build commands; complete relevant output; edge-case matrix; acceptance-criteria verification; regression verification; code-quality audit; completion report.

---

## 6. Implementation Rules

Implementation begins only after required stages and approvals.

Agents MUST:
- follow the approved Stage 2 design;
- remain inside WBS scope;
- preserve architectural boundaries (auth provider ↔ indexer ↔ search index ↔ API ↔ dashboard);
- isolate provider-specific behavior behind adapter/interface patterns — never embed Google API or Meilisearch SDK calls directly in core domain logic;
- add/update tests for behavior changes;
- avoid unrelated refactoring.

Agents MUST NOT:
- introduce infrastructure without WBS justification;
- introduce a dependency, library, or architectural pattern not covered by an accepted ADR or the approved Stage 2 design;
- modify unrelated systems;
- silently change API/architecture contracts;
- bypass verification;
- hide failures.

---

## 7. Error, Incident, and Failure Protocol

Errors are first-class engineering work. A runtime error, failing test, build failure, dependency failure, integration failure, performance regression, or production incident MUST NOT automatically be handled with the smallest visible patch.

Required flow:
```text
ERROR / INCIDENT
      ↓
Capture complete evidence
      ↓
Classify problem
      ↓
Determine whether root cause is known
      ↓
Inspect relevant codebase deeply
      ↓
Trace execution / data / dependencies
      ↓
Determine root cause
      ↓
Assess blast radius / regression risk
      ↓
Apply relevant lifecycle stages
      ↓
Design fix → Implement → Targeted verification → Regression verification
      ↓
Update issue record → Update WBS if scope changed
      ↓
RESOLVE or remain OPEN/BLOCKED
```
A disappearing error is **not** automatically a resolved error.

---

## 8. Issue and Error Register

The central register is `.agents/state/issues.md`. Every non-trivial error, failure, regression, incident, or unresolved technical issue MUST be recorded.

---

## 9. Regression Rules

Every non-trivial fix must consider: original failure + direct behavior + adjacent behavior + cross-component integration + data compatibility + performance + security.

Platform request/response flow:
```text
User (Browser)
 ↓
React Dashboard (local)
 ↓
FastAPI Backend (/api/search, auth stub)
 ↓
Meilisearch Index (fuzzy + label-tagged search)
 ↑
Python Indexer (crawl → export → ingest)
 ↑
Google Drive API (via swappable auth provider)
```

---

## 10. Automated Git Kickstart & Handover Protocol

Every AI agent operating in this workspace MUST automatically execute this lifecycle around every WBS task:

### 10.1 Pre-Task Kickstart (Before Stage 1 / Implementation)
1. **Branch Hygiene:** Inspect Git status. Ensure work is rooted on latest `main` branch (`git checkout main && git pull --rebase origin main`).
2. **Branch Creation:** Create and switch to the task-isolated feature branch: `feat/task-X.Y-<slug>`.

### 10.2 Post-Task Completion (After Stage 4 Verification)
1. **Selective Staging:** Stage ONLY task-relevant files. Never use blind `git add .`.
2. **Task-Based Conventional Commit:** Commit using format: `<type>(<scope>): [Task-X.Y] <imperative short summary>`.
3. **Push & Handover Command:** Provide copy-pasteable `git push -u origin <branch>` command.

---

## 11. Generic Developer Environment & Prerequisite Gating Protocol

### 11.1 Pre-Flight Environment & Credential Audit
Before entering Stage 1 or writing code for any task requiring external services (Google Drive API, Meilisearch, OAuth):
1. **Inspect `.env` & Environment:** Check if the required environment variables are defined.
2. **Zero-Setup Guarantee:** If external services are not configured, verify if the task can run on zero-setup local defaults.
3. **Halt on Missing Required Credentials:** If an external service/credential is required and missing, halt and output the standardized **Developer Action Card**.

---

## 12. Strict Usage Protection: Zero Terminal Testing Policy

To protect the user's credits and API usage:
1. **Never Run Automated Terminal Tests:** The agent is **STRICTLY FORBIDDEN** from executing terminal test commands (`pytest`, `npm test`, `playwright`, etc.) on its own initiative. Verification must be performed via static code inspection and dual-graph analysis. Only run tests if the user explicitly writes "run test" in their prompt.
2. **Never Run Terminal Build Commands for Checking:** The agent MUST NOT run `npm run build` or CLI builds to check for TypeScript errors. Inspect types and interfaces statically.
3. **Remote Push Protocol:** Pushing to remote (`git push`) is executed upon user instruction.
4. **No Unsolicited Terminal Commands:** Do not run shell or terminal commands to probe or monitor system status.


---

## 13. Mandatory Graperoot Dual-Graph MCP for Codebase Intelligence

The agent MUST use the **graperoot** dual-graph MCP server as the primary mechanism for codebase exploration, symbol resolution, and impact analysis:
1. **Codebase Exploration:** Use `graph_retrieve` to find ranked files and structural edges based on semantic queries, rather than guessing paths or running heavy CLI grep/find commands.
2. **Targeted Reading:** Use `graph_read` to inspect files or specific symbol anchors (`file::symbol`).
3. **Dependency & Topology Analysis:** Use `graph_neighbors` to inspect call graphs, imports, and exports.
4. **Blast Radius & Impact:** Use `graph_impact` before modifying code to verify caller impact and prevent regressions.
5. **Exact Text Fallback:** Use `fallback_rg` when textual regex search is required.
