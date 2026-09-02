# 🔭 Panopticon Observatory

> **High-speed document discovery, temporal version diffing, and agentic RAG intelligence for Google Workspace (Google Docs & Google Sheets).**

[![Python 3.12](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/Frontend-React%2019-61DAFB.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Bundler-Vite%206-646CFF.svg)](https://vitejs.dev/)
[![Meilisearch](https://img.shields.io/badge/Search-Meilisearch-FF5CAA.svg)](https://www.meilisearch.com/)
[![OpenRouter](https://img.shields.io/badge/AI-OpenRouter%20%2F%20Swappable%20LLM-7C3AED.svg)](https://openrouter.ai/)
[![TailwindCSS](https://img.shields.io/badge/Styling-TailwindCSS%203-38B2AC.svg)](https://tailwindcss.com/)

---

## 📖 Table of Contents
- [Executive Overview](#-executive-overview)
- [Key Pillars & Capabilities](#-key-pillars--capabilities)
  - [1. Typo-Tolerant Hybrid Search (<20ms)](#1-typo-tolerant-hybrid-search-20ms)
  - [2. Live Document Directory & Real-Time SSE Stream](#2-live-document-directory--real-time-sse-stream)
  - [3. Temporal Version Diffing & Change Engine](#3-temporal-version-diffing--change-engine)
  - [4. "Ask Panopticon" Agentic RAG & Multi-Turn Chat](#4-ask-panopticon-agentic-rag--multi-turn-chat)
  - [5. Dual Swappable Auth & Zero-Setup Process Supervision](#5-dual-swappable-auth--zero-setup-process-supervision)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [API Reference](#-api-reference)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Frontend Setup](#2-frontend-setup)
  - [3. Running the Application](#3-running-the-application)
- [Security Model & Constraints](#-security-model--constraints)
- [License](#-license)

---

## 🌟 Executive Overview

In engineering and product organizations, critical specifications, RFCs, roadmap spreadsheets, and architecture blueprints are scattered across hundreds of Google Docs and Google Sheets across personal drives, Shared Drives, and nested folders.

Traditional Google Drive search struggles with strict substring matching, lack of typo tolerance for project codenames, slow query latency, and zero visibility into temporal changes ("what changed in doc X yesterday?").

**Panopticon Observatory** solves this with a **four-in-one local-first intelligence platform**:
1. **Instant Pointer Index:** Sub-20ms typo-tolerant search across titles, project tags, and content snippets without mirroring full documents.
2. **Live Catalog Directory:** Real-time browsable document library powered by Server-Sent Events (SSE) with live modification heartbeats.
3. **Temporal Diff Engine:** Git-style unified text diffs and AI-generated semantic change summaries for every revision.
4. **Autonomous Agentic RAG:** An interactive ReAct agent assistant with multi-tool reasoning, citation verification, and persistent multi-turn conversational threads.

```
       ┌────────────────────────────────────────────────────────┐
       │                   The User Query                       │
       │     e.g., "Falcon RFC", "What changed in Q3 roadmap?"  │
       └───────────────────────────┬────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌─────────────────────────────────┐       ┌───────────────────────────────────┐
│   TYPO-TOLERANT SEARCH ENGINE   │       │     AUTONOMOUS AGENTIC RAG        │
│ • Governed Drive Label Tags     │       │ • Multi-Step ReAct Tool Loop      │
│ • Exact & Fuzzy Title Matching  │       │ • Temporal Version Diff Analysis  │
│ • Content Snippet Fallbacks     │       │ • Verified Google Drive Citations │
│ • Sub-20ms Meilisearch Response │       │ • Real-Time Thought Chain Stream  │
└────────────────┬────────────────┘       └─────────────────┬─────────────────┘
                 │                                          │
                 └─────────────────────────┬────────────────┘
                                           ▼
       ┌────────────────────────────────────────────────────────┐
       │               Actionable Intelligence Layer            │
       │  • Direct "View in Google Drive" Deep Links            │
       │  • Interactive Version History & Split/Unified Diffs   │
       │  • One-Click Document Exports (PDF, DOCX, XLSX, CSV)   │
       │  • Multi-Turn Persistent Chat Threads in SQLite        │
       └────────────────────────────────────────────────────────┘
```

---

## ✨ Key Pillars & Capabilities

### 1. Typo-Tolerant Hybrid Search (<20ms)
- **Ultra-Low Latency:** Powered by local Meilisearch with custom ranking rules (`words > typo > proximity > attribute > sort > exactness`).
- **Match Attribution Intelligence:** Prioritizes governed Google Workspace Drive Labels (`[TAG:HIGH]`), elevates title matches (`[TITLE:HIGH]`), and provides extracted preview snippets (`[CONTENT:MEDIUM]`).
- **Interactive Term Highlighting:** Renders `<mark>` highlighted keywords across titles and snippet bodies.
- **Direct Export Menus:** One-click downloads for `PDF`, `DOCX`, `XLSX`, and `CSV` directly from Google Drive export endpoints.
- **Keyboard Productivity:** Press `/` or `Cmd/Ctrl + K` to focus the search bar, and `Escape` to clear.

### 2. Live Document Directory & Real-Time SSE Stream
- **Dual Display Modes:** Seamless toggle between visual **Card Grid** and compact **Dense Table** view.
- **Real-Time Reactive Streaming:** Asynchronous in-memory `SyncEventBus` streaming live events (`file_created`, `file_modified`, `file_deleted`, `sync_completed`) via Server-Sent Events (`GET /api/events/live`).
- **Live Edit Heartbeats:** Documents update positions smoothly in the UI with relative timestamps ("Modified 3m ago by Sarah") and animated change indicators without page reloads.
- **Automated Background Sync:** Background worker with sliding overlap safety buffer, high-watermark delta polling, and ghost-entry purging.

### 3. Temporal Version Diffing & Change Engine
- **Git-Style Unified Text Diffs:** Content-addressable SHA-256 snapshotting with line-by-line delta computation (`difflib.unified_diff`), tracking exact lines added and lines removed.
- **Resilient Google Docs Normalization:** Line-ending and paragraph delimiter normalization that handles prose documents and spreadsheets with identical precision.
- **AI-Powered Semantic Change Summarizer:** Leverages OpenRouter / LLM to produce concise, 1-2 sentence human-readable change summaries per revision with fallback heuristic digests (`+15 lines added by Alex`).
- **Multi-Model Reasoning Guardrails:** Strict prompt sandboxing and regex stripping of internal scratchpad tokens (`<think>`, `<thought>`, `Thinking Process:`) from reasoning models (Nemotron, DeepSeek, Qwen).
- **Interactive Diff Viewer Modal:** Accessible slide-over diff inspector rendering color-coded additions, deletions, and chronological version history.

### 4. "Ask Panopticon" Agentic RAG & Multi-Turn Chat
- **Autonomous Tool-Calling Reasoning Loop:** ReAct agent (`AgentEngine`) dynamically orchestrates 4 specialized domain tools:
  1. `search_index(query, filters)`: Fast keyword, tag, and metadata search over Meilisearch.
  2. `get_document_diff(file_id, version)`: Temporal change log analysis ("What changed last week?").
  3. `get_file_metadata(file_id)`: Document ownership, sharing status, and timestamps.
  4. `semantic_chunk_search(query, limit)`: Dense vector chunk retrieval via local embeddings.
- **Streaming Thought Chains & Badges:** SSE endpoint (`POST /api/agent/query/stream`) streams real-time execution steps (`step_start`, `tool_call`, `tool_result`, `token`, `citations`, `done`) rendering collapsible thought accordions and tool activity badges.
- **Hallucination Guardrail & Grounded Citations:** `CitationVerifier` cross-checks every cited document against real SQLite records, appending verified Google Drive URLs, confidence scores, and preview excerpts.
- **Multi-Turn Persistent Sessions (RFC-0002):** SQLite-backed conversation threads (`agent_threads`, `agent_messages`) with automatic context compaction and a slide-over thread history drawer.
- **Swappable LLM Seam:** Hot-configurable support for OpenRouter models (Nemotron Ultra, Claude 3.5 Sonnet, Gemini 2.0 Flash, GPT-4o, DeepSeek) or custom OpenAI-compatible endpoints via `.env` or in-UI Settings.

### 5. Dual Swappable Auth & Zero-Setup Process Supervision
- **Dual Authentication Seam:**
  - **Personal OAuth 2.0:** Installed-app browser consent flow with automatic refresh token persistence (`credentials.json` + `token.json`).
  - **Domain-Wide Delegation (DWD):** Service account with user email impersonation for company-wide deployments.
  - Hot-switch between auth modes from the UI Settings Drawer without restarting the backend.
- **Zero-Setup Process Supervision:** FastAPI startup lifespan auto-detects, auto-downloads (if missing), spawns, and supervises the local `meilisearch` child process, with clean termination on shutdown.

---

## 🏛️ System Architecture

```mermaid
graph TD
    subgraph Client ["Frontend Layer — React 19 + TypeScript + Vite (Port 5173)"]
        UI_Search["Search Hub\n(Typo-Tolerant Cards)"]
        UI_Dir["Document Directory\n(Dense Table / Grid)"]
        UI_Diff["Diff Viewer Modal\n(Syntax Highlighted Patches)"]
        UI_Agent["Ask Panopticon\n(Streaming Agentic Chat Drawer)"]
        UI_Threads["Thread History Sidebar\n(Multi-Turn Sessions)"]
    end

    subgraph API ["Backend API Layer — FastAPI (Port 8000)"]
        FastAPIApp["FastAPI Core Application"]
        EventBus["SyncEventBus\n(In-Memory Pub/Sub)"]
        Supervisor["EngineSupervisor\n(Auto-binary spawn/health/kill)"]
        SyncManager["SyncManager\n(Background Delta Worker)"]
    end

    subgraph AgentSystem ["Agentic RAG Subsystem"]
        AgentEngine["AgentEngine\n(ReAct Reasoning Loop)"]
        LLMClient["LLMClient\n(OpenRouter / OpenAI-Compatible)"]
        CitationVerifier["CitationVerifier\n(Zero-Hallucination Guard)"]
        
        subgraph AgentTools ["Agent Domain Tools"]
            T_Search["search_index"]
            T_Diff["get_document_diff"]
            T_Meta["get_file_metadata"]
            T_Vector["semantic_chunk_search"]
        end
    end

    subgraph Ingestion ["Ingestion, Diffing & Chunking Pipeline"]
        Crawler["GoogleDriveCrawler\n(My Drive + Shared Drives)"]
        Exporter["ContentExporter\n(10MB Cap Safe)"]
        DiffEngine["DiffEngine\n(Unified Git-Style Patches)"]
        Summarizer["ChangeSummarizer\n(AI Summaries + Guardrails)"]
        Chunker["TextChunker & LocalEmbedder\n(FastEmbed / Vectors)"]
    end

    subgraph Persistence ["Persistence & Search Indices"]
        SQLite_DB[("SQLite Database (WAL Mode)\n• file_records\n• document_versions\n• document_diffs\n• agent_threads\n• agent_messages")]
        Meili_Index[("Meilisearch Engine (Port 7700)\n• Typo-Tolerant Index\n• Custom Ranking Rules")]
    end

    subgraph External ["External Services"]
        GoogleDrive["Google Drive API v3\n& Drive Labels API"]
        OpenRouterAPI["OpenRouter / LLM Providers\n(Nemotron, Gemini, Claude)"]
    end

    %% Client to API
    UI_Search -->|GET /api/search| FastAPIApp
    UI_Dir -->|GET /api/documents| FastAPIApp
    UI_Dir -.->|SSE GET /api/events/live| EventBus
    UI_Diff -->|GET /api/documents/{id}/diffs| FastAPIApp
    UI_Agent -->|SSE POST /api/agent/query/stream| FastAPIApp
    UI_Threads -->|CRUD /api/agent/threads| FastAPIApp

    %% API Internals
    FastAPIApp --> Supervisor
    Supervisor -.->|Manages Process| Meili_Index
    FastAPIApp --> SyncManager
    SyncManager --> EventBus

    %% Agent Flow
    FastAPIApp --> AgentEngine
    AgentEngine --> LLMClient
    LLMClient <-->|REST Completions| OpenRouterAPI
    AgentEngine --> AgentTools
    AgentEngine --> CitationVerifier
    CitationVerifier --> SQLite_DB
    AgentTools --> Meili_Index
    AgentTools --> SQLite_DB

    %% Ingestion Flow
    SyncManager --> Crawler
    Crawler --> GoogleDrive
    Crawler --> Exporter
    Exporter --> DiffEngine
    DiffEngine --> Summarizer
    Summarizer --> OpenRouterAPI
    DiffEngine --> SQLite_DB
    Exporter --> Chunker
    Chunker --> SQLite_DB
    SyncManager -->|Upsert Docs| Meili_Index
```

---

## 💻 Tech Stack

| Domain | Technology | Purpose |
|---|---|---|
| **Backend API** | Python 3.12, FastAPI, Pydantic v2, Uvicorn | High-performance asynchronous API, lifespan management, SSE streaming |
| **Search Engine** | Meilisearch (supervised standalone binary), Meilisearch SDK | Typo-tolerant indexing, sub-20ms latency, custom ranking rules |
| **Agentic RAG & AI** | OpenRouter API / OpenAI Client, ReAct Agent Engine | Autonomous multi-tool reasoning, semantic diff summaries, thought-chain streaming |
| **Persistence** | SQLite 3 (WAL Journal Mode, ACID transactions) | Metadata, version history, Git-style diffs, and multi-turn chat threads |
| **Diffing & Embeddings** | Python `difflib`, `fastembed` (ONNX runtime) | Unified line diff computation and fast local vector embeddings without GPU |
| **Google Cloud** | Drive API v3, Drive Labels API, Google Auth OAuthlib | Document crawling, label metadata extraction, and dual OAuth/DWD auth |
| **Frontend Dashboard** | React 19, TypeScript, Vite 6, Tailwind CSS 3 | Real-time reactive dashboard, design tokens, SSE subscriptions, diff viewer |

---

## 🔌 API Reference

### Search & Directory
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/search?q={query}` | Typo-tolerant keyword & label search with match attribution |
| `GET` | `/api/documents` | Paginated catalog with sorting (`modified_time:desc`) and facet filtering |
| `GET` | `/api/documents/{file_id}/versions` | Chronological version history for a specific document |
| `GET` | `/api/documents/{file_id}/diffs/{version}` | Structured Git-style unified diff patch and AI summary |

### Real-Time Streaming & Sync
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/events/live` | **Server-Sent Events (SSE)** stream of live file changes and sync progress |
| `POST` | `/api/sync/trigger` | Trigger an immediate manual incremental crawl run |
| `GET` | `/api/sync/status` | Current sync state, watermark timestamp, and statistics |

### "Ask Panopticon" Agent & Multi-Turn Threads
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/agent/query` | Standard synchronous agent question answering |
| `POST` | `/api/agent/query/stream` | **SSE streaming endpoint** emitting thought chain, tool badges, and tokens |
| `GET` | `/api/agent/threads` | List all saved conversational chat sessions |
| `POST` | `/api/agent/threads` | Create a new isolated conversation thread |
| `GET` | `/api/agent/threads/{thread_id}/messages` | Fetch complete chat history for a session |
| `DELETE` | `/api/agent/threads/{thread_id}` | Delete a chat thread and all associated messages |

### Configuration & Health
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Comprehensive health check (FastAPI, SQLite, Meilisearch) |
| `GET` | `/api/auth/status` | Current Google Drive authentication status and provider mode |
| `POST` | `/api/auth/switch` | Hot-switch between `oauth` and `service_account` modes |
| `GET` | `/api/settings/llm` | Active LLM provider configuration and model selection |
| `POST` | `/api/settings/llm` | Update OpenRouter API key and model without restarting |

---

## 🚀 Getting Started

### Prerequisites
- **Python:** 3.10 or higher (Python 3.12 recommended)
- **Node.js:** 18 or higher (with npm)
- **Google Cloud Project:** Enabled Google Drive API & Drive Labels API (with `credentials.json` for OAuth or `service_account.json` for DWD).
- **OpenRouter API Key (Optional):** For AI change summarization and Agentic RAG ([Get an OpenRouter key](https://openrouter.ai/keys)).

---

### 1. Backend Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Mubashar986/Panopticon.git
   cd Panopticon
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -e .
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` to configure your preferred settings:*
   ```ini
   DRIVE_AUTH_MODE=oauth
   GOOGLE_CLIENT_SECRETS_FILE=credentials.json
   
   # Optional: OpenRouter key for AI Summaries and Agentic Chat
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   OPENROUTER_MODEL=nvidia/nemotron-3.5-lightning:free
   ```

---

### 2. Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install Node dependencies:**
   ```bash
   npm install
   ```

---

### 3. Running the Application

#### Terminal 1 — Start the Backend Server:
```bash
uvicorn app.api.app:app --host 127.0.0.1 --port 8000 --reload
```
*The FastAPI application lifespan will automatically verify, download (if absent), spawn, and manage the local `meilisearch` engine on port `7700`.*

#### Terminal 2 — Start the React Dashboard:
```bash
cd frontend
npm run dev
```

Open **`http://localhost:5173`** in your browser to access the **Panopticon Observatory**!

---

## 🛡️ Security Model & Constraints

1. **Zero Full-Content Mirroring:** Panopticon acts strictly as an intelligent pointer index. Full document contents are never mirrored or stored in Meilisearch or API responses.
2. **Local-First Search Execution:** Search queries execute purely against the local Meilisearch index in <20ms, completely detached from live Google Drive API rate limits.
3. **Verified Grounded Citations:** The Agentic RAG engine verifies every cited file and URL against local SQLite records to eliminate AI hallucinations.
4. **Credential Isolation:** OAuth tokens, refresh tokens, and LLM API keys are never exposed in client API responses or committed to version control.
5. **10MB Server-Side Cap Protection:** Google Drive exports exceeding the 10MB limit are gracefully flagged as `oversized_metadata_only`, preventing pipeline failures.
6. **Untrusted Input Sanitization:** All document titles, editor metadata, and extracted snippets are stripped of illegal control characters prior to database or index insertion.

---

## 📄 License

Panopticon is open-source software licensed under the [MIT License](LICENSE).
