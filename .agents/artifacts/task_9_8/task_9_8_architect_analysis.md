# Narrsistic Pluto — Principal Architect & Lead QA/SRE Analysis: Task 9.8

**Task ID:** `9.8`  
**Task Title:** Multi-Turn Chat Sessions, SQLite Thread Persistence & UI Drawer History (RFC-0002)  
**Epic:** Epic 9 — Agentic RAG Intelligence & OpenRouter Provider Seam  
**Status:** APPROVED  
**Date:** 2026-09-02  
**Roles:** Principal Systems Architect & Lead QA/SRE Infrastructure Engineer  

---

## Phase 0: Task Intake & Definition of Ready

### 1. Acceptance Criteria Check
The acceptance criteria defined in `roadmap_wbs.md` (Task 9.8) and `docs/future/RFC-0002-agentic-skills-memory-streaming.md`:
- [x] **AC-1:** SQLite relational tables `agent_threads` and `agent_messages` persist full conversation metadata, tool execution traces, and verified citations across server restarts with foreign key integrity (`ON DELETE CASCADE`).
- [x] **AC-2:** Two-tier context compaction engine prunes raw tool output JSON blobs for prior completed turns ($t > 0$), passing clean conversational turns (`user` $\rightarrow$ `assistant`) while preserving full tool execution for the active turn ($t = 0$).
- [x] **AC-3:** REST endpoints for thread lifecycle: `GET /api/agent/threads` (list), `POST /api/agent/threads` (create), `GET /api/agent/threads/{thread_id}` (get thread + messages), `PATCH /api/agent/threads/{thread_id}` (rename), and `DELETE /api/agent/threads/{thread_id}` (delete).
- [x] **AC-4:** Streaming endpoint `POST /api/agent/query/stream` accepts optional `thread_id`; automatically appends the user query, executes within thread context, streams SSE frames, and commits assistant message + citations on completion.
- [x] **AC-5:** React UI drawer (`AgentChatDrawer.tsx`) features a collapsible thread history sidebar with "+ New Chat", session selection, inline title renaming, and deletion, adhering 100% to Picasso tokens and Vermeer interaction states.
- [x] **AC-6:** 100% test coverage with zero regressions across existing test suites (239/239 passing baseline).

### 2. Assumptions Ledger
- **Assumption 1 (Database Concurrency):** SQLite running in `PRAGMA journal_mode=WAL` with a 5,000ms busy timeout handles concurrent reads during background sync while chat messages are written.
- **Assumption 2 (Thread Isolation):** All message queries are strictly parameterized by `thread_id`; conversations are completely isolated and never leak messages into adjacent threads.
- **Assumption 3 (Backward Compatibility):** Omitting `thread_id` in `POST /api/agent/query/stream` or `POST /api/agent/query` maintains backward compatibility with stateless one-off requests.

### 3. Traceability Anchor
- **Originating Spec:** `docs/future/RFC-0002-agentic-skills-memory-streaming.md` (Section 2.2: Multi-Turn Persistent Conversation Memory & Pruning Invariant).
- **Roadmap WBS:** Section 8, Task 9.8 & Section 13.2.
- **Architectural Decision Record:** `docs/adr/ADR-0007-multi-turn-thread-persistence-context-compaction.md`.

---

## Phase 1: Architectural Compliance & Codebase Topology

### 1. Architectural Alignment
- **Domain-Driven Design (DDD) & Clean Architecture:**
  - `app/indexer/models.py`: Defines immutable Pydantic entities `AgentThread` and `AgentMessage`.
  - `app/indexer/storage.py`: Acts as the repository implementation encapsulating all SQL operations, schema migrations, and connection pooling.
  - `app/agent/engine.py`: Encapsulates conversational memory orchestration and context compaction without embedding raw database logic.
  - `app/api/routes/agent.py`: Pure transport adapter mapping HTTP/SSE requests to domain engines via FastAPI dependency injection (`CrawlStorageDep`).
- **Product Constraint Compliance:**
  - *Constraint 2 & 3:* No full document text is mirrored; search continues against local index.
  - *Constraint 6:* API auth seam preserved.
  - *Constraint 7:* Zero leakage of provider specifics into storage.
  - *Constraint 9:* Zero API keys or tokens persisted in message tables.

### 2. Blast Radius & Code Churn Mapping

| Module / File | Change Type | SemVer Classification | Blast Radius | Notes |
|---|---|---|---|---|
| `app/indexer/storage.py` | [MODIFY] | MINOR (Additive) | Low | New tables `agent_threads`, `agent_messages` & indices; CRUD methods. |
| `app/indexer/models.py` | [MODIFY] | MINOR (Additive) | Low | Pydantic models `AgentThread`, `AgentMessage`. |
| `app/agent/engine.py` | [MODIFY] | MINOR (Additive) | Low | Context compaction support in `run` and `run_stream`. |
| `app/api/schemas/agent.py` | [MODIFY] | MINOR (Additive) | Low | New schemas `AgentThreadItem`, `AgentThreadDetail`, `CreateThreadRequest`, `UpdateThreadRequest`; optional `thread_id` in `AgentQueryRequest`. |
| `app/api/routes/agent.py` | [MODIFY] | MINOR (Additive) | Low | Thread CRUD endpoints + `thread_id` streaming integration. |
| `frontend/src/types/agent.ts` | [MODIFY] | MINOR (Additive) | Low | TypeScript types for threads and thread operations. |
| `frontend/src/hooks/useAgentChat.ts` | [MODIFY] | MINOR (Additive) | Low | Multi-thread management, active thread state, thread switching. |
| `frontend/src/components/agent/AgentChatDrawer.tsx` | [MODIFY] | MINOR (Additive) | Low | Thread history sidebar, "+ New Chat" button, thread switching. |
| `tests/test_agent_threads.py` | [NEW] | PATCH (Internal) | Zero | Unit & integration tests for thread storage, engine compaction, and API. |

**Overall Breaking-Change Risk:** **LOW** (100% backward-compatible; existing stateless clients and test suites continue working unchanged).

---

## Phase 2: Operational Defect & Constraint Analysis (The Context Explosion Hazard)

While Task 9.8 is a new feature, it directly addresses a critical operational risk identified in `doc.md` and live testing:

1. **The Compounding Context Hazard:**
   - In Panopticon, `search_index` returns up to 2,500 characters of formatted search hits.
   - `get_document_diff` returns up to 1,200 characters of patch text.
   - `semantic_chunk_search` returns up to 4,000 characters of chunk text.
   - In a 5-turn conversation where each turn executes 2 tools, naive history retention would inject:
     $$5 \times 2 \times 2500 \approx 25,000 \text{ characters} \approx 6,500\text{--}8,000 \text{ prompt tokens}$$
   - On free OpenRouter models (Nemotron, Llama 3, MiniMax), this quickly triggers:
     - HTTP 429 Rate Limit Errors;
     - Severe generation latency (>15s);
     - Attention degradation ("lost-in-the-middle"), where the model confuses past tool results with current questions.
2. **The Invariant Solution:**
   - Tool outputs are kept in prompt context **only for the active turn ($t=0$)**.
   - As soon as a turn completes, the assistant's final response (which was verified against citations) becomes the historical record.
   - For all prior turns ($t > 0$), raw tool output JSON is stripped from the prompt memory. The LLM only receives the chronological Q&A dialog:
     `User(t-1) -> Assistant(t-1) -> User(t=0)`.

---

## Phase 3: Multi-Pattern Solution Engineering (Web-Researched)

### Approach 1: Naive Full Raw History Accumulation
- **Pattern:** Append all messages and tool events directly into the prompt context array.
- **Web Prior Art:** Common in early LangChain chat tutorials.
- **Honest Rejection Rationale:** Explodes context windows after 3 turns; burns token quota; causes frequent rate-limit failures on OpenRouter free tiers.

### Approach 2: Sliding-Window K-Turn Truncation (FIFO Drop)
- **Pattern:** Retain only the last $K$ raw messages (e.g. $K=4$). Any message older than $K$ is permanently dropped.
- **Web Prior Art:** Widely used in standard chat wrappers (OpenAI Assistants API naive truncation).
- **Honest Rejection Rationale:** If a user establishes critical context in Turn 1 (e.g., *"We are auditing the Falcon project"*), dropping Turn 1 in Turn 5 causes total context loss.

### Approach 3: Hierarchical SQLite Persistence with Two-Tier Selective Tool Pruning (Chosen)
- **Pattern:**
  - Persist complete fidelity in SQLite (`agent_threads`, `agent_messages` with `trace_json` and `citations_json`) for full UI observability and auditing.
  - In working LLM memory, prune raw multi-kilobyte tool payloads for $t > 0$, retaining only alternating user queries and factual assistant answers.
- **Web Research Grounding:** Confirmed by current industry practices (Mem0, Redis Memory Architecture, LangGraph Context Engineering): separate *Working Memory* (prompt) from *Long-Term Memory* (relational store), using selective compaction to prevent context rot.
- **Pros:** Bounded prompt overhead (~150 tokens per past turn); zero dependency additions; instant SQLite lookups (<1ms); 100% persistent across restarts.
- **Cons:** Requires schema migrations and state handling across UI/API/Engine.

### Approach 4: Offloaded Vector Summary Memory (Auto-Summarizer Node)
- **Pattern:** Run a secondary background LLM summarization call after every turn to compress prior dialog into an evolving episodic summary vector stored in a vector DB.
- **Web Prior Art:** LangChain `ConversationSummaryBufferMemory`.
- **Honest Rejection Rationale:** Adds extra LLM calls per turn, increasing cost and latency by 2–4 seconds per interaction, and introduces vector search dependencies for simple multi-turn sessions.

---

## Phase 4: Comparative Engineering Trade-Offs & QA Rigour Matrix

| Criteria | Approach 1 (Naive) | Approach 2 (FIFO Truncation) | Approach 3 (SQLite + Pruning) [RECOMMENDED] | Approach 4 (Auto-Summary) |
|---|---|---|---|---|
| **Prompt Token Overhead** | Exponential ($O(N \cdot \text{tool\_size})$) | Bounded to $K$ turns | Strictly Bounded ($O(N \cdot \text{answer\_size})$) | Minimal ($O(\text{summary})$) |
| **Context Retention** | 100% until context crash | Loses early context | 100% of facts, 0% of raw JSON bloat | Lossy natural language |
| **Turn Latency Overhead** | +3000ms compounding | Neutral | <2ms SQLite read | +2000–4000ms (extra LLM call) |
| **External Dependencies** | Zero | Zero | Zero (Built-in SQLite) | Vector DB / Embedder |
| **Auditability & Replay** | Ephemeral | Ephemeral | Full (Trace & Citations in DB) | Partial |

### Test Pyramid Strategy
1. **Unit Tests (`tests/test_agent_threads.py`):**
   - Verify `CrawlStorage` thread CRUD operations (create, get, list, update title, delete cascade).
   - Verify `AgenticReasoningEngine` context compaction (tool outputs pruned for prior turns, full tools for active turn).
2. **Integration Tests (`tests/test_api_agent_threads.py`):**
   - Test REST endpoints: `GET /api/agent/threads`, `POST /api/agent/threads`, `GET /api/agent/threads/{id}`, `DELETE /api/agent/threads/{id}`.
   - Test `POST /api/agent/query/stream` with `thread_id`: verify user and assistant messages are saved to database and chronological turns are maintained.
3. **Frontend Tests / Build Verification:**
   - Verify TypeScript compilation (`npm run build`).
   - Audit for 0 stray hex codes or un-tokenized px.

### Rollout & Rollback Matrix
- **Rollout Mechanism:** Expand-contract SQLite migration (new tables only); backward-compatible API params (`thread_id` is optional).
- **Rollback Trigger:** If any database lock contention or thread query latency exceeds 50ms, stateless queries remain unaffected; dropping the table reverts system to 9.5 baseline cleanly.

---

## Phase 4.5: Documentation & Knowledge Capture

- **ADR Created:** `docs/adr/ADR-0007-multi-turn-thread-persistence-context-compaction.md`
- **RFC Implemented:** `docs/future/RFC-0002-agentic-skills-memory-streaming.md` (Section 2.2)
- **API Documentation:** Update `docs/API_DOCUMENTATION.md` with thread routes.
