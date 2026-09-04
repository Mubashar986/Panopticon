"""Integration and unit tests for Task 10.3: 1-Click Hosted Web OAuth 2.0 & Workspace DWD Admin Install Seam.

Covers:
- GET /api/auth/google/login with ENV client config (client_source='environment').
- GET /api/auth/google/login with file config (client_source='credentials_file').
- GET /api/auth/google/login?redirect=true HTTP 307 temporary redirect.
- GET /api/auth/google/login missing credentials error handling (400 Bad Request).
- GET /api/auth/google/callback CSRF state token verification and single-use consumption.
- GET /api/auth/google/callback code exchange, token persistence, and auto-closing HTML response.
- GET /api/auth/google/callback error handling on user cancellation.
- GET /api/auth/workspace/install Google Workspace Marketplace manifest and DWD setup instructions.
- GET /api/auth/workspace/status diagnostics (missing_key, missing_delegated_user, and ready states).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.routes.auth import _oauth_states
from app.core.auth.factory import get_runtime_auth_mode
from app.core.config import Settings


@pytest.fixture(autouse=True)
def clean_oauth_states():
    """Ensure _oauth_states is reset before and after every test."""
    _oauth_states.clear()
    yield
    _oauth_states.clear()


# -----------------------------------------------------------------------------
# 1. 1-Click Google OAuth Login Tests
# -----------------------------------------------------------------------------


def test_google_login_with_env_credentials():
    """Verify GET /api/auth/google/login builds client flow from environment variables."""
    app = create_app()
    client = TestClient(app)

    custom_settings = Settings(
        GOOGLE_CLIENT_ID="hosted-client-id-123.apps.googleusercontent.com",
        GOOGLE_CLIENT_SECRET="GOCSPX-hostedsecret456",
        GOOGLE_REDIRECT_URI="http://localhost:8000/api/auth/google/callback",
        GOOGLE_CLIENT_SECRETS_FILE="nonexistent_credentials.json",
    )

    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?client_id=hosted-client-id-123",
        "mock_state_abc",
    )

    with (
        patch("app.api.routes.auth.get_settings", return_value=custom_settings),
        patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=mock_flow) as mock_from_config,
    ):
        response = client.get("/api/auth/google/login")
        assert response.status_code == 200
        data = response.json()

        assert data["client_source"] == "environment"
        assert "accounts.google.com" in data["authorization_url"]
        assert len(data["state"]) > 20
        assert data["redirect_uri"] == "http://localhost:8000/api/auth/google/callback"
        # Verify state was saved to _oauth_states
        assert data["state"] in _oauth_states
        assert mock_from_config.called


def test_google_login_with_file_credentials(tmp_path: Path):
    """Verify GET /api/auth/google/login falls back to credentials.json if ENV is unset."""
    app = create_app()
    client = TestClient(app)

    secrets_file = tmp_path / "credentials.json"
    secrets_file.write_text('{"installed": {"client_id": "file_id_789"}}', encoding="utf-8")

    custom_settings = Settings(
        GOOGLE_CLIENT_ID=None,
        GOOGLE_CLIENT_SECRET=None,
        GOOGLE_CLIENT_SECRETS_FILE=str(secrets_file),
    )

    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?client_id=file_id_789",
        "mock_state_file",
    )

    with (
        patch("app.api.routes.auth.get_settings", return_value=custom_settings),
        patch("google_auth_oauthlib.flow.Flow.from_client_secrets_file", return_value=mock_flow) as mock_from_file,
    ):
        response = client.get("/api/auth/google/login")
        assert response.status_code == 200
        data = response.json()

        assert data["client_source"] == "credentials_file"
        assert "accounts.google.com" in data["authorization_url"]
        assert data["state"] in _oauth_states
        assert mock_from_file.called


def test_google_login_redirect_mode():
    """Verify GET /api/auth/google/login?redirect=true immediately returns HTTP 307 Redirect."""
    app = create_app()
    client = TestClient(app, follow_redirects=False)

    custom_settings = Settings(
        GOOGLE_CLIENT_ID="hosted-id",
        GOOGLE_CLIENT_SECRET="hosted-secret",
    )

    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?client_id=hosted-id",
        "mock_state_redirect",
    )

    with (
        patch("app.api.routes.auth.get_settings", return_value=custom_settings),
        patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=mock_flow),
    ):
        response = client.get("/api/auth/google/login?redirect=true")
        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["Location"]


def test_google_login_missing_credentials(tmp_path: Path):
    """Verify GET /api/auth/google/login returns 400 if neither ENV nor credentials.json exist."""
    app = create_app()
    client = TestClient(app)

    custom_settings = Settings(
        GOOGLE_CLIENT_ID=None,
        GOOGLE_CLIENT_SECRET=None,
        GOOGLE_CLIENT_SECRETS_FILE=str(tmp_path / "absent_credentials.json"),
    )

    with patch("app.api.routes.auth.get_settings", return_value=custom_settings):
        response = client.get("/api/auth/google/login")
        assert response.status_code == 400
        assert "Google OAuth credentials missing" in response.json()["detail"]


# -----------------------------------------------------------------------------
# 2. Google OAuth Callback Tests
# -----------------------------------------------------------------------------


def test_google_callback_csrf_rejection():
    """Verify GET /api/auth/google/callback rejects requests with missing or unregistered state."""
    app = create_app()
    client = TestClient(app)

    # Missing state
    res1 = client.get("/api/auth/google/callback?code=mock_code")
    assert res1.status_code == 400
    assert "Invalid or expired OAuth state token" in res1.json()["detail"]

    # Unregistered state
    res2 = client.get("/api/auth/google/callback?code=mock_code&state=fake_forged_state")
    assert res2.status_code == 400
    assert "Invalid or expired OAuth state token" in res2.json()["detail"]


def test_google_callback_user_denied_consent():
    """Verify GET /api/auth/google/callback handles user-denied error gracefully."""
    app = create_app()
    client = TestClient(app)

    # User cancelled in browser
    response = client.get("/api/auth/google/callback?error=access_denied")
    assert response.status_code == 200
    assert "Google Drive Connection Cancelled" in response.text
    assert "PANOPTICON_OAUTH_FAILED" in response.text

    # With raw_json=true
    raw_res = client.get("/api/auth/google/callback?error=access_denied&raw_json=true")
    assert raw_res.status_code == 400
    assert "cancelled or denied" in raw_res.json()["detail"]


def test_google_callback_success(tmp_path: Path):
    """Verify GET /api/auth/google/callback exchanges code, persists token.json, and returns HTML."""
    app = create_app()
    client = TestClient(app)

    token_file = tmp_path / "token.json"
    custom_settings = Settings(
        GOOGLE_CLIENT_ID="hosted-client-id",
        GOOGLE_CLIENT_SECRET="hosted-secret",
        GOOGLE_TOKEN_CACHE_FILE=str(token_file),
    )

    # Pre-register state
    valid_state = "valid_secure_state_98765"
    _oauth_states.add(valid_state)

    mock_credentials = MagicMock()
    mock_credentials.to_json.return_value = json.dumps({
        "token": "ya29.mock_access_token",
        "refresh_token": "1//mock_refresh_token",
        "client_id": "hosted-client-id",
    })

    mock_flow = MagicMock()
    mock_flow.credentials = mock_credentials

    with (
        patch("app.api.routes.auth.get_settings", return_value=custom_settings),
        patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=mock_flow),
    ):
        response = client.get(f"/api/auth/google/callback?code=mock_auth_code_123&state={valid_state}")
        assert response.status_code == 200
        assert "Google Drive Connected Successfully" in response.text
        assert "PANOPTICON_OAUTH_SUCCESS" in response.text

        # Verify state was consumed (one-time use)
        assert valid_state not in _oauth_states

        # Verify token.json was written
        assert token_file.exists()
        saved_data = json.loads(token_file.read_text(encoding="utf-8"))
        assert saved_data["token"] == "ya29.mock_access_token"

        # Verify runtime auth mode is now 'oauth'
        assert get_runtime_auth_mode() == "oauth"


def test_google_callback_raw_json(tmp_path: Path):
    """Verify GET /api/auth/google/callback?raw_json=true returns JSON payload."""
    app = create_app()
    client = TestClient(app)

    token_file = tmp_path / "token.json"
    custom_settings = Settings(
        GOOGLE_CLIENT_ID="hosted-client-id",
        GOOGLE_CLIENT_SECRET="hosted-secret",
        GOOGLE_TOKEN_CACHE_FILE=str(token_file),
    )

    valid_state = "json_state_123"
    _oauth_states.add(valid_state)

    mock_credentials = MagicMock()
    mock_credentials.to_json.return_value = json.dumps({"token": "mock_token"})
    mock_flow = MagicMock()
    mock_flow.credentials = mock_credentials

    with (
        patch("app.api.routes.auth.get_settings", return_value=custom_settings),
        patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=mock_flow),
    ):
        response = client.get(f"/api/auth/google/callback?code=mock_code&state={valid_state}&raw_json=true")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "authenticated"
        assert data["token_saved"] is True


# -----------------------------------------------------------------------------
# 3. Google Workspace DWD Admin Seam Tests
# -----------------------------------------------------------------------------


def test_workspace_install_manifest_with_service_account(tmp_path: Path):
    """Verify GET /api/auth/workspace/install extracts client ID and returns setup instructions."""
    app = create_app()
    client = TestClient(app)

    sa_file = tmp_path / "service_account.json"
    sa_file.write_text(
        json.dumps({
            "client_id": "109876543210987654321",
            "client_email": "panopticon-dwd@project.iam.gserviceaccount.com",
        }),
        encoding="utf-8",
    )

    custom_settings = Settings(GOOGLE_SERVICE_ACCOUNT_FILE=str(sa_file))

    with patch("app.api.routes.auth.get_settings", return_value=custom_settings):
        response = client.get("/api/auth/workspace/install")
        assert response.status_code == 200
        data = response.json()

        assert data["application_name"] == "Panopticon"
        assert data["client_id"] == "109876543210987654321"
        assert data["service_account_email"] == "panopticon-dwd@project.iam.gserviceaccount.com"
        assert len(data["required_scopes"]) > 0
        assert "https://www.googleapis.com/auth/drive.readonly" in data["required_scopes"]
        assert "admin.google.com" in data["admin_console_url"]
        assert "Domain-wide delegation" in data["setup_instructions"]


def test_workspace_status_diagnostic(tmp_path: Path):
    """Verify GET /api/auth/workspace/status diagnoses missing key, missing email, and ready states."""
    app = create_app()
    client = TestClient(app)

    sa_file = tmp_path / "service_account.json"

    # State 1: Missing Key File
    settings_missing_key = Settings(
        GOOGLE_SERVICE_ACCOUNT_FILE=str(tmp_path / "absent_sa.json"),
        GOOGLE_DELEGATED_USER_EMAIL="admin@enterprise.com",
    )
    with patch("app.api.routes.auth.get_settings", return_value=settings_missing_key):
        res1 = client.get("/api/auth/workspace/status")
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["configured"] is False
        assert d1["connectivity_status"] == "missing_key"

    # State 2: Key File present, but missing delegated user email
    sa_file.write_text(
        json.dumps({"client_id": "123", "client_email": "sa@corp.iam.gserviceaccount.com"}),
        encoding="utf-8",
    )
    settings_missing_user = Settings(
        GOOGLE_SERVICE_ACCOUNT_FILE=str(sa_file),
        GOOGLE_DELEGATED_USER_EMAIL=None,
    )
    with patch("app.api.routes.auth.get_settings", return_value=settings_missing_user):
        res2 = client.get("/api/auth/workspace/status")
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["configured"] is False
        assert d2["connectivity_status"] == "missing_delegated_user"

    # State 3: Ready
    settings_ready = Settings(
        GOOGLE_SERVICE_ACCOUNT_FILE=str(sa_file),
        GOOGLE_DELEGATED_USER_EMAIL="admin@enterprise.com",
    )
    with patch("app.api.routes.auth.get_settings", return_value=settings_ready):
        res3 = client.get("/api/auth/workspace/status")
        assert res3.status_code == 200
        d3 = res3.json()
        assert d3["configured"] is True
        assert d3["connectivity_status"] == "ready"
        assert d3["service_account_email"] == "sa@corp.iam.gserviceaccount.com"
        assert d3["delegated_user_email"] == "admin@enterprise.com"
