"""FastAPI route handlers for the Agentic RAG assistant."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent.citations import CitationVerifier
from app.agent.engine import AgenticReasoningEngine
from app.agent.tools import AgentToolContext
from app.api.deps import CrawlStorageDep
from app.api.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentStepTraceItem,
    VerifiedCitationItem,
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

    return AgentQueryResponse(
        answer=sanitized_answer,
        steps_taken=result.steps_taken,
        tools_used=result.tools_used,
        trace=trace_items,
        citations=citation_items,
        model=result.model,
        latency_ms=result.latency_ms,
    )
