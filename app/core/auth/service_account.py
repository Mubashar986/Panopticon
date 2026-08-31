"""Enterprise Service Account Provider with Domain-Wide Delegation (DWD) Impersonation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from google.auth.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account

from app.core.auth.base import DriveAuthProvider
from app.core.auth.exceptions import (
    AuthError,
    MissingServiceAccountFileError,
)
from app.core.logging import get_logger

logger = get_logger("panopticon.auth.service_account")


class DomainWideDelegationProvider(DriveAuthProvider):
    """Manages enterprise Google Service Account credentials with optional user impersonation.

    Loads cryptographic RSA private keys from `service_account.json` and supports
    Domain-Wide Delegation by assuming the identity of a target Workspace user
    via `with_subject(email)`.
    """

    def __init__(
        self,
        service_account_path: Path | str = "service_account.json",
        subject_email: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        super().__init__(scopes=scopes)
        self.service_account_path = Path(service_account_path)
        self.subject_email = subject_email

    @property
    def provider_name(self) -> str:
        return "DomainWideDelegationProvider"

    @property
    def is_authenticated(self) -> bool:
        """Check if service account file exists and is readable."""
        return self.service_account_path.exists()

    def get_credentials(self) -> Credentials:

        """Load and return valid Google Service Account credentials with delegation if configured."""
        if not self.service_account_path.exists():
            logger.error("Service Account key file not found at: %s", self.service_account_path)
            raise MissingServiceAccountFileError(self.service_account_path)

        logger.debug(
            "Loading Service Account credentials from %s (Scopes: %s)",
            self.service_account_path,
            self.scopes,
        )
        try:
            creds: service_account.Credentials = (
                service_account.Credentials.from_service_account_file(
                    str(self.service_account_path),
                    scopes=self.scopes,
                )
            )

            if self.subject_email:
                logger.info(
                    "Applying Domain-Wide Delegation subject impersonation for: %s",
                    self.subject_email,
                )
                creds = creds.with_subject(self.subject_email)

            return cast(Credentials, creds)
        except (GoogleAuthError, OSError, ValueError) as e:
            logger.error("Failed to initialize Service Account credentials: %s", e)
            raise AuthError(
                f"Failed to load Service Account credentials from {self.service_account_path}: {e}"
            ) from e
