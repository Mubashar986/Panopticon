"""Panopticon Search Package: Meilisearch integration, models, and clients."""

from app.search.client import PanopticonSearchClient, get_search_client
from app.search.exceptions import (
    IndexConfigurationError,
    IndexNotFoundError,
    SearchAuthError,
    SearchConnectionError,
    SearchError,
)
from app.search.models import IndexStats, MeiliHealthStatus, MeiliVersionInfo

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
]
