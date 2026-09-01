"""Agentic Tool-Calling Reasoning Engine for Panopticon."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict, Field

from app.agent.tools import PANOPTICON_TOOLS, AgentToolContext, execute_tool
from app.core.llm import LLMClient, LLMMessage, get_llm_client
from app.core.logging import get_logger
from app.indexer.embeddings import get_embedding_provider
from app.indexer.storage import get_crawl_storage
from app.search.service import SearchService

logger = get_logger("panopticon.agent.engine")

PANOPTICON_SYSTEM_PROMPT = """You are Panopticon AI, an intelligent agentic assistant that answers user questions about internal documents, architecture designs, and version changes.

CRITICAL OPERATIONAL RULES:
1. GROUNDED FACTUALITY: You must NEVER invent or hallucinate document titles, version changes, owner emails, or URLs. Only state facts directly supported by the results of your tools.
2. TOOL USAGE: When the user asks a question, use your tools to look up the real facts:
   - Use `search_index` to find document IDs, titles, and owners.
   - Use `get_document_diff` when asked about changes, additions, deletions, or history.
   - Use `get_file_metadata` when asked about ownership, dates, or sharing status.
   - Use `semantic_chunk_search` when searching for conceptual paragraphs or specific technical clauses.
3. MULTI-STEP REASONING: If you don't know the document ID, search for the document first, then fetch its diff or chunks.
4. CITATION REQUIREMENT: In your final answer, explicitly reference the document name and file_id from which you derived your answer.
5. ADMIT LIMITATIONS: If tools return no results, clearly state that no matching records were found in Panopticon.
"""


class AgentStepTrace(BaseModel):
    """Execution record for a single tool call in the reasoning trace."""

    model_config = ConfigDict(frozen=True)

    step: int = Field(..., description="Step index (1-based)")
    tool_name: str = Field(..., description="Name of the tool invoked")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool")
    output_summary: str = Field(..., description="Truncated preview of the tool output")


class AgentRunResult(BaseModel):
    """Structured result returned by the Agentic Reasoning Engine."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(..., description="Final synthesized natural language answer")
    steps_taken: int = Field(..., description="Total execution turns in the loop")
    tools_used: list[str] = Field(default_factory=list, description="Unique tools executed")
    trace: list[AgentStepTrace] = Field(default_factory=list, description="Detailed reasoning trace")
    model: str = Field(..., description="LLM model used for reasoning")
    latency_ms: float = Field(..., description="Total execution time in milliseconds")


class AgentStreamEvent(BaseModel):
    """Structured event frame emitted over Server-Sent Events (SSE)."""

    model_config = ConfigDict(frozen=True)

    event_type: str = Field(..., description="Event name (step_start, tool_call, tool_result, token, citations, done, error)")
    data: dict[str, Any] = Field(default_factory=dict, description="JSON-serializable payload")

    def to_sse(self) -> str:
        """Format as standard W3C text/event-stream frame."""
        return f"event: {self.event_type}\ndata: {json.dumps(self.data)}\n\n"


class AgenticReasoningEngine:
    """Autonomous ReAct agent loop equipped with Panopticon tools and circuit breaker."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        context: AgentToolContext | None = None,
        max_steps: int = 5,
    ) -> None:
        self.llm_client = llm_client or get_llm_client()
        self.context = context or AgentToolContext(
            storage=get_crawl_storage(),
            search_service=SearchService(),
            embedding_provider=get_embedding_provider(),
        )
        self.max_steps = max_steps

    def run(self, query: str, user_instructions: str | None = None) -> AgentRunResult:
        """Execute the ReAct loop to answer user query autonomously."""
        start_time = time.perf_counter()
        clean_query = query.strip()
        if not clean_query:
            return AgentRunResult(
                answer="Please provide a valid question or query.",
                steps_taken=0,
                tools_used=[],
                trace=[],
                model=self.llm_client.model,
                latency_ms=0.0,
            )

        system_content = PANOPTICON_SYSTEM_PROMPT
        if user_instructions:
            system_content += f"\nADDITIONAL USER INSTRUCTIONS:\n{user_instructions.strip()}"

        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=clean_query),
        ]

        trace: list[AgentStepTrace] = []
        tools_used: list[str] = []
        final_answer: str | None = None
        step = 0

        while step < self.max_steps:
            step += 1
            logger.debug("Agent execution turn %d/%d", step, self.max_steps)

            # In the final allowed step, do not provide tools to force synthesis
            tools_param = PANOPTICON_TOOLS if step < self.max_steps else None

            response = self.llm_client.complete(
                messages=messages,
                tools=tools_param,
                temperature=0.1,
            )

            # Case 1: Model requested tool calls
            if response.tool_calls:
                # Record assistant message with tool calls
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                for tc in response.tool_calls:
                    tools_used.append(tc.name)
                    logger.info("Agent invoking tool '%s' with args: %s", tc.name, tc.arguments)

                    tool_output = execute_tool(tc.name, tc.arguments, self.context)
                    preview = tool_output[:300] + "..." if len(tool_output) > 300 else tool_output

                    trace.append(
                        AgentStepTrace(
                            step=step,
                            tool_name=tc.name,
                            arguments=tc.arguments,
                            output_summary=preview,
                        )
                    )

                    messages.append(
                        LLMMessage(
                            role="tool",
                            tool_call_id=tc.id,
                            content=tool_output,
                        )
                    )

                # If we've reached the step limit, inject a warning to force synthesis on the next turn
                if step >= self.max_steps - 1:
                    messages.append(
                        LLMMessage(
                            role="user",
                            content="Step limit reached. Please synthesize your final answer now based on the information gathered.",
                        )
                    )
                continue

            # Case 2: Model emitted a direct text answer
            if response.content:
                final_answer = response.content.strip()
                break

        # Fallback if loop terminated without content
        if not final_answer:
            final_answer = (
                "I examined the available records, but was unable to reach a conclusive answer within the step budget."
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Unique tool names preserving insertion order
        unique_tools = list(dict.fromkeys(tools_used))

        return AgentRunResult(
            answer=final_answer,
            steps_taken=step,
            tools_used=unique_tools,
            trace=trace,
            model=self.llm_client.model,
            latency_ms=round(latency_ms, 2),
        )

    def run_stream(
        self,
        query: str,
        user_instructions: str | None = None,
    ) -> Iterator[AgentStreamEvent]:
        """Execute the ReAct loop yielding real-time SSE stream events."""
        start_time = time.perf_counter()
        clean_query = query.strip()
        if not clean_query:
            yield AgentStreamEvent(
                event_type="error",
                data={"error": "Please provide a valid question or query."},
            )
            return

        system_content = PANOPTICON_SYSTEM_PROMPT
        if user_instructions:
            system_content += f"\nADDITIONAL USER INSTRUCTIONS:\n{user_instructions.strip()}"

        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=clean_query),
        ]

        trace: list[AgentStepTrace] = []
        tools_used: list[str] = []
        final_answer: str | None = None
        step = 0

        while step < self.max_steps:
            step += 1
            yield AgentStreamEvent(
                event_type="step_start",
                data={"step": step, "max_steps": self.max_steps},
            )

            # In the final allowed step, do not provide tools to force synthesis
            tools_param = PANOPTICON_TOOLS if step < self.max_steps else None

            response = self.llm_client.complete(
                messages=messages,
                tools=tools_param,
                temperature=0.1,
            )

            # Case 1: Model requested tool calls
            if response.tool_calls:
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                for tc in response.tool_calls:
                    tools_used.append(tc.name)
                    yield AgentStreamEvent(
                        event_type="tool_call",
                        data={
                            "step": step,
                            "tool_name": tc.name,
                            "arguments": tc.arguments,
                        },
                    )

                    tool_output = execute_tool(tc.name, tc.arguments, self.context)
                    preview = tool_output[:300] + "..." if len(tool_output) > 300 else tool_output

                    trace.append(
                        AgentStepTrace(
                            step=step,
                            tool_name=tc.name,
                            arguments=tc.arguments,
                            output_summary=preview,
                        )
                    )

                    yield AgentStreamEvent(
                        event_type="tool_result",
                        data={
                            "step": step,
                            "tool_name": tc.name,
                            "output_summary": preview,
                        },
                    )

                    messages.append(
                        LLMMessage(
                            role="tool",
                            tool_call_id=tc.id,
                            content=tool_output,
                        )
                    )

                if step >= self.max_steps - 1:
                    messages.append(
                        LLMMessage(
                            role="user",
                            content="Step limit reached. Please synthesize your final answer now based on the information gathered.",
                        )
                    )
                continue

            # Case 2: Model emitted a direct text answer
            if response.content:
                final_answer = response.content.strip()
                break

        if not final_answer:
            final_answer = (
                "I examined the available records, but was unable to reach a conclusive answer within the step budget."
            )

        # Run Citation Verification & Hallucination Guardrail
        from app.agent.citations import CitationVerifier

        verifier = CitationVerifier()
        sanitized_answer, verified_citations = verifier.verify_and_sanitize(
            text=final_answer,
            trace=trace,
            storage=self.context.storage,
        )

        # Stream the synthesized answer tokens
        words = re.split(r"(\s+)", sanitized_answer)
        chunk_buf: list[str] = []
        for w in words:
            chunk_buf.append(w)
            if len(chunk_buf) >= 4:
                yield AgentStreamEvent(
                    event_type="token",
                    data={"delta": "".join(chunk_buf)},
                )
                chunk_buf = []
        if chunk_buf:
            yield AgentStreamEvent(
                event_type="token",
                data={"delta": "".join(chunk_buf)},
            )

        # Emit verified citations
        yield AgentStreamEvent(
            event_type="citations",
            data={
                "citations": [c.model_dump() for c in verified_citations],
            },
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        unique_tools = list(dict.fromkeys(tools_used))

        # Emit completion event
        yield AgentStreamEvent(
            event_type="done",
            data={
                "answer": sanitized_answer,
                "steps_taken": step,
                "tools_used": unique_tools,
                "trace": [t.model_dump() for t in trace],
                "citations": [c.model_dump() for c in verified_citations],
                "model": self.llm_client.model,
                "latency_ms": round(latency_ms, 2),
            },
        )
