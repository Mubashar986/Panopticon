"""FastAPI REST router for Project Dossiers management."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CrawlStorageDep, CurrentUser
from app.api.schemas.documents import DocumentResponseItem
from app.api.schemas.dossiers import (
    DossierAddItemsRequest,
    DossierAddMemberRequest,
    DossierCreateRequest,
    DossierDetailResponse,
    DossierItemsModifiedResponse,
    DossierListResponse,
    DossierMemberResponse,
    DossierResponse,
    DossierSummaryResponse,
    DossierUpdateRequest,
)
from app.core.logging import get_logger

logger = get_logger("panopticon.api.dossiers")

router = APIRouter(prefix="/api/dossiers", tags=["Project Dossiers"])


@router.post(
    "",
    response_model=DossierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project dossier",
)
def create_dossier(
    payload: DossierCreateRequest,
    storage: CrawlStorageDep,
    current_user: CurrentUser,
) -> DossierResponse:
    """Create a new containerized project dossier workspace.

    Registers the creator as the default 'admin' member and optionally attaches initial files.
    """
    try:
        dossier = storage.create_dossier(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            color=payload.color,
            icon=payload.icon,
            status="active",
            created_by=current_user.email,
            initial_file_ids=payload.initial_file_ids,
        )
        return DossierResponse.from_domain(dossier)
    except Exception as exc:
        logger.error("Failed to create dossier: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not create dossier: {exc}",
        ) from exc


@router.get(
    "",
    response_model=DossierListResponse,
    summary="List all project dossiers",
)
def list_dossiers(
    storage: CrawlStorageDep,
    status_filter: Annotated[
        Literal["active", "archived"] | None,
        Query(alias="status", description="Filter by active or archived lifecycle status"),
    ] = None,
    sort_by: Annotated[
        Literal[
            "updated_at:desc",
            "updated_at:asc",
            "name:asc",
            "name:desc",
            "created_at:desc",
            "created_at:asc",
        ],
        Query(description="Sort order strategy"),
    ] = "updated_at:desc",
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> DossierListResponse:
    """List all project dossiers with aggregated item and member counts."""
    summaries, total = storage.list_dossiers(
        status=status_filter,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return DossierListResponse(
        items=[DossierSummaryResponse.from_domain(s) for s in summaries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{dossier_id}",
    response_model=DossierDetailResponse,
    summary="Get dossier details with items and members",
)
def get_dossier(
    dossier_id: str,
    storage: CrawlStorageDep,
) -> DossierDetailResponse:
    """Fetch complete dossier detail by its unique ID or URL slug."""
    # Look up by ID first; if not found, look up by slug
    dossier = storage.get_dossier(dossier_id)
    if not dossier:
        dossier = storage.get_dossier_by_slug(dossier_id)

    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    # Fetch associated files and members
    files, item_count = storage.list_dossier_items(dossier.id, limit=100, offset=0)
    members = storage.list_dossier_members(dossier.id)

    return DossierDetailResponse(
        dossier=DossierResponse.from_domain(dossier),
        items=[DocumentResponseItem.from_drive_file_metadata(f) for f in files],
        members=[DossierMemberResponse.from_domain(m) for m in members],
        item_count=item_count,
        member_count=len(members),
    )


@router.patch(
    "/{dossier_id}",
    response_model=DossierResponse,
    summary="Update dossier metadata or status",
)
def update_dossier(
    dossier_id: str,
    payload: DossierUpdateRequest,
    storage: CrawlStorageDep,
) -> DossierResponse:
    """Update metadata (name, slug, description, color, icon, status) for a dossier."""
    # Find dossier by ID or slug
    existing = storage.get_dossier(dossier_id) or storage.get_dossier_by_slug(dossier_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    try:
        updated = storage.update_dossier(
            dossier_id=existing.id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            color=payload.color,
            icon=payload.icon,
            status=payload.status,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dossier '{dossier_id}' not found",
            )
        return DossierResponse.from_domain(updated)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        logger.error("Failed to update dossier '%s': %s", dossier_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not update dossier: {exc}",
        ) from exc


@router.delete(
    "/{dossier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project dossier",
)
def delete_dossier(
    dossier_id: str,
    storage: CrawlStorageDep,
) -> None:
    """Delete a dossier and its associations. Underlying Google Drive files remain untouched."""
    existing = storage.get_dossier(dossier_id) or storage.get_dossier_by_slug(dossier_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    success = storage.delete_dossier(existing.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )


@router.post(
    "/{dossier_id}/items",
    response_model=DossierItemsModifiedResponse,
    summary="Associate Google Drive files with a dossier",
)
def add_dossier_items(
    dossier_id: str,
    payload: DossierAddItemsRequest,
    storage: CrawlStorageDep,
    current_user: CurrentUser,
) -> DossierItemsModifiedResponse:
    """Add one or more Google Drive files into a project dossier."""
    existing = storage.get_dossier(dossier_id) or storage.get_dossier_by_slug(dossier_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    try:
        added_count = storage.add_dossier_items(
            dossier_id=existing.id,
            file_ids=payload.file_ids,
            added_by=current_user.email,
        )
        _, total_items = storage.list_dossier_items(existing.id, limit=1, offset=0)
        return DossierItemsModifiedResponse(
            dossier_id=existing.id,
            modified_count=added_count,
            total_items=total_items,
            message=f"Successfully associated {added_count} file(s) with dossier.",
        )
    except Exception as exc:
        logger.error("Failed to add items to dossier '%s': %s", dossier_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not associate files: {exc}",
        ) from exc


@router.delete(
    "/{dossier_id}/items/{file_id}",
    response_model=DossierItemsModifiedResponse,
    summary="Remove a Google Drive file from a dossier",
)
def remove_dossier_item(
    dossier_id: str,
    file_id: str,
    storage: CrawlStorageDep,
) -> DossierItemsModifiedResponse:
    """Remove a Google Drive file association from a dossier. The file is NOT deleted from Google Drive."""
    existing = storage.get_dossier(dossier_id) or storage.get_dossier_by_slug(dossier_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    removed = storage.remove_dossier_item(existing.id, file_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_id}' is not associated with dossier '{dossier_id}'",
        )

    _, total_items = storage.list_dossier_items(existing.id, limit=1, offset=0)
    return DossierItemsModifiedResponse(
        dossier_id=existing.id,
        modified_count=1,
        total_items=total_items,
        message=f"Successfully removed file '{file_id}' from dossier.",
    )


@router.get(
    "/{dossier_id}/items",
    summary="List files associated with a dossier",
)
def list_dossier_items(
    dossier_id: str,
    storage: CrawlStorageDep,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> dict:
    """List paginated Google Drive files belonging to this dossier."""
    existing = storage.get_dossier(dossier_id) or storage.get_dossier_by_slug(dossier_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    files, total = storage.list_dossier_items(existing.id, limit=limit, offset=offset)
    return {
        "dossier_id": existing.id,
        "items": [DocumentResponseItem.from_drive_file_metadata(f) for f in files],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "/{dossier_id}/members",
    response_model=DossierMemberResponse,
    summary="Add or update a member in a dossier",
)
def add_or_update_member(
    dossier_id: str,
    payload: DossierAddMemberRequest,
    storage: CrawlStorageDep,
) -> DossierMemberResponse:
    """Add a user email with an assigned role ('admin', 'editor', 'viewer') to a dossier."""
    existing = storage.get_dossier(dossier_id) or storage.get_dossier_by_slug(dossier_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    try:
        member = storage.add_dossier_member(
            dossier_id=existing.id,
            user_email=payload.user_email,
            role=payload.role,
        )
        return DossierMemberResponse.from_domain(member)
    except Exception as exc:
        logger.error("Failed to add member to dossier '%s': %s", dossier_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not assign member: {exc}",
        ) from exc


@router.delete(
    "/{dossier_id}/members/{user_email}",
    status_code=status.HTTP_200_OK,
    summary="Remove a member from a dossier",
)
def remove_member(
    dossier_id: str,
    user_email: str,
    storage: CrawlStorageDep,
) -> dict[str, str]:
    """Remove a user from a dossier's membership list."""
    existing = storage.get_dossier(dossier_id) or storage.get_dossier_by_slug(dossier_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier '{dossier_id}' not found",
        )

    removed = storage.remove_dossier_member(existing.id, user_email)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_email}' is not a member of dossier '{dossier_id}'",
        )

    return {"message": f"Successfully removed member '{user_email}' from dossier."}
