Here is the complete, comprehensive list of all constraints, limits, and ceilings currently enforced in the Panopticon architecture, followed by the definitive answer on whether what you experienced was an "agentic loop issue" or caused by something else.

Part 1: The Complete List of System Constraints & Limits
1. Agentic Reasoning Engine Constraints (app/agent/engine.py)
Maximum Reasoning Turns (max_steps): 5 turns maximum. The agent can execute at most 5 ReAct cycles (thought 
→
→ action 
→
→ observation) before it is forcibly stopped.
Forced Synthesis on Step 5: On turn 5 (step == self.max_steps), the engine explicitly sets tools_param = None. It completely revokes all tools to force the model to write an answer.
Context Accumulation: All prior tool calls and their JSON outputs remain in the prompt memory for all 5 turns. If tools return large payloads, prompt tokens compound rapidly.
2. LLM & Token Limits (app/core/llm.py & .env)
Maximum Output Tokens (max_tokens): 1,500 tokens per completion (hardcoded in complete() and run_stream()). Any answer longer than ~1,100 words will be cut off by finish_reason: "length".
Temperature: 0.1 (low temperature to minimize hallucination and enforce factual grounding).
Provider Rate Limits / Concurrency: OpenRouter free tiers (:free) enforce strict queries-per-minute (QPM) caps and queue concurrency limits. When saturated, they return HTTP 200/429 JSON payloads with an error envelope instead of choices.
3. Tool Output & Search Truncation Limits (app/agent/tools.py)
Global Tool Output Circuit Breaker (MAX_TOOL_OUTPUT_CHARS): 2,500 characters. Any tool execution whose JSON string exceeds 2,500 characters is sliced off with "... [Output truncated at 2500 chars]".
Semantic Chunk Search (semantic_chunk_search):
Hit Limit: Hardcoded to 
min
⁡
(
requested_limit
,
5
)
min(requested_limit,5) — maximum 5 chunks per search.
Chunk Character Cap: Each retrieved chunk is sliced to text[:800] — maximum 800 characters per chunk.
Maximum Text Delivered: 
5
×
800
 chars
=
4
,
000
 characters
5×800 chars=4,000 characters (
≈
1.5
≈1.5 pages of reading material total).
Index / Metadata Search (search_index):
Content Preview Snippet (content_snippet): First 500 characters only (DEFAULT_MAX_SNIPPET_CHARS = 500 in exporter.py). Any text appearing after the first 500 characters of a document is invisible to this tool.
SQLite Fallback Scan Limit: 50 files maximum (list_files(limit=50)). If Meilisearch fails, files 51–91 are not even inspected.
Document Diff Retrieval (get_document_diff):
Diff Count Limit: Hardcoded to 
min
⁡
(
requested_limit
,
3
)
min(requested_limit,3) — maximum 3 revision diffs.
Patch Length Cap: Each patch is sliced to patch_text[:1200] — maximum 1,200 characters per diff.
4. Ingestion, Crawling & Export Ceilings (app/indexer/)
Google Drive Export Payload Ceiling: 10 MB (MAX_EXPORT_BYTES = 10 * 1024 * 1024). Files exceeding 10MB degrade to metadata-only indexing.
Incremental Crawl Watermark: Queries Google Drive using modifiedTime > watermark. Files modified prior to the watermark timestamp are skipped completely.
Zero Historical Chunks: Chunks are only created during an active version export. Because chunking was introduced recently, any older document that has not been crawled via a full_refresh=True sync has zero chunks in SQLite.
Part 2: Was It an "Agentic Loop Issue" or Something Else?
It was NOT a pure agentic loop bug. It was a compounding interaction between three separate layers:


Layer 1: The Missing Data (SQLite)
   0 chunks existed for SmartTrade because it was never full-crawled after Task 9.1.
                           │
                           ▼
Layer 2: The Model's Refusal to Hallucinate (Nemotron)
   Nemotron searched for chunks in Steps 3 & 4. Getting 0 chunks, it refused
   to invent fake proposals and wanted to search again.
                           │
                           ▼
Layer 3: The Engine's Abrupt Tool Revocation (Step 5)
   The engine reached step 5 and abruptly stripped tools (tools=None) without
   instructing the model. Nemotron, still trying to search, emitted raw XML:
   <tool_call> <function=semantic_chunk_search> ... </tool_call>
Why Changing the Model Didn't Fix It
When you switched from MiniMax to Nemotron, the data in the database was still missing (0 chunks for SmartTrade).
Both models were placed in the same impossible situation:
The user asked "what does SmartTrade propose?".
The model found the 7 document titles.
The model called semantic_chunk_search to read the proposal text.
The database returned nothing.
The model tried rephrasing the query on turn 4 
→
→ still nothing.
On turn 5, the engine revoked the tools.
MiniMax either timed out or errored out on parameter parsing, while Nemotron stubbornly tried to output the tool call as raw text because it refused to answer without evidence.
Why the 'choices' Error Happened Afterwards
When you asked the follow-up question, the request went to OpenRouter's free endpoint (nemotron-3-ultra:free).
The free provider was temporarily overloaded and returned a rate-limit error JSON payload ({"error": {"message": "...", "code": 429}}).
Because the code accessed data["choices"][0] without checking for "error", Python threw KeyError: 'choices'.
Summary
The system did not get stuck because the ReAct loop logic was broken; the agent was searching for text that literally did not exist in the database, ran out of turns (5-turn limit), had its tools abruptly revoked, and the free provider simultaneously hit a rate-limit ceiling.




Side Question: make sthe limit of those harccoded limits tell me we can test differeccnt size of those

Here is the breakdown of the **exact hardcoded limits** in our codebase, where they live, how we make them dynamic, and how we can benchmark and test different sizes.

---

### 1. The 7 Hardcoded Limits Currently in the System

| Limit | Location | Current Hardcoded Value | What It Restricts |
| :--- | :--- | :--- | :--- |
| **Tool Output Buffer** | `app/agent/tools.py:L17` | `MAX_TOOL_OUTPUT_CHARS = 2500` | Slices search and diff payloads after ~3-4 documents. |
| **Max Chunks Retrieved** | `app/agent/tools.py:L268` | `limit = min(int(args.get("limit", 3)), 5)` | Hard ceiling of at most 5 chunks per semantic query. |
| **Chunk Text Slicing** | `app/agent/tools.py:L287` | `c.text[:800]` | Cuts each chunk down to 800 characters (even though 1,500 chars are stored). |
| **Diff Patch Truncation** | `app/agent/tools.py:L234` | `d.patch_text[:1200]` | Cuts diffs down to 1,200 characters. |
| **ReAct Max Turns** | `app/agent/engine.py:L48` | `max_steps: int = 5` | Forces tool shutdown at step 5. |
| **LLM Output Tokens** | `app/core/llm.py:L158` | `max_tokens: int = 1500` | Limits generation to 1,500 tokens ($\approx 1,100$ words). |
| **Document Snippet Size** | `app/indexer/exporter.py` | `max_snippet_chars: int = 500` | Only indexes first 500 chars for keyword search. |

---

### 2. How We Make Them Configurable (Zero Hardcoding)

Instead of hardcoded constants, we move them into **`Settings` in `app/core/config.py`** and allow dynamic per-request overrides:

#### Step A: Expose in Environment & Settings (`app/core/config.py`)
```python
class Settings(BaseSettings):
    # Agent Retrieval & Buffer Tuning
    AGENT_MAX_TOOL_OUTPUT_CHARS: int = 10000       # Expand from 2,500 to 10,000+
    AGENT_MAX_CHUNKS_LIMIT: int = 15               # Expand from 5 to 15
    AGENT_CHUNK_SNIPPET_CHARS: int = 1500          # Full chunk size (no slicing)
    AGENT_DIFF_SNIPPET_CHARS: int = 4000           # Expand from 1,200 to 4,000
    AGENT_MAX_REASONING_STEPS: int = 8             # Expand from 5 to 8 turns
    AGENT_LLM_MAX_TOKENS: int = 3000               # Expand from 1,500 to 3,000 tokens
```

#### Step B: Allow Per-Query Overrides (`POST /api/agent/query/stream`)
Allow passing overrides directly in the request body so the UI or a benchmark script can test different sizes on the fly:
```json
{
  "query": "Compare all SmartTrade technical requirements",
  "tuning": {
    "max_chunks": 12,
    "max_steps": 7,
    "max_tool_chars": 15000,
    "max_tokens": 2500
  }
}
```

---

### 3. How to Test & Benchmark Different Sizes

To find the optimal balance between **retrieval completeness**, **latency**, and **LLM context costs**, test across 3 size profiles:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ PROFILE 1: Conservative (Current State)                                                     │
│ • Chunks: 5 (800 chars each = ~4k chars)                                                    │
│ • Max Tool Output: 2,500 chars | Max Steps: 5 | Max Tokens: 1,500                          │
│ • Pros: Ultra-fast (~3s), lowest token cost                                                 │
│ • Cons: Misses documents 4–10, cannot answer complete multi-document queries                │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ PROFILE 2: Balanced Production (Recommended)                                                │
│ • Chunks: 12 (1,500 chars each = ~18k chars)                                                │
│ • Max Tool Output: 10,000 chars | Max Steps: 7 | Max Tokens: 2,500                         │
│ • Pros: Captures all 10 SmartTrade docs, deep paragraph context, ~6-8s streaming            │
│ • Cons: Moderate token usage                                                                │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ PROFILE 3: Deep Research / Exhaustive Audit                                                 │
│ • Chunks: 25 (1,500 chars each = ~37.5k chars)                                              │
│ • Max Tool Output: 25,000 chars | Max Steps: 10 | Max Tokens: 4,000                        │
│ • Pros: Complete whole-document syntheses, full technical diff comparisons                  │
│ • Cons: Higher latency (~12-18s), requires models with 64k+ context windows                │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Verification Testing Script:
You can test these sizes by running a parameterized script or curl command against `POST /api/agent/query`:
* Test at `max_chunks = 5` $\rightarrow$ Check if SmartTrade proposal details are truncated.
* Test at `max_chunks = 12` and `max_tool_chars = 12000` $\rightarrow$ Confirm that all 10 document hits fit in the tool buffer and the model cites sections across the entire catalog without truncation.