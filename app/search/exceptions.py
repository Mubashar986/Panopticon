"""Custom typed exceptions for the Panopticon search package."""

from __future__ import annotations


class SearchError(Exception):
    """Base exception for all search-related errors."""


class SearchConnectionError(SearchError):
    """Raised when Meilisearch is unreachable or connection is refused."""


class SearchAuthError(SearchError):
    """Raised when Meilisearch authentication or API key validation fails."""


class IndexConfigurationError(SearchError):
    """Raised when an index schema or settings configuration fails."""


class IndexNotFoundError(SearchError):
    """Raised when querying an index that does not exist."""
