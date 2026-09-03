# Global Rules — Panopticon

This file is loaded for every conversation in this workspace. Its purpose is to guarantee the hardest constraints hold even if a skill isn't triggered or `AGENTS.md` isn't picked up for some reason — treat it as a backstop, not a replacement for `AGENTS.md`.

**Always check for `AGENTS.md` in the project workspace root first and load it in full before any planning or implementation.** It is the operating contract for this project.

## 1. Non-Negotiable Product Constraints

These are permanent, drawn directly from the project requirements, and apply regardless of which WBS task is active. No design or task may propose violating one:

1. Drive auth must be abstracted behind a swappable provider interface — crawler/indexer code must never touch OAuth specifics directly.
2. The dashboard is a pointer/index — it shows titles, snippets, and links. No full document content is mirrored or cached.
3. Search operates against the local Meilisearch index only — no live Google Drive API calls on search requests.
4. Crawled content and metadata must be treated as untrusted input (sanitize before indexing).
5. File exports must handle the 10MB Drive server-side cap gracefully (metadata-only fallback, never crash).
6. API authentication must be a pluggable seam (currently a no-op stub for local use, swappable later).
7. Provider-specific logic (Google API, Meilisearch internals) must not leak into core domain logic — use adapter/interface patterns.
8. Crawl scope must be explicitly bounded and documented (personal-account limitations vs. future domain-wide).
9. No OAuth tokens, refresh tokens, or API secrets may be stored in the search index, committed to Git, or exposed via API responses.
10. Incremental sync must be safe — deleted/moved files must be detected and removed from the index, not left as stale ghost entries.

## 2. Terminal Command Error Lock
- ANY error in terminal execution (build, test, lint, script, runtime) means the agent **IMMEDIATELY HALTS** all other work.
- It must invoke the `narrsistic-pluto` skill for full 5-Whys/Fishbone Root Cause Analysis before resuming.
- The error must be logged in `.agents/state/issues.md`.
- A disappearing error is NOT automatically resolved.

## 3. Zero Silent Library/Dependency Ingestion
- The agent is STRICTLY FORBIDDEN from introducing ANY library, SDK, package, or dependency by habit or assumption.
- Must evaluate platform primitives first, then compare 3-5 alternatives.
- Must get explicit user approval in Stage 2 Design before any `npm install` or `pip install`.

## 4. Full-File Inspection Mandate
- Before modifying ANY file, the agent MUST read the ENTIRE file.
- Before changing any function signature or return type, the agent MUST search for and inspect ALL callers across the repository.
- Every claim about code must be tagged VERIFIED, INFERRED, or UNVERIFIED.

## 5. Single Developer Git Protocol
- Feature branch: `feat/task-X.Y-<slug>`
- Stage only task-relevant files.
- Commit format: `<type>(<scope>): [Task-X.Y] <summary>`

## 6. Mandatory UI/UX & Design System Rule (The Muses: Picasso + Escher + Vermeer)
- **Zero Hallucinated Styles:** The agent is **STRICTLY FORBIDDEN** from inventing random hex colors, arbitrary px padding/margins, or unapproved fonts.
- **Tokens First:** Before any UI work, check `design-system/tokens.json`. If missing, run **Picasso** first to establish tokens.
- **Backend-Aware Data Contract:** Before building UI that touches backend data, run **Escher** to inspect real API schemas. Never invent silent mock fields; flag any missing backend capability in `design-system/backend-requirements.md`.
- **Heuristic & Token Enforcement:** Build all UI strictly via **Vermeer** (100% tokens, 10 usability heuristics, 6 interactive states: `default, hover, active, focus, disabled, loading`).
- **Self-Audit:** Verify 0 stray hex codes or un-tokenized px before marking any UI task complete.

## 7. Strict Zero-Terminal-Testing & Zero-Push Policy (Usage Protection)
- The agent is **STRICTLY FORBIDDEN** from running automated terminal tests (`pytest`, `npm test`, etc.) or checking builds (`npm run build`) in terminal.
- The agent is **STRICTLY FORBIDDEN** from running `git push`. Local commits only.
- Code verification must be performed via static inspection, typing analysis, and MCP graph tools.

## 8. Mandatory Graperoot Dual-Graph MCP
- Codebase exploration, symbol lookups, call-graph analysis, and blast radius impact MUST be performed using the `graperoot` MCP tools (`graph_retrieve`, `graph_read`, `graph_neighbors`, `graph_impact`, `fallback_rg`).
- Never run blind shell commands when the dual-graph provides structural and semantic code intelligence.

