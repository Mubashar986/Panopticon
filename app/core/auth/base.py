"""Abstract Base Classes and Interfaces for Google Drive Authentication Providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from google.auth.credentials import Credentials

# Canonical Read-Only Scopes for Panopticon Search Indexing
DEFAULT_DRIVE_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.labels.readonly",
]


class DriveAuthProvider(ABC):
    """Abstract interface defining the contract for Google Drive credential providers."""

    def __init__(self, scopes: list[str] | None = None) -> None:
        self._scopes = scopes if scopes is not None else list(DEFAULT_DRIVE_SCOPES)

    @property
    def scopes(self) -> list[str]:
        """Return the list of requested OAuth/API authorization scopes."""
        return self._scopes

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return human-readable identifier for diagnostics and logging."""

    @abstractmethod
    def get_credentials(self) -> Credentials:
        """Acquire, refresh if necessary, and return valid Google authentication credentials.

        Returns:
            google.auth.credentials.Credentials: Valid authorized credentials instance.

        Raises:
            AuthError: If credential acquisition, refresh, or authorization fails.
        """
