"""FastAPI router for LLM runtime settings and connectivity testing."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas.llm import (
    LLMSettingsResponse,
    LLMSettingsUpdateRequest,
    LLMTestConnectionRequest,
    LLMTestConnectionResponse,
)
from app.core.llm import (
    RECOMMENDED_MODELS,
    OpenRouterClient,
    get_runtime_llm_config,
    mask_api_key,
    set_runtime_llm_config,
)
from app.core.logging import get_logger

logger = get_logger("panopticon.api.routes.settings")

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings() -> LLMSettingsResponse:
    """Retrieve currently active LLM settings with masked API key."""
    cfg = get_runtime_llm_config()
    raw_key = cfg.get("api_key")
    return LLMSettingsResponse(
        model=cfg["model"],
        base_url=cfg["base_url"],
        has_api_key=bool(raw_key and raw_key.strip()),
        masked_api_key=mask_api_key(raw_key),
        recommended_models=RECOMMENDED_MODELS,
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
        recommended_models=RECOMMENDED_MODELS,
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
