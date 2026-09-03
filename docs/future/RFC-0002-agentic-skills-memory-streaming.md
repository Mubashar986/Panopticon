# RFC-0002: Advanced Agentic Engineering — Progressive Skills, Multi-Turn Memory & Real-Time Streaming

**Status:** Proposed (Scheduled for Post-Epic 10 Future Work)  
**Date:** 2026-09-01  
**Target Subsystem:** Agentic RAG Subsystem (`app/agent`)  

---

## 1. Executive Summary

This RFC formalizes the next-generation architectural enhancements for Panopticon's Agentic RAG engine following the completion of Epic 9 (Agentic RAG Intelligence) and Epic 10 (Multi-Source Connectors):

1. **Document Reading Skill & Progressive Disclosure (`load_skill`)**: Modular procedural guidance for dense Google Docs and complex Google Sheets matrices.
2. **Multi-Turn Persistent Conversation Memory & Tool-Output Pruning**: Long-lived chat sessions (`thread_id`) with sliding-window compaction.
3. **Native Meilisearch Hybrid Vector Indexing**: Single-engine keyword + dense vector search via Meilisearch `_vectors`.
4. **Real-Time Server-Sent Events (SSE) Agent Streaming**: Low-latency visibility into thought progression and tool calls.
5. **Parallel Tool Calling & Plan-and-Solve Decomposition**: Concurrent tool dispatch and structured multi-step execution scratchpads.
6. **Semantic Query & Q&A Response Caching**: Sub-20ms instant answers for repeated queries with zero LLM API cost.

---

## 2. Architectural Components

### 2.1 Document Reading Skill & Progressive Disclosure
- **Problem:** Feeding exhaustive instructions for all document formats into every system prompt causes context window bloat and "lost-in-the-middle" attention degradation.
- **Solution:** Follow the [agentskills.io](https://agentskills.io) standard:
  - Maintain `.agents/skills/document-reader/SKILL.md` with explicit heuristics for:
    - *Google Sheets / CSV:* Column header anchoring to every cell value, handling sparse/merged rows, formula cross-referencing.
    - *Google Docs:* Legal clause boundaries, revision tables, and multi-tier section hierarchies.
  - Expose a `load_skill(skill_name: str)` tool to the agent runtime so the engine dynamically loads specialized reading instructions only when relevant documents are retrieved.

### 2.2 Multi-Turn Persistent Conversation Memory & Pruning Invariant
- **Problem:** Current reasoning engine runs are single-turn stateless queries. Keeping raw multi-kilobyte tool outputs across 5+ turns would quickly saturate context limits.
- **Solution:**
  - Persist conversation threads in SQLite (`agent_threads` and `agent_messages`).
  - **Tool-Output Pruning Rule:**
    - Full tool arguments and outputs are retained **only for the active turn ($t=0$)**.
    - For all prior turns ($t > 0$), raw tool output JSON blobs are replaced by 1-line execution summaries (e.g. `"[Pruned output: 3 files inspected for 'Falcon']"`). The assistant's natural-language answer preserves the synthesized factual ground.

### 2.3 Native Meilisearch Hybrid Vector Indexing
- **Problem:** In-memory SQLite cosine similarity calculation requires linear scans over chunk tables.
- **Solution:** Compute chunk embeddings during sync and push them directly to Meilisearch under the document `_vectors` field. Meilisearch evaluates BM25 keyword matching and vector cosine distance in a single query pass.

### 2.4 Server-Sent Events (SSE) Real-Time Agent Streaming
- **Problem:** Synchronous HTTP calls force users to wait 5–15 seconds with a static loading spinner.
- **Solution:** Implement `GET /api/agent/query/stream` producing real-time SSE frames:
  - `event: step_start`: Execution turn index.
  - `event: tool_call`: Tool name and arguments.
  - `event: tool_result`: Tool execution summary badge.
  - `event: token`: Streaming delta tokens of the synthesized answer.

### 2.5 Parallel Tool Calling & Plan-and-Solve Decomposition
- **Problem:** Sequential tool execution compounds network latency.
- **Solution:** Dispatch concurrent tool calls using Python `asyncio.gather()`, paired with a high-level plan scratchpad for cross-document comparisons.

### 2.6 Semantic Query & Q&A Response Caching
- **Problem:** Identical questions burn unnecessary LLM API tokens and incur repeated latency.
- **Solution:** Cache query answers in SQLite/Redis, keyed by prompt hash and project tags, invalidated automatically when the sync watermark commits changes.
