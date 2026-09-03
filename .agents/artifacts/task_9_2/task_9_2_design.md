# Stage 2: Codebase Design — Task 9.2: Swappable LLM Client & Settings Configuration

**Task ID:** `9.2`  
**Task Title:** Build OpenRouter / Swappable LLM Client & Settings Configuration  
**Epic:** Epic 9 — Agentic RAG Intelligence & OpenRouter Provider Seam  
**Target Files:**
- `[NEW]` [`app/core/llm.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/core/llm.py)
- `[NEW]` [`app/api/schemas/llm.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/schemas/llm.py)
- `[NEW]` [`app/api/routes/settings.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/routes/settings.py)
- `[MODIFY]` [`app/api/router.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/router.py)
- `[NEW]` [`tests/test_llm_client.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/tests/test_llm_client.py)
- `[NEW]` [`tests/test_api_settings.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/tests/test_api_settings.py)
**Artifact Version:** 1.0.0  
**Status:** READY FOR IMPLEMENTATION  

---

## 1. Current State vs Target Architecture

### Current State
Panopticon has `OpenRouterSummarizer` in `app/indexer/summarizer.py`, which is a specialized 1-shot diff summarizer. It does not support multi-turn conversations, tool calling, schema-based argument deserialization, or dynamic runtime settings reconfiguration via REST endpoints.

### Target State
Task 9.2 introduces the general-purpose, pluggable `LLMClient` subsystem:
1. **`LLMClient` Protocol (`app/core/llm.py`)**: Universal OpenAI-compatible client supporting multi-turn chat, system prompts, temperature, and standard JSON **Tool Calling**.
2. **`OpenRouterClient`**: Production adapter connecting to OpenRouter, OpenAI, or local OpenAI-compatible daemons (Ollama/vLLM) via `httpx`.
3. **`MockLLMClient`**: Deterministic in-memory client for testing and offline CI execution without API keys.
4. **Dynamic Settings API (`app/api/routes/settings.py`)**:
   - `GET /api/settings/llm`: Return active configuration with masked API key.
   - `POST /api/settings/llm`: Update active model and credentials live in-memory.
   - `POST /api/settings/llm/test`: Probe credentials with a live 1-token round-trip.

---

## 2. File-Level Impact Analysis

### `[NEW]` [`app/core/llm.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/core/llm.py)
- Models:
  - `LLMMessage(role: str, content: str | None, name: str | None = None, tool_call_id: str | None = None, tool_calls: list[ToolCall] | None = None)`
  - `ToolDefinition(name: str, description: str, parameters: dict[str, Any])`
  - `ToolCall(id: str, name: str, arguments: dict[str, Any])`
  - `LLMResponse(content: str | None, tool_calls: list[ToolCall], model: str, finish_reason: str)`
- Protocol:
  - `LLMClient(Protocol)` with `complete()`, `test_connection()`, `model`, `base_url`.
- Implementation:
  - `OpenRouterClient(LLMClient)`: Real HTTP client with error mapping and retry timeouts.
  - `MockLLMClient(LLMClient)`: Configurable mock responses for testing.
  - Helper `mask_api_key(key: str | None) -> str | None`.

### `[NEW]` [`app/api/schemas/llm.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/schemas/llm.py)
- `LLMSettingsResponse`:
  - `model: str`
  - `base_url: str`
  - `has_api_key: bool`
  - `masked_api_key: str | None`
  - `recommended_models: list[str]`
- `LLMSettingsUpdate`:
  - `model: str | None = None`
  - `base_url: str | None = None`
  - `api_key: str | None = None`
- `LLMTestConnectionRequest`:
  - `model: str | None = None`
  - `api_key: str | None = None`
  - `base_url: str | None = None`
- `LLMTestConnectionResponse`:
  - `success: bool`
  - `latency_ms: float`
  - `message: str`
  - `model_tested: str`

### `[NEW]` [`app/api/routes/settings.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/routes/settings.py)
- `GET /api/settings/llm`
- `POST /api/settings/llm`
- `POST /api/settings/llm/test`

### `[MODIFY]` [`app/api/router.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/router.py)
- Include `settings.router` with prefix `""` and tag `settings`.

---

## 3. Regression Risk Matrix

| Risk ID | Risk Description | Severity | Affected Area | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **R-01** | Accidental API key exposure in REST response | 🔴 High | `settings.py` / `schemas/llm.py` | Strict Pydantic serialization through `mask_api_key()`. Never return raw key. |
| **R-02** | OpenRouter downtime during live health test | 🟢 Low | `POST /test` | Caught in try/except block; returns 200 OK with `success=False` and clear error description. |
| **R-03** | Malformed tool arguments JSON from LLM | 🟡 Med | `llm.py` | Wrapped in safe JSON deserializer falling back to empty dict or raw string. |

---

## 4. Rollback Plan

### If Changes Are Uncommitted:
```bash
git checkout -- app/api/router.py
rm app/core/llm.py app/api/schemas/llm.py app/api/routes/settings.py tests/test_llm_client.py tests/test_api_settings.py
```

### If Changes Are Committed:
```bash
git revert HEAD --no-edit
pytest tests/
```
