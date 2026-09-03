---
name: adr-and-dependency-governance
description: Enforces the zero-assumption technology and library decision protocol. No tool, library, framework, or architectural pattern may be used without formal evaluation and user acceptance.
---

# Rule 03: ADR and Dependency Governance

This rule strictly enforces the **Zero Silent Library Ingestion Policy** and the **Decision-First Execution Model** outlined in `AGENTS.md` §1.2. The platform architecture explicitly leaves foundational technology choices undecided until formal Architecture Decision Records (ADRs) are approved. 

**An agent CANNOT default to any library, framework, or service based on its training habits.**

## The Open Technology List

The following components MUST have an accepted ADR in `docs/adr/` before any related code is written or library is imported:
- Primary database technology & ORMs
- Redis / Caching strategy
- Vector Database technology
- Background Task Framework (e.g., Celery vs RQ)
- Message Broker
- LLM Provider & Abstraction Layer
- Embedding Provider
- Frontend Framework
- Object Storage Provider
- Deployment Platform
- Authentication Provider
- AI Structured-Output Validation Framework

### Evaluation Hierarchy
When a task requires a missing technology decision, use the following evaluation hierarchy:
1. **Platform Primitives First:** Can we do this with the standard library or existing accepted tools?
2. **3-5 Pattern Comparison:** Use Narrsistic Pluto to evaluate 3-5 distinct patterns.
3. **Stage 2 Sign-off:** Integrate the chosen pattern into the design artifact.
4. **ADR Generation:** Generate the formal ADR using `docs/adr/ADR-PROMPT-TEMPLATE.md`.

## The Living Decision Registry Protocol

All decisions are recorded in the central registries in `docs/adr/` and summarized in `.agents/state/decisions.md`. 
The registries are categorized into four types:
- **ADR (Architecture Decision Registry):** Core infrastructure, services, hosting, patterns.
- **DDR (Data Decision Registry):** Database models, ORMs, caching strategies, state management.
- **AIDR (AI/LLM/RAG Decision Registry):** Prompt structures, embeddings, RAG chunking, mastery models.
- **FDR (Frontend Decision Registry):** Frameworks, state management, CSS paradigms.

### When a Decision Surfaces (The STOP Protocol)

If an agent realizes a WBS task depends on an unresolved technology:
```text
STOP execution
→ Check docs/adr/ADR-INDEX.md
→ If PENDING or non-existent: Halt implementation.
→ Generate the ADR/DDR/AIDR using the standard prompt template.
→ Present to the user for formal acceptance.
→ Record the decision in .agents/state/decisions.md once approved.
→ Resume the stage lifecycle.
```

### Concrete Examples of Violations

- **Violation 1:** Auto-importing `SQLAlchemy` or `asyncpg` to write database queries when no database ADR has been accepted.
- **Violation 2:** Choosing to use `Redis` for caching without writing an ADR to evaluate alternatives (e.g., in-memory cache, memcached).
- **Violation 3:** Defaulting to `LangChain` or `LlamaIndex` to implement RAG when the architectural approach hasn't been formalized via AIDR.
- **Violation 4:** Hardcoding `axios` for API calls in the frontend when `fetch` or a different client hasn't been established.

### Supersession Protocol

To change a previously accepted decision:
1. Halt implementation.
2. Run Narrsistic Pluto to evaluate the migration/impact.
3. Draft a superseding ADR that explicitly marks the old ADR as "Superseded".
4. Obtain user approval before writing any migration code.
