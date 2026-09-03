# ADR-0007: Multi-Turn Chat Sessions, SQLite Thread Persistence & Context Compaction

**Status:** Accepted  
**Date:** 2026-09-02  
**Decision Type:** ADR / DDR (Architecture & Data Decision Record)  
**Authors:** Principal Systems Architect & Lead QA/SRE  
**Task Association:** Epic 9 / Task 9.8 — Multi-Turn Chat Sessions, SQLite Thread Persistence & UI Drawer History (RFC-0002)  

---

## 1. Context & Problem Statement

In Tasks 9.3 through 9.5, Panopticon introduced the autonomous Agentic RAG reasoning engine (`AgenticReasoningEngine`) and the slide-over "Ask Panopticon" chat workspace (`AgentChatDrawer.tsx`). However, current agent interactions suffer from two fundamental operational limitations:

1. **Stateless Single-Turn Ephemerality:** Every query submitted by the user executes statelessly (`messages = [system, user]`). When a user asks a natural follow-up question (e.g., Turn 1: *"What did SmartTrade propose for database scaling?"* $\rightarrow$ Turn 2: *"Who was the author of that document?"*), the agent has zero recollection of Turn 1, cannot resolve pronouns or context, and fails to maintain conversational coherence. Furthermore, refreshing the browser wipes all chat history.
2. **Context Window Saturation from Tool Outputs:** Panopticon's tools (`search_index`, `get_document_diff`, `get_file_metadata`, `semantic_chunk_search`) return rich multi-kilobyte JSON payloads (e.g. 2,500-character search snippets, unified text diff patches, chunk vectors). Naively appending all raw tool outputs across a 5-turn or 10-turn conversation would compound token counts exponentially, triggering provider rate limits, ballooning latency, and causing "lost-in-the-middle" attention degradation.

To satisfy Section 13.2 of the Roadmap WBS and RFC-0002 without violating Panopticon's non-negotiable product constraints (zero full document mirroring, zero unapproved dependencies, local ACID durability), we must formalize:
- The persistent thread and message data schema in SQLite;
- The context compaction & tool output pruning invariant for prior conversational turns ($t > 0$);
- The REST/SSE streaming API contracts for thread-scoped reasoning;
- The session history drawer interface in the React dashboard.

---

## 2. Candidate Approaches Evaluated

### Option A: Naive Full Raw History Accumulation
- **Description:** Append all prior user inputs, assistant responses, tool calls, and raw JSON tool outputs verbatim into the LLM message array on every turn.
- **Pros:** Trivial to implement; zero summarization or compaction logic required.
- **Cons:** Rapidly blows past context limits (8k–32k tokens in 3–4 turns); compounds OpenRouter token costs; induces context clash and attention dilution.
- **Rejection Rationale:** Fails token economy, latency, and context window ceilings.

### Option B: External Third-Party Agent Memory Framework (Mem0 / LangGraph / Zep)
- **Description:** Introduce an external agent framework or hosted memory service to handle vector retrieval and conversational graph state.
- **Pros:** Off-the-shelf abstractions for conversational entity extraction.
- **Cons:** Violates Rule 3 (Zero Silent Dependency Ingestion) and Product Constraint 6/7; introduces external cloud network dependencies or heavy PyTorch/Chroma runtimes; adds vendor lock-in.
- **Rejection Rationale:** Overkill for internal document search; violates offline zero-setup guarantee and platform boundaries.

### Option C: SQLite Relational Thread Persistence with Deterministic Context Compaction (Chosen)
- **Description:** Store threads (`agent_threads`) and messages (`agent_messages`) in Panopticon's existing ACID SQLite database (`crawl_state.db`). Implement a deterministic **two-tier context compaction pipeline**:
  1. Full raw tool arguments and outputs are preserved in SQLite for auditability and UI rendering, and provided in LLM working memory **only for the active turn ($t=0$)**.
  2. For all prior completed turns ($t > 0$), raw tool output JSON blobs in the LLM prompt context are pruned: the assistant's synthesized answer and verified citations preserve the factual truth, while intermediate tool turns are either condensed into a 1-line execution receipt (e.g., `"[Tool search_index executed: 3 documents found]"`) or cleanly compacted to the standard alternating `user` $\rightarrow$ `assistant` conversational history.
- **Pros:** 100% zero new dependencies; sub-1ms SQLite read/write; guarantees constant-bounded prompt overhead per prior turn (~100–300 tokens); full offline resilience across server restarts.
- **Cons:** Requires explicit SQLite migrations and thread lifecycle API endpoints.

---

## 3. Decision & Architecture Commitments

We accept **Option C: SQLite Relational Thread Persistence with Deterministic Context Compaction**.

### 3.1 Relational Schema (`app/indexer/storage.py`)

Two new tables are added with WAL mode durability and cascaded deletion:

```sql
CREATE TABLE IF NOT EXISTS agent_threads (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user' | 'assistant'
    content TEXT NOT NULL,
    trace_json TEXT,     -- JSON array of AgentStepTrace
    citations_json TEXT, -- JSON array of VerifiedCitationItem
    model TEXT,
    latency_ms REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES agent_threads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_threads_updated_at ON agent_threads(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON agent_messages(thread_id, created_at ASC);
```

### 3.2 Two-Tier Context Compaction Invariant

When `AgenticReasoningEngine.run()` or `run_stream()` executes with an active `thread_id`:

```text
[System Prompt] (PANOPTICON_SYSTEM_PROMPT with grounding rules)
   ↓
[Prior Turn t-2: User] "What did SmartTrade propose for database scaling?"
[Prior Turn t-2: Assistant] "SmartTrade proposed a read-replica pool with partitioned shards..."
   (Note: Raw 2.5KB tool JSON outputs from t-2 are PRUNED from prompt context)
   ↓
[Prior Turn t-1: User] "Who was the author of that document?"
[Prior Turn t-1: Assistant] "The primary author was Alex Chen (alex@company.com)..."
   (Note: Raw metadata tool outputs from t-1 are PRUNED from prompt context)
   ↓
[Active Turn t=0: User] "When was the last time it was modified?"
[Active Turn t=0: Reasoning Loop] -> Live tool calls, full tool execution payloads, SSE stream
   ↓
[Persist t=0 to SQLite] -> Thread updated_at bumped; Full trace & citations stored
```

### 3.3 REST & SSE Streaming API Contracts

- `GET /api/agent/threads`: List all conversation threads ordered by `updated_at DESC`.
- `POST /api/agent/threads`: Create a new conversation thread with initial title and model.
- `GET /api/agent/threads/{thread_id}`: Retrieve thread metadata and full chronological messages.
- `PATCH /api/agent/threads/{thread_id}`: Rename thread title.
- `DELETE /api/agent/threads/{thread_id}`: Delete thread and cascade delete all associated messages.
- `POST /api/agent/query/stream`: Accepts optional `thread_id: str | None`. If supplied, executes within that persistent thread context and automatically writes user and assistant records to SQLite.

### 3.4 React UI Drawer History Experience

`AgentChatDrawer.tsx` is enhanced with a collapsible / toggleable **Thread History Sidebar**:
- Header displays conversation title with a "+ New Chat" button and History toggle.
- Thread list displays active conversation, message count, and relative timestamps ("Updated 5m ago").
- Actions to switch threads, inline rename thread titles, and delete threads with confirmation.
- 100% compliant with Picasso design tokens (`tokens.json`), 6 interaction states (`default, hover, active, focus, disabled, loading`), and Vermeer usability heuristics.

---

## 4. Quality Controls & Mandatory Gates Assessment

| Gate / Control | Status | Evaluation & Verification |
|---|---|---|
| 1. LLM Groundedness | PASS | Prior turn answers retain verified citations; active turn executes strict tool grounding. |
| 2. Thread Isolation | PASS | SQLite foreign keys and thread-scoped queries prevent cross-talk between conversations. |
| 3. State Auditability | PASS | Complete trace JSON and citation JSON persisted in `agent_messages`. |
| 4. Context Boundary | PASS | Prior turn tool output pruning prevents context window blowup. |
| 5. Zero-Setup Guarantee | PASS | Uses existing SQLite database file (`crawl_state.db`); zero new external dependencies. |
| 6. Graceful Degradation | PASS | Stateless query mode remains 100% backward-compatible if `thread_id` is omitted. |

---

## 5. Consequences & Rollout

- **Positive:** Multi-turn conversational flow is unlocked; users can ask iterative follow-up questions; chat history persists across browser refreshes and backend restarts; context tokens remain strictly bounded.
- **Negative:** SQLite file incurs incremental write load for chat logs (mitigated by WAL mode and indexing).
- **Rollback Strategy:** Schema addition is purely additive; deleting the tables or disabling `thread_id` in API requests immediately falls back to stateless single-turn execution with zero blast radius.
