"""Health and system diagnostics API response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Liveness probe response model."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="ok", description="Liveness status of the API server")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of the health check")
    auth_mode: str = Field(..., description="Active Drive authentication provider mode")


class SystemStatusResponse(BaseModel):
    """Deep diagnostic system status response model."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="Overall system health status ('healthy', 'degraded', 'unhealthy')")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    auth_mode: str = Field(..., description="Active Drive authentication mode")
    api_endpoint: str = Field(..., description="Base API endpoint URL")
    meilisearch_connected: bool = Field(..., description="True if Meilisearch engine is reachable")
    meilisearch_health: str = Field(..., description="Meilisearch status string or error summary")
    meilisearch_host: str = Field(..., description="Configured Meilisearch host URL")
    index_name: str = Field(..., description="Configured default search index UID")
    document_count: int = Field(default=0, description="Total indexed document count in search index")
    is_indexing: bool = Field(default=False, description="True if search index is currently building")
    is_managed_process: bool = Field(default=False, description="True if Meilisearch process is actively supervised by FastAPI")
    process_pid: int | None = Field(default=None, description="Operating system PID of the managed Meilisearch child process")
    details: dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic metrics and metadata")
