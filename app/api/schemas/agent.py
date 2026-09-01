"""Pydantic wire contracts for the Agentic RAG API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentStepTraceItem(BaseModel):
    """Wire representation of an executed tool call."""

    model_config = ConfigDict(frozen=True)

    step: int = Field(..., description="Execution turn number")
    tool_name: str = Field(..., description="Target tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments sent to tool")
    output_summary: str = Field(..., description="Truncated preview of output")


class AgentQueryRequest(BaseModel):
    """Incoming user request for agentic reasoning."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., min_length=1, description="Question or task for the agent to investigate")
    model: str | None = Field(default=None, description="Optional override model ID")
    user_instructions: str | None = Field(
        default=None, description="Optional custom guidelines (e.g. 'Format in markdown table')"
    )


class VerifiedCitationItem(BaseModel):
    """Wire representation of an authoritatively verified citation."""

    model_config = ConfigDict(frozen=True)

    file_id: str = Field(..., description="Google Drive unique file ID")
    document_name: str = Field(..., description="Canonical document title")
    web_view_link: str = Field(..., description="Authoritative Google Drive URL")
    mime_type: str = Field(default="application/vnd.google-apps.document", description="Document MIME type")
    matched_snippet: str | None = Field(default=None, description="Verified quote or excerpt from source text")
    confidence_score: float = Field(default=1.0, description="Groundedness confidence score (0.0 to 1.0)")
    verification_status: str = Field(default="verified", description="Grounding status ('verified' | 'unverified' | 'hallucination_flagged')")


class AgentQueryResponse(BaseModel):
    """Structured response from the Agentic Reasoning Engine."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(..., description="Natural language answer synthesized by the agent")
    steps_taken: int = Field(..., description="Total execution turns taken")
    tools_used: list[str] = Field(default_factory=list, description="List of unique tools executed")
    trace: list[AgentStepTraceItem] = Field(
        default_factory=list, description="Step-by-step reasoning and tool execution trace"
    )
    citations: list[VerifiedCitationItem] = Field(
        default_factory=list, description="Authoritatively verified document citations and Drive pointers"
    )
    model: str = Field(..., description="Model ID that generated the answer")
    latency_ms: float = Field(..., description="Execution duration in milliseconds")
