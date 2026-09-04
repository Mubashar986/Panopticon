"""Search execution service with typo tolerance, ranking rules, and match attribution."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.search.client import PanopticonSearchClient, get_search_client
from app.search.exceptions import IndexNotFoundError, SearchConnectionError, SearchError
from app.search.models import ConfidenceLevel, MatchSource, SearchHit, SearchResult

logger = logging.getLogger("panopticon.search.service")


class SearchService:
    """High-level query execution service encapsulating Meilisearch ranking, filtering, and highlighting."""

    def __init__(
        self,
        search_client: PanopticonSearchClient | None = None,
    ) -> None:
        self.client = search_client or get_search_client()

    def _build_filter_expression(
        self,
        file_type: str | None = None,
        mime_type: str | None = None,
        sharing_status: str | None = None,
        project_tag: str | None = None,
        primary_owner: str | None = None,
        custom_filter: str | None = None,
        allowed_file_ids: list[str] | set[str] | None = None,
        id_field: str = "id",
    ) -> str | None:
        """Construct a Meilisearch filter string from facet criteria."""
        clauses: list[str] = []

        if file_type:
            clauses.append(f'file_type = "{file_type}"')
        if mime_type:
            clauses.append(f'mime_type = "{mime_type}"')
        if sharing_status:
            clauses.append(f'sharing_status = "{sharing_status}"')
        if project_tag:
            clauses.append(f'project_tags = "{project_tag}"')
        if primary_owner:
            clauses.append(f'primary_owner = "{primary_owner}"')
        if allowed_file_ids:
            ids_str = ", ".join(f'"{fid}"' for fid in sorted(allowed_file_ids))
            clauses.append(f'{id_field} IN [{ids_str}]')
        if custom_filter:
            clauses.append(f"({custom_filter})")

        return " AND ".join(clauses) if clauses else None

    def _classify_match(
        self,
        query: str,
        hit_dict: dict[str, Any],
        formatted_dict: dict[str, Any],
    ) -> tuple[MatchSource, ConfidenceLevel]:
        """Determine matched_via source ('tag', 'title', 'content', 'owner') and confidence level."""
        if not query.strip():
            return "title", "medium"

        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        
        # 1. Check if highlight exists in project_tags or tags contain query
        formatted_tags = formatted_dict.get("project_tags", [])
        raw_tags = hit_dict.get("project_tags", [])
        if any("<em>" in str(tag) for tag in formatted_tags):
            return "tag", "high"
        for q in query_terms:
            if any(q in str(tag).lower() for tag in raw_tags):
                return "tag", "high"

        # 2. Check if highlight exists in name (title) or name contains query
        formatted_name = str(formatted_dict.get("name", ""))
        raw_name = str(hit_dict.get("name", "")).lower()
        if "<em>" in formatted_name:
            return "title", "medium"
        for q in query_terms:
            if q in raw_name:
                return "title", "medium"

        # 3. Check owners
        formatted_owner = str(formatted_dict.get("primary_owner", ""))
        raw_owner = str(hit_dict.get("primary_owner", "")).lower()
        if "<em>" in formatted_owner or any(q in raw_owner for q in query_terms):
            return "owner", "low"

        # 4. Fallback: content snippet match
        return "content", "low"

    def search(
        self,
        query: str,
        file_type: str | None = None,
        mime_type: str | None = None,
        sharing_status: str | None = None,
        project_tag: str | None = None,
        primary_owner: str | None = None,
        sort_by: list[str] | str | None = None,
        limit: int = 20,
        offset: int = 0,
        index_name: str | None = None,
        custom_filter: str | None = None,
        vector: list[float] | None = None,
        hybrid: bool = False,
        semantic_ratio: float = 0.5,
        allowed_file_ids: list[str] | set[str] | None = None,
    ) -> SearchResult:
        """Execute a typo-tolerant search query against the Meilisearch index.

        Args:
            query: User search query string (supports typos).
            file_type: Optional facet filter: 'document', 'spreadsheet', or 'other'.
            mime_type: Optional MIME type filter.
            sharing_status: Optional visibility filter: 'private', 'shared', 'domain'.
            project_tag: Optional tag facet filter (e.g. 'Falcon').
            primary_owner: Optional owner email filter.
            sort_by: Optional sort criteria (e.g. ['modified_time:desc']).
            limit: Maximum hits to return (default 20).
            offset: Hit offset for pagination.
            index_name: Target index UID override.
            custom_filter: Raw Meilisearch filter expression string.
            vector: Optional dense vector query for hybrid semantic retrieval.
            hybrid: Whether to enforce hybrid vector search if vector is supplied.
            semantic_ratio: Balance between BM25 (0.0) and vector similarity (1.0).
            allowed_file_ids: Optional set of file IDs to restrict search (Dossier scoping).

        Returns:
            SearchResult containing ordered SearchHit items and execution metrics.
        """
        # Fast early exit if dossier is empty
        if allowed_file_ids is not None and len(allowed_file_ids) == 0:
            return SearchResult(
                query=query,
                hits=[],
                total_hits=0,
                processing_time_ms=0.0,
                limit=limit,
                offset=offset,
                facet_distribution={},
            )

        target_uid = index_name or self.client.index_name
        filter_expr = self._build_filter_expression(
            file_type=file_type,
            mime_type=mime_type,
            sharing_status=sharing_status,
            project_tag=project_tag,
            primary_owner=primary_owner,
            custom_filter=custom_filter,
            allowed_file_ids=allowed_file_ids,
            id_field="id",
        )

        # Normalize sort parameter
        sort_param: list[str] | None = None
        if isinstance(sort_by, str):
            sort_param = [sort_by]
        elif isinstance(sort_by, list):
            sort_param = sort_by

        search_params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "attributesToHighlight": ["*"],
            "highlightPreTag": "<em>",
            "highlightPostTag": "</em>",
            "attributesToCrop": ["content_snippet"],
            "cropLength": 40,
            "facets": ["file_type", "mime_type", "sharing_status", "project_tags", "primary_owner"],
        }

        if filter_expr:
            search_params["filter"] = filter_expr
        if sort_param:
            search_params["sort"] = sort_param
        if vector is not None:
            search_params["vector"] = vector
            search_params["hybrid"] = {
                "embedder": "default",
                "semanticRatio": semantic_ratio,
            }

        try:
            index = self.client.ensure_index(target_uid, primary_key="id")
            raw_response = index.search(query, search_params)

            hits_data = raw_response.get("hits", [])
            total_hits = raw_response.get("estimatedTotalHits", len(hits_data))
            processing_time = raw_response.get("processingTimeMs", 0.0)
            facet_dist = raw_response.get("facetDistribution", {})

            hits: list[SearchHit] = []
            for hit in hits_data:
                formatted = hit.get("_formatted", {})
                matched_via, confidence = self._classify_match(query, hit, formatted)

                highlighted_name = formatted.get("name") if formatted else None
                highlighted_snippet = formatted.get("content_snippet") if formatted else None

                search_hit = SearchHit(
                    id=hit["id"],
                    name=hit["name"],
                    mime_type=hit["mime_type"],
                    file_type=hit.get("file_type", "other"),
                    primary_owner=hit.get("primary_owner", "Shared Drive / Organization"),
                    owners=hit.get("owners", []),
                    last_modifying_user=hit.get("last_modifying_user"),
                    modified_time=hit.get("modified_time"),
                    created_time=hit.get("created_time"),
                    sharing_status=hit.get("sharing_status", "private"),
                    project_tags=hit.get("project_tags", []),
                    content_snippet=hit.get("content_snippet"),
                    export_status=hit.get("export_status"),
                    web_view_link=hit.get("web_view_link"),
                    icon_link=hit.get("icon_link"),
                    size_bytes=hit.get("size_bytes"),
                    matched_via=matched_via,
                    confidence=confidence,
                    highlighted_name=highlighted_name,
                    highlighted_snippet=highlighted_snippet,
                )
                hits.append(search_hit)

            return SearchResult(
                query=query,
                hits=hits,
                total_hits=total_hits,
                processing_time_ms=processing_time,
                limit=limit,
                offset=offset,
                facet_distribution=facet_dist,
            )

        except Exception as exc:
            err_str = str(exc).lower()
            if "connection refused" in err_str or "communicationerror" in type(exc).__name__.lower():
                raise SearchConnectionError(
                    f"Cannot connect to Meilisearch at {self.client.url}: {exc}"
                ) from exc
            if "index_not_found" in err_str:
                raise IndexNotFoundError(f"Index '{target_uid}' not found in Meilisearch") from exc
            raise SearchError(f"Search query failed: {exc}") from exc

    def search_chunks(
        self,
        query_vector: list[float],
        limit: int = 3,
        file_id: str | None = None,
        query_text: str = "",
        index_name: str = "panopticon_chunks",
        allowed_file_ids: list[str] | set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query panopticon_chunks index with dense vector for sub-5ms paragraph retrieval.

        Args:
            query_vector: Dense embedding vector representing the search query.
            limit: Maximum paragraph chunks to return.
            file_id: Optional filter restricting search to a specific file.
            query_text: Optional keyword string to run hybrid vector+keyword chunk search.
            index_name: Target index UID (defaults to 'panopticon_chunks').
            allowed_file_ids: Optional set of file IDs to restrict vector search (Dossier scoping).

        Returns:
            list[dict[str, Any]]: List of matching chunk dictionaries.
        """
        # Fast early exit if dossier is empty
        if allowed_file_ids is not None and len(allowed_file_ids) == 0:
            return []

        search_params: dict[str, Any] = {
            "limit": limit,
            "vector": query_vector,
            "hybrid": {
                "embedder": "default",
                "semanticRatio": 1.0 if not query_text.strip() else 0.8,
            },
        }

        filter_clauses: list[str] = []
        if file_id:
            filter_clauses.append(f'file_id = "{file_id}"')
        if allowed_file_ids:
            ids_str = ", ".join(f'"{fid}"' for fid in sorted(allowed_file_ids))
            filter_clauses.append(f'file_id IN [{ids_str}]')

        if filter_clauses:
            search_params["filter"] = " AND ".join(filter_clauses)

        try:
            index = self.client.ensure_index(index_name, primary_key="id")
            raw_response = index.search(query_text, search_params)
            hits = raw_response.get("hits", [])
            return hits
        except Exception as exc:
            err_str = str(exc).lower()
            if "connection refused" in err_str or "communicationerror" in type(exc).__name__.lower():
                raise SearchConnectionError(
                    f"Cannot connect to Meilisearch at {self.client.url}: {exc}"
                ) from exc
            if "index_not_found" in err_str:
                raise IndexNotFoundError(f"Index '{index_name}' not found in Meilisearch") from exc
            raise SearchError(f"Vector chunk search failed: {exc}") from exc


def get_search_service(
    search_client: PanopticonSearchClient | None = None,
) -> SearchService:
    """Factory helper returning an initialized SearchService instance."""
    return SearchService(search_client=search_client)
