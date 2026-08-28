"""Health check and system diagnostics route handlers."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.api.deps import SearchClientDep
from app.api.schemas.health import HealthResponse, SystemStatusResponse
from app.core.config import get_settings

router = APIRouter(tags=["Health & Diagnostics"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application Liveness Probe",
    description="Returns 200 OK if the FastAPI backend service is running.",
)
async def health_check() -> HealthResponse:
    """Liveness probe endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        auth_mode=settings.DRIVE_AUTH_MODE,
    )


@router.get(
    "/api/system/status",
    response_model=SystemStatusResponse,
    summary="Comprehensive System Health Diagnostics",
    description="Inspects backend service state, active Drive auth mode, and live Meilisearch connectivity.",
)
async def system_status(
    search_client: SearchClientDep,
) -> SystemStatusResponse:
    """Deep system health diagnostic endpoint."""
    settings = get_settings()
    health_info = search_client.health_check()
    
    doc_count = 0
    is_indexing = False
    details: dict[str, object] = {
        "meilisearch_version": health_info.version,
    }

    if health_info.is_available:
        try:
            stats = search_client.get_index_stats()
            doc_count = stats.number_of_documents
            is_indexing = stats.is_indexing
            details["index_stats"] = stats.model_dump()
        except Exception as exc:  # noqa: BLE001
            details["index_stats_error"] = str(exc)

    overall_status = "healthy" if health_info.is_available else "degraded"

    return SystemStatusResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        auth_mode=settings.DRIVE_AUTH_MODE,
        api_endpoint=f"http://{settings.API_HOST}:{settings.API_PORT}",
        meilisearch_connected=health_info.is_available,
        meilisearch_health=health_info.status if health_info.is_available else (health_info.error_message or "unreachable"),
        meilisearch_host=health_info.host,
        index_name=settings.MEILI_INDEX_NAME,
        document_count=doc_count,
        is_indexing=is_indexing,
        details=details,
    )
