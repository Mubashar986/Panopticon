# Stage 1 Concept-to-Code Bridge: Task 10.2 — Project-Scoped RAG Rig & Tool Isolation ("Ask Dossier")

## Section 1: Visual Architecture

```mermaid
graph TD
    User([User / Browser Dashboard])
    
    subgraph FastAPI_Endpoints ["FastAPI Agent Endpoints"]
        QueryRoute["POST /api/agent/query\n{query, thread_id, dossier_id}"]
        StreamRoute["POST /api/agent/query/stream\n(Real-Time SSE Stream)"]
    end

    subgraph Agentic_Core ["Agentic Reasoning Subsystem"]
        AgentEngine["AgenticReasoningEngine\n(app/agent/engine.py)"]
        Context["AgentToolContext\n(holds storage, search_service, dossier_id)"]
        
        subgraph Tool_Registry ["5 Agent Tools (Dossier-Scoped)"]
            T_Search["search_index(query, dossier_id)"]
            T_Diff["get_document_diff(file_id, dossier_id)"]
            T_Meta["get_file_metadata(file_id, dossier_id)"]
            T_Vector["semantic_chunk_search(query, dossier_id)"]
            T_Stats["get_document_catalog_stats(dossier_id)"]
        end
    end

    subgraph Isolation_Barrier ["Project Dossier Security Boundary"]
        DossierCheck{"Check dossier_items\nin SQLite"}
        AllowedFiles["Allowed File IDs Set\n[doc_1, doc_2, ...]"]
    end

    subgraph Retrieval_Backends ["Filtered Search Engines"]
        MeiliDocs[("Meilisearch: panopticon_docs\nFilter: id IN [allowed_file_ids]")]
        MeiliChunks[("Meilisearch: panopticon_chunks\nFilter: file_id IN [allowed_file_ids]")]
        SQLiteStore[("SQLite: crawl_state.db\nfile_records & diffs")]
    end

    User -->|Ask Question in Dossier| QueryRoute & StreamRoute
    QueryRoute & StreamRoute --> AgentEngine
    AgentEngine --> Context
    Context --> Tool_Registry
    Tool_Registry --> DossierCheck
    DossierCheck --> AllowedFiles
    AllowedFiles --> MeiliDocs & MeiliChunks & SQLiteStore
```

---

## Section 2: The Physical Analogy

> Imagine a **corporate defense research institute with multiple classified project vaults** (e.g. Vault A: *"Project Falcon"*, Vault B: *"Project Apollo"*).
>
> In the global un-scoped mode, the research assistant walks through the open public lobby and answers questions from any document on any desk.
>
> In **"Ask Dossier" mode**, the assistant is escorted into **Vault A ("Project Falcon")**. The door locks behind it. The assistant is only permitted to read the blueprints, change logs, and meeting minutes stored on Vault A's shelves. If someone asks *"What is the budget for Project Apollo?"*, the assistant immediately reports that Apollo documents do not exist inside Vault A. Cross-vault contamination, leakage, and distraction are physically impossible.

---

## Section 3: Why & What

### 1. Why are we doing this task?
- **Zero Cross-Project Hallucination**: When an engineering or product team chats with "Project Falcon", they want answers derived solely from Falcon specifications. Returning snippets from an unrelated "SmartTrade" or "Internal IT" document creates confusion and undermines trust.
- **Token Economy & Precision**: Scoping retrieval to a specific Dossier eliminates thousands of irrelevant tokens from the prompt context, dramatically boosting answer quality and speeding up reasoning latency.
- **Enterprise Multi-Project Privacy**: Prepares Panopticon for multi-tenant / multi-project workspaces where users should only query documents they have access to.

### 2. What is the concept?
**Project-Scoped RAG** is an architectural constraint that injects a `dossier_id` parameter across the entire query pipeline. All 5 agent tools (`search_index`, `get_document_diff`, `get_file_metadata`, `semantic_chunk_search`, `get_document_catalog_stats`) resolve the set of authorized `file_ids` contained in that Dossier, and constrain keyword queries, vector similarity searches, diff lookups, and repository statistics strictly to that set.

### 3. What breaks if we skip it?
- The Dossiers created in Task 10.1 remain static file folders with no intelligence or conversational capability.
- An agent answering inside a Dossier would query the global repository and hallucinate information from other projects.
- The upcoming High-Rhythm Frontend Redesign (Task 10.4) cannot deliver the "Ask Dossier" chat drawer.

---

## Section 4: Abstraction Level Map

| Level | What Lives Here | Current Project Example | Touched by Task 10.2? |
|---|---|---|---|
| **Product / UX** | "Ask Dossier" chat drawer in React | Frontend (Task 10.4) | ❌ (Deferred to 10.4) |
| **API / Transport** | `/api/agent/query`, `/api/agent/query/stream` accepting `dossier_id` | `app/api/routes/agent.py` | ✅ **YES** |
| **Agent / Reasoning** | ReAct tool loop, tool schemas, context injection | `app/agent/engine.py`, `app/agent/tools.py` | ✅ **YES** |
| **Search Engine** | Meilisearch `IN [allowed_ids]` filter expression | `app/search/service.py` | ✅ **YES** |
| **Storage / Persistence** | Querying `dossier_items` for file membership | `app/indexer/storage.py` | ✅ **YES** (uses Task 10.1 methods) |

---

## Section 5: Mermaid Diagrams

### 1. Sequence Diagram: Dossier-Scoped Agentic Query Execution

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Dashboard
    participant API as FastAPI Router (/api/agent/query)
    participant Engine as AgenticReasoningEngine
    participant Tools as Agent Tool Dispatcher
    participant Storage as CrawlStorage (SQLite)
    participant Search as SearchService (Meilisearch)
    participant LLM as OpenRouter / Swappable LLM

    User->>API: POST /api/agent/query {prompt: "What were the changes in specs?", dossier_id: "dos_falcon"}
    API->>Storage: Verify dossier exists & retrieve file_ids
    Storage-->>API: file_ids = ["doc_falcon_arch", "doc_falcon_api"]
    API->>Engine: query(prompt, dossier_id="dos_falcon", allowed_file_ids=[...])
    
    Engine->>LLM: Prompt + Tool Schemas (scoped context injected in system prompt)
    LLM-->>Engine: Tool Call: search_index(query="specs", dossier_id="dos_falcon")
    
    Engine->>Tools: execute("search_index", args, ctx)
    Tools->>Search: search(query="specs", allowed_file_ids=["doc_falcon_arch", ...])
    Search-->>Tools: Scoped Search Hits (Falcon only)
    Tools-->>Engine: Tool Output (Falcon files only)
    
    Engine->>LLM: Tool Result Observation
    LLM-->>Engine: Final Synthesized Answer citing Falcon Docs
    Engine-->>API: AgentResponse (Verified Falcon citations)
    API-->>User: HTTP 200 JSON Response
```

### 2. Decision Logic for Tool Execution Scoping

```mermaid
flowchart TD
    Start[Tool Call Received] --> HasDossier{dossier_id provided in tool args or context?}
    
    HasDossier -- No --> GlobalSearch[Execute Global Search across all files]
    HasDossier -- Yes --> GetItems[Retrieve allowed_file_ids from storage.list_dossier_items]
    
    GetItems --> IsEmpty{Is dossier empty?}
    IsEmpty -- Yes --> EmptyResult[Return instant empty result: 'No documents in this dossier yet']
    IsEmpty -- No --> ToolType{Tool Name}
    
    ToolType -- search_index --> MeiliFilter[Filter Meilisearch query: id IN allowed_file_ids]
    ToolType -- semantic_chunk_search --> ChunkFilter[Filter Meilisearch vector query: file_id IN allowed_file_ids]
    ToolType -- get_file_metadata / diff --> BoundaryCheck{Is file_id in allowed_file_ids?}
    BoundaryCheck -- No --> Reject[Error: Document does not belong to this Dossier]
    BoundaryCheck -- Yes --> FetchLocal[Return diff or metadata]
    ToolType -- get_document_catalog_stats --> ScopedStats[Compute stats restricted to dossier files]
```

---

## Section 6: Data Flow Trace-Through

1. **Request Ingestion (`POST /api/agent/query` or `POST /api/agent/query/stream`)**:
   - Client passes `prompt`, optional `thread_id`, and `dossier_id` (e.g. `"dos_falcon"`).
   - Router validates that `dossier_id` exists in `CrawlStorage`. If invalid, returns `404 Not Found`.
2. **Context Setup & Allowed File Resolution**:
   - Router fetches `allowed_files, total = storage.list_dossier_items(dossier_id)`.
   - Populates `allowed_file_ids = {f.id for f in allowed_files}`.
   - Injects `dossier_id` and `allowed_file_ids` into `AgentToolContext` and system prompt.
3. **ReAct Tool Execution Loop**:
   - When the LLM calls `search_index` or `semantic_chunk_search`, the dispatcher passes `allowed_file_ids` to `SearchService`.
   - If the dossier has 0 files, the tools return a helpful notice immediately without querying Meilisearch.
   - If the LLM attempts to call `get_document_diff` or `get_file_metadata` on a file outside the dossier, the tool refuses and warns the model: `"Security restriction: Document 'xyz' does not belong to Project Dossier '...'."`
4. **Citation Verification**:
   - `CitationVerifier` checks cited document IDs against both SQLite and the dossier boundary. Citations outside the dossier are stripped.
5. **Response Delivery**:
   - Response streams tokens and verified citations with 100% boundary isolation.
