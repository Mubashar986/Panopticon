---
name: evidence-and-truthfulness
description: Enforces evidence-based reasoning, full-file inspection before code changes, and prohibits hallucinated claims about code, tests, or system behavior.
---

# Rule 04: Evidence and Truthfulness

This rule enforces explicit, verifiable evidence gathering and completely prohibits hallucinations regarding system state, file existence, or test outcomes. The AI must interact with the codebase exactly as a meticulous human engineer would.

## Evidence Taxonomy

Whenever providing status or reasoning, classify the evidence into one of these categories:
- **VERIFIED:** You executed a tool command (e.g., ran a test, read a file) and directly observed the output.
- **INFERRED:** Deduced from verified information (e.g., a test passed, so the underlying logic is likely correct). Must be clearly stated as inference.
- **ASSUMED:** Information believed to be true but not verified. **(Highly restricted: DO NOT use assumptions for critical paths.)**
- **UNKNOWN:** Information that is missing. Must explicitly state: "I don't know, I need to check."
- **BLOCKED:** Unable to gather evidence due to missing tools, permissions, or dependencies.

## Evidence Preference Hierarchy

When determining the truth of the system, always default to the highest level of evidence available:
1. **Repository Evidence** (Actual code via `view_file`)
2. **Executed Commands** (Outputs from `run_command` via terminal)
3. **Tests & Benchmarks** (Live test execution results)
4. **Accepted ADRs** (`docs/adr/`)
5. **Intuition** (NEVER ALLOWED)

## Full-File Inspection Mandate

Agents are strictly prohibited from modifying files blindly based on grep snippets or partial memory.

**Before modifying ANY file:**
1. Use `view_file` to read the ENTIRE file (all imports, class definitions, types, signatures, and exports).
2. Before changing a function signature or return type, you MUST search and inspect ALL callers/consumers across the repository.
3. **NO Grep-Snippet Editing:** Do not rely on isolated snippets for context. You must understand the full file state.
4. **NO Lazy Placeholder Snippets:** When writing code, generating artifacts, or making edits, using phrases like `"// ... rest unchanged"` or `"# ... previous code"` is **STRICTLY PROHIBITED**. Provide the complete and precise edit block.

## Rules Against Hallucination

The following behaviors will result in an immediate incident report:
- **Never invent test results or benchmark numbers.** If you didn't run the command, do not claim it passed.
- **Never claim a fix without running verification.** A patch is not a fix until verified.
- **Never claim a file/function/schema exists without inspecting the repository.**
- **Inspect complete logs before diagnosing runtime failures.** Do not guess based on a stack trace snippet; read the surrounding logs.

### Concrete Examples

- **Correct Behavior:** "I checked `api/routes/exam.py` and see the function `submit_exam` takes `user_id`. I will now run `pytest tests/test_exam.py` to ensure my change doesn't break existing coverage."
- **Violation:** "I fixed the bug. The tests pass. The issue is resolved." (When no test command was actually executed).
- **Violation:** Attempting to use the `replace_file_content` tool on a file without having used `view_file` first to verify the exact string layout and whitespace.
