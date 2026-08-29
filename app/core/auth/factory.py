"""Central Factory for Instantiating Configured Google Drive Auth Providers."""

from __future__ import annotations

from app.core.auth.base import DriveAuthProvider
from app.core.auth.exceptions import AuthConfigurationError
from app.core.auth.oauth import PersonalOAuthProvider
from app.core.auth.service_account import DomainWideDelegationProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("panopticon.auth.factory")

_runtime_mode_override: str | None = None
_runtime_delegated_email_override: str | None = None
_cached_provider: DriveAuthProvider | None = None


def set_runtime_auth_mode(mode: str, delegated_user_email: str | None = None) -> None:
    """Dynamically switch the active Google Drive auth mode at runtime without restarting.

    Args:
        mode: 'oauth' or 'service_account'
        delegated_user_email: Optional Google Workspace user email to impersonate
    """
    global _runtime_mode_override, _runtime_delegated_email_override, _cached_provider
    normalized_mode = mode.lower().strip()
    if normalized_mode not in ("oauth", "service_account"):
        raise AuthConfigurationError(
            f"Unsupported DRIVE_AUTH_MODE: '{mode}'. Allowed values are 'oauth' or 'service_account'."
        )
    _runtime_mode_override = normalized_mode
    _runtime_delegated_email_override = delegated_user_email
    _cached_provider = None
    logger.info(
        "Runtime auth mode dynamically switched to '%s' (Delegated email: %s)",
        normalized_mode,
        delegated_user_email,
    )


def get_runtime_auth_mode(settings: Settings | None = None) -> str:
    """Return the currently effective auth mode string ('oauth' or 'service_account')."""
    if _runtime_mode_override is not None:
        return _runtime_mode_override
    cfg = settings or get_settings()
    return cfg.DRIVE_AUTH_MODE.lower() if cfg.DRIVE_AUTH_MODE else "oauth"


def reset_auth_provider() -> None:
    """Flush any cached credentials or provider instance to force fresh evaluation."""
    global _cached_provider
    _cached_provider = None
    logger.debug("DriveAuthProvider cache flushed.")


def get_auth_provider(settings: Settings | None = None) -> DriveAuthProvider:
    """Factory function returning the configured DriveAuthProvider instance.

    Reads DRIVE_AUTH_MODE from application settings or runtime overrides to instantiate
    either PersonalOAuthProvider or DomainWideDelegationProvider.

    Args:
        settings: Optional Settings instance. If omitted, uses global get_settings().

    Returns:
        DriveAuthProvider: Concrete provider ready for credential retrieval.

    Raises:
        AuthConfigurationError: If DRIVE_AUTH_MODE is invalid.
    """
    global _cached_provider

    if settings is not None:
        # Explicit settings passed (e.g. in unit tests) — instantiate directly without caching
        mode = settings.DRIVE_AUTH_MODE.lower() if settings.DRIVE_AUTH_MODE else "oauth"
        delegated_email = settings.GOOGLE_DELEGATED_USER_EMAIL
        if mode == "oauth":
            return PersonalOAuthProvider(
                credentials_path=settings.GOOGLE_CLIENT_SECRETS_FILE,
                token_path=settings.GOOGLE_TOKEN_CACHE_FILE,
            )
        elif mode == "service_account":
            return DomainWideDelegationProvider(
                service_account_path=settings.GOOGLE_SERVICE_ACCOUNT_FILE,
                subject_email=delegated_email,
            )
        else:
            raise AuthConfigurationError(
                f"Unsupported DRIVE_AUTH_MODE: '{mode}'. Allowed values are 'oauth' or 'service_account'."
            )

    if _cached_provider is not None:
        return _cached_provider

    cfg = get_settings()
    mode = get_runtime_auth_mode(cfg)
    delegated_email = _runtime_delegated_email_override or cfg.GOOGLE_DELEGATED_USER_EMAIL

    logger.debug("Resolving DriveAuthProvider for mode: '%s'", mode)

    provider: DriveAuthProvider
    if mode == "oauth":
        provider = PersonalOAuthProvider(
            credentials_path=cfg.GOOGLE_CLIENT_SECRETS_FILE,
            token_path=cfg.GOOGLE_TOKEN_CACHE_FILE,
        )
    elif mode == "service_account":
        provider = DomainWideDelegationProvider(
            service_account_path=cfg.GOOGLE_SERVICE_ACCOUNT_FILE,
            subject_email=delegated_email,
        )
    else:
        raise AuthConfigurationError(
            f"Unsupported DRIVE_AUTH_MODE: '{mode}'. Allowed values are 'oauth' or 'service_account'."
        )

    _cached_provider = provider
    return provider
