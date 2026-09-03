"""Unit tests for Agent tools and execution dispatcher."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agent.tools import (
    PANOPTICON_TOOLS,
    AgentToolContext,
    execute_tool,
)
from app.indexer.embeddings import DeterministicHashEmbeddingProvider
from app.indexer.models import DocumentChunk, DocumentDiff, DocumentVersion, DriveFileMetadata
from app.indexer.storage import CrawlStorage


@pytest.fixture
def test_storage(tmp_path: Path) -> CrawlStorage:
    storage = CrawlStorage(db_path=tmp_path / "agent_tools_test.db")
    doc = DriveFileMetadata(
        id="doc_falcon_01",
        name="Project Falcon Technical Specification",
        mime_type="application/vnd.google-apps.document",
        modified_time=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
        created_time=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        owners=["lead.architect@company.com"],
        last_modifying_user="alice@company.com",
        shared=True,
        sharing_status="domain",
        project_tags=["Falcon", "Security"],
        content_snippet="Falcon technical specification covering OAuth 2.0 PKCE and rate limits.",
        export_status="success",
        web_view_link="https://docs.google.com/document/d/doc_falcon_01/edit",
        size_bytes=15000,
    )
    storage.upsert_files([doc])

    storage.save_version(
        DocumentVersion(
            id="ver_1",
            file_id="doc_falcon_01",
            version_number=1,
            content_hash="hash_v1",
            modified_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            snapshot_text="Falcon spec v1",
        )
    )
    storage.save_version(
        DocumentVersion(
            id="ver_2",
            file_id="doc_falcon_01",
            version_number=2,
            content_hash="hash_v2",
            modified_time=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
            snapshot_text="Falcon spec v2",
        )
    )

    diff = DocumentDiff(
        file_id="doc_falcon_01",
        from_version_id="ver_1",
        to_version_id="ver_2",
        lines_added=4,
        lines_removed=1,
        patch_text="--- v1\n+++ v2\n@@ -10,3 +10,6 @@\n-rate_limit = 60\n+rate_limit = 120\n",
        ai_summary="Increased OAuth rate limit from 60 to 120 requests per minute.",
    )
    storage.save_diff(diff)

    provider = DeterministicHashEmbeddingProvider()
    text = "[Document: Falcon | Section: OAuth]\nOAuth 2.0 PKCE is enforced for all client apps."
    vec = provider.embed_query(text)

    chunk = DocumentChunk(
        id="chk_01",
        file_id="doc_falcon_01",
        version_id="ver_2",
        chunk_index=0,
        section_heading="OAuth 2.0 PKCE",
        content_text=text,
        char_start=0,
        char_end=100,
        embedding=vec,
    )
    storage.save_chunks([chunk])

    return storage


@pytest.fixture
def tool_context(test_storage: CrawlStorage) -> AgentToolContext:
    return AgentToolContext(
        storage=test_storage,
        search_service=None,
        embedding_provider=DeterministicHashEmbeddingProvider(),
    )


def test_panopticon_tools_declaration():
    """Verify tool schemas are valid and contain required fields."""
    assert len(PANOPTICON_TOOLS) == 5
    tool_names = [t.name for t in PANOPTICON_TOOLS]
    assert "get_document_catalog_stats" in tool_names
    assert "search_index" in tool_names
    assert "get_document_diff" in tool_names
    assert "get_file_metadata" in tool_names
    assert "semantic_chunk_search" in tool_names

    for t in PANOPTICON_TOOLS:
        openai_dict = t.to_openai_dict()
        assert openai_dict["type"] == "function"
        assert "parameters" in openai_dict["function"]


def test_tool_search_index(tool_context: AgentToolContext):
    """Verify search_index returns matching documents."""
    out = execute_tool("search_index", {"query": "Falcon"}, tool_context)
    data = json.loads(out)
    assert data["results_count"] == 1
    assert data["hits"][0]["file_id"] == "doc_falcon_01"
    assert "Falcon" in data["hits"][0]["name"]

    # Filter with non-matching tag
    out_filtered = execute_tool("search_index", {"query": "Falcon", "project_tag": "NonExistent"}, tool_context)
    data_filtered = json.loads(out_filtered)
    assert data_filtered["results_count"] == 0


def test_tool_get_document_diff(tool_context: AgentToolContext):
    """Verify get_document_diff returns version diffs and patches."""
    out = execute_tool("get_document_diff", {"file_id": "doc_falcon_01"}, tool_context)
    data = json.loads(out)
    assert data["file_id"] == "doc_falcon_01"
    assert len(data["diffs"]) == 1
    assert data["diffs"][0]["to_version_id"] == "ver_2"
    assert "rate_limit = 120" in data["diffs"][0]["patch_snippet"]
    assert "Increased OAuth rate limit" in data["diffs"][0]["ai_summary"]


def test_tool_get_file_metadata(tool_context: AgentToolContext):
    """Verify get_file_metadata returns complete file details."""
    out = execute_tool("get_file_metadata", {"file_id": "doc_falcon_01"}, tool_context)
    data = json.loads(out)
    assert data["file_id"] == "doc_falcon_01"
    assert data["owners"] == ["lead.architect@company.com"]
    assert data["sharing_status"] == "domain"
    assert "Falcon" in data["project_tags"]


def test_tool_semantic_chunk_search(tool_context: AgentToolContext):
    """Verify semantic_chunk_search retrieves relevant text chunks."""
    out = execute_tool("semantic_chunk_search", {"query": "OAuth 2.0 PKCE", "limit": 2}, tool_context)
    data = json.loads(out)
    assert data["chunks_count"] >= 1
    assert data["chunks"][0]["file_id"] == "doc_falcon_01"
    assert "OAuth" in data["chunks"][0]["text"]


def test_tool_get_document_catalog_stats(tool_context: AgentToolContext):
    """Verify get_document_catalog_stats returns corpus inventory and breakdown."""
    out = execute_tool("get_document_catalog_stats", {}, tool_context)
    data = json.loads(out)
    assert data["status"] == "success"
    inv = data["inventory"]
    assert inv["total_files"] == 1
    assert inv["docs_count"] == 1
    assert inv["sheets_count"] == 0
    assert inv["total_versions"] == 2
    assert inv["total_diffs"] == 1
    assert inv["total_chunks"] == 1
    assert inv["files_with_zero_chunks"] == 0
    assert inv["project_tags_distribution"]["Falcon"] == 1
    assert inv["project_tags_distribution"]["Security"] == 1
    assert len(inv["recent_files"]) == 1
    assert inv["recent_files"][0]["name"] == "Project Falcon Technical Specification"


def test_tool_unknown_tool_and_error_handling(tool_context: AgentToolContext):
    """Verify unknown tool returns informative error message."""
    out = execute_tool("non_existent_tool", {"foo": "bar"}, tool_context)
    data = json.loads(out)
    assert "Unknown tool" in data["error"]
