---
name: non-negotiable-constraints
description: Enforces the 10 non-negotiable product constraints for Panopticon that apply regardless of task or stage.
---

# Rule 01: Non-Negotiable Product Constraints

This rule enforces the 10 core product constraints defined in `AGENTS.md` §1.3. These constraints apply permanently across all WBS tasks, epic definitions, and implementation stages.

**No WBS task, codebase design, or architectural decision may propose violating any of these constraints. If a task or user request appears to require it, STOP and escalate immediately.**

---

## Constraint 1: Drive auth must be abstracted behind a swappable provider interface
- **WHAT it means:** The crawler/indexer code must only ever call `auth_provider.get_credentials()` — zero OAuth-specific or Service-Account-specific logic outside the auth provider implementation.
- **WHY it exists:** The system uses personal-account OAuth for local dev but supports Google Workspace Domain-Wide Delegation for the team via a clean factory switch (`DRIVE_AUTH_MODE`).
- **WHAT the agent must do:** Ensure all Drive API calls receive credentials through the `DriveAuthProvider` interface. Both `PersonalOAuthProvider` and `DomainWideDelegationProvider` satisfy this interface.
- **WHAT happens if violated:** STOP the current task and flag a `CRITICAL` architectural risk.
- **EXAMPLE Violation:** Importing `google_auth_oauthlib` directly in `crawler.py` instead of going through the auth provider interface.

## Constraint 2: Dashboard is a pointer/index — no content mirroring
- **WHAT it means:** The dashboard shows titles, snippets, metadata, and "View" links to real Drive files. It does NOT store, cache, or display full document bodies.
- **WHY it exists:** Security, privacy, and scope control. The dashboard is a search pointer, not a document mirror.
- **WHAT the agent must do:** Ensure API responses include only: id, name, type, owner, lastEditor, lastModified, matchedVia, confidence, sharedWith, snippet, viewUrl, exportLinks.
- **WHAT happens if violated:** HALT implementation. Re-design the API response schema.
- **EXAMPLE Violation:** Adding a `full_content` field to the search API response or caching entire document bodies in Meilisearch.

## Constraint 3: Search operates against the local index only
- **WHAT it means:** When a user searches on the dashboard, the query hits Meilisearch — never the Google Drive API in real time.
- **WHY it exists:** Performance, quota protection, and offline resilience. Live Drive queries would be slow and rate-limited.
- **WHAT the agent must do:** Ensure the `/api/search` endpoint queries Meilisearch only. Drive API calls happen exclusively during indexer crawl runs.
- **WHAT happens if violated:** STOP and re-architect the search flow.
- **EXAMPLE Violation:** Calling `service.files().list()` inside the FastAPI search endpoint handler.

## Constraint 4: Crawled content treated as untrusted input
- **WHAT it means:** File metadata, labels, content text, and permissions returned by the Drive API must be sanitized before being stored in the search index or displayed in the dashboard.
- **WHY it exists:** Prevents XSS, control-character corruption, or index malformation.
- **WHAT the agent must do:** Validate and sanitize all Drive API output before indexing.
- **WHAT happens if violated:** Escalate to QA and re-enter Stage 2 to build sanitization middleware.
- **EXAMPLE Violation:** Indexing raw text or rendering HTML without sanitizing script tags or special characters.

## Constraint 5: 10MB export cap handled gracefully
- **WHAT it means:** Google Drive's server-side export has a 10MB per file ceiling. Files exceeding this must be indexed with metadata only, not crash the pipeline.
- **WHY it exists:** One oversized file must not break the crawl run.
- **WHAT the agent must do:** Detect export size/failure, log a warning, index the file with metadata only, and flag it as "metadata_only".
- **WHAT happens if violated:** Execute Narrsistic Pluto RCA on the failure-handling logic.
- **EXAMPLE Violation:** Wrapping export in a bare `try...except pass` and silently dropping the file without indexing metadata.

## Constraint 6: API auth is a pluggable seam
- **WHAT it means:** The FastAPI API has an auth dependency that currently passes locally (no-op stub), but is structured so real auth drops in later without touching route handlers.
- **WHY it exists:** Keeps local development friction-free while maintaining a clean seam for future team authentication.
- **WHAT the agent must do:** Implement auth as a single FastAPI dependency function. Route handlers must never reference auth details directly.
- **WHAT happens if violated:** Design rejection. Halt task and extract the auth coupling.
- **EXAMPLE Violation:** Hardcoding auth checks directly inside individual route handlers.

## Constraint 7: Provider-specific logic stays behind adapters
- **WHAT it means:** No Google API SDK calls or Meilisearch client calls embedded directly in core domain/search logic. Use adapter/interface patterns.
- **WHY it exists:** Enables clean unit testing with mocks and isolates vendor SDK changes.
- **WHAT the agent must do:** Create thin adapter layers for Google Drive API and Meilisearch.
- **WHAT happens if violated:** Refactor immediately to extract the dependency.
- **EXAMPLE Violation:** Importing `meilisearch` directly inside `search_service.py` and constructing raw Meilisearch query objects in the business logic layer.

## Constraint 8: Crawl scope explicitly bounded and documented
- **WHAT it means:** The system must clearly define and document what files it can see based on the active auth mode (personal account visibility vs. full domain-wide crawl).
- **WHY it exists:** Prevents false expectations when demoing or deploying.
- **WHAT the agent must do:** Log and document the crawl scope boundaries clearly.
- **WHAT happens if violated:** Log a `MEDIUM` risk issue about unclear scope communication.
- **EXAMPLE Violation:** Presenting a personal-account crawl as a full company-wide index without qualification.

## Constraint 9: No secrets in the index, Git, or API responses
- **WHAT it means:** OAuth tokens, refresh tokens, client secrets, and Service Account JSON keys must never appear in the Meilisearch index, be committed to Git, or be returned in API responses.
- **WHY it exists:** Prevents credential leakage.
- **WHAT the agent must do:** Store credentials in `.env` or dedicated key files listed in `.gitignore`. Audit API responses and index documents.
- **WHAT happens if violated:** Log a `CRITICAL` security issue and halt all non-security tasks.
- **EXAMPLE Violation:** Storing OAuth access tokens in search documents or committing `credentials.json` to Git.

## Constraint 10: Incremental sync is safe — no stale ghost entries
- **WHAT it means:** When a file is deleted, moved, or has its permissions revoked in Drive, the next indexer run must detect this and remove the stale entry from the search index.
- **WHY it exists:** Stale results that link to deleted files destroy user trust.
- **WHAT the agent must do:** Implement delete detection in the incremental sync reconciliation logic.
- **WHAT happens if violated:** Re-enter Stage 2 to design proper sync reconciliation.
- **EXAMPLE Violation:** Only adding/updating files during sync without detecting deletions.
