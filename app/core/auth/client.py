"""Google Drive API Client Construction & Resource Factory."""

from __future__ import annotations

from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from app.core.auth.base import DriveAuthProvider
from app.core.auth.exceptions import (
    AuthError,
    DrivePermissionDeniedError,
    DriveQuotaExceededError,
    DriveRateLimitError,
)
from app.core.auth.factory import get_auth_provider
from app.core.logging import get_logger

logger = get_logger("panopticon.auth.client")


def build_drive_service(provider: DriveAuthProvider | None = None) -> Resource:
    """Construct and return an authorized Google Drive v3 Resource service object.

    Args:
        provider: Optional DriveAuthProvider instance. If None, uses default get_auth_provider().

    Returns:
        Resource: Initialized Google Drive v3 API service resource.

    Raises:
        AuthError: If credentials cannot be acquired or service initialization fails.
    """
    auth_provider = provider or get_auth_provider()
    logger.debug(
        "Building Google Drive v3 client with provider: %s", auth_provider.provider_name
    )

    try:
        credentials = auth_provider.get_credentials()
        # cache_discovery=False avoids file cache deprecation warnings in googleapiclient
        service: Resource = build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
        logger.debug("Google Drive v3 API resource constructed successfully.")
        return service
    except HttpError as http_err:
        status = http_err.resp.status
        content_str = (
            http_err.content.decode("utf-8", errors="ignore")
            if getattr(http_err, "content", None)
            else ""
        )
        error_context = f"{http_err._get_reason()} {content_str} {http_err}".lower()

        logger.error("Google Drive API HTTP error %d: %s", status, error_context)

        if status == 429 or "ratelimit" in error_context or "user_rate_limit" in error_context:
            raise DriveRateLimitError(
                f"Google Drive API rate limit reached: {content_str or http_err._get_reason()}"
            ) from http_err
        elif status == 403:
            if "quota" in error_context or "dailylimit" in error_context:
                raise DriveQuotaExceededError(
                    f"Google Drive API quota exhausted: {content_str or http_err._get_reason()}"
                ) from http_err
            raise DrivePermissionDeniedError(
                f"Google Drive permission denied: {content_str or http_err._get_reason()}"
            ) from http_err
        raise AuthError(
            f"Google Drive API communication error ({status}): {content_str or http_err._get_reason()}"
        ) from http_err
    except AuthError:
        raise
    except Exception as e:
        logger.error("Unexpected error constructing Google Drive service: %s", e)
        raise AuthError(f"Failed to build Google Drive API service: {e}") from e
