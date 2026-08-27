"""Panopticon Google Drive Authentication Package."""

from app.core.auth.base import DEFAULT_DRIVE_SCOPES, DriveAuthProvider
from app.core.auth.exceptions import (
    AuthConfigurationError,
    AuthError,
    ConsentFlowError,
    DrivePermissionDeniedError,
    DriveQuotaExceededError,
    DriveRateLimitError,
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
    "DrivePermissionDeniedError",
    "DriveQuotaExceededError",
    "DriveRateLimitError",
    "MissingCredentialsFileError",
    "MissingServiceAccountFileError",
    "PersonalOAuthProvider",
    "TokenRefreshError",
    "get_auth_provider",
]
