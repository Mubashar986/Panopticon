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
    thread_id: str | None = Field(default=None, description="Optional conversation thread identifier")
    model: str | None = Field(default=None, description="Optional override model ID")
    user_instructions: str | None = Field(
        default=None, description="Optional custom guidelines (e.g. 'Format in markdown table')"
    )


class AgentThreadItem(BaseModel):
    """Wire representation of a conversation thread summary."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique thread identifier")
    title: str = Field(..., description="Title of the thread")
    model: str | None = Field(default=None, description="Model ID used in this thread")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 last update timestamp")
    message_count: int = Field(default=0, description="Total messages in thread")


class ChatMessageWireItem(BaseModel):
    """Wire representation of an individual message turn in a thread."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique message identifier")
    thread_id: str = Field(..., description="Parent thread identifier")
    role: str = Field(..., description="Message sender role ('user' | 'assistant')")
    content: str = Field(..., description="Message text content")
    trace: list[AgentStepTraceItem] = Field(
        default_factory=list, description="Execution trace of tool calls"
    )
    citations: list[VerifiedCitationItem] = Field(
        default_factory=list, description="Verified document citations"
    )
    model: str | None = Field(default=None, description="Model ID used")
    latency_ms: float | None = Field(default=None, description="Execution latency in ms")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")


class AgentThreadDetail(BaseModel):
    """Wire representation of a thread including full message history."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique thread identifier")
    title: str = Field(..., description="Title of the thread")
    model: str | None = Field(default=None, description="Model ID used in this thread")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 last update timestamp")
    message_count: int = Field(default=0, description="Total messages in thread")
    messages: list[ChatMessageWireItem] = Field(
        default_factory=list, description="Chronological message list"
    )


class CreateThreadRequest(BaseModel):
    """Request payload to create a new thread."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, description="Optional title for thread")
    model: str | None = Field(default=None, description="Optional model for thread")


class UpdateThreadRequest(BaseModel):
    """Request payload to update a thread's title."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., min_length=1, max_length=200, description="Updated thread title")


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
