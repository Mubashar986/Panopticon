"""Route handlers for Google Drive synchronization and Meilisearch re-indexing."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SyncManagerDep
from app.api.schemas.sync import (
    ReindexResponse,
    SyncStatusResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
)
from app.api.services.sync_manager import SyncInProgressError

logger = logging.getLogger("panopticon.api.routes.sync")

router = APIRouter(tags=["Sync & Ingestion"])


@router.post(
    "/api/sync",
    response_model=SyncTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Asynchronous Google Drive Sync",
    description=(
        "Initiates background Google Drive crawl, text export, SQLite watermark delta update, "
        "and Meilisearch search index synchronization. Returns 202 Accepted immediately. "
        "Returns 409 Conflict if a sync job is already active."
    ),
    responses={
        202: {"description": "Background sync job successfully started"},
        409: {"description": "Another sync job is already in progress"},
    },
)
async def trigger_drive_sync(
    sync_manager: SyncManagerDep,
    current_user: CurrentUser,
    request: SyncTriggerRequest | None = None,
) -> SyncTriggerResponse:
    """Launch background Drive sync job."""
    req = request or SyncTriggerRequest()
    logger.info(
        "Sync request received from user [%s] (full_refresh=%s, export_content=%s)",
        current_user.email,
        req.full_refresh,
        req.export_content,
    )

    try:
        return sync_manager.trigger_sync(
            full_refresh=req.full_refresh,
            export_content=req.export_content,
            page_size=req.page_size,
        )
    except SyncInProgressError as exc:
        logger.warning("Sync request rejected due to active job collision: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "sync_in_progress",
                "message": "A synchronization job is already running. Please wait for it to complete.",
                "details": str(exc),
            },
        ) from exc


@router.get(
    "/api/sync/status",
    response_model=SyncStatusResponse,
    summary="Get Sync Status and Progress",
    description=(
        "Returns the live status of the synchronization subsystem, active phase, "
        "last watermark timestamp from SQLite, and metrics from the most recent run."
    ),
)
async def get_sync_status(
    sync_manager: SyncManagerDep,
    current_user: CurrentUser,
) -> SyncStatusResponse:
    """Query live sync state."""
    return sync_manager.get_status()


@router.post(
    "/api/sync/reindex",
    response_model=ReindexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Local SQLite to Meilisearch Re-Indexing",
    description=(
        "Re-pushes all documents stored in the local SQLite database into Meilisearch "
        "without making any network calls to the Google Drive API."
    ),
    responses={
        202: {"description": "Background re-indexing job started"},
        409: {"description": "A job is already in progress"},
    },
)
async def trigger_reindex(
    sync_manager: SyncManagerDep,
    current_user: CurrentUser,
) -> ReindexResponse:
    """Launch background search re-indexing job."""
    logger.info("Re-indexing request received from user [%s]", current_user.email)
    try:
        return sync_manager.trigger_reindex()
    except SyncInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "sync_in_progress",
                "message": "A synchronization or re-indexing job is already in progress.",
                "details": str(exc),
            },
        ) from exc
