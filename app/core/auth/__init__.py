"""Panopticon Google Drive Authentication Package."""

from app.core.auth.base import DEFAULT_DRIVE_SCOPES, DriveAuthProvider
from app.core.auth.client import build_drive_service
from app.core.auth.exceptions import (
    AuthConfigurationError,
    AuthError,
    ConsentFlowError,
    DriveConnectionError,
    DriveNetworkError,
    DrivePermissionDeniedError,
    DriveQuotaExceededError,
    DriveRateLimitError,
    DriveTimeoutError,
    MissingCredentialsFileError,
    MissingServiceAccountFileError,
    TokenRefreshError,
)
from app.core.auth.factory import get_auth_provider
from app.core.auth.oauth import PersonalOAuthProvider
from app.core.auth.service_account import DomainWideDelegationProvider

__all__ = [
    "DEFAULT_DRIVE_SCOPES",
    "AuthConfigurationError",
    "AuthError",
    "ConsentFlowError",
    "DomainWideDelegationProvider",
    "DriveAuthProvider",
    "DriveConnectionError",
    "DriveNetworkError",
    "DrivePermissionDeniedError",
    "DriveQuotaExceededError",
    "DriveRateLimitError",
    "DriveTimeoutError",
    "MissingCredentialsFileError",
    "MissingServiceAccountFileError",
    "PersonalOAuthProvider",
    "TokenRefreshError",
    "build_drive_service",
    "get_auth_provider",
]
