---
description: Run the full WBS-first, stage-gated, decision-gated, error-locked development lifecycle for a task on Panopticon.
---

# DevCycle Workflow

This is the standard development lifecycle workflow for Panopticon. When executing a task, orchestrate strictly using `AGENTS.md` and the skills under `.agents/skills/`.

## Core Execution Sequence

0. **Git Kickstart & Environment Pre-Flight Audit:**
   - Check Git status, ensure work is rooted on latest `main` (`git checkout main && git pull --rebase origin main`), and switch to the task-isolated feature branch (`feat/task-X.Y-<slug>`).
   - Run Pre-Flight Environment Audit (Section 25): Check `.env` for task prerequisites. If external credentials (Google OAuth, Meilisearch) are missing, present the **Developer Action Card** or fallback to local zero-setup defaults (mock data, local Meilisearch).

1. **Load Constraints:** Load `AGENTS.md` in full. Restate the active constraints from §1.2 (decision-first execution), §1.3 (non-negotiable product constraints), and §25 (prerequisite gating) before doing anything else.

2. **WBS Check:** Check `.agents/state/current_task.md`. If no active WBS leaf task matches the current work, execute the `roadmap-wbs-planner` skill (Stage 0). **STOP** and wait for explicit user approval of the WBS before continuing.

3. **Conceptual Understanding:** Execute the `conceptual-understanding` skill (Stage 1) for the approved leaf task.

4. **Living Decision Registry Checks:** Check `docs/adr/ADR-INDEX.md` and related indexes.
   - If this task depends on any decision marked `PENDING`, involves choosing between competing patterns, or requires a difficult defect fix — execute `adr-generator` or `narrsistic-pluto`.
   - **STOP** for user acceptance. Update indices and `.agents/state/decisions.md` only after acceptance.

5. **Codebase Design (Stage 2):** Execute the `codebase-design` skill. No code changes yet.
   - **STOP** and wait for explicit user approval.

5.5. **Frontend Design System & Data Seams (The Muses — For UI Tasks):**
   - **Check Tokens:** Check `design-system/tokens.json`. If missing, execute `picasso` first to define design tokens with the user.
   - **Check Backend Contract:** If building UI that displays/submits data, execute `escher` to inspect real FastAPI schemas/endpoints. Flag any missing backend capabilities in `design-system/backend-requirements.md`.
   - **Build Visuals (Vermeer):** Enforce 100% token usage (zero raw hex/px) and 10 usability heuristics with all 6 interactive states.

6. **CS Domain Learning (Stage 3):** If the task touches search ranking/relevance tuning, Google Drive API pagination/auth flows, incremental sync algorithms, Meilisearch configuration, or unfamiliar behavior — execute `cs-domain-learning`.
   - **STOP** and present Stage 1–3 artifacts together.

7. **Implementation (Stage 4 - Coding):** Implement strictly according to the approved Stage 2 design.
   - **Terminal Command Error Lock:** Enforced at every stage. If ANY terminal command fails, halt the devcycle and immediately trigger `/incident-rca`. No proceeding past errors.
   - **Zero Silent Library Ingestion:** Do not introduce ANY dependency or architectural pattern not covered by an accepted ADR. Stop and flag it instead.
   - **UI Self-Audit:** For UI tasks, scan for stray hex codes or un-tokenized px before finishing.
   - **Full-File Inspection:** Inspect all modified files fully before finishing implementation to ensure zero drift.

8. **QA & Verification (Stage 5):** Execute the `testing-verification` and `qa-audit` workflows.

9. **Git Staging & Commit:** Stage only task-specific files and state files. Commit with task ID format: `<type>(<scope>): [Task-X.Y] <summary>`. Provide copy-pasteable `git push -u origin <branch>` command.

10. **Completion:** Update `.agents/state/current_task.md`, `current_stage.md`, `decisions.md`, and `docs/adr/ADR-INDEX.md`. Report completion using the Agent Response Contract format.
