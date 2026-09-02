"""Unit and integration tests for multi-turn chat sessions, SQLite thread persistence & context compaction."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.agent.engine import AgenticReasoningEngine
from app.api.app import create_app
from app.api.deps import get_crawl_storage_dep
from app.core.llm import LLMMessage, LLMResponse, ToolCall
from app.indexer.models import AgentMessage, AgentThread
from app.indexer.storage import CrawlStorage


class MockCompactionLLMClient:
    """Mock LLM client capturing messages received to verify context compaction."""

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self.model = "mock-compaction-model"
        self.recorded_messages: list[list[LLMMessage]] = []
        self.responses = responses or [
            LLMResponse(
                content="I have verified the information across the conversation.",
                tool_calls=[],
                model="mock-compaction-model",
            )
        ]
        self._call_count = 0

    def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        self.recorded_messages.append(list(messages))
        if self._call_count < len(self.responses):
            resp = self.responses[self._call_count]
            self._call_count += 1
            return resp
        return LLMResponse(
            content="Fallback answer.",
            tool_calls=[],
            model=self.model,
        )


@pytest.fixture
def temp_storage(tmp_path: Path) -> CrawlStorage:
    """Provide a fresh CrawlStorage in temporary directory."""
    db_file = tmp_path / "test_threads.db"
    return CrawlStorage(db_path=db_file)


@pytest.fixture
def test_client(temp_storage: CrawlStorage) -> TestClient:
    """FastAPI TestClient with overridden CrawlStorage dependency."""
    app = create_app()
    app.dependency_overrides[get_crawl_storage_dep] = lambda: temp_storage
    return TestClient(app)


# -------------------------------------------------------------------------
# Storage Layer Unit Tests
# -------------------------------------------------------------------------


def test_storage_thread_crud(temp_storage: CrawlStorage) -> None:
    """Verify creating, listing, getting, updating, and deleting threads."""
    # 1. Create thread
    t1 = temp_storage.create_thread(title="Project Falcon Investigation", model="gpt-4o")
    assert t1.id.startswith("th_")
    assert t1.title == "Project Falcon Investigation"
    assert t1.model == "gpt-4o"
    assert t1.message_count == 0

    # 2. Get thread
    fetched = temp_storage.get_thread(t1.id)
    assert fetched is not None
    assert fetched.id == t1.id
    assert fetched.title == t1.title

    # 3. Update thread title
    updated = temp_storage.update_thread_title(t1.id, "Falcon Auth Investigation")
    assert updated is not None
    assert updated.title == "Falcon Auth Investigation"

    # 4. List threads
    t2 = temp_storage.create_thread(title="SmartTrade Architecture")
    threads = temp_storage.list_threads()
    assert len(threads) == 2
    # Ordered by updated_at DESC
    assert threads[0].id == t2.id

    # 5. Delete thread
    deleted = temp_storage.delete_thread(t1.id)
    assert deleted is True
    assert temp_storage.get_thread(t1.id) is None
    assert len(temp_storage.list_threads()) == 1


def test_storage_message_persistence_and_cascade(temp_storage: CrawlStorage) -> None:
    """Verify persisting messages and cascaded deletion when thread is removed."""
    thread = temp_storage.create_thread(title="Multi-Turn Session")

    msg1 = AgentMessage(
        thread_id=thread.id,
        role="user",
        content="What is the database design?",
    )
    temp_storage.save_message(msg1)

    msg2 = AgentMessage(
        thread_id=thread.id,
        role="assistant",
        content="The database uses SQLite WAL mode.",
        trace_json=json.dumps([{"step": 1, "tool_name": "search_index"}]),
        citations_json=json.dumps([{"file_id": "f_1", "document_name": "DB Spec"}]),
        latency_ms=123.4,
    )
    temp_storage.save_message(msg2)

    # Fetch messages
    messages = temp_storage.get_thread_messages(thread.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is the database design?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "The database uses SQLite WAL mode."
    assert messages[1].latency_ms == 123.4

    # Check updated message count on thread
    t_fetched = temp_storage.get_thread(thread.id)
    assert t_fetched is not None
    assert t_fetched.message_count == 2

    # Delete thread -> verify messages are cascade deleted
    temp_storage.delete_thread(thread.id)
    assert len(temp_storage.get_thread_messages(thread.id)) == 0


# -------------------------------------------------------------------------
# Context Compaction & Pruning Unit Tests
# -------------------------------------------------------------------------


def test_engine_context_compaction(temp_storage: CrawlStorage) -> None:
    """Verify that prior conversation history is injected without raw tool outputs."""
    mock_llm = MockCompactionLLMClient()
    engine = AgenticReasoningEngine(llm_client=mock_llm, max_steps=3)

    # Prepare prior history with 2 turns (Turn 1 Q&A)
    history = [
        AgentMessage(
            thread_id="th_test",
            role="user",
            content="Who wrote the architecture document?",
        ),
        AgentMessage(
            thread_id="th_test",
            role="assistant",
            content="Alex Chen wrote the architecture document.",
            trace_json=json.dumps([{"step": 1, "tool_name": "search_index", "output": "2500 chars raw json"}]),
        ),
    ]

    result = engine.run(
        query="When did he write it?",
        history=history,
    )

    assert result.answer is not None
    assert len(mock_llm.recorded_messages) > 0
    first_turn_messages = mock_llm.recorded_messages[0]

    # Verify message sequence:
    # 0: system
    # 1: user (turn 1)
    # 2: assistant (turn 1)
    # 3: user (turn 2)
    assert first_turn_messages[0].role == "system"
    assert first_turn_messages[1].role == "user"
    assert first_turn_messages[1].content == "Who wrote the architecture document?"
    assert first_turn_messages[2].role == "assistant"
    assert first_turn_messages[2].content == "Alex Chen wrote the architecture document."
    assert first_turn_messages[3].role == "user"
    assert first_turn_messages[3].content == "When did he write it?"

    # Verify no raw tool JSON was injected into the prior assistant message
    assert "2500 chars raw json" not in first_turn_messages[2].content


# -------------------------------------------------------------------------
# REST API Integration Tests
# -------------------------------------------------------------------------


def test_api_threads_lifecycle(test_client: TestClient) -> None:
    """Test REST endpoints: list, create, get, patch, delete."""
    # List empty
    resp = test_client.get("/api/agent/threads")
    assert resp.status_code == 200
    assert resp.json() == []

    # Create thread
    resp = test_client.post("/api/agent/threads", json={"title": "Test Chat", "model": "nemotron"})
    assert resp.status_code == 201
    created = resp.json()
    thread_id = created["id"]
    assert created["title"] == "Test Chat"
    assert created["model"] == "nemotron"

    # Get thread detail
    resp = test_client.get(f"/api/agent/threads/{thread_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == thread_id
    assert detail["messages"] == []

    # Update thread title
    resp = test_client.patch(f"/api/agent/threads/{thread_id}", json={"title": "Renamed Chat"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed Chat"

    # Delete thread
    resp = test_client.delete(f"/api/agent/threads/{thread_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # 404 after delete
    resp = test_client.get(f"/api/agent/threads/{thread_id}")
    assert resp.status_code == 404


def test_api_query_with_thread_persistence(test_client: TestClient) -> None:
    """Test that POST /api/agent/query persists messages and thread state."""
    # Run query with thread_id
    resp = test_client.post(
        "/api/agent/query",
        json={"query": "List all security architecture docs", "thread_id": "th_integration_test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data

    # Verify thread was auto-created and has 2 messages (user + assistant)
    detail_resp = test_client.get("/api/agent/threads/th_integration_test")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][0]["content"] == "List all security architecture docs"
    assert detail["messages"][1]["role"] == "assistant"


def test_api_stream_with_thread_persistence(test_client: TestClient) -> None:
    """Test that POST /api/agent/query/stream persists user and assistant messages."""
    resp = test_client.post(
        "/api/agent/query/stream",
        json={"query": "What is the project roadmap?", "thread_id": "th_stream_test"},
    )
    assert resp.status_code == 200
    # Consume the SSE stream
    content = resp.text
    assert "event: done" in content

    # Verify thread and messages persisted
    detail_resp = test_client.get("/api/agent/threads/th_stream_test")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][0]["content"] == "What is the project roadmap?"
    assert detail["messages"][1]["role"] == "assistant"
    assert len(detail["messages"][1]["content"]) > 0
