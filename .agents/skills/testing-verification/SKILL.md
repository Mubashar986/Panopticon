---
name: testing-verification
description: Creates a Stage 4 Testing & Completion Artifact for any project. Defines stack-appropriate test matrices with expected outputs and copy-pasteable commands, guides user-run verification, analyzes reported results, performs code quality review, and produces a final completion report.
---

# Testing & Verification Skill

This is **Stage 4** of the generic task lifecycle. After code is implemented, this skill creates a rigorous verification protocol and completion report.

This skill is **stack-adaptive**. Use the current repository's actual language, framework, package manager, test runner, environment, services, and deployment style.

---

## Core Principles (Non-Negotiable)

1. **User runs tests by default.** Provide exact, copy-pasteable commands. Only run commands yourself if the user explicitly asks or the active workflow allows it.
2. **Pre-test checklist first.** Verify the environment is in a known-good state before testing.
3. **Categorize every test.** Tag test cases by category such as Unit, Integration, E2E, Security, Accessibility, Performance, Failover, Regression, or UX.
4. **Expected output required.** Every test must say what success and failure look like.
5. **Clean up after testing.** Provide cleanup/reset commands when tests create data, files, containers, or external resources.
6. **Watch logs when relevant.** If the project has servers, workers, containers, or background jobs, tell the user what logs to watch.
7. **Code quality review.** After functional tests pass, audit the new code for maintainability, safety, and project conventions.

---

## Required Document Structure

Save as `task_X_Y_testing.md` in the artifact directory.

### Section 1: Pre-Test Environment Checklist

Adapt this to the project. Include only verified or clearly relevant commands.

```markdown
## Pre-Test Checklist

1. Install dependencies if needed.
2. Confirm environment variables are set.
3. Confirm database/services are running if the task needs them.
4. Confirm the app/server starts if required.
5. Open logs in a second terminal if relevant.
```

Examples by stack:

```powershell
# JavaScript/TypeScript
npm install
npm run build

# Python
python -m pip install -r requirements.txt
python -m pytest --collect-only

# Health check if a local API exists
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
```

Use the repository's actual commands in the final artifact.

### Section 2: Test Categories & Edge Case Matrices

Choose categories that fit the task. For small tasks, provide at least 10 total edge cases. For larger or risky tasks, provide multiple categories with at least 10 cases each.

Recommended categories:

#### Category A: Static Checks / Unit Tests

```markdown
| ID | Test Case | Command/Input | Expected Output |
|----|-----------|---------------|-----------------|
| U-01 | Typecheck/build compiles | project command | 0 errors |
| U-02 | Unit tests pass | project command | All tests pass |
| U-03 | Lint passes | project command | 0 lint errors |
```

#### Category B: Integration Tests

Use when multiple layers interact: UI + API, route + service + DB, command + file system, etc.

```markdown
| ID | Test Case | Steps/Input | Expected Output |
|----|-----------|-------------|-----------------|
| I-01 | Happy path | ... | ... |
| I-02 | Missing required input | ... | Validation error, no crash |
```

#### Category C: User Flow / E2E Tests

Use for frontend or full-stack behavior.

```markdown
| ID | Test Case | Steps/Input | Expected Output |
|----|-----------|-------------|-----------------|
| E-01 | User completes main flow | ... | Correct screen/state appears |
| E-02 | Refresh page mid-flow | ... | State recovers or fails safely |
```

#### Category D: Security & Validation Tests

Use when handling auth, roles, user input, secrets, files, payment, network, or data persistence.

```markdown
| ID | Test Case | Input | Expected Output |
|----|-----------|-------|-----------------|
| S-01 | Unauthorized access | No/invalid credentials | 401/redirect/blocked action |
| S-02 | Role mismatch | Lower-privilege user | 403/hidden action |
| S-03 | Injection/XSS-style input | Malicious string | Safely escaped/rejected |
```

#### Category E: Accessibility / UX Tests

Use for frontend tasks.

```markdown
| ID | Test Case | Steps | Expected Output |
|----|-----------|-------|-----------------|
| A-01 | Keyboard navigation | Tab through UI | Focus order is logical |
| A-02 | Form labels | Inspect fields | Inputs have visible/accessible labels |
| A-03 | Error announcement | Submit invalid form | Error text is clear and associated |
```

#### Category F: Performance / Stress / Failover Tests

Use when relevant to backend, infrastructure, or heavy UI rendering.

```markdown
| ID | Test Case | Trigger | Expected Output |
|----|-----------|---------|-----------------|
| P-01 | Repeated requests/actions | Loop or manual repeat | No memory leak/crash |
| P-02 | Slow network/API | Simulated delay | Loading/error states work |
| F-01 | Service unavailable | Stop/mock dependency | Graceful error, recovery path |
```

### Section 3: Observability Guide

Tell the user what to watch:

```markdown
| Signal | Where to Check | Healthy Pattern | Problem Pattern |
|--------|----------------|-----------------|-----------------|
| Browser console | DevTools Console | No red errors | Unhandled exceptions |
| Network calls | DevTools Network | Expected status/body | 401 loop, 500, CORS |
| Server logs | Terminal/log file | Expected request logs | Tracebacks/panics |
| Test output | Terminal | All tests pass | Failures with stack traces |
```

Adapt to available logs, tools, and services.

### Section 4: Code Quality Review

After tests pass, perform a stack-specific audit.

```markdown
## Code Quality Audit

### 4.1 Error Handling
- [ ] Errors are handled explicitly.
- [ ] Messages are clear and actionable.
- [ ] No silent failures.
- [ ] No unsafe production crashes for expected errors.

### 4.2 Type / Contract Safety
- [ ] Types/schemas/interfaces match API or module contracts.
- [ ] Public function/component signatures are minimal.
- [ ] Runtime validation exists for untrusted input.

### 4.3 State and Side Effects
- [ ] State updates are predictable.
- [ ] Async operations handle loading/success/error states.
- [ ] Cleanup occurs for subscriptions, timers, files, or connections.

### 4.4 Security and Privacy
- [ ] Auth/role checks are preserved.
- [ ] No secrets are logged or committed.
- [ ] User input is validated/escaped.
- [ ] Sensitive tokens/data are stored appropriately.

### 4.5 Accessibility and UX (Frontend)
- [ ] Keyboard navigation works.
- [ ] Inputs have labels.
- [ ] Errors are visible and understandable.
- [ ] Loading/empty states are clear.

### 4.6 Code Hygiene
- [ ] No dead code or unused imports.
- [ ] No unnecessary complexity.
- [ ] Naming matches project conventions.
- [ ] Formatting/linting passes.
- [ ] Tests/docs updated where appropriate.
```

### Section 5: Post-Test Cleanup

Provide cleanup commands only for resources created during testing:

```powershell
# Examples only; adapt to the project
# Remove generated test files
Remove-Item .\tmp-test-file.txt -ErrorAction SilentlyContinue

# Stop containers if they were started for testing
docker compose down

# Remove test database records only if safe and clearly scoped
# DELETE FROM table WHERE name LIKE 'test-%';
```

Warn before destructive cleanup such as dropping databases, deleting user files, or resetting repositories.

### Section 6: Test Results Analysis

When the user shares output, analyze it using this table:

```markdown
| Test ID | Status | Observation | Root Cause (if failed) | Fix/Next Step |
|---------|--------|-------------|------------------------|---------------|
| U-01 | ✅ PASS | ... | — | — |
| I-02 | ❌ FAIL | ... | ... | ... |
```

If a test fails:

1. Identify whether it is a real bug, environment issue, flaky test, or expected behavior.
2. Explain the root cause in plain language.
3. If code must change, return to Stage 2/3 as needed.
4. Re-test only the affected cases first.
5. Repeat until the task is complete or remaining limitations are clearly documented.

### Section 7: Completion Report

```markdown
## Completion Report

| Metric | Value |
|--------|-------|
| Total Tests Planned | N |
| Tests Run By User | N |
| Tests Passed | N |
| Tests Failed | N |
| Code Quality Issues Found | N |
| Files Modified | N |
| Remaining Risks | None / List |
| Follow-Up Recommended | None / List |
```

Do not claim tests passed unless the user or agent actually ran them and saw passing output.

---

## Workflow Checklist

Before marking the Testing Artifact as complete, verify:

- [ ] Pre-test checklist provided.
- [ ] Test categories match the task and stack.
- [ ] At least 10 relevant edge cases included for non-trivial tasks.
- [ ] Commands are copy-pasteable and project-appropriate.
- [ ] Expected outputs are included.
- [ ] Observability/log guide included where relevant.
- [ ] Code quality audit included.
- [ ] Cleanup instructions included where needed.
- [ ] User-reported results analyzed if available.
- [ ] Completion report filled in.
