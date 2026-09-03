# ADR-0005: Selection of OpenRouter API with Rule-Based Fallback for AI Semantic Change Summarization

**Status:** Accepted  
**Date:** 2026-08-31  
**Decision Type:** ADR (Architecture Decision Record)  
**Authors:** Principal Systems Architect  
**Task Association:** Epic 8 / Task 8.3 — OpenRouter AI Semantic Change Summarizer & Epic 9 (Agentic Intelligence)  

---

## 1. Context & Problem Statement

Panopticon's temporal diff engine (Task 8.2) generates line-level unified diff patches (`@@ -line,count +line,count @@`) whenever a Google Doc or Google Sheet is modified between incremental sync cycles.

To make these changes instantly understandable in the React dashboard (Task 8.4) and searchable across document histories, Panopticon needs to generate a concise, human-readable 1-sentence summary of what changed (e.g. *"Alice added Section 2 defining OAuth 2.0 PKCE authentication flow and updated the rate limit threshold"*).

We must establish:
1. The AI/LLM integration strategy for calling external language models.
2. The zero-setup offline fallback guarantee (Constraint 6 & 11) when an `OPENROUTER_API_KEY` is not provided or when the user works completely offline.
3. Decoupling the LLM provider behind a swappable interface so that downstream consumers never call OpenRouter or vendor APIs directly.

---

## 2. Decision

We choose **OpenRouter API** via a lightweight `httpx`-based adapter, paired with a deterministic **Heuristic Fallback Summarizer** that operates when no API key is provided or when network errors occur.

### Key Architectural Commitments:

1. **Abstract `ChangeSummarizer` Interface:**
   - Define a domain protocol `ChangeSummarizer` with method `summarize_diff(patch_text: str, file_name: str, editor: str | None) -> str`.
   - Core indexer and sync code depends exclusively on `ChangeSummarizer`, never on raw OpenAI/Anthropic/OpenRouter SDKs (Constraint 7).

2. **Dual Implementation Strategy:**
   - **`OpenRouterSummarizer`**: Makes an authenticated JSON request to OpenRouter (`https://openrouter.ai/api/v1/chat/completions`) using a lightweight, cost-effective model (default `openai/gpt-4o-mini` or `anthropic/claude-3.5-haiku` / `meta-llama/llama-3.3-70b-instruct`) with a concise system prompt instructing the model to output a single plain-text sentence.
   - **`HeuristicSummarizer` (Zero-Setup Fallback)**: When `OPENROUTER_API_KEY` is missing or invalid, or when offline, parses the diff hunks to produce an accurate statistical summary (e.g. *"Updated 4 lines across 2 sections in 'Architecture.gdoc'"*).

3. **Circuit Breaker & Fallback Resilience:**
   - If OpenRouter returns 401 (invalid key), 429 (rate limit), or network timeout, the summarizer automatically falls back to `HeuristicSummarizer` and logs a warning without crashing the sync cycle (Constraint 5).

4. **Security & Privacy (Constraint 9):**
   - API keys are loaded strictly from `.env` or environment variables via `Settings.OPENROUTER_API_KEY`.
   - Keys are never logged, committed to Git, or exposed in API responses or SQLite search documents.

---

## 3. Evaluated Alternatives

### Option A: OpenRouter API + Heuristic Fallback (SELECTED)
- **Description:** Aggregator gateway supporting all major models (OpenAI, Anthropic, DeepSeek, Meta) through a unified OpenAI-compatible REST schema, with local rule-based fallback.
- **Score:** 85/85
- **Pros:** Model-agnostic; lowest cost routing; zero heavy SDK dependencies (standard `httpx`); guaranteed zero-setup local developer experience via automatic heuristic fallback.
- **Cons:** Requires internet access for LLM summaries (mitigated 100% by local fallback).

### Option B: Vendor-Specific SDKs (`openai`, `anthropic`, `google-generativeai`)
- **Description:** Direct Python SDK dependencies for each individual model vendor.
- **Score:** 62/85
- **Pros:** Native vendor features.
- **Cons:** Introduces multiple heavy third-party SDK dependencies; requires distinct auth formats; locks system to specific proprietary APIs.

### Option C: Local Ollama / llama.cpp Embedding & Completion Server
- **Description:** Run local quantized LLM (e.g. Llama 3 8B) on the user's workstation.
- **Score:** 68/85
- **Pros:** 100% local and offline.
- **Cons:** Requires heavy local GPU/RAM resources (4GB–8GB VRAM); complex developer setup on diverse OS environments. (Deferred as an optional swappable provider in Epic 9).

---

## 4. Consequences & Migration Impact

- **Positive:**
  - High-quality, context-aware 1-sentence change summaries when configured.
  - 100% operational offline with zero setup required.
  - Zero heavy vendor SDK dependencies added.
- **Negative / Risks:**
  - LLM response latency (~300ms–800ms) on API calls (handled via async/sync batching and background execution).

---

## 5. Compliance with Project Constraints

| Constraint | Compliance Status | Rationale |
|---|---|---|
| **Constraint 6 / 11** (Zero-Setup Guarantee) | ✅ PASS | Falls back to `HeuristicSummarizer` seamlessly when `OPENROUTER_API_KEY` is omitted. |
| **Constraint 7** (Vendor Isolation) | ✅ PASS | `ChangeSummarizer` protocol shields domain logic from OpenRouter HTTP specifics. |
| **Constraint 9** (No Secret Leakage) | ✅ PASS | API key is injected via `Settings` and never persisted to SQLite or search indices. |
