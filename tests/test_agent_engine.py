"""Unit tests for the AgenticReasoningEngine loop and multi-step reasoning."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app.agent.engine import AgenticReasoningEngine
from app.agent.tools import AgentToolContext
from app.core.llm import LLMClient, LLMMessage, LLMResponse, ToolCall, ToolDefinition
from app.indexer.embeddings import DeterministicHashEmbeddingProvider
from app.indexer.models import DocumentDiff, DocumentVersion, DriveFileMetadata
from app.indexer.storage import CrawlStorage


class ScriptedMockLLMClient:
    """Mock LLM client that returns a pre-scripted sequence of responses."""

    def __init__(self, responses: list[LLMResponse], model: str = "mock-agent-model") -> None:
        self.responses = responses
        self._model = model
        self.call_count = 0
        self.received_messages: list[list[LLMMessage]] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return "mock://localhost"

    def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> LLMResponse:
        self.received_messages.append(messages)
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        # Default stop response if script exhausted
        return LLMResponse(
            content="Fallback answer: exhausted scripted steps.",
            tool_calls=[],
            model=self._model,
            finish_reason="stop",
        )

    def test_connection(self) -> tuple[bool, float, str]:
        return True, 1.0, "OK"


@pytest.fixture
def agent_storage(tmp_path: Path) -> CrawlStorage:
    storage = CrawlStorage(db_path=tmp_path / "agent_engine_test.db")
    doc = DriveFileMetadata(
        id="doc_falcon_01",
        name="Falcon Architecture",
        mime_type="application/vnd.google-apps.document",
        modified_time=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
        created_time=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        owners=["alice@company.com"],
        last_modifying_user="alice@company.com",
        shared=True,
        sharing_status="domain",
        project_tags=["Falcon"],
        content_snippet="Falcon architecture and auth rules.",
        export_status="success",
        web_view_link="https://docs.google.com/document/d/doc_falcon_01/edit",
        size_bytes=12000,
    )
    storage.upsert_files([doc])

    storage.save_version(
        DocumentVersion(
            id="ver_1",
            file_id="doc_falcon_01",
            version_number=1,
            content_hash="hash_v1",
            modified_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            snapshot_text="Falcon architecture v1",
        )
    )
    storage.save_version(
        DocumentVersion(
            id="ver_2",
            file_id="doc_falcon_01",
            version_number=2,
            content_hash="hash_v2",
            modified_time=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
            snapshot_text="Falcon architecture v2",
        )
    )

    diff = DocumentDiff(
        file_id="doc_falcon_01",
        from_version_id="ver_1",
        to_version_id="ver_2",
        lines_added=5,
        lines_removed=0,
        patch_text="+added rate limit 120",
        ai_summary="Added rate limiting rules.",
    )
    storage.save_diff(diff)
    return storage


@pytest.fixture
def agent_context(agent_storage: CrawlStorage) -> AgentToolContext:
    return AgentToolContext(
        storage=agent_storage,
        search_service=None,
        embedding_provider=DeterministicHashEmbeddingProvider(),
    )


def test_agent_empty_query(agent_context: AgentToolContext):
    """Verify engine handles empty query without error."""
    engine = AgenticReasoningEngine(
        llm_client=ScriptedMockLLMClient([]),
        context=agent_context,
    )
    result = engine.run("")
    assert result.steps_taken == 0
    assert "valid question" in result.answer


def test_agent_direct_answer(agent_context: AgentToolContext):
    """Verify engine returns direct answer when LLM needs no tools."""
    mock_client = ScriptedMockLLMClient([
        LLMResponse(
            content="Panopticon is a Google Docs and Sheets search and index dashboard.",
            tool_calls=[],
            model="mock-agent-model",
            finish_reason="stop",
        )
    ])
    engine = AgenticReasoningEngine(llm_client=mock_client, context=agent_context)
    result = engine.run("What is Panopticon?")

    assert result.steps_taken == 1
    assert len(result.tools_used) == 0
    assert "Panopticon is a Google Docs" in result.answer


def test_agent_single_tool_react_loop(agent_context: AgentToolContext):
    """Verify multi-turn loop: Turn 1 tool call -> Turn 2 synthesized answer."""
    mock_client = ScriptedMockLLMClient([
        # Turn 1: Request search_index
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="c1", name="search_index", arguments={"query": "Falcon"})],
            model="mock-agent-model",
            finish_reason="tool_calls",
        ),
        # Turn 2: Synthesize answer
        LLMResponse(
            content="Project Falcon was found in file 'doc_falcon_01' owned by alice@company.com.",
            tool_calls=[],
            model="mock-agent-model",
            finish_reason="stop",
        ),
    ])

    engine = AgenticReasoningEngine(llm_client=mock_client, context=agent_context)
    result = engine.run("Where is Falcon?")

    assert result.steps_taken == 2
    assert result.tools_used == ["search_index"]
    assert len(result.trace) == 1
    assert result.trace[0].tool_name == "search_index"
    assert "doc_falcon_01" in result.answer


def test_agent_multi_tool_chain(agent_context: AgentToolContext):
    """Verify multi-tool chain: search_index -> get_document_diff -> synthesis."""
    mock_client = ScriptedMockLLMClient([
        # Turn 1: Search for document
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="c1", name="search_index", arguments={"query": "Falcon"})],
            model="mock-agent-model",
            finish_reason="tool_calls",
        ),
        # Turn 2: Get diff for found file
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="c2", name="get_document_diff", arguments={"file_id": "doc_falcon_01"})],
            model="mock-agent-model",
            finish_reason="tool_calls",
        ),
        # Turn 3: Final answer
        LLMResponse(
            content="In 'Falcon Architecture' (doc_falcon_01), version 2 added rate limiting rules.",
            tool_calls=[],
            model="mock-agent-model",
            finish_reason="stop",
        ),
    ])

    engine = AgenticReasoningEngine(llm_client=mock_client, context=agent_context)
    result = engine.run("What changed in Falcon?")

    assert result.steps_taken == 3
    assert result.tools_used == ["search_index", "get_document_diff"]
    assert len(result.trace) == 2
    assert "doc_falcon_01" in result.answer
    assert "rate limiting rules" in result.answer


def test_agent_circuit_breaker_max_steps(agent_context: AgentToolContext):
    """Verify engine bounds execution to max_steps when model requests tools endlessly."""
    infinite_tool_responses = [
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id=f"c_{i}", name="search_index", arguments={"query": "loop"})],
            model="mock-agent-model",
            finish_reason="tool_calls",
        )
        for i in range(10)
    ]
    mock_client = ScriptedMockLLMClient(infinite_tool_responses)

    engine = AgenticReasoningEngine(
        llm_client=mock_client,
        context=agent_context,
        max_steps=4,
    )
    result = engine.run("Keep looping")

    assert result.steps_taken <= 4
    assert len(result.trace) <= 4
