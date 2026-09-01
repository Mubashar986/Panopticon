"""Integration tests for the Agentic RAG REST API (POST /api/agent/query)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.engine import AgentRunResult, AgentStepTrace
from app.api.app import create_app
from app.api.deps import get_crawl_storage_dep
from app.indexer.storage import CrawlStorage


@pytest.fixture
def client(tmp_path) -> TestClient:
    storage = CrawlStorage(db_path=tmp_path / "api_agent_test.db")
    app = create_app()
    app.dependency_overrides[get_crawl_storage_dep] = lambda: storage
    return TestClient(app)


def test_api_agent_query_endpoint(client: TestClient):
    """Verify POST /api/agent/query executes agent and returns structured response."""
    mock_run_result = AgentRunResult(
        answer="Based on records, Falcon's OAuth rate limit was updated to 120 rpm.",
        steps_taken=2,
        tools_used=["search_index", "get_document_diff"],
        trace=[
            AgentStepTrace(
                step=1,
                tool_name="search_index",
                arguments={"query": "Falcon"},
                output_summary='{"results_count": 1}',
            ),
            AgentStepTrace(
                step=2,
                tool_name="get_document_diff",
                arguments={"file_id": "doc_falcon_01"},
                output_summary='{"diffs": [{"version_id": 2}]}',
            ),
        ],
        model="minimax/minimax-m3:free",
        latency_ms=45.2,
    )

    with patch.object(
        AgentRunResult, "model_validate", return_value=mock_run_result
    ), patch(
        "app.agent.engine.AgenticReasoningEngine.run",
        return_value=mock_run_result,
    ):
        payload = {
            "query": "What changed in Falcon?",
            "model": "minimax/minimax-m3:free",
        }
        resp = client.post("/api/agent/query", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "Falcon's OAuth rate limit" in data["answer"]
        assert data["steps_taken"] == 2
        assert "search_index" in data["tools_used"]
        assert len(data["trace"]) == 2
        assert data["model"] == "minimax/minimax-m3:free"
        assert data["latency_ms"] == 45.2
