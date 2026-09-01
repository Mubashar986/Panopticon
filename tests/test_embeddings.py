"""Unit tests for embedding providers and SQLite chunk vector storage."""

import math
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.indexer.embeddings import (
    DeterministicHashEmbeddingProvider,
    OpenRouterEmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
)
from app.indexer.models import DocumentChunk, DriveFileMetadata
from app.indexer.storage import CrawlStorage


def test_cosine_similarity_edge_cases():
    """Verify mathematical correctness of cosine similarity."""
    # Identical vectors
    v1 = [1.0, 2.0, 3.0]
    assert pytest.approx(cosine_similarity(v1, v1), 0.001) == 1.0

    # Orthogonal vectors
    v_a = [1.0, 0.0]
    v_b = [0.0, 1.0]
    assert pytest.approx(cosine_similarity(v_a, v_b), 0.001) == 0.0

    # Opposite vectors
    v_pos = [1.0, 0.0]
    v_neg = [-1.0, 0.0]
    assert pytest.approx(cosine_similarity(v_pos, v_neg), 0.001) == -1.0

    # Mismatched lengths
    assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0

    # Zero vectors
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([], []) == 0.0


def test_deterministic_hash_embeddings():
    """Verify offline deterministic hash vector provider."""
    provider = DeterministicHashEmbeddingProvider(dimension=64)
    assert provider.dimension == 64

    # Empty string handling
    empty_vec = provider.embed_query("")
    assert empty_vec == [0.0] * 64

    # Non-empty embedding produces L2 unit norm
    vec1 = provider.embed_query("OAuth 2.0 PKCE authentication flow for mobile security")
    norm1 = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(norm1, 0.001) == 1.0

    # Related queries have positive similarity
    vec2 = provider.embed_query("OAuth PKCE authentication security")
    sim_related = cosine_similarity(vec1, vec2)
    assert sim_related > 0.5

    # Unrelated queries have lower similarity
    vec_unrelated = provider.embed_query("Baking chocolate cake with fresh strawberries")
    sim_unrelated = cosine_similarity(vec1, vec_unrelated)
    assert sim_related > sim_unrelated


def test_openrouter_embedding_mock_success():
    """Verify OpenRouter embedding client parses OpenAI-compatible response correctly."""
    provider = OpenRouterEmbeddingProvider(
        api_key="sk-test-key",
        model="text-embedding-3-small",
        dimension=3,
    )

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_resp):
        embeddings = provider.embed_texts(["Chunk one", "Chunk two"])
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]


def test_openrouter_embedding_network_fallback():
    """Verify OpenRouter embedding client falls back gracefully on network failure."""
    fallback_provider = DeterministicHashEmbeddingProvider(dimension=16)
    provider = OpenRouterEmbeddingProvider(
        api_key="sk-test-key",
        fallback=fallback_provider,
    )

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Network offline")):
        embeddings = provider.embed_texts(["Fallback test passage"])
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 16


def test_storage_chunk_persistence_and_vector_search(tmp_path):
    """Verify SQLite saving, retrieval, cascading delete, and cosine vector search."""
    db_path = tmp_path / "test_crawl_state.db"
    storage = CrawlStorage(db_path=db_path)

    # 1. Create a parent file
    file_record = DriveFileMetadata(
        id="doc_vec_01",
        name="Security Policy.gdoc",
        mime_type="application/vnd.google-apps.document",
    )
    storage.upsert_file(file_record)

    # 2. Create chunks with embeddings
    c1 = DocumentChunk(
        id="chk_01",
        file_id="doc_vec_01",
        chunk_index=0,
        section_heading="Authentication",
        content_text="[Doc: Security] OAuth 2.0 PKCE authentication required.",
        char_start=0,
        char_end=50,
        word_count=7,
        embedding=[1.0, 0.0, 0.0],
    )
    c2 = DocumentChunk(
        id="chk_02",
        file_id="doc_vec_01",
        chunk_index=1,
        section_heading="Storage",
        content_text="[Doc: Security] SQLite encrypted database storage.",
        char_start=51,
        char_end=100,
        word_count=6,
        embedding=[0.0, 1.0, 0.0],
    )

    saved_count = storage.save_chunks([c1, c2])
    assert saved_count == 2
    assert storage.count_chunks("doc_vec_01") == 2

    # 3. Retrieve chunks by file
    retrieved = storage.get_chunks_for_file("doc_vec_01")
    assert len(retrieved) == 2
    assert retrieved[0].id == "chk_01"
    assert retrieved[0].embedding == [1.0, 0.0, 0.0]

    # 4. Search similar chunks
    # Query vector close to c1
    query_auth = [0.9, 0.1, 0.0]
    results = storage.search_similar_chunks(query_auth, limit=2)
    assert len(results) >= 1
    top_chunk, score = results[0]
    assert top_chunk.id == "chk_01"
    assert score > 0.8

    # 5. Cascading deletion when file is deleted
    storage.delete_files(["doc_vec_01"])
    assert storage.count_chunks("doc_vec_01") == 0
