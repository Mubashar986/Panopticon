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

__all__ = [
    "PanopticonSearchClient",
    "get_search_client",
    "SearchError",
    "SearchConnectionError",
    "SearchAuthError",
    "IndexConfigurationError",
    "IndexNotFoundError",
    "MeiliHealthStatus",
    "MeiliVersionInfo",
    "IndexStats",
    "SearchDocument",
    "INDEX_SETTINGS",
    "configure_index_schema",
    "get_index_schema",
    "SearchIngestionEngine",
    "IngestionResult",
]
