"""Route handlers for Google Drive authentication setup, OAuth consent, and credential management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.api.deps import CurrentUser
from app.api.schemas.auth import (
    AuthConfigResponse,
    AuthSwitchRequest,
    AuthSwitchResponse,
    CredentialUploadResponse,
    GoogleLoginResponse,
    OAuthCallbackResponse,
    OAuthStartResponse,
    WorkspaceDWDManifestResponse,
    WorkspaceDWDStatusResponse,
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


OAUTH_SUCCESS_HTML = """<!DOCTYPE html>
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

OAUTH_ERROR_HTML = """<!DOCTYPE html>
<html>
<head><title>Panopticon - Google Auth Cancelled</title></head>
<body style="font-family: system-ui, sans-serif; text-align: center; padding: 40px; background: #0f172a; color: #f8fafc;">
  <h2 style="color: #ef4444;">✗ Google Drive Connection Cancelled</h2>
  <p>{error_detail}</p>
  <script>
    if (window.opener) {
      window.opener.postMessage({ type: 'PANOPTICON_OAUTH_FAILED', error: '{error_detail}' }, '*');
      setTimeout(() => window.close(), 2500);
    }
  </script>
</body>
</html>"""


def _get_oauth_flow(redirect_uri: str) -> tuple[Flow, str]:
    """Construct google_auth_oauthlib Flow from either ENV variables or credentials.json.

    Returns:
        (flow_instance, client_source) where client_source is 'environment' or 'credentials_file'.
    Raises:
        HTTPException(400) if neither source is configured.
    """
    settings = get_settings()

    # 1. First priority: Environment variables (Zero-file setup for hosted/container environments)
    if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=DEFAULT_DRIVE_SCOPES,
            redirect_uri=redirect_uri,
        )
        return flow, "environment"

    # 2. Second priority: credentials.json file on disk
    secrets_path = Path(settings.GOOGLE_CLIENT_SECRETS_FILE).resolve()
    if secrets_path.exists():
        flow = Flow.from_client_secrets_file(
            str(secrets_path),
            scopes=DEFAULT_DRIVE_SCOPES,
            redirect_uri=redirect_uri,
        )
        return flow, "credentials_file"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Google OAuth credentials missing. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET "
            f"in your .env file, or upload '{settings.GOOGLE_CLIENT_SECRETS_FILE}' before initiating authorization."
        ),
    )


# -----------------------------------------------------------------------------
# 1-Click Hosted Web OAuth 2.0 Endpoints (Task 10.3)
# -----------------------------------------------------------------------------


@router.get(
    "/google/login",
    summary="1-Click Hosted Google Drive OAuth Login",
    description="Generates CSRF state and redirects user directly to Google consent screen, or returns authorization URL JSON.",
)
async def google_login(
    redirect: bool = Query(
        default=False,
        description="If True, immediately returns HTTP 307 redirect to Google consent screen (ideal for direct links/popups). If False, returns JSON.",
    ),
    redirect_uri: str | None = Query(
        default=None,
        description="Optional redirect callback URI override",
    ),
) -> Any:
    """Initiate 1-Click Hosted Google OAuth 2.0 flow."""
    settings = get_settings()
    callback_url = (
        redirect_uri
        or settings.GOOGLE_REDIRECT_URI
        or f"http://{settings.API_HOST}:{settings.API_PORT}/api/auth/google/callback"
    )

    flow, client_source = _get_oauth_flow(callback_url)

    state = secrets.token_urlsafe(32)
    _oauth_states.add(state)

    auth_url, _ = flow.authorization_url(
        state=state,
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    logger.info("Initiated 1-Click Google OAuth flow (source: %s, state: %s...)", client_source, state[:8])

    if redirect:
        return RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return GoogleLoginResponse(
        authorization_url=auth_url,
        state=state,
        redirect_uri=callback_url,
        client_source=client_source,
    )


@router.get(
    "/google/callback",
    summary="Google OAuth2 Redirect Callback Handler",
    description="Validates state token, exchanges code for credentials, persists token.json, hot-swaps auth provider, and returns auto-closing HTML.",
)
async def google_callback(
    code: str | None = Query(default=None, description="Google OAuth authorization code"),
    state: str | None = Query(default=None, description="CSRF state token"),
    error: str | None = Query(default=None, description="Error code if user denied consent"),
    raw_json: bool = Query(default=False, description="If True, returns JSON instead of auto-closing HTML"),
    redirect_uri: str | None = Query(default=None, description="Redirect URI used in initial authorization"),
) -> Any:
    """Exchange authorization code for user tokens and activate OAuth provider."""
    # 1. Check for user-denied error from Google
    if error:
        logger.warning("Google OAuth consent cancelled by user: %s", error)
        if raw_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google OAuth consent cancelled or denied: {error}",
            )
        err_msg = "Access was denied or cancelled during Google consent."
        return HTMLResponse(content=OAUTH_ERROR_HTML.format(error_detail=err_msg), status_code=200)

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'code' parameter in Google OAuth callback.",
        )

    # 2. Verify CSRF state token
    if not state or state not in _oauth_states:
        logger.warning("Rejected Google OAuth callback with invalid/missing state token: %s", state)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state token. Potential Cross-Site Request Forgery (CSRF).",
        )
    _oauth_states.discard(state)

    settings = get_settings()
    callback_url = (
        redirect_uri
        or settings.GOOGLE_REDIRECT_URI
        or f"http://{settings.API_HOST}:{settings.API_PORT}/api/auth/google/callback"
    )

    try:
        flow, _ = _get_oauth_flow(callback_url)
        flow.fetch_token(code=code)
        credentials = flow.credentials

        token_path = Path(settings.GOOGLE_TOKEN_CACHE_FILE).resolve()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

        # Invalidate provider cache & switch runtime mode to oauth
        set_runtime_auth_mode("oauth")
        reset_auth_provider()
        logger.info("Successfully exchanged and saved OAuth token to %s", token_path)

        if raw_json:
            return OAuthCallbackResponse(
                status="authenticated",
                message="Google OAuth token acquired and saved successfully.",
                token_saved=True,
            )

        return HTMLResponse(content=OAUTH_SUCCESS_HTML, status_code=200)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed exchanging OAuth code for tokens: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth code exchange failed: {exc}",
        ) from exc


# -----------------------------------------------------------------------------
# Google Workspace Marketplace & Domain-Wide Delegation Seam (Task 10.3)
# -----------------------------------------------------------------------------


@router.get(
    "/workspace/install",
    response_model=WorkspaceDWDManifestResponse,
    summary="Google Workspace Marketplace / DWD Admin Installation Manifest",
    description="Provides setup instructions, numeric client ID, and required OAuth scopes for Google Workspace Super Admins.",
)
async def get_workspace_install_manifest() -> WorkspaceDWDManifestResponse:
    """Retrieve setup manifest and scopes required for Google Workspace Domain-Wide Delegation."""
    settings = get_settings()
    sa_path = Path(settings.GOOGLE_SERVICE_ACCOUNT_FILE).resolve()

    client_id: str | None = None
    sa_email: str | None = None
    if sa_path.exists():
        try:
            sa_data = json.loads(sa_path.read_text(encoding="utf-8"))
            client_id = sa_data.get("client_id")
            sa_email = sa_data.get("client_email")
        except Exception:
            pass

    instructions = (
        "1. Open Google Workspace Admin Console (https://admin.google.com) > Security > Access and data control > API controls.\n"
        "2. In the 'Domain-wide delegation' pane, select 'Manage Domain Wide Delegation'.\n"
        "3. Click 'Add new', enter the Service Account Numeric Client ID, and paste the comma-delimited OAuth Scopes.\n"
        "4. Click 'Authorize'. Panopticon will now index authorized documents on behalf of users in your domain."
    )

    return WorkspaceDWDManifestResponse(
        application_name="Panopticon",
        client_id=client_id,
        service_account_email=sa_email,
        required_scopes=list(DEFAULT_DRIVE_SCOPES),
        admin_console_url="https://admin.google.com/ac/owl/domainwidedelegation",
        setup_instructions=instructions,
    )


@router.get(
    "/workspace/status",
    response_model=WorkspaceDWDStatusResponse,
    summary="Google Workspace Domain-Wide Delegation Diagnostic Status",
    description="Audits whether Service Account credentials and delegated user email are properly configured.",
)
async def get_workspace_dwd_status() -> WorkspaceDWDStatusResponse:
    """Audit Google Workspace Domain-Wide Delegation configuration."""
    settings = get_settings()
    sa_path = Path(settings.GOOGLE_SERVICE_ACCOUNT_FILE).resolve()

    sa_found = sa_path.exists()
    sa_email: str | None = None
    if sa_found:
        try:
            sa_data = json.loads(sa_path.read_text(encoding="utf-8"))
            sa_email = sa_data.get("client_email")
        except Exception:
            pass

    delegated_email = settings.GOOGLE_DELEGATED_USER_EMAIL

    if not sa_found:
        status_code = "missing_key"
        msg = f"Service Account key file '{settings.GOOGLE_SERVICE_ACCOUNT_FILE}' is missing on server."
    elif not delegated_email:
        status_code = "missing_delegated_user"
        msg = "Service Account key present, but GOOGLE_DELEGATED_USER_EMAIL is not configured in settings."
    else:
        status_code = "ready"
        msg = f"Domain-Wide Delegation configured for service account '{sa_email}' impersonating '{delegated_email}'."

    configured = (status_code == "ready")

    return WorkspaceDWDStatusResponse(
        configured=configured,
        service_account_found=sa_found,
        service_account_email=sa_email,
        delegated_user_email=delegated_email,
        scopes_authorized=list(DEFAULT_DRIVE_SCOPES),
        connectivity_status=status_code,
        message=msg,
    )


# -----------------------------------------------------------------------------
# Legacy Desktop Consent Flow Endpoints (Backward Compatibility)
# -----------------------------------------------------------------------------


@router.post(
    "/oauth/start",
    response_model=OAuthStartResponse,
    summary="Initiate Google OAuth2 Consent Flow (Legacy/Desktop)",
    description="Generates an authorization URL and CSRF state token for user consent in the browser.",
)
async def start_oauth_flow(
    current_user: CurrentUser,
    redirect_uri: str | None = None,
) -> OAuthStartResponse:
    """Generate Google OAuth authorization URL."""
    settings = get_settings()
    callback_url = (
        redirect_uri
        or f"http://{settings.API_HOST}:{settings.API_PORT}/api/auth/oauth/callback"
    )

    try:
        flow, _ = _get_oauth_flow(callback_url)
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed creating OAuth flow")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Google OAuth authorization flow: {exc}",
        ) from exc


@router.get(
    "/oauth/callback",
    summary="Google OAuth2 Redirect Callback Handler (Legacy)",
    description="Exchanges the authorization code for offline tokens, writes token.json, and closes popup.",
)
async def oauth_callback(
    code: str = Query(..., description="Google OAuth authorization code"),
    state: str | None = Query(default=None, description="CSRF state token"),
    raw_json: bool = Query(default=False, description="If True, returns JSON instead of auto-closing HTML"),
) -> Any:
    """Handle legacy Google OAuth callback redirect and persist token."""
    settings = get_settings()
    callback_url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/auth/oauth/callback"

    try:
        flow, _ = _get_oauth_flow(callback_url)
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

        return HTMLResponse(content=OAUTH_SUCCESS_HTML, status_code=200)

    except HTTPException:
        raise
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
