"""Unit tests for LLMClient protocol, OpenRouter adapter, and tool calling engine."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.llm import (
    LLMAPIError,
    LLMMessage,
    LLMResponse,
    MockLLMClient,
    OpenRouterClient,
    ToolCall,
    ToolDefinition,
    get_runtime_llm_config,
    mask_api_key,
    set_runtime_llm_config,
)


def test_mask_api_key():
    """Verify API key masking security utility."""
    assert mask_api_key(None) is None
    assert mask_api_key("") is None
    assert mask_api_key("short") == "***"
    test_key = "test-provider-key-abcdef-987654"
    masked = mask_api_key(test_key)
    assert masked == "test-prov***987654"
    assert "abcdef" not in masked


def test_tool_definition_and_message_serialization():
    """Verify tool and message models serialize to standard OpenAI-compatible format."""
    tool = ToolDefinition(
        name="search_index",
        description="Search Meilisearch index",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    openai_tool = tool.to_openai_dict()
    assert openai_tool["type"] == "function"
    assert openai_tool["function"]["name"] == "search_index"
    assert "query" in openai_tool["function"]["parameters"]["properties"]

    # Assistant message with tool call
    tc = ToolCall(id="call_123", name="search_index", arguments={"query": "Falcon"})
    msg_asst = LLMMessage(role="assistant", tool_calls=[tc])
    asst_dict = msg_asst.to_openai_dict()
    assert asst_dict["role"] == "assistant"
    assert len(asst_dict["tool_calls"]) == 1
    assert asst_dict["tool_calls"][0]["id"] == "call_123"
    assert asst_dict["tool_calls"][0]["function"]["arguments"] == '{"query": "Falcon"}'

    # Tool response message
    msg_tool = LLMMessage(
        role="tool",
        tool_call_id="call_123",
        content='{"hits": ["doc_falcon"]}',
    )
    tool_dict = msg_tool.to_openai_dict()
    assert tool_dict["role"] == "tool"
    assert tool_dict["tool_call_id"] == "call_123"
    assert tool_dict["content"] == '{"hits": ["doc_falcon"]}'


def test_mock_llm_client():
    """Verify MockLLMClient execution for offline testing."""
    mock_client = MockLLMClient(
        model="test-mock",
        default_content="Test response from mock.",
    )
    assert mock_client.model == "test-mock"

    res = mock_client.complete(
        messages=[LLMMessage(role="user", content="Hello")],
    )
    assert res.content == "Test response from mock."
    assert res.finish_reason == "stop"
    assert len(mock_client.call_history) == 1

    success, latency, msg = mock_client.test_connection()
    assert success is True
    assert "successful" in msg


def test_openrouter_client_complete_text():
    """Verify OpenRouterClient parses text completion response."""
    client = OpenRouterClient(
        api_key="sk-test-key",
        model="deepseek/deepseek-chat",
    )

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "deepseek/deepseek-chat",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "OAuth 2.0 PKCE protects authorization codes.",
                },
                "finish_reason": "stop",
            }
        ],
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = client.complete(messages=[LLMMessage(role="user", content="Explain PKCE")])
        assert res.content == "OAuth 2.0 PKCE protects authorization codes."
        assert res.finish_reason == "stop"
        assert res.model == "deepseek/deepseek-chat"
        assert res.latency_ms > 0.0


def test_openrouter_client_tool_call_parsing():
    """Verify OpenRouterClient correctly parses tool calls and JSON arguments."""
    client = OpenRouterClient(api_key="sk-test-key", model="openai/gpt-4o-mini")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "openai/gpt-4o-mini",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_search_999",
                            "type": "function",
                            "function": {
                                "name": "search_index",
                                "arguments": '{"query": "SmartTrade rate limits", "limit": 5}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }

    tool = ToolDefinition(
        name="search_index",
        description="Search documents",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = client.complete(
            messages=[LLMMessage(role="user", content="Find rate limits in SmartTrade")],
            tools=[tool],
        )
        assert res.content is None
        assert res.finish_reason == "tool_calls"
        assert len(res.tool_calls) == 1
        tc = res.tool_calls[0]
        assert tc.id == "call_search_999"
        assert tc.name == "search_index"
        assert tc.arguments == {"query": "SmartTrade rate limits", "limit": 5}

        # Verify request payload
        payload = mock_post.call_args[1]["json"]
        assert "tools" in payload
        assert payload["tools"][0]["function"]["name"] == "search_index"


def test_openrouter_client_malformed_tool_args():
    """Verify client handles malformed non-JSON tool arguments without raising JSONDecodeError."""
    client = OpenRouterClient(api_key="sk-test-key")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_bad",
                            "function": {"name": "test_tool", "arguments": "not valid json {"},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = client.complete(messages=[LLMMessage(role="user", content="Hi")])
        assert len(res.tool_calls) == 1
        assert "raw_arguments" in res.tool_calls[0].arguments


def test_openrouter_test_connection_401():
    """Verify test_connection returns clean failure when API key is invalid."""
    client = OpenRouterClient(api_key="invalid-key")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = '{"error": {"message": "Invalid API key"}}'
    err = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=mock_resp
    )

    with patch("httpx.Client.post", side_effect=err):
        success, latency, msg = client.test_connection()
        assert success is False
        assert "HTTP 401" in msg


def test_runtime_llm_config_mutation():
    """Verify in-memory dynamic configuration updates."""
    initial = get_runtime_llm_config()
    assert "model" in initial

    updated = set_runtime_llm_config(model="anthropic/claude-3.5-sonnet")
    assert updated["model"] == "anthropic/claude-3.5-sonnet"
    assert get_runtime_llm_config()["model"] == "anthropic/claude-3.5-sonnet"


def test_openrouter_client_error_payload():
    """Verify OpenRouterClient raises LLMAPIError when provider returns error object under HTTP 200."""
    client = OpenRouterClient(api_key="sk-test-key", model="nvidia/nemotron-3-ultra")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "error": {
            "message": "Provider rate limit exceeded. Please retry later.",
            "code": 429,
        }
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(LLMAPIError) as exc_info:
            client.complete(messages=[LLMMessage(role="user", content="Hi")])
        assert "LLM Provider Error [429]" in str(exc_info.value)
        assert "Provider rate limit exceeded" in str(exc_info.value)


def test_openrouter_client_missing_choices():
    """Verify OpenRouterClient raises LLMAPIError when response lacks choices array."""
    client = OpenRouterClient(api_key="sk-test-key", model="nvidia/nemotron-3-ultra")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "gen-12345", "choices": []}

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(LLMAPIError) as exc_info:
            client.complete(messages=[LLMMessage(role="user", content="Hi")])
        assert "no choices" in str(exc_info.value)

