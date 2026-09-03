---
description: Pre-commit and pre-completion quality audit workflow. Verifies code quality, contract stability, dependency hygiene, test coverage, and architectural compliance before marking any task complete.
---

# QA Audit Workflow

## 1. Trigger
This workflow must be run before marking any WBS task as complete.

## 2. Full-File Review
Perform a full-file review of all modified files. Ensure no partial edits, syntax errors, or unresolved merge conflict markers remain.

## 3. Dependency Audit
Check `package.json`, `requirements.txt`, `Cargo.toml`, or relevant dependency files.
- Were any unapproved libraries introduced?
- If yes, halt and trigger the ADR Decision Workflow.

## 4. Type Safety Check
Run the static type checker (e.g., `tsc`, `mypy`). Ensure zero errors.

## 5. Lint Check
Run the project's linter (e.g., `eslint`, `ruff`, `flake8`). Enforce clean output.

## 6. Test Execution
Run all relevant test suites (Unit, Integration, E2E). Ensure all pass. 

## 7. Contract Stability Verification
Check that API shapes, database schemas, and frontend props are unchanged OR properly documented in updated contracts.

## 8. Security Quick-Check
- Verify no secrets (API keys, passwords, tokens) were committed.
- Verify safe input handling (e.g., parameterized queries, sanitized HTML).

## 9. Architecture Compliance
Ensure domain boundaries are respected. Confirm no provider lock-in was introduced silently (e.g., no OpenAI-specific code embedded deep inside domain entities).

## 10. Stage 4 Integration
Integrate directly with the `testing-verification` skill output to validate all QA matrices.

## 11. Completion Report Template
Generate and output the completion report:
```markdown
### QA Audit Completion Report
- **Task:** [Task ID & Name]
- **Type Check:** PASS
- **Lint Check:** PASS
- **Tests Executed:** [N] (PASS)
- **Dependencies Added:** [List or None]
- **Architectural Flags:** [List or None]
- **Status:** APPROVED FOR COMPLETION
```
