"""FastAPI router for LLM runtime settings, dynamic model discovery, and connectivity testing."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.schemas.llm import (
    LLMModelsDiscoveryResponse,
    LLMSettingsResponse,
    LLMSettingsUpdateRequest,
    LLMTestConnectionRequest,
    LLMTestConnectionResponse,
)
from app.core.config import get_settings
from app.core.llm import (
    OpenRouterClient,
    fetch_remote_models,
    get_recommended_models,
    get_runtime_llm_config,
    mask_api_key,
    set_runtime_llm_config,
)
from app.core.logging import get_logger

logger = get_logger("panopticon.api.routes.settings")

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings() -> LLMSettingsResponse:
    """Retrieve currently active LLM settings with masked API key and dynamic models list."""
    cfg = get_runtime_llm_config()
    raw_key = cfg.get("api_key")
    return LLMSettingsResponse(
        model=cfg["model"],
        base_url=cfg["base_url"],
        has_api_key=bool(raw_key and raw_key.strip()),
        masked_api_key=mask_api_key(raw_key),
        recommended_models=get_recommended_models(),
    )


@router.post("/llm", response_model=LLMSettingsResponse)
def update_llm_settings(payload: LLMSettingsUpdateRequest) -> LLMSettingsResponse:
    """Dynamically update active model, base URL, or API key at runtime."""
    cfg = set_runtime_llm_config(
        model=payload.model,
        api_key=payload.api_key,
        base_url=payload.base_url,
    )
    raw_key = cfg.get("api_key")
    logger.info("Updated active LLM configuration via API: model=%s", cfg["model"])
    return LLMSettingsResponse(
        model=cfg["model"],
        base_url=cfg["base_url"],
        has_api_key=bool(raw_key and raw_key.strip()),
        masked_api_key=mask_api_key(raw_key),
        recommended_models=get_recommended_models(),
    )


@router.get("/llm/models", response_model=LLMModelsDiscoveryResponse)
def discover_llm_models(
    base_url: str | None = Query(default=None, description="Optional custom gateway base URL to probe"),
    api_key: str | None = Query(default=None, description="Optional custom API key to use for probe"),
) -> LLMModelsDiscoveryResponse:
    """Dynamically discover available models from the target provider/gateway (/models endpoint).

    Supports OpenRouter, OpenAI, Groq, local Ollama (http://localhost:11434/v1), LM Studio, and vLLM.
    """
    settings = get_settings()
    cfg = get_runtime_llm_config()
    target_base = (base_url or cfg.get("base_url") or settings.OPENROUTER_BASE_URL).rstrip("/")

    success, models, message = fetch_remote_models(base_url=base_url, api_key=api_key)
    source = "live_discovery" if success else "fallback_config"

    return LLMModelsDiscoveryResponse(
        success=success,
        models=models,
        count=len(models),
        source=source,
        base_url=target_base,
        message=message,
    )


@router.post("/llm/test", response_model=LLMTestConnectionResponse)
def test_llm_connection(payload: LLMTestConnectionRequest | None = None) -> LLMTestConnectionResponse:
    """Probe an LLM connection to verify credentials and model responsiveness."""
    cfg = get_runtime_llm_config()

    test_model = (payload.model.strip() if payload and payload.model and payload.model.strip() else cfg["model"])
    test_key = (payload.api_key.strip() if payload and payload.api_key and payload.api_key.strip() else (cfg["api_key"] or ""))
    test_base_url = (payload.base_url.strip() if payload and payload.base_url and payload.base_url.strip() else cfg["base_url"])

    client = OpenRouterClient(
        api_key=test_key,
        model=test_model,
        base_url=test_base_url,
        timeout_seconds=15.0,
    )

    success, latency, msg = client.test_connection()
    return LLMTestConnectionResponse(
        success=success,
        latency_ms=latency,
        message=msg,
        model_tested=test_model,
    )
