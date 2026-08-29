"""Panopticon API Pydantic validation schemas and response contracts."""

from app.api.schemas.auth import (
    AuthConfigResponse,
    AuthMode,
    AuthSwitchRequest,
    AuthSwitchResponse,
    CredentialUploadResponse,
    OAuthCallbackResponse,
    OAuthStartResponse,
)
from app.api.schemas.health import HealthResponse, SystemStatusResponse
from app.api.schemas.search import SearchItemResponse, SearchResponse
from app.api.schemas.sync import (
    ReindexResponse,
    SyncMode,
    SyncPhase,
    SyncStats,
    SyncStatusResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
)

__all__ = [
    "AuthConfigResponse",
    "AuthMode",
    "AuthSwitchRequest",
    "AuthSwitchResponse",
    "CredentialUploadResponse",
    "HealthResponse",
    "OAuthCallbackResponse",
    "OAuthStartResponse",
    "ReindexResponse",
    "SearchItemResponse",
    "SearchResponse",
    "SyncMode",
    "SyncPhase",
    "SyncStats",
    "SyncStatusResponse",
    "SyncTriggerRequest",
    "SyncTriggerResponse",
    "SystemStatusResponse",
]
