"""Unit and integration tests for native Meilisearch hybrid vector search and deep chunk ingestion."""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.agent.tools import AgentToolContext, execute_tool
from app.indexer.models import DocumentChunk, DriveFileMetadata
from app.indexer.storage import CrawlStorage
from app.search.client import PanopticonSearchClient
from app.search.exceptions import SearchConnectionError
from app.search.ingestion import SearchIngestionEngine
from app.search.models import ChunkSearchDocument, SearchDocument
from app.search.schema import (
    CHUNK_INDEX_NAME,
    configure_chunk_index_schema,
    configure_index_schema,
    enable_vector_store,
)
from app.search.service import SearchService


def test_chunk_search_document_serialization():
    """Verify ChunkSearchDocument serializes _vectors alias correctly for Meilisearch."""
    chunk_doc = ChunkSearchDocument(
        id="chk_test_01",
        file_id="file_01",
        file_name="Architecture PRD",
        section_heading="Authentication",
        content_text="OAuth 2.0 PKCE authentication flow.",
        char_start=0,
        char_end=45,
        word_count=6,
        vectors={"default": [0.1, 0.2, 0.3]},
    )

    data = chunk_doc.to_meili_dict()
    assert data["id"] == "chk_test_01"
    assert data["file_id"] == "file_01"
    assert "_vectors" in data
    assert data["_vectors"]["default"] == [0.1, 0.2, 0.3]


def test_search_document_with_vectors_serialization():
    """Verify SearchDocument serializes _vectors alias correctly."""
    metadata = DriveFileMetadata(
        id="doc_vec_01",
        name="Security Policy.gdoc",
        mime_type="application/vnd.google-apps.document",
    )
    search_doc = SearchDocument.from_drive_metadata(metadata, vector=[0.5, -0.2, 0.8])
    data = search_doc.to_meili_dict()

    assert data["id"] == "doc_vec_01"
    assert "_vectors" in data
    assert data["_vectors"]["default"] == [0.5, -0.2, 0.8]

    # When no vector is provided, _vectors must be omitted so Meilisearch does not reject null
    doc_no_vec = SearchDocument.from_drive_metadata(metadata, vector=None)
    data_no_vec = doc_no_vec.to_meili_dict()
    assert "_vectors" not in data_no_vec


def test_enable_vector_store_mock():
    """Verify enable_vector_store handles success and exception paths."""
    mock_client = MagicMock()
    mock_client.url = "http://localhost:7700"
    mock_client.api_key = "test_key"

    # Mock success response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.Client.patch", return_value=mock_resp):
        assert enable_vector_store(mock_client) is True

    # Mock error response
    mock_err_resp = MagicMock()
    mock_err_resp.status_code = 500
    mock_err_resp.text = "Internal error"
    with patch("httpx.Client.patch", return_value=mock_err_resp):
        assert enable_vector_store(mock_client) is False


def test_configure_chunk_index_schema_mock():
    """Verify configure_chunk_index_schema configures userProvided embedders and wait_for_task."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_index.uid = "panopticon_chunks"
    mock_index.get_settings.return_value = {"embedders": {"default": {"dimensions": 128}}}

    mock_client.ensure_index.return_value = mock_index
    mock_client.raw_client.wait_for_task.return_value = {"status": "succeeded"}
    mock_task = MagicMock()
    mock_task.task_uid = 101
    mock_index.update_settings.return_value = mock_task

    with patch("app.search.schema.enable_vector_store", return_value=True):
        settings = configure_chunk_index_schema(mock_client, dimension=128)
        assert "embedders" in settings
        mock_index.update_settings.assert_called_once()
        call_args = mock_index.update_settings.call_args[0][0]
        assert call_args["embedders"]["default"]["dimensions"] == 128
        assert call_args["embedders"]["default"]["source"] == "userProvided"


def test_search_service_search_chunks():
    """Verify SearchService.search_chunks queries Meilisearch index with vector."""
    mock_client = MagicMock()
    mock_client.index_name = "panopticon_docs"
    mock_index = MagicMock()
    mock_client.ensure_index.return_value = mock_index

    mock_index.search.return_value = {
        "hits": [
            {
                "id": "chk_01",
                "file_id": "file_123",
                "section_heading": "Overview",
                "content_text": "System architecture overview paragraph.",
                "_rankingScore": 0.942,
            }
        ]
    }

    service = SearchService(search_client=mock_client)
    hits = service.search_chunks(
        query_vector=[0.1, 0.2, 0.3],
        limit=2,
        file_id="file_123",
        query_text="architecture",
    )

    assert len(hits) == 1
    assert hits[0]["id"] == "chk_01"
    mock_index.search.assert_called_once()
    search_payload = mock_index.search.call_args[0][1]
    assert search_payload["vector"] == [0.1, 0.2, 0.3]
    assert search_payload["filter"] == 'file_id = "file_123"'
    assert search_payload["hybrid"]["embedder"] == "default"


def test_search_service_hybrid_search_dispatch():
    """Verify SearchService.search applies vector and hybrid parameters when passed."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.ensure_index.return_value = mock_index

    mock_index.search.return_value = {
        "hits": [
            {
                "id": "doc_01",
                "name": "Falcon PRD",
                "mime_type": "application/vnd.google-apps.document",
                "file_type": "document",
                "owners": ["alex@company.com"],
                "project_tags": ["Falcon"],
            }
        ],
        "estimatedTotalHits": 1,
        "processingTimeMs": 2.5,
    }

    service = SearchService(search_client=mock_client)
    res = service.search(
        query="Falcon rate limits",
        vector=[0.12, 0.34, 0.56],
        hybrid=True,
        semantic_ratio=0.7,
    )

    assert res.total_hits == 1
    assert res.hits[0].id == "doc_01"
    search_payload = mock_index.search.call_args[0][1]
    assert search_payload["vector"] == [0.12, 0.34, 0.56]
    assert search_payload["hybrid"]["semanticRatio"] == 0.7


def test_agent_tools_semantic_chunk_search_with_meili_and_fallback(tmp_path):
    """Verify _handle_semantic_chunk_search routes to Meilisearch first and falls back to SQLite on error."""
    db_path = tmp_path / "test_crawl_state.db"
    storage = CrawlStorage(db_path=db_path)

    # Insert a chunk into SQLite
    f = DriveFileMetadata(id="doc_fb_01", name="Fallback Doc", mime_type="application/vnd.google-apps.document")
    storage.upsert_file(f)
    c = DocumentChunk(
        id="chk_fb_01",
        file_id="doc_fb_01",
        chunk_index=0,
        section_heading="Security",
        content_text="Fallback sqlite chunk passage.",
        char_start=0,
        char_end=35,
        word_count=4,
        embedding=[1.0, 0.0],
    )
    storage.save_chunks([c])

    # 1. Success case: Meilisearch returns results
    mock_search_service = MagicMock()
    mock_search_service.search_chunks.return_value = [
        {
            "id": "chk_meili_01",
            "file_id": "doc_fb_01",
            "section_heading": "Meili Security",
            "content_text": "Meilisearch accelerated paragraph chunk.",
            "_rankingScore": 0.985,
        }
    ]

    mock_provider = MagicMock()
    mock_provider.embed_query.return_value = [1.0, 0.0]

    ctx_success = AgentToolContext(
        storage=storage,
        search_service=mock_search_service,
        embedding_provider=mock_provider,
    )

    raw_output = execute_tool("semantic_chunk_search", {"query": "security"}, ctx_success)
    data = json.loads(raw_output)
    assert data["engine"] == "meilisearch_vector"
    assert data["chunks_count"] == 1
    assert data["chunks"][0]["chunk_id"] == "chk_meili_01"
    assert data["chunks"][0]["similarity_score"] == 0.985

    # 2. Failure case: Meilisearch raises ConnectionError -> routes to SQLite fallback
    mock_search_service.search_chunks.side_effect = SearchConnectionError("Meilisearch server offline")

    ctx_fallback = AgentToolContext(
        storage=storage,
        search_service=mock_search_service,
        embedding_provider=mock_provider,
    )

    raw_output_fb = execute_tool("semantic_chunk_search", {"query": "security"}, ctx_fallback)
    data_fb = json.loads(raw_output_fb)
    assert data_fb["engine"] == "sqlite_fallback"
    assert data_fb["chunks_count"] == 1
    assert data_fb["chunks"][0]["chunk_id"] == "chk_fb_01"
    assert data_fb["chunks"][0]["similarity_score"] == 1.0


def test_ingest_chunks_engine():
    """Verify SearchIngestionEngine.ingest_chunks batches and sends chunks to Meilisearch."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.ensure_index.return_value = mock_index
    mock_client.get_stats.return_value = MagicMock(number_of_documents=2)

    mock_task = MagicMock()
    mock_task.task_uid = 201
    mock_index.add_documents.return_value = mock_task
    mock_client.raw_client.wait_for_task.return_value = {"status": "succeeded"}

    engine = SearchIngestionEngine(search_client=mock_client, batch_size=2)
    chunks = [
        DocumentChunk(
            id="c1",
            file_id="f1",
            chunk_index=0,
            content_text="Chunk 1",
            char_start=0,
            char_end=7,
            word_count=2,
            embedding=[0.1, 0.2],
        ),
        DocumentChunk(
            id="c2",
            file_id="f1",
            chunk_index=1,
            content_text="Chunk 2",
            char_start=8,
            char_end=15,
            word_count=2,
            embedding=[0.3, 0.4],
        ),
    ]

    res = engine.ingest_chunks(chunks, wait_for_tasks=True)
    assert res.indexed_count == 2
    assert res.batch_count == 1
    mock_client.configure_chunk_schema.assert_called_once()
    mock_index.add_documents.assert_called_once()
