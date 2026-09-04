# Issues and Error Register — Panopticon

This is the central register for all non-trivial errors, failures, regressions, incidents, and unresolved technical issues encountered during Panopticon development.

Use the template below when adding new issues:

```markdown
## ISSUE-XXXX — Short title

Status: OPEN | INVESTIGATING | BLOCKED | FIXED_PENDING_VERIFICATION | RESOLVED | WONT_FIX
Severity: LOW | MEDIUM | HIGH | CRITICAL
Detected: YYYY-MM-DD
Detected During: WBS task / stage
Architectural Domain: (e.g. Indexer, Search, API, Dashboard, Auth, Infrastructure)
Component: component/path
Symptom:
Reproduction:
Evidence:
Root Cause:
Contributing Factors:
Affected Scope:
Regression Risk: LOW | MEDIUM | HIGH
Related WBS:
Related Artifacts:
Fix:
Verification:
Regression Verification:
Resolution:
Remaining Risk:
Resolved On: YYYY-MM-DD
```

## ISSUE-0001 — PowerShell multi-line string quote stripping in inline Python CLI execution

Status: RESOLVED
Severity: LOW
Detected: 2026-08-30
Detected During: Epic 7 Drop 1 verification
Architectural Domain: Infrastructure / Tooling
Component: verification command
Symptom: Inline `python -c` script failed with `SyntaxError: unterminated string literal` on Windows PowerShell.
Reproduction: `python -c "cursor.execute(\"SELECT ...\")"` in PowerShell.
Evidence: PowerShell stripped escaped quotes before passing string to Python interpreter.
Root Cause: PowerShell parsing treats backslash-quote `\"` differently than POSIX shells, resulting in quote stripping and broken syntax in multi-line inline commands.
Contributing Factors: Using inline `-c` script instead of a clean standalone verification `.py` script.
Affected Scope: CLI verification commands only. No application code or database affected.
Regression Risk: LOW
Related WBS: Epic 7 Drop 1
Related Artifacts: `backend/migrations/0007_add_change_tracking.py`
Fix: Use a dedicated Python verification script file instead of inline multi-line PowerShell string commands.
Verification: Executed verification script via file execution.
Regression Verification: All schema checks confirmed passing cleanly.
Resolution: Resolved.
Remaining Risk: None.
Resolved On: 2026-08-30

## ISSUE-0002 — Meilisearch rejection of null _vectors field during batch ingestion

Status: RESOLVED
Severity: MEDIUM
Detected: 2026-09-03
Detected During: Task 9.9 dual-index ingestion
Architectural Domain: Search / Serialization
Component: app/search/models.py (SearchDocument.to_meili_dict, ChunkSearchDocument.to_meili_dict)
Symptom: Ingestion failed with Meilisearch task error: `Index panopticon_docs: invalid type: null, expected a map at line 1 column 4`.
Reproduction: `python scripts/ingest_to_meilisearch.py` when documents have `vectors=None`.
Evidence: Task failure returned by Meilisearch: `{'message': 'Index panopticon_docs: invalid type: null, expected a map at line 1 column 4', 'code': 'internal', 'type': 'internal'}`.
Root Cause: In Pydantic model serialization, `vectors: dict | None = Field(default=None, alias="_vectors")` dumped as `{"_vectors": null}` when unassigned. Meilisearch v1.12 vector deserializer expects `_vectors` to be a valid JSON map/object (e.g. `{"default": [...]}`) and rejects `null` as invalid type.
Contributing Factors: `to_meili_dict()` called `model_dump(by_alias=True)` without pruning `None` vectors.
Affected Scope: `SearchDocument` and `ChunkSearchDocument` Meilisearch dictionary serialization.
Regression Risk: LOW
Related WBS: Task 9.9
Related Artifacts: `app/search/models.py`
Fix: In `to_meili_dict()`, strip `_vectors` if it is `None` or empty dictionary, ensuring Meilisearch only receives `_vectors` when valid vector embeddings are present.
Verification: Re-ran `ingest_to_meilisearch.py`, successfully upserting 92 documents and 92 chunks with zero errors in 2.42s.
Regression Verification: Serializing documents with and without vectors verified in `tests/test_hybrid_vector_search.py`.
Resolution: Resolved.
Remaining Risk: None.
Resolved On: 2026-09-03

## ISSUE-0003 — Windows PowerShell npm script resolution failure: 'vite' is not recognized

Status: RESOLVED
Severity: MEDIUM
Detected: 2026-09-04
Detected During: Task 10.4 frontend development server startup
Architectural Domain: Tooling / Build Environment
Component: frontend/package.json (scripts.dev: vite)
Symptom: Running `npm run dev` in `frontend/` failed with `'vite' is not recognized as an internal or external command, operable program or batch file.`
Reproduction: `cd frontend; npm run dev` when `node_modules` is absent or actively locked during concurrent installation.
Evidence: 
  Terminal stdout:
  > panopticon-observatory@0.1.0 dev
  > vite
  'vite' is not recognized as an internal or external command, operable program or batch file.
Root Cause: 
  1. `node_modules` was initially absent after repo setup.
  2. Race condition: The user executed `npm run dev` in an interactive PowerShell session while the background `npm install` task was still actively writing and extracting packages into `frontend/node_modules\.bin\`. Under Windows file locking semantics and cmd.exe script-shell path resolution, executing the script prior to the completion of `.bin\vite.cmd` wrapper creation produces `ERROR_FILE_NOT_FOUND`.
Contributing Factors: Background asynchronous installation without an explicit synchronous barrier before command invocation.
Affected Scope: Local development server startup (`frontend/`).
Regression Risk: LOW
Related WBS: Task 10.4
Related Artifacts: `.agents/artifacts/task_10_4/task_10_4_architect_analysis.md`
Fix: Completed full `npm install` (134 packages audited, `node_modules\.bin\vite.cmd` confirmed present).
Verification: Verified `npx vite --version` and `.\node_modules\.bin\vite --version` return `vite/6.4.3 win32-x64 node-v24.12.0`.
Regression Verification: Tested binary execution directly via PowerShell.
Resolution: Resolved.
Remaining Risk: None.
Resolved On: 2026-09-04

## ISSUE-0004 — Windows cmd.exe subshell 'node' resolution failure during npm script execution

Status: FIXED_PENDING_VERIFICATION
Severity: MEDIUM
Detected: 2026-09-04
Detected During: Task 10.4 frontend local dev execution
Architectural Domain: Tooling / OS Environment / Windows PATH
Component: Windows HKCU/HKLM Environment, frontend/package.json
Symptom: Running `npm run dev` in PowerShell produced:
  > panopticon-observatory@0.1.0 dev
  > node ./node_modules/vite/bin/vite.js
  'node' is not recognized as an internal or external command, operable program or batch file.
Reproduction: `cd frontend; npm run dev` in a terminal where user environment has not inherited `C:\Program Files\nodejs\` or where Machine PATH bloat causes `cmd.exe` buffer truncation.
Evidence: 
  1. `Machine PATH` length was 11,740 characters across 286 segments containing recursive `%PATH%` (segment 18) and 18 duplicate blocks.
  2. `User PATH` (HKCU\Environment\Path) completely lacked `C:\Program Files\nodejs`.
  3. `npm.ps1` runs because PowerShell executes it with internal `$NODE_EXE="$PSScriptRoot/node.exe"`, but npm spawns `cmd.exe /d /s /c "node ..."` which relies on `%PATH%`.
  4. In existing open terminals, the process environment lacks Node in User PATH, causing `cmd.exe` to fail lookup.
Root Cause: 
  Node.js was installed only into the system-wide Machine PATH (HKLM) and not User PATH (HKCU). Because Machine PATH was bloated to 11,740 characters with unexpanded/recursive `%PATH%`, Windows `cmd.exe` subshells spawned by `npm` either truncated `%PATH%` or did not inherit `C:\Program Files\nodejs`. Running processes also do not dynamically refresh environment variables from registry without session reload.
Contributing Factors: Legacy bloated Machine PATH, npm default `script-shell` being `cmd.exe`.
Affected Scope: Local frontend development server runner in PowerShell.
Regression Risk: LOW
Related WBS: Task 10.4
Related Artifacts: `.agents/artifacts/task_10_4/task_10_4_architect_analysis.md`
Fix: 
  1. Safely prepended `C:\Program Files\nodejs` directly to `HKCU\Environment\Path` via WinReg and broadcasted `WM_SETTINGCHANGE`.
  2. Added native `frontend/dev.ps1` runner for zero-dependency, zero-cmd.exe direct execution in PowerShell.
Verification: HKCU registry entry verified present at index 0.
Regression Verification: Cross-checked `inspect_path.py`.
Resolution: Fixed pending user verification in their terminal session.
Remaining Risk: Existing terminal window needs one-time session variable refresh `$env:Path = 'C:\Program Files\nodejs;' + $env:Path` or a fresh terminal window.
Resolved On: 2026-09-04
