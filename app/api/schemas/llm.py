"""Pydantic wire schemas for LLM Settings, Dynamic Model Discovery, and Health Probes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LLMSettingsResponse(BaseModel):
    """Wire representation of current active LLM configuration."""

    model_config = ConfigDict(frozen=True)

    model: str = Field(..., description="Currently active LLM model identifier")
    base_url: str = Field(..., description="Provider gateway base URL")
    has_api_key: bool = Field(..., description="True if an API key is configured")
    masked_api_key: str | None = Field(
        default=None, description="Masked API key (e.g. sk-or-v1-***06c136)"
    )
    recommended_models: list[str] = Field(
        default_factory=list, description="Curated list of high-performance models"
    )


class LLMSettingsUpdateRequest(BaseModel):
    """Wire representation of an LLM configuration update."""

    model_config = ConfigDict(extra="ignore")

    model: str | None = Field(default=None, description="New target model ID")
    base_url: str | None = Field(default=None, description="Custom base URL (e.g. for local Ollama)")
    api_key: str | None = Field(
        default=None, description="New API key (leave null/empty to keep existing)"
    )


class LLMTestConnectionRequest(BaseModel):
    """Optional parameters for an ad-hoc LLM credential test."""

    model_config = ConfigDict(extra="ignore")

    model: str | None = Field(default=None, description="Candidate model to test")
    base_url: str | None = Field(default=None, description="Candidate base URL to test")
    api_key: str | None = Field(default=None, description="Candidate API key to test")


class LLMTestConnectionResponse(BaseModel):
    """Result of an active LLM connectivity probe."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Whether the connection test succeeded")
    latency_ms: float = Field(..., description="Round-trip latency in milliseconds")
    message: str = Field(..., description="Response message or detailed error")
    model_tested: str = Field(..., description="Model ID used during test probe")


class LLMModelsDiscoveryResponse(BaseModel):
    """Result of dynamic model discovery from an OpenAI-compatible gateway."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Whether live discovery succeeded")
    models: list[str] = Field(..., description="List of discovered or fallback model IDs")
    count: int = Field(..., description="Total models available")
    source: str = Field(..., description="'live_discovery' or 'fallback_config'")
    base_url: str = Field(..., description="Gateway URL queried")
    message: str = Field(..., description="Informational message or error summary")
