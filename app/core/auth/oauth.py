"""Personal OAuth 2.0 Authentication Provider with Local Caching and Auto-Refresh."""

from __future__ import annotations

import json
from pathlib import Path

from google.auth.credentials import Credentials
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuth2Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.core.auth.base import DriveAuthProvider
from app.core.auth.exceptions import (
    AuthError,
    ConsentFlowError,
    MissingCredentialsFileError,
)
from app.core.logging import get_logger

logger = get_logger("panopticon.auth.oauth")


class PersonalOAuthProvider(DriveAuthProvider):
    """Manages personal Google account OAuth 2.0 credentials for desktop development.

    Handles offline token caching in `token.json`, automatic refresh on expiration,
    and fallback to browser consent via `InstalledAppFlow` on dynamic loopback.
    """

    def __init__(
        self,
        credentials_path: Path | str = "credentials.json",
        token_path: Path | str = "token.json",
        scopes: list[str] | None = None,
    ) -> None:
        super().__init__(scopes=scopes)
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)

    @property
    def provider_name(self) -> str:
        return "PersonalOAuthProvider"

    def get_credentials(self) -> Credentials:
        """Acquire and return valid Google OAuth2 user credentials."""
        creds: OAuth2Credentials | None = None

        # 1. Attempt loading from cached token file
        if self.token_path.exists():
            logger.debug("Loading cached OAuth credentials from %s", self.token_path)
            try:
                creds = OAuth2Credentials.from_authorized_user_file(
                    str(self.token_path), self.scopes
                )
            except (GoogleAuthError, json.JSONDecodeError, OSError, ValueError) as e:
                logger.warning(
                    "Failed to parse cached token file at %s (%s). Will re-authenticate.",
                    self.token_path,
                    e,
                )
                creds = None

        # 2. Check validity and perform automatic token refresh if needed
        if creds and creds.valid:
            logger.debug("Using valid cached OAuth credentials.")
            return creds

        if creds and creds.expired and creds.refresh_token:
            logger.info("Cached OAuth access token expired. Refreshing token via Google...")
            try:
                creds.refresh(Request())
                self._save_token(creds)
                logger.info("OAuth access token refreshed and cached successfully.")
                return creds
            except (RefreshError, GoogleAuthError, OSError) as err:
                logger.warning(
                    "Failed to refresh OAuth token: %s. Initiating interactive consent flow.",
                    err,
                )
                # Fall through to re-authenticate via browser

        # 3. Interactive Consent Flow (Initial run or after token invalidation)
        if not self.credentials_path.exists():
            logger.error("OAuth client secrets file not found at: %s", self.credentials_path)
            raise MissingCredentialsFileError(self.credentials_path)

        logger.info(
            "Launching browser consent flow for personal Google account authorization..."
        )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                scopes=self.scopes,
            )
            # Run local loopback server with access_type='offline' to guarantee a refresh_token
            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )
            self._save_token(creds)
            logger.info("Authorization successful. Credentials cached to %s", self.token_path)
            return creds
        except Exception as e:
            if isinstance(e, AuthError):
                raise
            logger.error("OAuth consent flow failed: %s", e)
            raise ConsentFlowError(
                f"Failed to complete OAuth consent flow: {e}"
            ) from e

    def _save_token(self, creds: OAuth2Credentials) -> None:
        """Atomically persist authorized credentials JSON to token cache path."""
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
        except OSError as e:
            logger.error("Failed to write token cache to %s: %s", self.token_path, e)
            raise AuthError(f"Failed to write credentials token file: {e}") from e
