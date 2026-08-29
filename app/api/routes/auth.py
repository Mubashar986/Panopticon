"""Route handlers for Google Drive authentication setup, OAuth consent, and credential management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.api.deps import CurrentUser
from app.api.schemas.auth import (
    AuthConfigResponse,
    AuthSwitchRequest,
    AuthSwitchResponse,
    CredentialUploadResponse,
    OAuthCallbackResponse,
    OAuthStartResponse,
)
from app.core.auth.base import DEFAULT_DRIVE_SCOPES
from app.core.auth.factory import (
    get_runtime_auth_mode,
    reset_auth_provider,
    set_runtime_auth_mode,
)
from app.core.config import get_settings

logger = logging.getLogger("panopticon.api.routes.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication & Credentials"])

# In-memory OAuth state registry for CSRF protection
_oauth_states: set[str] = set()


@router.get(
    "/config",
    response_model=AuthConfigResponse,
    summary="Get Authentication Configuration & Token Validity",
    description=(
        "Inspects active Drive auth mode, presence of credentials.json / token.json / "
        "service_account.json on disk, and current OAuth token validity/expiration timestamp."
    ),
)
async def get_auth_config(current_user: CurrentUser) -> AuthConfigResponse:
    """Query current Google Drive authentication status."""
    settings = get_settings()
    active_mode = get_runtime_auth_mode(settings)

    secrets_path = Path(settings.GOOGLE_CLIENT_SECRETS_FILE).resolve()
    token_path = Path(settings.GOOGLE_TOKEN_CACHE_FILE).resolve()
    sa_path = Path(settings.GOOGLE_SERVICE_ACCOUNT_FILE).resolve()

    secrets_found = secrets_path.exists()
    token_found = token_path.exists()
    sa_found = sa_path.exists()

    token_valid = False
    token_expired = False
    token_expiry_str: str | None = None

    if token_found:
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_path),
                scopes=DEFAULT_DRIVE_SCOPES,
            )
            token_valid = bool(creds.valid)
            token_expired = bool(creds.expired)
            if creds.expiry:
                token_expiry_str = creds.expiry.isoformat()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed inspecting cached token: %s", exc)

    return AuthConfigResponse(
        auth_mode=active_mode,  # type: ignore[arg-type]
        client_secrets_path=str(secrets_path),
        client_secrets_found=secrets_found,
        token_cache_path=str(token_path),
        token_cache_found=token_found,
        token_valid=token_valid,
        token_expired=token_expired,
        token_expiry=token_expiry_str,
        service_account_path=str(sa_path),
        service_account_found=sa_found,
        delegated_user_email=settings.GOOGLE_DELEGATED_USER_EMAIL,
        scopes=list(DEFAULT_DRIVE_SCOPES),
    )


@router.post(
    "/config",
    response_model=AuthSwitchResponse,
    summary="Hot-Switch Active Auth Mode",
    description="Switches the active Google Drive auth provider between 'oauth' and 'service_account' on the fly.",
)
async def switch_auth_mode(
    request: AuthSwitchRequest,
    current_user: CurrentUser,
) -> AuthSwitchResponse:
    """Hot-switch active Drive auth mode without restarting server."""
    try:
        set_runtime_auth_mode(request.auth_mode, request.delegated_user_email)
        return AuthSwitchResponse(
            status="switched",
            auth_mode=request.auth_mode,
            delegated_user_email=request.delegated_user_email,
            message=f"Drive authentication provider switched to '{request.auth_mode}'.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to switch auth mode: {exc}",
        ) from exc


@router.post(
    "/oauth/start",
    response_model=OAuthStartResponse,
    summary="Initiate Google OAuth2 Consent Flow",
    description="Generates an authorization URL and CSRF state token for user consent in the browser.",
)
async def start_oauth_flow(
    current_user: CurrentUser,
    redirect_uri: str | None = None,
) -> OAuthStartResponse:
    """Generate Google OAuth authorization URL."""
    settings = get_settings()
    secrets_path = Path(settings.GOOGLE_CLIENT_SECRETS_FILE).resolve()

    if not secrets_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Client secrets file '{settings.GOOGLE_CLIENT_SECRETS_FILE}' is missing on server. "
                "Please upload credentials.json before initiating OAuth flow."
            ),
        )

    callback_url = (
        redirect_uri
        or f"http://{settings.API_HOST}:{settings.API_PORT}/api/auth/oauth/callback"
    )

    try:
        flow = Flow.from_client_secrets_file(
            str(secrets_path),
            scopes=DEFAULT_DRIVE_SCOPES,
            redirect_uri=callback_url,
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        _oauth_states.add(state)

        logger.info("Generated OAuth authorization URL for user [%s]", current_user.email)
        return OAuthStartResponse(
            authorization_url=auth_url,
            state=state,
            redirect_uri=callback_url,
        )
    except Exception as exc:
        logger.exception("Failed creating OAuth flow")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Google OAuth authorization flow: {exc}",
        ) from exc


@router.get(
    "/oauth/callback",
    summary="Google OAuth2 Redirect Callback Handler",
    description="Exchanges the authorization code for offline tokens, writes token.json, and closes popup.",
)
async def oauth_callback(
    code: str = Query(..., description="Google OAuth authorization code"),
    state: str | None = Query(default=None, description="CSRF state token"),
    raw_json: bool = Query(default=False, description="If True, returns JSON instead of auto-closing HTML"),
) -> Any:
    """Handle Google OAuth callback redirect and persist token."""
    settings = get_settings()
    secrets_path = Path(settings.GOOGLE_CLIENT_SECRETS_FILE).resolve()
    callback_url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/auth/oauth/callback"

    if not secrets_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client secrets file is missing on server.",
        )

    try:
        flow = Flow.from_client_secrets_file(
            str(secrets_path),
            scopes=DEFAULT_DRIVE_SCOPES,
            redirect_uri=callback_url,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        token_path = Path(settings.GOOGLE_TOKEN_CACHE_FILE).resolve()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

        # Invalidate provider cache to pick up new tokens immediately
        reset_auth_provider()
        logger.info("Successfully exchanged and saved OAuth token to %s", token_path)

        if raw_json:
            return OAuthCallbackResponse(
                status="authenticated",
                message="Google OAuth token acquired and saved successfully.",
                token_saved=True,
            )

        html_content = """<!DOCTYPE html>
<html>
<head><title>Panopticon - Google Auth Success</title></head>
<body style="font-family: system-ui, sans-serif; text-align: center; padding: 40px; background: #0f172a; color: #f8fafc;">
  <h2 style="color: #22c55e;">✓ Google Drive Connected Successfully!</h2>
  <p>Your OAuth token has been saved. You can close this window now.</p>
  <script>
    if (window.opener) {
      window.opener.postMessage({ type: 'PANOPTICON_OAUTH_SUCCESS' }, '*');
      setTimeout(() => window.close(), 1200);
    }
  </script>
</body>
</html>"""
        return HTMLResponse(content=html_content, status_code=200)

    except Exception as exc:
        logger.exception("Failed exchanging OAuth code for tokens")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth code exchange failed: {exc}",
        ) from exc


@router.post(
    "/credentials/upload",
    response_model=CredentialUploadResponse,
    summary="Upload Client Secrets or Service Account Key",
    description="Accepts JSON file upload for credentials.json (OAuth) or service_account.json (DWD).",
)
async def upload_credentials_file(
    current_user: CurrentUser,
    file: UploadFile,
) -> CredentialUploadResponse:
    """Upload and save credentials.json or service_account.json directly from the UI."""
    settings = get_settings()

    try:
        content_bytes = await file.read()
        parsed_json = json.loads(content_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file is not a valid JSON document: {exc}",
        ) from exc

    # Identify file type
    if "web" in parsed_json or "installed" in parsed_json:
        file_type = "credentials"
        target_path = Path(settings.GOOGLE_CLIENT_SECRETS_FILE).resolve()
        message = "OAuth Client Secrets (credentials.json) saved successfully."
    elif parsed_json.get("type") == "service_account":
        file_type = "service_account"
        target_path = Path(settings.GOOGLE_SERVICE_ACCOUNT_FILE).resolve()
        message = "Service Account Key (service_account.json) saved successfully."
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unrecognized Google credentials JSON structure. Expected OAuth client secrets "
                "(with 'web' or 'installed' root) or Service Account key (with 'type': 'service_account')."
            ),
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content_bytes)

    # Invalidate provider cache so changes take effect immediately
    reset_auth_provider()
    logger.info("Saved uploaded %s to %s by user [%s]", file_type, target_path, current_user.email)

    return CredentialUploadResponse(
        status="saved",
        file_type=file_type,
        saved_path=str(target_path),
        message=message,
    )
