"""Search execution API route handlers."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, SearchServiceDep
from app.api.schemas.search import SearchResponse
from app.search.exceptions import IndexNotFoundError, SearchConnectionError, SearchError

logger = logging.getLogger("panopticon.api.routes.search")

router = APIRouter(tags=["Search"])


@router.get(
    "/api/search",
    response_model=SearchResponse,
    summary="Execute Typo-Tolerant Project Document Search",
    description=(
        "Searches indexed Google Docs and Google Sheets by project name, title, or content snippet. "
        "Supports typo tolerance, Google Drive label tag filtering, facet narrowing, and pagination."
    ),
    responses={
        200: {"description": "Matching documents successfully retrieved"},
        400: {"description": "Invalid query parameters"},
        503: {"description": "Search index engine is unreachable or unavailable"},
    },
)
async def search_documents(
    search_service: SearchServiceDep,
    current_user: CurrentUser,
    q: str = Query(
        default="",
        max_length=500,
        description="Search query string (supports project names, keywords, typos, or empty string to browse all)",
        examples=["Falcon", "Project Alpha", "SmartTrde", ""],
    ),
    mode: Literal["fuzzy", "tag", "exact"] = Query(
        default="fuzzy",
        description="Search mode: 'fuzzy' (typo-tolerant), 'tag' (prioritize/filter project tags), or 'exact'",
    ),
    file_type: Literal["document", "spreadsheet", "other"] | None = Query(
        default=None,
        description="Facet filter for document category",
    ),
    mime_type: str | None = Query(
        default=None,
        description="Filter by exact MIME type",
    ),
    sharing_status: Literal["private", "shared", "domain"] | None = Query(
        default=None,
        description="Filter by sharing scope badge",
    ),
    project_tag: str | None = Query(
        default=None,
        description="Filter by specific Google Drive project label tag",
    ),
    primary_owner: str | None = Query(
        default=None,
        description="Filter by primary owner email or name",
    ),
    sort_by: str | None = Query(
        default=None,
        description="Sort field and direction, e.g. 'modified_time:desc'",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum result items to return per page",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Pagination offset",
    ),
) -> SearchResponse:
    """Execute search query against local Meilisearch index."""
    logger.info(
        "Search request from user [%s]: q='%s', mode='%s', limit=%d, offset=%d",
        current_user.email,
        q,
        mode,
        limit,
        offset,
    )

    # If tag mode requested without a specific project_tag facet, apply q to project_tag if plausible
    effective_tag = project_tag
    effective_query = q
    if mode == "tag" and not project_tag and q.strip():
        effective_tag = q.strip()
    elif mode == "exact" and q.strip():
        # In exact mode, enclose multi-word query in quotes for phrase matching
        effective_query = f'"{q.strip()}"' if " " in q.strip() and not q.startswith('"') else q

    # If blank query and no sort specified, default to sorting by newest modified
    effective_sort = sort_by or ("modified_time:desc" if not q.strip() else None)

    try:
        domain_result = search_service.search(
            query=effective_query,
            file_type=file_type,
            mime_type=mime_type,
            sharing_status=sharing_status,
            project_tag=effective_tag,
            primary_owner=primary_owner,
            sort_by=effective_sort,
            limit=limit,
            offset=offset,
        )

        return SearchResponse.from_search_result(domain_result)


    except SearchConnectionError as exc:
        logger.error("Search engine connection failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "search_engine_unavailable",
                "message": "The search engine service is currently unreachable.",
                "details": str(exc),
            },
        ) from exc

    except IndexNotFoundError as exc:
        logger.warning("Search index missing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "search_index_not_found",
                "message": "The Panopticon search index has not been provisioned yet. Run the indexer to initialize.",
                "details": str(exc),
            },
        ) from exc

    except SearchError as exc:
        logger.error("Search execution failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "search_execution_error",
                "message": "An internal error occurred while executing the search query.",
                "details": str(exc),
            },
        ) from exc
