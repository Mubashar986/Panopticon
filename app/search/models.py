"""Data models for Meilisearch client, health checks, stats, and search documents."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.search.schema import SearchDocument


class MeiliVersionInfo(BaseModel):
    """Meilisearch server version metadata."""

    pkg_version: str = Field(description="Meilisearch server semver release version")
    commit_date: str | None = Field(default=None, description="Git commit date of the engine binary")
    commit_sha: str | None = Field(default=None, description="Git commit hash of the engine binary")


class MeiliHealthStatus(BaseModel):
    """Health check status and connectivity diagnostics for Meilisearch."""

    is_available: bool = Field(description="True if Meilisearch responds with HTTP 200 to /health")
    status: str = Field(default="unknown", description="Reported health status string (e.g., 'available')")
    host: str = Field(description="Target host URL configured for Meilisearch")
    version: str | None = Field(default=None, description="Engine version string if reachable")
    error_message: str | None = Field(default=None, description="Error details if connection failed")


class IndexStats(BaseModel):
    """Document and indexing statistics for a Meilisearch index."""

    index_uid: str = Field(description="Index identifier UID")
    is_indexing: bool = Field(default=False, description="True if background indexing task is running")
    number_of_documents: int = Field(default=0, description="Total indexed document count")
    field_distribution: dict[str, int] = Field(default_factory=dict, description="Field count distribution")


__all__ = [
    "SearchDocument",
    "MeiliVersionInfo",
    "MeiliHealthStatus",
    "IndexStats",
]
