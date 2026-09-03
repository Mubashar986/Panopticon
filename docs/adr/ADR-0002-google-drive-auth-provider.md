# ADR-0002: Dual Drive Auth Providers (Personal OAuth + Domain-Wide Delegation Factory)

**Status:** Accepted  
**Date:** 2026-08-27  
**Decision Type:** ADR (Architecture Decision Record)  
**Authors:** Principal Systems Architect  
**Task Association:** Task 1.2 — Build dual Drive auth providers (Personal OAuth + Domain-Wide Delegation Factory)  

---

## 1. Context & Problem Statement

Panopticon indexes files and metadata across Google Drive and Google Workspace.
During initial local development, the developer operates on a personal `@gmail.com` account. In production or enterprise team deployments, the application must index organizational Google Workspace drives using a Service Account with Domain-Wide Delegation (DWD).

We must establish an authentication architecture that:
1. Enables immediate local personal development without enterprise Google Workspace admin approvals.
2. Enables zero-code-change enterprise handover where switching to a corporate Service Account requires only a single `.env` setting flip.
3. Completely prevents external Google auth libraries from leaking into the core crawler, parser, and search indexing logic (Non-Negotiable Product Constraint 1 & 7).
4. Strictly prevents secret leakage (Non-Negotiable Product Constraint 9).

---

## 2. Decision

We will implement a **Pluggable Abstract Base Class Provider Hierarchy with a Central Configuration Factory** in `app/core/auth/`:

1. **`DriveAuthProvider` (Abstract Base Class):** Defines the core contract `get_credentials(self) -> google.auth.credentials.Credentials`.
2. **`PersonalOAuthProvider` (Adapter):** Implements user-consent OAuth2 flow via `google_auth_oauthlib.flow.InstalledAppFlow` and caches offline refresh tokens in `token.json`, automatically performing token refresh via `google.auth.transport.requests.Request`.
3. **`DomainWideDelegationProvider` (Adapter):** Implements enterprise service account authentication via `google.oauth2.service_account.Credentials.from_service_account_file()` and optionally impersonates a delegated user email via `.with_subject(email)`.
4. **`get_auth_provider()` (Factory):** Reads `DRIVE_AUTH_MODE` ("oauth" vs. "service_account") from `app.core.config.Settings` and returns the configured provider instance.
5. **Custom Auth Exceptions:** Typed exceptions (`AuthError`, `AuthConfigurationError`, `MissingCredentialsFileError`) to provide clear, actionable developer guidance when secret files are absent.

---

## 3. Evaluated Alternatives

### Option A: Abstract Base Class + Factory Pattern (SELECTED)
- **Score:** 85/85
- **Pros:** Strict Dependency Inversion; zero SDK leakage; 100% unit-testable with mock providers; instant config-driven switching.
- **Cons:** Additional class definitions and factory layer.

### Option B: Duck Typing via `typing.Protocol`
- **Score:** 72/85
- **Pros:** Structural subtyping without explicit inheritance.
- **Cons:** Less rigid runtime verification; missing shared base helper utilities.

### Option C: In-line `if/else` inside Crawler
- **Score:** 31/85 (FAILS Mandatory Gate 10)
- **Pros:** Fast to write in a single file.
- **Cons:** Violates Product Constraints 1 & 7; tightly couples business logic to Google SDKs; makes testing crawler impossible without real credentials.

---

## 4. Consequences & Guarantees

### Positive Consequences
- **Loose Coupling:** The crawler and indexer know only about `DriveAuthProvider` and standard `Credentials`.
- **Seamless Testing:** Test suites mock `DriveAuthProvider` with 0 network calls and 0 real credentials.
- **Security:** Secret files (`credentials.json`, `token.json`, `service_account.json`) remain isolated in project root and are strictly gitignored.
- **Resilience:** Token refreshes happen automatically on expired tokens without re-prompting the user.

### Negative Consequences / Trade-offs
- Developers must supply either `credentials.json` (for OAuth) or `service_account.json` (for DWD) when performing live integration tests against real Google Drive APIs.

---

## 5. Compliance with Mandatory Product Constraints

- **Constraint 1 (Swappable Provider Seam):** COMPLIANT. Core crawler imports only `DriveAuthProvider`.
- **Constraint 7 (No Provider Logic Leakage):** COMPLIANT. OAuth flows and SA parsing are fully encapsulated inside `app.core.auth.*`.
- **Constraint 9 (No Secrets in Index / Git):** COMPLIANT. Tokens are serialized strictly to local filesystem files covered by `.gitignore`.
