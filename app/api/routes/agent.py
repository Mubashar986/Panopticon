"""FastAPI route handlers for the Agentic RAG assistant and multi-turn threads."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.agent.citations import CitationVerifier
from app.agent.engine import AgentStreamEvent, AgenticReasoningEngine
from app.agent.tools import AgentToolContext
from app.api.deps import CrawlStorageDep
from app.api.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentStepTraceItem,
    AgentThreadDetail,
    AgentThreadItem,
    ChatMessageWireItem,
    CreateThreadRequest,
    UpdateThreadRequest,
    VerifiedCitationItem,
)
from app.core.llm import OpenRouterClient, get_llm_client, get_runtime_llm_config
from app.core.logging import get_logger
from app.indexer.embeddings import get_embedding_provider
from app.indexer.models import AgentMessage, AgentThread
from app.search.service import SearchService

logger = get_logger("panopticon.api.routes.agent")

router = APIRouter(prefix="/api/agent", tags=["Agentic Intelligence"])


def _message_to_wire(msg: AgentMessage) -> ChatMessageWireItem:
    """Project an internal AgentMessage entity into a wire DTO."""
    trace_items: list[AgentStepTraceItem] = []
    if msg.trace_json:
        try:
            raw_traces = json.loads(msg.trace_json)
            trace_items = [AgentStepTraceItem(**t) for t in raw_traces]
        except Exception:
            trace_items = []

    citation_items: list[VerifiedCitationItem] = []
    if msg.citations_json:
        try:
            raw_citations = json.loads(msg.citations_json)
            citation_items = [VerifiedCitationItem(**c) for c in raw_citations]
        except Exception:
            citation_items = []

    return ChatMessageWireItem(
        id=msg.id,
        thread_id=msg.thread_id,
        role=msg.role,
        content=msg.content,
        trace=trace_items,
        citations=citation_items,
        model=msg.model,
        latency_ms=msg.latency_ms,
        created_at=msg.created_at.isoformat(),
    )


# -------------------------------------------------------------------------
# Thread Management Endpoints (Task 9.8 / RFC-0002)
# -------------------------------------------------------------------------


@router.get("/threads", response_model=list[AgentThreadItem])
def list_threads(
    storage: CrawlStorageDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AgentThreadItem]:
    """List all persisted conversation threads ordered by last activity descending."""
    threads = storage.list_threads(limit=limit, offset=offset)
    return [
        AgentThreadItem(
            id=t.id,
            title=t.title,
            model=t.model,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
            message_count=t.message_count,
        )
        for t in threads
    ]


@router.post("/threads", response_model=AgentThreadItem, status_code=201)
def create_thread(
    payload: CreateThreadRequest,
    storage: CrawlStorageDep,
) -> AgentThreadItem:
    """Create a new conversation thread."""
    title = payload.title.strip() if payload.title else "New Conversation"
    thread = storage.create_thread(title=title, model=payload.model)
    return AgentThreadItem(
        id=thread.id,
        title=thread.title,
        model=thread.model,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
        message_count=0,
    )


@router.get("/threads/{thread_id}", response_model=AgentThreadDetail)
def get_thread(
    thread_id: str,
    storage: CrawlStorageDep,
) -> AgentThreadDetail:
    """Retrieve thread metadata and its chronological message history."""
    thread = storage.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation thread not found.")

    raw_messages = storage.get_thread_messages(thread_id)
    wire_messages = [_message_to_wire(m) for m in raw_messages]

    return AgentThreadDetail(
        id=thread.id,
        title=thread.title,
        model=thread.model,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
        message_count=len(wire_messages),
        messages=wire_messages,
    )


@router.patch("/threads/{thread_id}", response_model=AgentThreadItem)
def update_thread(
    thread_id: str,
    payload: UpdateThreadRequest,
    storage: CrawlStorageDep,
) -> AgentThreadItem:
    """Update a conversation thread's title."""
    updated = storage.update_thread_title(thread_id, payload.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation thread not found.")
    return AgentThreadItem(
        id=updated.id,
        title=updated.title,
        model=updated.model,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
        message_count=updated.message_count,
    )


@router.delete("/threads/{thread_id}")
def delete_thread(
    thread_id: str,
    storage: CrawlStorageDep,
) -> dict[str, str]:
    """Delete a conversation thread and all its messages."""
    deleted = storage.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation thread not found.")
    return {"status": "deleted", "id": thread_id}


# -------------------------------------------------------------------------
# Synchronous & Streaming Query Endpoints (Multi-Turn Capable)
# -------------------------------------------------------------------------


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(
    payload: AgentQueryRequest,
    storage: CrawlStorageDep,
) -> AgentQueryResponse:
    """Execute autonomous agentic reasoning over Panopticon's documents and change history."""
    logger.info("Agent query received: '%s' (thread_id: %s)", payload.query, payload.thread_id)

    # Determine LLM client
    if payload.model and payload.model.strip():
        cfg = get_runtime_llm_config()
        llm_client = OpenRouterClient(
            api_key=cfg.get("api_key") or "",
            model=payload.model.strip(),
            base_url=cfg.get("base_url") or "https://openrouter.ai/api/v1",
        )
    else:
        llm_client = get_llm_client()

    tool_context = AgentToolContext(
        storage=storage,
        search_service=SearchService(),
        embedding_provider=get_embedding_provider(),
    )

    engine = AgenticReasoningEngine(
        llm_client=llm_client,
        context=tool_context,
    )

    history: list[AgentMessage] = []
    if payload.thread_id:
        existing_thread = storage.get_thread(payload.thread_id)
        if not existing_thread:
            # Auto-create thread
            title = payload.query[:40].strip() or "New Conversation"
            storage.create_thread(title=title, model=payload.model, thread_id=payload.thread_id)
        else:
            history = storage.get_thread_messages(payload.thread_id)
            if existing_thread.title == "New Conversation" and len(history) == 0:
                storage.update_thread_title(payload.thread_id, payload.query[:40].strip() or "New Conversation")

        # Persist user message
        storage.save_message(
            AgentMessage(
                thread_id=payload.thread_id,
                role="user",
                content=payload.query.strip(),
                model=llm_client.model,
            )
        )

    result = engine.run(
        query=payload.query,
        user_instructions=payload.user_instructions,
        history=history,
    )

    # Execute Citation Verification & Hallucination Guardrail
    verifier = CitationVerifier()
    sanitized_answer, verified_citations = verifier.verify_and_sanitize(
        text=result.answer,
        trace=result.trace,
        storage=storage,
    )

    citation_items = [
        VerifiedCitationItem(
            file_id=c.file_id,
            document_name=c.document_name,
            web_view_link=c.web_view_link,
            mime_type=c.mime_type,
            matched_snippet=c.matched_snippet,
            confidence_score=c.confidence_score,
            verification_status=c.verification_status,
        )
        for c in verified_citations
    ]

    trace_items = [
        AgentStepTraceItem(
            step=t.step,
            tool_name=t.tool_name,
            arguments=t.arguments,
            output_summary=t.output_summary,
        )
        for t in result.trace
    ]

    # Persist assistant turn if in a thread
    if payload.thread_id:
        storage.save_message(
            AgentMessage(
                thread_id=payload.thread_id,
                role="assistant",
                content=sanitized_answer,
                trace_json=json.dumps([t.model_dump() for t in trace_items]),
                citations_json=json.dumps([c.model_dump() for c in citation_items]),
                model=result.model,
                latency_ms=result.latency_ms,
            )
        )

    return AgentQueryResponse(
        answer=sanitized_answer,
        steps_taken=result.steps_taken,
        tools_used=result.tools_used,
        trace=trace_items,
        citations=citation_items,
        model=result.model,
        latency_ms=result.latency_ms,
    )


@router.post(
    "/query/stream",
    response_class=StreamingResponse,
    summary="Execute Agentic Reasoning with Real-Time SSE Stream",
    description="Streams real-time step_start, tool_call, tool_result, token deltas, citations, and done events over text/event-stream.",
)
async def stream_agent_query(
    request: Request,
    payload: AgentQueryRequest,
    storage: CrawlStorageDep,
) -> StreamingResponse:
    """Stream real-time agent reasoning steps, tool activations, tokens, and verified citations."""
    logger.info("Streaming agent query received: '%s' (thread_id: %s)", payload.query, payload.thread_id)

    # Determine LLM client
    if payload.model and payload.model.strip():
        cfg = get_runtime_llm_config()
        llm_client = OpenRouterClient(
            api_key=cfg.get("api_key") or "",
            model=payload.model.strip(),
            base_url=cfg.get("base_url") or "https://openrouter.ai/api/v1",
        )
    else:
        llm_client = get_llm_client()

    tool_context = AgentToolContext(
        storage=storage,
        search_service=SearchService(),
        embedding_provider=get_embedding_provider(),
    )

    engine = AgenticReasoningEngine(
        llm_client=llm_client,
        context=tool_context,
    )

    history: list[AgentMessage] = []
    if payload.thread_id:
        existing_thread = storage.get_thread(payload.thread_id)
        if not existing_thread:
            # Auto-create thread
            title = payload.query[:40].strip() or "New Conversation"
            storage.create_thread(title=title, model=payload.model, thread_id=payload.thread_id)
        else:
            history = storage.get_thread_messages(payload.thread_id)
            if existing_thread.title == "New Conversation" and len(history) == 0:
                storage.update_thread_title(payload.thread_id, payload.query[:40].strip() or "New Conversation")

        # Persist user message turn
        storage.save_message(
            AgentMessage(
                thread_id=payload.thread_id,
                role="user",
                content=payload.query.strip(),
                model=llm_client.model,
            )
        )

    async def event_generator() -> AsyncIterator[str]:
        try:
            for event in engine.run_stream(
                query=payload.query,
                user_instructions=payload.user_instructions,
                history=history,
            ):
                if await request.is_disconnected():
                    logger.debug("Client disconnected during agent streaming; aborting.")
                    break

                # If thread_id is active and done event arrives, persist assistant message
                if payload.thread_id and event.event_type == "done":
                    done_data = event.data
                    storage.save_message(
                        AgentMessage(
                            thread_id=payload.thread_id,
                            role="assistant",
                            content=done_data.get("answer", ""),
                            trace_json=json.dumps(done_data.get("trace", [])),
                            citations_json=json.dumps(done_data.get("citations", [])),
                            model=done_data.get("model", llm_client.model),
                            latency_ms=done_data.get("latency_ms"),
                        )
                    )

                yield event.to_sse()
        except Exception as exc:
            logger.exception("Error in agent streaming generator: %s", exc)
            err_event = AgentStreamEvent(
                event_type="error",
                data={"error": f"Internal agent reasoning error: {exc}"},
            )
            yield err_event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
