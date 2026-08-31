"""FastAPI application factory, lifespan management, middleware, and exception handlers."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.api.services.sync_manager import get_sync_manager
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.supervisor import get_engine_supervisor
from app.search.client import get_search_client
from app.search.exceptions import IndexNotFoundError, SearchConnectionError, SearchError

logger = get_logger("panopticon.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle hooks."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting %s API server v%s...", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Search Engine Host: %s", settings.MEILI_HOST)
    logger.info("Drive Auth Provider Mode: %s", settings.DRIVE_AUTH_MODE)

    # 1. Supervise Meilisearch engine lifecycle (auto-download & auto-spawn if offline)
    supervisor = get_engine_supervisor()
    try:
        supervisor.start(timeout_seconds=5.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not auto-start Meilisearch supervisor: %s", exc)

    # 2. Verify search engine connectivity and auto-provision schema
    try:
        client = get_search_client()
        health = client.health_check()
        if health.is_available:
            logger.info("Meilisearch health verified: [%s] (Version: %s)", health.status, health.version)
        else:
            logger.warning(
                "Meilisearch is currently unreachable at %s: %s (API will start in degraded mode)",
                health.host,
                health.error_message,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Search client check on startup encountered: %s", exc)

    # 3. Start auto-sync background polling scheduler if enabled
    sync_manager = get_sync_manager()
    if settings.AUTO_SYNC_ENABLED:
        sync_manager.start_background_scheduler(interval_seconds=settings.AUTO_SYNC_INTERVAL_SECONDS)

    yield

    # 4. Stop auto-sync background scheduler
    if settings.AUTO_SYNC_ENABLED:
        sync_manager.stop_background_scheduler()

    # 5. Graceful shutdown of managed search engine process
    supervisor.stop(timeout_seconds=3.0)
    logger.info("Shutting down %s API server cleanly.", settings.APP_NAME)



def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    settings = get_settings()

    application = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        description=(
            "Backend API for Panopticon Google Docs/Sheets Project-Name Search. "
            "Exposes typo-tolerant search and health diagnostics over local Meilisearch."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request timing middleware
    @application.middleware("http")
    async def add_process_time_header(request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
        return response

    # Global Exception Handlers for Search Exceptions
    @application.exception_handler(SearchConnectionError)
    async def handle_search_connection_error(
        request: Request, exc: SearchConnectionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "search_connection_error",
                "message": "Meilisearch engine connection failed.",
                "details": str(exc),
            },
        )

    @application.exception_handler(IndexNotFoundError)
    async def handle_index_not_found_error(
        request: Request, exc: IndexNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "index_not_found",
                "message": "Search index not provisioned yet.",
                "details": str(exc),
            },
        )

    @application.exception_handler(SearchError)
    async def handle_search_error(
        request: Request, exc: SearchError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "search_error",
                "message": "Search service error.",
                "details": str(exc),
            },
        )

    # Include API Routers
    application.include_router(api_router)

    return application


# Global application entrypoint for uvicorn (e.g. `uvicorn app.api.app:app`)
app = create_app()
