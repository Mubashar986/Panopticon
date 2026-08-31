"""Document catalog and directory REST route handlers."""

from __future__ import annotations

import logging
import time
from typing import Literal

from fastapi import APIRouter, Query, status

from app.api.deps import CrawlStorageDep, CurrentUser
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
