# Escher Backend Contract & Gap Register — Task 9.8 (Multi-Turn Chat Sessions & SQLite Thread Persistence)

**Target Components:** 
- "Ask Panopticon" Agentic Chat Workspace (`frontend/src/components/agent/AgentChatDrawer.tsx`)
- Thread History Sidebar (`frontend/src/components/agent/ThreadHistorySidebar.tsx`)
- Agent Chat Hook (`frontend/src/hooks/useAgentChat.ts`)

**Backend Endpoints:**
- `GET /api/agent/threads` (List conversation threads)
- `POST /api/agent/threads` (Create new conversation thread)
- `GET /api/agent/threads/{thread_id}` (Retrieve thread details & full messages)
- `PATCH /api/agent/threads/{thread_id}` (Rename conversation thread)
- `DELETE /api/agent/threads/{thread_id}` (Delete conversation thread)
- `POST /api/agent/query/stream` (Stream reasoning with `thread_id`)

**Inspected Backend Routes:** [`app/api/routes/agent.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/routes/agent.py)  
**Inspected Backend Schemas:** [`app/api/schemas/agent.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/schemas/agent.py)  

---

## 1. Thread Management Endpoints & Wire Schemas

| Endpoint | Method | Request Payload | Response Model | Status |
|---|---|---|---|---|
| `/api/agent/threads` | `GET` | `?limit=50&offset=0` | `list[AgentThreadItem]` | ✅ IMPLEMENTED |
| `/api/agent/threads` | `POST` | `{"title": str, "model": str \| null}` | `AgentThreadItem` | ✅ IMPLEMENTED |
| `/api/agent/threads/{id}` | `GET` | None | `AgentThreadDetail` (includes `messages`) | ✅ IMPLEMENTED |
| `/api/agent/threads/{id}` | `PATCH` | `{"title": str}` | `AgentThreadItem` | ✅ IMPLEMENTED |
| `/api/agent/threads/{id}` | `DELETE` | None | `{"status": "deleted", "id": str}` | ✅ IMPLEMENTED |

### Schema Definitions:

```typescript
export interface AgentThread {
  id: string;
  title: string;
  model: string | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface AgentThreadDetail extends AgentThread {
  messages: ChatMessageWireItem[];
}

export interface ChatMessageWireItem {
  id: string;
  thread_id: string;
  role: 'user' | 'assistant';
  content: string;
  trace?: AgentStepTraceItem[];
  citations?: VerifiedCitationItem[];
  model?: string;
  latency_ms?: number;
  created_at: string;
}
```

---

## 2. Streaming Query with Thread Context (`POST /api/agent/query/stream`)

| Request Field | Status | Data Type | Notes |
|---|---|---|---|
| `query` | ✅ AVAILABLE | `string` | User prompt/question |
| `thread_id` | ✅ AVAILABLE | `string \| null` | If supplied, loads prior messages, saves user & assistant turns to SQLite |
| `model` | ✅ AVAILABLE | `string \| null` | Optional model override |
| `user_instructions` | ✅ AVAILABLE | `string \| null` | Optional system formatting instructions |

---

## 3. Two-Tier Context Compaction & Pruning Invariant

- **Active Turn ($t = 0$):**
  - Full tool declarations sent to LLM.
  - Live tool execution and streaming SSE frames (`step_start`, `tool_call`, `tool_result`, `token`, `citations`, `done`).
- **Prior Turns ($t > 0$):**
  - Raw tool outputs (multi-KB JSON payloads) are **pruned** from the prompt memory.
  - Only clean alternating `user` $\rightarrow$ `assistant` turns are supplied in context.
  - Preserves factual continuity while eliminating context explosion and rate limits.

---

## 4. Frontend Interaction & Visual Design Constraints (Vermeer)

- **History Drawer / Sidebar:**
  - Drawer width: 560px total; when history sidebar is expanded, it toggles a clean sliding list or overlay without horizontal clipping.
  - "+ New Chat" button at the top of the history panel.
  - Active thread highlighted with `var(--color-bg-surface-elevated)` and border `var(--color-brand-primary)`.
  - Delete button has hover styling (`var(--color-error)`) and confirmation step.
  - Zero raw hex codes or arbitrary px; 100% tokenized from `design-system/tokens.json`.
