"""Custom Authentication and API Exception Hierarchy for Panopticon.

Provides explicit, typed exceptions with developer-friendly remediation
guidance, actionable setup cards, rate limit handling, and quota tracking.
"""

from __future__ import annotations

from pathlib import Path


class AuthError(Exception):
    """Base exception for all Panopticon authentication and authorization errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\nDetails: {self.details}"
        return self.message


class AuthConfigurationError(AuthError):
    """Raised when authentication settings or configuration parameters are invalid."""



class MissingCredentialsFileError(AuthError):
    """Raised when OAuth client secrets file (credentials.json) cannot be located."""

    def __init__(self, file_path: Path | str) -> None:
        path_str = str(file_path)
        action_card = (
            f"\n"
            f"================================================================================\n"
            f" DEVELOPER ACTION CARD: Missing Google OAuth Client Secrets\n"
            f"================================================================================\n"
            f" Expected file location : {path_str}\n"
            f"\n"
            f" Quick Setup Instructions:\n"
            f" 1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials\n"
            f" 2. Select or create your project.\n"
            f" 3. Enable 'Google Drive API' in Enabled APIs & Services.\n"
            f" 4. Click 'Create Credentials' -> 'OAuth client ID'.\n"
            f" 5. Select Application Type: 'Desktop App'.\n"
            f" 6. Download the generated client secrets JSON.\n"
            f" 7. Rename and save it as '{path_str}' in your project root.\n"
            f"================================================================================\n"
        )
        super().__init__(
            message=f"Google OAuth client secrets file not found: {path_str}",
            details=action_card,
        )
        self.file_path = Path(path_str)


class MissingServiceAccountFileError(AuthError):
    """Raised when Service Account JSON key file cannot be located."""

    def __init__(self, file_path: Path | str) -> None:
        path_str = str(file_path)
        action_card = (
            f"\n"
            f"================================================================================\n"
            f" DEVELOPER ACTION CARD: Missing Service Account Credentials\n"
            f"================================================================================\n"
            f" Expected file location : {path_str}\n"
            f"\n"
            f" Quick Setup Instructions:\n"
            f" 1. Go to Google Cloud Console: https://console.cloud.google.com/iam-admin/serviceaccounts\n"
            f" 2. Select or create a Service Account.\n"
            f" 3. Click 'Keys' -> 'Add Key' -> 'Create new key' (JSON).\n"
            f" 4. Download and save the JSON file to '{path_str}' in your project root.\n"
            f" 5. If using Domain-Wide Delegation, ensure Client ID is authorized in\n"
            f"    Google Workspace Admin Console (Security > API Controls > Domain-Wide Delegation).\n"
            f"================================================================================\n"
        )
        super().__init__(
            message=f"Google Service Account key file not found: {path_str}",
            details=action_card,
        )
        self.file_path = Path(path_str)


class TokenRefreshError(AuthError):
    """Raised when an expired OAuth access token cannot be refreshed."""



class ConsentFlowError(AuthError):
    """Raised when interactive OAuth2 user consent loop fails or is cancelled."""



class DriveRateLimitError(AuthError):
    """Raised when Google Drive API rate limits (HTTP 429 / userRateLimitExceeded) are encountered."""

    def __init__(
        self,
        message: str = "Google Drive API rate limit exceeded. Please back off before retrying.",
        retry_after_seconds: float = 60.0,
        details: str | None = None,
    ) -> None:
        super().__init__(message, details)
        self.retry_after_seconds = retry_after_seconds


class DriveQuotaExceededError(AuthError):
    """Raised when Google Drive project or daily API quota is exhausted."""

    def __init__(
        self,
        message: str = "Google Drive API daily/project quota exhausted (quotaExceeded).",
        details: str | None = None,
    ) -> None:
        super().__init__(message, details)


class DrivePermissionDeniedError(AuthError):
    """Raised when the authenticated entity lacks permission to access requested Drive scopes."""

    def __init__(
        self,
        message: str = "Permission denied for requested Google Drive resource or scope.",
        details: str | None = None,
    ) -> None:
        super().__init__(message, details)
