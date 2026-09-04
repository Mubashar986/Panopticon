"""Pydantic schemas and response contracts for Google Drive authentication management."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuthMode = Literal["oauth", "service_account"]


class AuthConfigResponse(BaseModel):
    """Status of configured Google Drive credentials, token validity, and active provider."""

    model_config = ConfigDict(frozen=True)

    auth_mode: AuthMode = Field(..., description="Active Drive authentication provider mode")
    client_secrets_path: str = Field(..., description="Configured path to credentials.json")
    client_secrets_found: bool = Field(..., description="True if credentials.json exists on disk")
    token_cache_path: str = Field(..., description="Configured path to token.json")
    token_cache_found: bool = Field(..., description="True if token.json exists on disk")
    token_valid: bool = Field(..., description="True if cached OAuth token is currently valid")
    token_expired: bool = Field(..., description="True if cached OAuth token has expired")
    token_expiry: str | None = Field(default=None, description="ISO 8601 UTC timestamp of token expiry")
    service_account_path: str = Field(..., description="Configured path to service_account.json")
    service_account_found: bool = Field(..., description="True if service_account.json exists on disk")
    delegated_user_email: str | None = Field(default=None, description="Workspace email for Domain-Wide Delegation")
    scopes: list[str] = Field(default_factory=list, description="Google Drive OAuth scopes required")


class AuthSwitchRequest(BaseModel):
    """Payload to hot-switch the active Drive auth mode without restarting server."""

    model_config = ConfigDict(frozen=True)

    auth_mode: AuthMode = Field(..., description="Target auth mode: 'oauth' or 'service_account'")
    delegated_user_email: str | None = Field(
        default=None, description="Optional Workspace user email when switching to service_account"
    )


class AuthSwitchResponse(BaseModel):
    """Response returned when active auth mode is successfully switched."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="switched", description="Status string: 'switched'")
    auth_mode: AuthMode = Field(..., description="New active Drive auth mode")
    delegated_user_email: str | None = Field(default=None, description="Delegated user email, if configured")
    message: str = Field(..., description="Confirmation message")


class OAuthStartResponse(BaseModel):
    """Google OAuth2 consent flow initiation payload."""

    model_config = ConfigDict(frozen=True)

    authorization_url: str = Field(..., description="Google consent screen URL for browser redirect")
    state: str = Field(..., description="CSRF protection state token")
    redirect_uri: str = Field(..., description="Authorized redirect callback URI")


class OAuthCallbackResponse(BaseModel):
    """Response returned after Google OAuth2 code exchange."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="authenticated", description="Status string: 'authenticated'")
    message: str = Field(..., description="Description of the authorization result")
    token_saved: bool = Field(..., description="True if token.json was successfully written")


class CredentialUploadResponse(BaseModel):
    """Response returned after uploading credential files."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="saved", description="Status string: 'saved'")
    file_type: str = Field(..., description="'credentials' (OAuth) or 'service_account' (DWD)")
    saved_path: str = Field(..., description="Path where file was stored")
    message: str = Field(..., description="Confirmation message")


class GoogleLoginResponse(BaseModel):
    """Payload returned when initiating the 1-Click Google OAuth flow."""

    model_config = ConfigDict(frozen=True)

    authorization_url: str = Field(..., description="Google consent screen URL for browser redirect")
    state: str = Field(..., description="CSRF protection state token")
    redirect_uri: str = Field(..., description="Authorized redirect callback URI")
    client_source: str = Field(..., description="Source of client credentials: 'environment' or 'credentials_file'")


class WorkspaceDWDManifestResponse(BaseModel):
    """Google Workspace Marketplace Admin installation manifest & DWD setup metadata."""

    model_config = ConfigDict(frozen=True)

    application_name: str = Field(default="Panopticon", description="Application name")
    client_id: str | None = Field(default=None, description="Numeric Client ID for Domain-Wide Delegation in Admin Console")
    service_account_email: str | None = Field(default=None, description="Service Account email address")
    required_scopes: list[str] = Field(default_factory=list, description="Google API scopes required for DWD installation")
    admin_console_url: str = Field(
        default="https://admin.google.com/ac/owl/domainwidedelegation",
        description="Direct URL to Google Workspace Admin Console Domain-Wide Delegation settings",
    )
    setup_instructions: str = Field(..., description="Step-by-step guidance for Google Workspace Super Admins")


class WorkspaceDWDStatusResponse(BaseModel):
    """Diagnostic status for enterprise Google Workspace Domain-Wide Delegation."""

    model_config = ConfigDict(frozen=True)

    configured: bool = Field(..., description="True if service account file and delegated email are configured")
    service_account_found: bool = Field(..., description="True if service_account.json exists on disk")
    service_account_email: str | None = Field(default=None, description="Parsed service account email, if available")
    delegated_user_email: str | None = Field(default=None, description="Configured user email to impersonate")
    scopes_authorized: list[str] = Field(default_factory=list, description="Configured DWD scopes")
    connectivity_status: str = Field(..., description="'ready', 'missing_key', 'missing_delegated_user', or 'error'")
    message: str = Field(..., description="Diagnostic assessment details")
