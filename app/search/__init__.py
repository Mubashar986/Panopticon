"""Panopticon Search Package: Meilisearch integration, models, and clients."""

from app.search.client import PanopticonSearchClient, get_search_client
from app.search.exceptions import (
    IndexConfigurationError,
    IndexNotFoundError,
    SearchAuthError,
    SearchConnectionError,
    SearchError,
)
from app.search.ingestion import IngestionResult, SearchIngestionEngine
from app.search.models import IndexStats, MeiliHealthStatus, MeiliVersionInfo, SearchDocument
from app.search.schema import INDEX_SETTINGS, configure_index_schema, get_index_schema
from app.search.service import SearchHit, SearchResult, SearchService, get_search_service

__all__ = [
    "INDEX_SETTINGS",
    "IndexConfigurationError",
    "IndexNotFoundError",
    "IndexStats",
    "IngestionResult",
    "MeiliHealthStatus",
    "MeiliVersionInfo",
    "PanopticonSearchClient",
    "SearchAuthError",
    "SearchConnectionError",
    "SearchDocument",
    "SearchError",
    "SearchHit",
    "SearchIngestionEngine",
    "SearchResult",
    "SearchService",
    "configure_index_schema",
    "get_index_schema",
    "get_search_client",
    "get_search_service",
]
