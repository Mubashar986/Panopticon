"""Unit and integration tests for dynamic environment configuration and model discovery."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.engine import AgenticReasoningEngine
from app.agent.tools import AgentToolContext, execute_tool
from app.api.app import app
from app.core.config import Settings, get_settings
from app.core.llm import (
    LLMMessage,
    OpenRouterClient,
    fetch_remote_models,
    get_recommended_models,
    get_runtime_llm_config,
    set_runtime_llm_config,
)
from app.indexer.chunker import TextChunker
from app.indexer.exporter import ContentExporter


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear lru_cache for get_settings before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_defaults():
    """Verify that all dynamic configuration settings have sensible defaults."""
    s = get_settings()

    assert s.AGENT_MAX_REASONING_STEPS == 5
    assert s.AGENT_MAX_TOOL_OUTPUT_CHARS == 4000
    assert s.AGENT_DEFAULT_SEARCH_LIMIT == 5
    assert s.AGENT_MAX_SEARCH_LIMIT == 15
    assert s.AGENT_MAX_CHUNKS_LIMIT == 8
    assert s.AGENT_CHUNK_SNIPPET_CHARS == 1200
    assert s.AGENT_DIFF_SNIPPET_CHARS == 2500

    assert s.LLM_MAX_OUTPUT_TOKENS == 2000
    assert s.LLM_TEMPERATURE == 0.1
    assert s.LLM_STREAM_CHUNK_BATCH_SIZE == 4
    assert len(s.default_models_list) == 16
    assert "nvidia/nemotron-3-ultra:free" in s.default_models_list
    assert "openrouter/free" in s.default_models_list
    assert "minimax/minimax-m3:free" in s.default_models_list

    assert s.CHUNK_SIZE == 1500
    assert s.CHUNK_OVERLAP == 200
    assert s.EXPORT_MAX_SNIPPET_CHARS == 500
    assert s.EXPORT_MAX_BYTES == 10 * 1024 * 1024
    assert s.EMBEDDING_MODEL == "text-embedding-3-small"
    assert s.EMBEDDING_DIMENSION == 1536
    assert s.SYNC_WATERMARK_BUFFER_SECONDS == 120


def test_settings_environment_override(monkeypatch):
    """Verify that environment variables dynamically override defaults."""
    monkeypatch.setenv("AGENT_MAX_REASONING_STEPS", "9")
    monkeypatch.setenv("AGENT_MAX_TOOL_OUTPUT_CHARS", "8500")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "3500")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.6")
    monkeypatch.setenv("CHUNK_SIZE", "2000")
    monkeypatch.setenv("CHUNK_OVERLAP", "250")
    monkeypatch.setenv("LLM_DEFAULT_MODELS", "custom/model-x,custom/model-y")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embedding-model")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "768")
    monkeypatch.setenv("SYNC_WATERMARK_BUFFER_SECONDS", "180")

    get_settings.cache_clear()
    s = get_settings()

    assert s.AGENT_MAX_REASONING_STEPS == 9
    assert s.AGENT_MAX_TOOL_OUTPUT_CHARS == 8500
    assert s.LLM_MAX_OUTPUT_TOKENS == 3500
    assert s.LLM_TEMPERATURE == 0.6
    assert s.CHUNK_SIZE == 2000
    assert s.CHUNK_OVERLAP == 250
    assert s.default_models_list == ["custom/model-x", "custom/model-y"]
    assert s.EMBEDDING_MODEL == "custom-embedding-model"
    assert s.EMBEDDING_DIMENSION == 768
    assert s.SYNC_WATERMARK_BUFFER_SECONDS == 180


def test_chunker_uses_settings_defaults(monkeypatch):
    """Verify TextChunker pulls chunk_size and overlap from central settings."""
    monkeypatch.setenv("CHUNK_SIZE", "1800")
    monkeypatch.setenv("CHUNK_OVERLAP", "220")
    get_settings.cache_clear()

    chunker = TextChunker()
    assert chunker.chunk_size == 1800
    assert chunker.overlap == 220


def test_engine_uses_settings_max_steps(monkeypatch):
    """Verify AgenticReasoningEngine adopts AGENT_MAX_REASONING_STEPS from settings."""
    monkeypatch.setenv("AGENT_MAX_REASONING_STEPS", "7")
    get_settings.cache_clear()

    mock_llm = MagicMock()
    mock_context = MagicMock()

    engine = AgenticReasoningEngine(llm_client=mock_llm, context=mock_context)
    assert engine.max_steps == 7


def test_tool_truncation_respects_settings(monkeypatch):
    """Verify execute_tool character ceiling adjusts to AGENT_MAX_TOOL_OUTPUT_CHARS."""
    monkeypatch.setenv("AGENT_MAX_TOOL_OUTPUT_CHARS", "100")
    get_settings.cache_clear()

    mock_storage = MagicMock()
    mock_storage.get_file.return_value = None
    ctx = AgentToolContext(storage=mock_storage)

    # Calling get_file_metadata with non-existent file produces a JSON output longer than 50 chars
    output = execute_tool("get_file_metadata", {"file_id": "non_existent_long_id_test"}, ctx)
    assert len(output) <= 150
    assert "output truncated for context limit" in output


def test_llm_complete_respects_settings(monkeypatch):
    """Verify OpenRouterClient.complete passes temperature and max_tokens from settings."""
    monkeypatch.setenv("LLM_TEMPERATURE", "0.4")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "2500")
    get_settings.cache_clear()

    client = OpenRouterClient(api_key="test-key", model="test-model")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello world"}, "finish_reason": "stop"}]
    }

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        client.complete([LLMMessage(role="user", content="Hi")])

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["temperature"] == 0.4
        assert payload["max_tokens"] == 2500


def test_dynamic_models_discovery_success():
    """Verify fetch_remote_models dynamically extracts model IDs from standard /models response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {"id": "meta-llama/llama-3.3-70b-instruct"},
            {"id": "qwen/qwen-2.5-72b-instruct"},
            {"id": "anthropic/claude-3.7-sonnet"},
        ]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        success, models, msg = fetch_remote_models(base_url="https://mock.ai/v1", api_key="sk-test")
        assert success is True
        assert len(models) == 3
        assert "meta-llama/llama-3.3-70b-instruct" in models
        assert "qwen/qwen-2.5-72b-instruct" in models
        assert "discovered 3 models" in msg.lower()


def test_dynamic_models_discovery_fallback_on_error():
    """Verify fetch_remote_models falls back to configured default models when endpoint fails."""
    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        success, models, msg = fetch_remote_models(base_url="http://invalid-host:9999/v1")
        assert success is False
        assert len(models) >= 10
        assert "Could not connect" in msg


def test_api_settings_llm_models_endpoint():
    """Verify GET /api/settings/llm/models returns valid model catalog schema."""
    client = TestClient(app)
    response = client.get("/api/settings/llm/models")

    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "count" in data
    assert "source" in data
    assert data["count"] > 0
    assert isinstance(data["models"], list)


def test_embedding_provider_respects_settings(monkeypatch):
    """Verify get_embedding_provider uses EMBEDDING_MODEL and EMBEDDING_DIMENSION from settings."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embed-v2")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "768")
    get_settings.cache_clear()

    from app.indexer.embeddings import OpenRouterEmbeddingProvider, get_embedding_provider

    provider = get_embedding_provider()
    assert isinstance(provider, OpenRouterEmbeddingProvider)
    assert provider.model == "custom-embed-v2"
    assert provider.dimension == 768


def test_sync_engine_respects_watermark_settings(monkeypatch):
    """Verify IncrementalSyncEngine pulls SYNC_WATERMARK_BUFFER_SECONDS from settings."""
    monkeypatch.setenv("SYNC_WATERMARK_BUFFER_SECONDS", "240")
    get_settings.cache_clear()

    from app.indexer.sync import IncrementalSyncEngine

    engine = IncrementalSyncEngine()
    assert engine.watermark_buffer_seconds == 240
