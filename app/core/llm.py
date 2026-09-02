"""Universal LLM Client Protocol, OpenRouter Adapter, and Tool Calling Engine."""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("panopticon.core.llm")

# Curated list of recommended models spanning speed, cost, and advanced reasoning
RECOMMENDED_MODELS: list[str] = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-ultra",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "anthropic/claude-3.7-sonnet",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-2.5-pro",
    "google/gemini-2.0-flash",
    "deepseek/deepseek-r1",
    "deepseek/deepseek-chat",
    "openai/gpt-4o",
    "openai/o3-mini",
]


def mask_api_key(key: str | None) -> str | None:
    """Mask an API key for safe display, revealing only prefix and trailing characters.

    Examples:
        "sk-or-v1-a81107e5...06c136" -> "sk-or-v1-***06c136"
        None -> None
    """
    if not key or not key.strip():
        return None
    k = key.strip()
    if len(k) <= 12:
        return "***"
    prefix = k[:9]
    suffix = k[-6:]
    return f"{prefix}***{suffix}"


class LLMAPIError(RuntimeError):
    """Exception raised when an LLM provider returns an API error or malformed payload."""


class ToolCall(BaseModel):
    """Represents a tool/function call requested by the LLM."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique tool call identifier (e.g. call_abc123)")
    name: str = Field(..., description="Name of the target tool to invoke")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Parsed dictionary of tool arguments"
    )


class ToolDefinition(BaseModel):
    """OpenAI-compatible function tool definition."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Function name")
    description: str = Field(..., description="What the tool does and when to call it")
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema specifying argument names, types, and constraints",
    )

    def to_openai_dict(self) -> dict[str, Any]:
        """Format as OpenAI-compatible tools payload element."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLMMessage(BaseModel):
    """Represents a single message in a multi-turn conversation."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(..., description="Message role: 'system', 'user', 'assistant', or 'tool'")
    content: str | None = Field(default=None, description="Plain text message content")
    name: str | None = Field(default=None, description="Optional author or function name")
    tool_call_id: str | None = Field(
        default=None, description="ID of the tool call this message is responding to (for role='tool')"
    )
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="List of tool calls requested by assistant"
    )

    def to_openai_dict(self) -> dict[str, Any]:
        """Format message as OpenAI-compatible dictionary."""
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.name:
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        return d


class LLMResponse(BaseModel):
    """Unified response from an LLM completion."""

    model_config = ConfigDict(frozen=True)

    content: str | None = Field(default=None, description="Direct text response if any")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tool calls requested by the model"
    )
    model: str = Field(..., description="Name of the model that generated this completion")
    finish_reason: str = Field(default="stop", description="stop, tool_calls, length, or content_filter")
    latency_ms: float = Field(default=0.0, description="Response latency in milliseconds")


class LLMClient(Protocol):
    """Protocol defining the interface for swappable LLM clients."""

    @property
    def model(self) -> str:
        """Active model identifier."""
        ...

    @property
    def base_url(self) -> str:
        """Provider endpoint base URL."""
        ...

    def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> LLMResponse:
        """Execute a synchronous completion with optional tool definitions."""
        ...

    def test_connection(self) -> tuple[bool, float, str]:
        """Probe the endpoint with a minimal test message. Returns (success, latency_ms, message)."""
        ...


class OpenRouterClient:
    """Production OpenAI-compatible client connecting to OpenRouter or custom gateways."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek/deepseek-chat",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> LLMResponse:
        """Execute completion request over HTTP with tool-calling schema serialization."""
        if not self._api_key:
            raise ValueError("OpenRouter API key is not configured.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Mubashar986/Panopticon",
            "X-Title": "Panopticon Agentic RAG",
        }

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.to_openai_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [t.to_openai_dict() for t in tools]
            payload["tool_choice"] = "auto"

        # Handle reasoning model exclusion to prevent thinking tokens from hijacking response
        if any(r in self._model.lower() for r in ["deepseek-r1", "qwq", "o1", "o3"]):
            payload["reasoning"] = {"exclude": True}

        start_time = time.perf_counter()

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if not isinstance(data, dict):
            raise LLMAPIError(
                f"Malformed response from LLM gateway: expected JSON object, got {type(data).__name__}"
            )

        # Catch OpenRouter / upstream API error payloads returned under HTTP 200
        if "error" in data and data["error"]:
            err_info = data["error"]
            if isinstance(err_info, dict):
                err_msg = err_info.get("message") or str(err_info)
                err_code = err_info.get("code")
                code_str = f" [{err_code}]" if err_code else ""
                raise LLMAPIError(f"LLM Provider Error{code_str}: {err_msg}")
            raise LLMAPIError(f"LLM Provider Error: {err_info}")

        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            raise LLMAPIError(
                f"LLM provider returned no choices. Gateway response: {str(data)[:300]}"
            )

        choice = choices[0]
        if not isinstance(choice, dict):
            raise LLMAPIError(
                f"Malformed choice in LLM response: expected dict, got {type(choice).__name__}"
            )

        message_data = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")

        raw_content = message_data.get("content")
        tool_calls: list[ToolCall] = []

        if "tool_calls" in message_data and message_data["tool_calls"]:
            for tc in message_data["tool_calls"]:
                tc_id = tc.get("id", f"call_{time.time()}")
                fn_name = tc.get("function", {}).get("name", "")
                raw_args = tc.get("function", {}).get("arguments", "{}")

                # Safe JSON deserialization
                if isinstance(raw_args, dict):
                    args_dict = raw_args
                elif isinstance(raw_args, str):
                    try:
                        args_dict = json.loads(raw_args)
                    except json.JSONDecodeError:
                        logger.warning("Malformed tool arguments from model: %s", raw_args)
                        args_dict = {"raw_arguments": raw_args}
                else:
                    args_dict = {}

                tool_calls.append(ToolCall(id=tc_id, name=fn_name, arguments=args_dict))

        return LLMResponse(
            content=raw_content,
            tool_calls=tool_calls,
            model=data.get("model", self._model),
            finish_reason=finish_reason,
            latency_ms=round(latency_ms, 2),
        )

    def test_connection(self) -> tuple[bool, float, str]:
        """Probe the endpoint with a minimal test message."""
        if not self._api_key:
            return False, 0.0, "API key is missing. Configure OPENROUTER_API_KEY in Settings."

        start_time = time.perf_counter()
        try:
            res = self.complete(
                messages=[LLMMessage(role="user", content="Ping. Respond with 'pong' only.")],
                max_tokens=10,
            )
            latency = (time.perf_counter() - start_time) * 1000.0
            reply = res.content.strip() if res.content else "OK"
            return True, round(latency, 2), f"Connection successful ({res.model}): {reply}"
        except httpx.HTTPStatusError as exc:
            latency = (time.perf_counter() - start_time) * 1000.0
            code = exc.response.status_code
            msg = f"HTTP {code} error: {exc.response.text[:200]}"
            return False, round(latency, 2), msg
        except LLMAPIError as exc:
            latency = (time.perf_counter() - start_time) * 1000.0
            return False, round(latency, 2), str(exc)
        except Exception as exc:
            latency = (time.perf_counter() - start_time) * 1000.0
            return False, round(latency, 2), f"Network/Connection error: {exc}"


class MockLLMClient:
    """In-memory mock client for unit testing and offline CI execution."""

    def __init__(
        self,
        model: str = "mock-model",
        base_url: str = "mock://localhost",
        default_content: str | None = "Mock assistant response.",
        default_tool_calls: list[ToolCall] | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self.default_content = default_content
        self.default_tool_calls = default_tool_calls or []
        self.call_history: list[list[LLMMessage]] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> LLMResponse:
        self.call_history.append(messages)
        finish = "tool_calls" if self.default_tool_calls else "stop"
        return LLMResponse(
            content=self.default_content,
            tool_calls=self.default_tool_calls,
            model=self._model,
            finish_reason=finish,
            latency_ms=1.5,
        )

    def test_connection(self) -> tuple[bool, float, str]:
        return True, 1.2, f"Mock connection to {self._model} successful."


# ------------------------------------------------------------------------------
# Runtime LLM Configuration Singleton Seam
# ------------------------------------------------------------------------------

_RUNTIME_CONFIG: dict[str, Any] = {
    "model": None,
    "api_key": None,
    "base_url": None,
}


def get_runtime_llm_config() -> dict[str, Any]:
    """Retrieve current in-memory active LLM configuration."""
    settings = get_settings()
    return {
        "model": _RUNTIME_CONFIG["model"] or settings.OPENROUTER_MODEL or "nvidia/nemotron-3-ultra",
        "api_key": _RUNTIME_CONFIG["api_key"] or settings.OPENROUTER_API_KEY,
        "base_url": _RUNTIME_CONFIG["base_url"] or settings.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1",
    }


def set_runtime_llm_config(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Update in-memory active LLM configuration at runtime without server restart."""
    if model is not None and model.strip():
        _RUNTIME_CONFIG["model"] = model.strip()
    if api_key is not None and api_key.strip():
        _RUNTIME_CONFIG["api_key"] = api_key.strip()
    if base_url is not None and base_url.strip():
        _RUNTIME_CONFIG["base_url"] = base_url.strip()

    logger.info("Updated runtime LLM config: model=%s", _RUNTIME_CONFIG.get("model"))
    return get_runtime_llm_config()


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Factory creating an LLMClient instance using active runtime credentials."""
    s = settings if settings is not None else get_settings()
    cfg = get_runtime_llm_config()
    key = cfg.get("api_key") or s.OPENROUTER_API_KEY or ""
    model = cfg.get("model") or s.OPENROUTER_MODEL or "nvidia/nemotron-3-ultra"
    base_url = cfg.get("base_url") or s.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1"

    if not key:
        logger.debug("OPENROUTER_API_KEY not configured; returning MockLLMClient fallback.")
        return MockLLMClient(model=model, base_url=base_url)

    return OpenRouterClient(
        api_key=key,
        model=model,
        base_url=base_url,
    )
