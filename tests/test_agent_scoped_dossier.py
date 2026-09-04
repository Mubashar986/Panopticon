"""Integration and unit tests for Project-Scoped RAG Rig & Tool Isolation ("Ask Dossier").

Covers:
- Scoped search_index tool queries restricting hits exclusively to dossier members.
- Fast zero-result notice on empty dossiers without query failures.
- Permission boundaries on get_document_diff and get_file_metadata blocking cross-container access.
- Scoped semantic_chunk_search vector filtering and file_id validation.
- Dossier-isolated get_document_catalog_stats inventory metrics.
- AgenticReasoningEngine bounded system prompt injection and tool context propagation.
- FastAPI /api/agent/query and /api/agent/query/stream container validation and 404 handling.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.agent.engine import AgentRunResult, AgenticReasoningEngine
from app.agent.tools import AgentToolContext, execute_tool
from app.core.llm import LLMCompletionResponse, LLMMessage, LLMToolCall
from app.indexer.embeddings import DeterministicHashEmbeddingProvider
from app.indexer.models import (
    DocumentChunk,
    DocumentDiff,
    DocumentVersion,
    DriveFileMetadata,
    GOOGLE_DOC_MIME_TYPE,
)
from app.indexer.storage import CrawlStorage
from app.main import app


@pytest.fixture
def scoped_storage(tmp_path: Path) -> CrawlStorage:
    """Fixture providing a CrawlStorage populated with two distinct dossiers and items."""
    storage = CrawlStorage(db_path=tmp_path / "scoped_agent_test.db")

    # Document 1: Project Falcon
    doc1 = DriveFileMetadata(
        id="doc_falcon_01",
        name="Falcon Architecture Spec",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        created_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        modified_time=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
        owners=["falcon.lead@company.com"],
        last_modifying_user="alice@company.com",
        shared=True,
        sharing_status="domain",
        project_tags=["Falcon"],
        content_snippet="Falcon architecture spec details on PKCE OAuth.",
        web_view_link="https://docs.google.com/document/d/doc_falcon_01/view",
        size_bytes=12000,
    )

    # Document 2: Project Orion
    doc2 = DriveFileMetadata(
        id="doc_orion_01",
        name="Orion Quantum Computing Architecture",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        created_time=datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
        modified_time=datetime(2026, 8, 29, 11, 0, tzinfo=timezone.utc),
        owners=["orion.lead@company.com"],
        last_modifying_user="bob@company.com",
        shared=True,
        sharing_status="private",
        project_tags=["Orion"],
        content_snippet="Orion quantum algorithm benchmarks and qubit gates.",
        web_view_link="https://docs.google.com/document/d/doc_orion_01/view",
        size_bytes=18000,
    )
    storage.upsert_files([doc1, doc2])

    # Versions & Diffs for both docs
    storage.save_version(
        DocumentVersion(
            id="ver_f1",
            file_id="doc_falcon_01",
            version_number=1,
            content_hash="h_f1",
            modified_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            snapshot_text="Falcon initial",
        )
    )
    storage.save_diff(
        DocumentDiff(
            file_id="doc_falcon_01",
            from_version_id="ver_f1",
            to_version_id="ver_f1",
            lines_added=5,
            lines_removed=0,
            patch_text="+++ Falcon OAuth initialized",
            ai_summary="Falcon spec initialized",
        )
    )

    storage.save_version(
        DocumentVersion(
            id="ver_o1",
            file_id="doc_orion_01",
            version_number=1,
            content_hash="h_o1",
            modified_time=datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
            snapshot_text="Orion initial",
        )
    )
    storage.save_diff(
        DocumentDiff(
            file_id="doc_orion_01",
            from_version_id="ver_o1",
            to_version_id="ver_o1",
            lines_added=10,
            lines_removed=0,
            patch_text="+++ Orion Quantum Gates initialized",
            ai_summary="Orion spec initialized",
        )
    )

    # Chunks for both docs
    provider = DeterministicHashEmbeddingProvider()
    f_text = "Falcon OAuth PKCE auth flow authentication tokens."
    f_vec = provider.embed_query(f_text)
    storage.save_chunks([
        DocumentChunk(
            id="chk_f1",
            file_id="doc_falcon_01",
            version_id="ver_f1",
            chunk_index=0,
            section_heading="OAuth PKCE",
            content_text=f_text,
            char_start=0,
            char_end=len(f_text),
            embedding=f_vec,
        )
    ])

    o_text = "Orion Quantum Gates circuit simulation qubits."
    o_vec = provider.embed_query(o_text)
    storage.save_chunks([
        DocumentChunk(
            id="chk_o1",
            file_id="doc_orion_01",
            version_id="ver_o1",
            chunk_index=0,
            section_heading="Quantum Gates",
            content_text=o_text,
            char_start=0,
            char_end=len(o_text),
            embedding=o_vec,
        )
    ])

    # Create Dossier A (Falcon) with doc1
    dos_a = storage.create_dossier(
        name="Falcon Initiative",
        description="Falcon project files",
        color="#3B82F6",
        icon="folder",
        created_by="falcon.lead@company.com",
        initial_file_ids=["doc_falcon_01"],
    )

    # Create Dossier B (Orion) with doc2
    dos_b = storage.create_dossier(
        name="Orion Initiative",
        description="Orion quantum files",
        color="#8B5CF6",
        icon="atom",
        created_by="orion.lead@company.com",
        initial_file_ids=["doc_orion_01"],
    )

    # Create Dossier C (Empty)
    dos_c = storage.create_dossier(
        name="Empty Initiative",
        description="Container with zero documents",
        color="#64748B",
        icon="inbox",
        created_by="admin@company.com",
        initial_file_ids=[],
    )

    return storage


@pytest.fixture
def tool_context(scoped_storage: CrawlStorage) -> AgentToolContext:
    return AgentToolContext(
        storage=scoped_storage,
        search_service=None,
        embedding_provider=DeterministicHashEmbeddingProvider(),
    )


# ------------------------------------------------------------------------------
# 1. search_index Scoping & Boundary Tests
# ------------------------------------------------------------------------------

def test_search_index_scoped_to_dossier(scoped_storage: CrawlStorage, tool_context: AgentToolContext):
    """Verify search_index in Dossier A only returns doc_falcon and never leaks doc_orion."""
    dos_a = scoped_storage.get_dossier_by_slug("falcon-initiative")
    assert dos_a is not None

    # Search for common term "spec" inside Dossier A
    res_a_raw = execute_tool(
        "search_index",
        {"query": "spec", "dossier_id": dos_a.id},
        tool_context,
    )
    res_a = json.loads(res_a_raw)
    assert res_a["results_count"] == 1
    assert res_a["hits"][0]["file_id"] == "doc_falcon_01"
    assert res_a.get("dossier_id") == dos_a.id

    # Search for "spec" inside Dossier B
    dos_b = scoped_storage.get_dossier_by_slug("orion-initiative")
    assert dos_b is not None
    res_b_raw = execute_tool(
        "search_index",
        {"query": "spec", "dossier_id": dos_b.id},
        tool_context,
    )
    res_b = json.loads(res_b_raw)
    assert res_b["results_count"] == 0  # Orion doc doesn't have "spec" in name or snippet


def test_search_index_empty_dossier(scoped_storage: CrawlStorage, tool_context: AgentToolContext):
    """Verify searching an empty dossier returns 0 results cleanly with a notice."""
    dos_c = scoped_storage.get_dossier_by_slug("empty-initiative")
    assert dos_c is not None

    res_raw = execute_tool(
        "search_index",
        {"query": "anything", "dossier_id": dos_c.id},
        tool_context,
    )
    res = json.loads(res_raw)
    assert res["results_count"] == 0
    assert res["hits"] == []
    assert "contains no indexed documents" in res.get("notice", "")
    assert res.get("dossier_id") == dos_c.id


# ------------------------------------------------------------------------------
# 2. get_document_diff Boundary Isolation Tests
# ------------------------------------------------------------------------------

def test_get_document_diff_scoped_boundary(scoped_storage: CrawlStorage, tool_context: AgentToolContext):
    """Verify get_document_diff allows access to dossier members and blocks external files."""
    dos_a = scoped_storage.get_dossier_by_slug("falcon-initiative")
    assert dos_a is not None

    # Permitted access: doc_falcon_01 inside dos_a
    res_raw = execute_tool(
        "get_document_diff",
        {"file_id": "doc_falcon_01", "dossier_id": dos_a.id},
        tool_context,
    )
    res = json.loads(res_raw)
    assert res["file_id"] == "doc_falcon_01"
    assert len(res["diffs"]) == 1
    assert "patch_snippet" in res["diffs"][0]

    # Blocked access: doc_orion_01 inside dos_a (attempted cross-container access)
    denied_raw = execute_tool(
        "get_document_diff",
        {"file_id": "doc_orion_01", "dossier_id": dos_a.id},
        tool_context,
    )
    denied = json.loads(denied_raw)
    assert denied.get("status") == "permission_denied"
    assert "outside the boundary of Project Dossier" in denied.get("error", "")


# ------------------------------------------------------------------------------
# 3. get_file_metadata Boundary Isolation Tests
# ------------------------------------------------------------------------------

def test_get_file_metadata_scoped_boundary(scoped_storage: CrawlStorage, tool_context: AgentToolContext):
    """Verify get_file_metadata allows member files and denies unauthorized foreign files."""
    dos_a = scoped_storage.get_dossier_by_slug("falcon-initiative")
    assert dos_a is not None

    # Permitted access
    res_raw = execute_tool(
        "get_file_metadata",
        {"file_id": "doc_falcon_01", "dossier_id": dos_a.id},
        tool_context,
    )
    res = json.loads(res_raw)
    assert res["file_id"] == "doc_falcon_01"
    assert res["name"] == "Falcon Architecture Spec"

    # Denied access
    denied_raw = execute_tool(
        "get_file_metadata",
        {"file_id": "doc_orion_01", "dossier_id": dos_a.id},
        tool_context,
    )
    denied = json.loads(denied_raw)
    assert denied.get("status") == "permission_denied"
    assert "outside the boundary" in denied.get("error", "")


# ------------------------------------------------------------------------------
# 4. semantic_chunk_search Scoping Tests
# ------------------------------------------------------------------------------

def test_semantic_chunk_search_scoped(scoped_storage: CrawlStorage, tool_context: AgentToolContext):
    """Verify semantic_chunk_search restricts retrieval to chunks belonging to dossier files."""
    dos_a = scoped_storage.get_dossier_by_slug("falcon-initiative")
    dos_b = scoped_storage.get_dossier_by_slug("orion-initiative")
    dos_c = scoped_storage.get_dossier_by_slug("empty-initiative")

    # Inside Dossier A: searching general term returns falcon chunk
    res_a_raw = execute_tool(
        "semantic_chunk_search",
        {"query": "OAuth security tokens", "dossier_id": dos_a.id},
        tool_context,
    )
    res_a = json.loads(res_a_raw)
    assert res_a["chunks_count"] == 1
    assert res_a["chunks"][0]["file_id"] == "doc_falcon_01"

    # Inside Dossier B: searching the same returns orion chunk (or 0 if low similarity, but not falcon!)
    res_b_raw = execute_tool(
        "semantic_chunk_search",
        {"query": "OAuth security tokens", "dossier_id": dos_b.id},
        tool_context,
    )
    res_b = json.loads(res_b_raw)
    for c in res_b.get("chunks", []):
        assert c["file_id"] == "doc_orion_01"
        assert c["file_id"] != "doc_falcon_01"

    # Attempting explicit file_id filter for an out-of-boundary file
    denied_raw = execute_tool(
        "semantic_chunk_search",
        {"query": "auth", "dossier_id": dos_a.id, "file_id": "doc_orion_01"},
        tool_context,
    )
    denied = json.loads(denied_raw)
    assert denied.get("status") == "permission_denied"

    # Empty dossier returns fast notice
    empty_raw = execute_tool(
        "semantic_chunk_search",
        {"query": "anything", "dossier_id": dos_c.id},
        tool_context,
    )
    empty = json.loads(empty_raw)
    assert empty["chunks_count"] == 0
    assert "contains no indexed documents" in empty.get("notice", "")


# ------------------------------------------------------------------------------
# 5. get_document_catalog_stats Isolated Scoping
# ------------------------------------------------------------------------------

def test_get_document_catalog_stats_scoped(scoped_storage: CrawlStorage, tool_context: AgentToolContext):
    """Verify catalog stats returns isolated counts when scoped to a dossier."""
    dos_a = scoped_storage.get_dossier_by_slug("falcon-initiative")
    dos_c = scoped_storage.get_dossier_by_slug("empty-initiative")

    # Scoped to Dossier A (1 file)
    stats_a_raw = execute_tool(
        "get_document_catalog_stats",
        {"dossier_id": dos_a.id},
        tool_context,
    )
    stats_a = json.loads(stats_a_raw)
    assert stats_a["status"] == "success"
    assert stats_a["inventory"]["total_files"] == 1
    assert stats_a["inventory"]["docs_count"] == 1
    assert stats_a["inventory"]["total_chunks"] == 1
    assert "Falcon" in stats_a["inventory"]["project_tags_distribution"]
    assert "Orion" not in stats_a["inventory"]["project_tags_distribution"]

    # Scoped to empty Dossier C
    stats_c_raw = execute_tool(
        "get_document_catalog_stats",
        {"dossier_id": dos_c.id},
        tool_context,
    )
    stats_c = json.loads(stats_c_raw)
    assert stats_c["status"] == "success"
    assert stats_c["inventory"]["total_files"] == 0
    assert stats_c["inventory"]["docs_count"] == 0
    assert stats_c["inventory"]["total_chunks"] == 0

    # Unscoped (all 2 files)
    stats_all_raw = execute_tool(
        "get_document_catalog_stats",
        {},
        tool_context,
    )
    stats_all = json.loads(stats_all_raw)
    assert stats_all["inventory"]["total_files"] == 2


# ------------------------------------------------------------------------------
# 6. AgenticReasoningEngine Scoped Execution
# ------------------------------------------------------------------------------

def test_engine_run_with_dossier_id(scoped_storage: CrawlStorage):
    """Verify AgenticReasoningEngine run() resolves container context and scopes tool executions."""
    dos_a = scoped_storage.get_dossier_by_slug("falcon-initiative")
    assert dos_a is not None

    mock_llm = MagicMock()
    # Step 1: Model calls search_index without explicitly passing dossier_id
    mock_llm.complete.side_effect = [
        LLMCompletionResponse(
            content=None,
            tool_calls=[
                LLMToolCall(
                    id="call_1",
                    name="search_index",
                    arguments={"query": "spec"},
                )
            ],
            model="openrouter/auto",
        ),
        # Step 2: Model synthesizes answer based on tool output
        LLMCompletionResponse(
            content="According to the Falcon Architecture Spec (doc_falcon_01), PKCE OAuth is configured.",
            tool_calls=None,
            model="openrouter/auto",
        ),
    ]

    engine = AgenticReasoningEngine(
        llm_client=mock_llm,
        context=AgentToolContext(
            storage=scoped_storage,
            search_service=None,
            embedding_provider=DeterministicHashEmbeddingProvider(),
        ),
    )

    result = engine.run(
        query="What is the Falcon spec?",
        dossier_id=dos_a.id,
    )

    assert result.steps_taken == 1
    assert "search_index" in result.tools_used
    assert len(result.trace) == 1
    # Check that dossier_id was auto-injected into tool call arguments
    assert result.trace[0].arguments.get("dossier_id") == dos_a.id
    assert "doc_falcon_01" in result.trace[0].output_summary
    assert "doc_orion_01" not in result.trace[0].output_summary


# ------------------------------------------------------------------------------
# 7. FastAPI Endpoint Scoped Dossier Integration
# ------------------------------------------------------------------------------

def test_api_query_scoped_dossier(scoped_storage: CrawlStorage, monkeypatch):
    """Verify /api/agent/query validates dossier_id and returns 404 for invalid containers."""
    from app.api.deps import get_crawl_storage_dep

    # Dependency override
    app.dependency_overrides[get_crawl_storage_dep] = lambda: scoped_storage
    client = TestClient(app)

    dos_a = scoped_storage.get_dossier_by_slug("falcon-initiative")
    assert dos_a is not None

    # Mock engine.run to avoid hitting remote LLM
    mock_run_result = AgentRunResult(
        answer="Falcon architecture is verified.",
        steps_taken=1,
        tools_used=["search_index"],
        trace=[],
        model="openrouter/auto",
        latency_ms=120.5,
    )

    monkeypatch.setattr(
        AgenticReasoningEngine,
        "run",
        lambda self, query, user_instructions=None, history=None, dossier_id=None: mock_run_result,
    )

    # 1. Valid dossier_id
    resp = client.post(
        "/api/agent/query",
        json={"query": "Explain Falcon architecture", "dossier_id": dos_a.id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Falcon architecture is verified."
    assert data["dossier_id"] == dos_a.id

    # 2. Invalid dossier_id -> 404 Not Found
    err_resp = client.post(
        "/api/agent/query",
        json={"query": "Explain Falcon architecture", "dossier_id": "dos_nonexistent_999"},
    )
    assert err_resp.status_code == 404
    assert "Project Dossier 'dos_nonexistent_999' not found" in err_resp.json()["detail"]

    # 3. Invalid dossier_id on stream -> 404 Not Found
    stream_err_resp = client.post(
        "/api/agent/query/stream",
        json={"query": "Explain Falcon architecture", "dossier_id": "dos_nonexistent_999"},
    )
    assert stream_err_resp.status_code == 404
    assert "Project Dossier 'dos_nonexistent_999' not found" in stream_err_resp.json()["detail"]

    # Clean up override
    app.dependency_overrides.clear()
