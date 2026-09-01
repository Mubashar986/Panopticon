"""FastAPI route handlers for the Agentic RAG assistant."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent.engine import AgenticReasoningEngine
from app.agent.tools import AgentToolContext
from app.api.deps import CrawlStorageDep
from app.api.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentStepTraceItem,
)
from app.core.llm import OpenRouterClient, get_llm_client, get_runtime_llm_config
from app.core.logging import get_logger
from app.indexer.embeddings import get_embedding_provider
from app.search.service import SearchService

logger = get_logger("panopticon.api.routes.agent")

router = APIRouter(prefix="/api/agent", tags=["Agentic Intelligence"])


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(
    payload: AgentQueryRequest,
    storage: CrawlStorageDep,
) -> AgentQueryResponse:
    """Execute autonomous agentic reasoning over Panopticon's documents and change history."""
    logger.info("Agent query received: '%s'", payload.query)

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
        max_steps=5,
    )

    result = engine.run(
        query=payload.query,
        user_instructions=payload.user_instructions,
    )

    trace_items = [
        AgentStepTraceItem(
            step=t.step,
            tool_name=t.tool_name,
            arguments=t.arguments,
            output_summary=t.output_summary,
        )
        for t in result.trace
    ]

    return AgentQueryResponse(
        answer=result.answer,
        steps_taken=result.steps_taken,
        tools_used=result.tools_used,
        trace=trace_items,
        model=result.model,
        latency_ms=result.latency_ms,
    )
