"""Integration and unit tests for Real-Time SSE Agent Streaming."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.engine import (
    AgentStreamEvent,
    AgenticReasoningEngine,
)
from app.agent.tools import AgentToolContext
from app.api.app import create_app
from app.api.deps import get_crawl_storage_dep
from app.core.llm import LLMResponse, MockLLMClient, ToolCall
from app.indexer.storage import CrawlStorage


@pytest.fixture
def client(tmp_path) -> TestClient:
    storage = CrawlStorage(db_path=tmp_path / "agent_streaming_test.db")
    app = create_app()
    app.dependency_overrides[get_crawl_storage_dep] = lambda: storage
    return TestClient(app)


def test_agent_stream_event_to_sse_format():
    """Verify AgentStreamEvent serializes to standard W3C text/event-stream syntax."""
    event = AgentStreamEvent(
        event_type="tool_call",
        data={"step": 1, "tool_name": "search_index", "arguments": {"query": "Falcon"}},
    )
    sse_text = event.to_sse()
    assert sse_text.startswith("event: tool_call\n")
    assert "data: " in sse_text
    assert sse_text.endswith("\n\n")

    # Parse back the data line
    data_str = sse_text.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert data["step"] == 1
    assert data["tool_name"] == "search_index"


def test_engine_run_stream_yields_expected_events(tmp_path):
    """Verify run_stream yields step_start, tool_call, tool_result, token, citations, and done."""
    storage = CrawlStorage(db_path=tmp_path / "engine_stream_test.db")
    context = AgentToolContext(
        storage=storage,
        search_service=MagicMock(),
        embedding_provider=MagicMock(),
    )

    mock_llm = MockLLMClient()
    mock_llm.complete = MagicMock()

    # Turn 1: Model requests search tool call
    mock_llm.complete.side_effect = [
        LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_001",
                    name="search_index",
                    arguments={"query": "Falcon"},
                )
            ],
            model="mock-llm",
        ),
        # Turn 2: Model synthesizes final answer
        LLMResponse(
            content="Falcon auth was upgraded to PKCE.",
            tool_calls=[],
            model="mock-llm",
        ),
    ]

    engine = AgenticReasoningEngine(llm_client=mock_llm, context=context, max_steps=3)
    events = list(engine.run_stream(query="What is Falcon?"))

    event_types = [e.event_type for e in events]
    assert "step_start" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "token" in event_types
    assert "citations" in event_types
    assert "done" in event_types

    done_event = next(e for e in events if e.event_type == "done")
    assert done_event.data["steps_taken"] == 2
    assert "search_index" in done_event.data["tools_used"]
    assert "Falcon auth was upgraded" in done_event.data["answer"]


def test_api_agent_streaming_endpoint(client: TestClient):
    """Verify POST /api/agent/query/stream establishes SSE stream and returns structured frames."""
    with patch(
        "app.agent.engine.AgenticReasoningEngine.run_stream",
        return_value=[
            AgentStreamEvent(event_type="step_start", data={"step": 1, "max_steps": 5}),
            AgentStreamEvent(
                event_type="tool_call",
                data={"step": 1, "tool_name": "search_index", "arguments": {"query": "Falcon"}},
            ),
            AgentStreamEvent(
                event_type="tool_result",
                data={"step": 1, "tool_name": "search_index", "output_summary": "1 hit"},
            ),
            AgentStreamEvent(event_type="token", data={"delta": "Falcon updated."}),
            AgentStreamEvent(event_type="citations", data={"citations": []}),
            AgentStreamEvent(
                event_type="done",
                data={
                    "answer": "Falcon updated.",
                    "steps_taken": 1,
                    "tools_used": ["search_index"],
                    "trace": [],
                    "citations": [],
                    "model": "mock-llm",
                    "latency_ms": 120.5,
                },
            ),
        ],
    ):
        resp = client.post(
            "/api/agent/query/stream",
            json={"query": "What changed?"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        content = resp.text
        assert "event: step_start" in content
        assert "event: tool_call" in content
        assert "event: tool_result" in content
        assert "event: token" in content
        assert "event: citations" in content
        assert "event: done" in content


def test_api_agent_streaming_empty_query(client: TestClient):
    """Verify empty query emits error SSE event."""
    resp = client.post(
        "/api/agent/query/stream",
        json={"query": "   "},
    )
    assert resp.status_code == 200
    assert "event: error" in resp.text
    assert "Please provide a valid question" in resp.text
