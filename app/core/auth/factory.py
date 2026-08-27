"""Central Factory for Instantiating Configured Google Drive Auth Providers."""

from __future__ import annotations

from app.core.auth.base import DriveAuthProvider
from app.core.auth.exceptions import AuthConfigurationError
from app.core.auth.oauth import PersonalOAuthProvider
from app.core.auth.service_account import DomainWideDelegationProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("panopticon.auth.factory")


def get_auth_provider(settings: Settings | None = None) -> DriveAuthProvider:
    """Factory function returning the configured DriveAuthProvider instance.

    Reads DRIVE_AUTH_MODE from application settings to instantiate either
    PersonalOAuthProvider or DomainWideDelegationProvider.

    Args:
        settings: Optional Settings instance. If omitted, uses global get_settings().

    Returns:
        DriveAuthProvider: Concrete provider ready for credential retrieval.

    Raises:
        AuthConfigurationError: If DRIVE_AUTH_MODE is invalid.
    """
    cfg = settings or get_settings()
    mode = cfg.DRIVE_AUTH_MODE.lower() if cfg.DRIVE_AUTH_MODE else "oauth"

    logger.debug("Resolving DriveAuthProvider for mode: '%s'", mode)

    if mode == "oauth":
        return PersonalOAuthProvider(
            credentials_path=cfg.GOOGLE_CLIENT_SECRETS_FILE,
            token_path=cfg.GOOGLE_TOKEN_CACHE_FILE,
        )
    elif mode == "service_account":
        return DomainWideDelegationProvider(
            service_account_path=cfg.GOOGLE_SERVICE_ACCOUNT_FILE,
            subject_email=cfg.GOOGLE_DELEGATED_USER_EMAIL,
        )
    else:
        raise AuthConfigurationError(
            f"Unsupported DRIVE_AUTH_MODE: '{mode}'. Allowed values are 'oauth' or 'service_account'."
        )
