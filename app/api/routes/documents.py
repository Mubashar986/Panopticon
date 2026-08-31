"""Document catalog and directory REST route handlers."""

from __future__ import annotations

import logging
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CrawlStorageDep, CurrentUser
from app.api.schemas.diffs import (
    DiffListResponse,
    DocumentDiffResponse,
    DocumentVersionResponse,
    VersionHistoryResponse,
)
from app.api.schemas.documents import DocumentListResponse, DocumentResponseItem

logger = logging.getLogger("panopticon.api.routes.documents")

router = APIRouter(tags=["Document Directory"])


@router.get(
    "/api/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Tracked Documents with Pagination and Facet Filters",
    description=(
        "Returns a paginated list of all Google Docs and Sheets tracked in the local SQLite repository. "
        "Supports dynamic sorting (newest modified first, alphabetical), category filtering, "
        "sharing status badges, and project tag facets without requiring an active search keyword."
    ),
    responses={
        200: {"description": "Paginated document catalog successfully retrieved"},
        422: {"description": "Validation error on pagination or sorting parameters"},
    },
)
def list_documents(
    storage: CrawlStorageDep,
    current_user: CurrentUser,
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of document records to return per page (1 to 500)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Pagination offset index",
    ),
    sort_by: Literal[
        "modified_time:desc",
        "modified_time:asc",
        "name:asc",
        "name:desc",
        "created_time:desc",
        "created_time:asc",
    ] = Query(
        default="modified_time:desc",
        description="Sorting field and direction (defaults to newest modified first)",
    ),
    file_type: Literal["document", "spreadsheet", "other"] | None = Query(
        default=None,
        description="Filter by file category ('document', 'spreadsheet', 'other')",
    ),
    mime_type: str | None = Query(
        default=None,
        description="Filter by exact Google Workspace MIME type",
    ),
    sharing_status: Literal["private", "shared", "domain", "anyone"] | None = Query(
        default=None,
        description="Filter by sharing scope badge",
    ),
    project_tag: str | None = Query(
        default=None,
        description="Filter by attached Google Drive project label tag",
    ),
    primary_owner: str | None = Query(
        default=None,
        description="Filter by primary owner email or name substring",
    ),
) -> DocumentListResponse:
    """Retrieve paginated document catalog items from local SQLite storage."""
    start_time = time.perf_counter()

    logger.debug(
        "Listing documents for user [%s]: limit=%d, offset=%d, sort_by='%s', file_type=%s, tag=%s",
        current_user.email,
        limit,
        offset,
        sort_by,
        file_type,
        project_tag,
    )

    items, total_count = storage.list_documents_paginated(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        file_type=file_type,
        mime_type=mime_type,
        sharing_status=sharing_status,
        project_tag=project_tag,
        primary_owner=primary_owner,
    )

    processing_time_ms = (time.perf_counter() - start_time) * 1000

    document_dtos = [
        DocumentResponseItem.from_drive_file_metadata(file) for file in items
    ]

    return DocumentListResponse(
        total_count=total_count,
        limit=limit,
        offset=offset,
        processing_time_ms=round(processing_time_ms, 2),
        documents=document_dtos,
    )


@router.get(
    "/api/documents/{file_id}/versions",
    response_model=VersionHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Version Snapshots",
    description="Returns chronological version snapshot history for a tracked document.",
    responses={
        200: {"description": "Version snapshot history retrieved successfully"},
        404: {"description": "Document not found"},
    },
)
def get_document_versions(
    file_id: str,
    storage: CrawlStorageDep,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100, description="Max snapshots to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> VersionHistoryResponse:
    """Retrieve version snapshots for a document."""
    file_record = storage.get_file(file_id)
    if file_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{file_id}' not found.",
        )

    versions = storage.get_version_history(file_id, limit=limit, offset=offset)
    total = storage.count_versions(file_id)

    return VersionHistoryResponse(
        file_id=file_id,
        total=total,
        items=[DocumentVersionResponse.model_validate(v) for v in versions],
    )


@router.get(
    "/api/documents/{file_id}/diffs",
    response_model=DiffListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Revision Diffs",
    description="Returns structured diff records and AI change summaries for a tracked document.",
    responses={
        200: {"description": "Diff delta history retrieved successfully"},
        404: {"description": "Document not found"},
    },
)
def get_document_diffs(
    file_id: str,
    storage: CrawlStorageDep,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100, description="Max diffs to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> DiffListResponse:
    """Retrieve diff records and AI summaries for a document."""
    file_record = storage.get_file(file_id)
    if file_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{file_id}' not found.",
        )

    diffs = storage.get_diffs(file_id, limit=limit, offset=offset)
    total = storage.count_diffs(file_id)

    return DiffListResponse(
        file_id=file_id,
        total=total,
        items=[DocumentDiffResponse.model_validate(d) for d in diffs],
    )

