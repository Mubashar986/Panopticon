"""Integration and unit tests for Google Drive authentication management API endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.auth.factory import get_runtime_auth_mode
from app.core.config import Settings


def test_get_auth_config() -> None:
    """Verify GET /api/auth/config returns configuration and token validity."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/auth/config")
    assert response.status_code == 200

    data = response.json()
    assert data["auth_mode"] in ("oauth", "service_account")
    assert "client_secrets_found" in data
    assert "token_cache_found" in data
    assert "service_account_found" in data
    assert "scopes" in data
    assert len(data["scopes"]) > 0


def test_switch_auth_mode() -> None:
    """Verify POST /api/auth/config hot-switches the active auth mode."""
    app = create_app()
    client = TestClient(app)

    # Switch to service_account
    response = client.post(
        "/api/auth/config",
        json={"auth_mode": "service_account", "delegated_user_email": "admin@workspace.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "switched"
    assert data["auth_mode"] == "service_account"
    assert data["delegated_user_email"] == "admin@workspace.com"
    assert get_runtime_auth_mode() == "service_account"

    # Switch back to oauth
    response = client.post("/api/auth/config", json={"auth_mode": "oauth"})
    assert response.status_code == 200
    assert response.json()["auth_mode"] == "oauth"
    assert get_runtime_auth_mode() == "oauth"


def test_switch_auth_mode_invalid() -> None:
    """Verify POST /api/auth/config rejects invalid auth mode."""
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/auth/config", json={"auth_mode": "invalid_mode"})
    assert response.status_code == 422


def test_start_oauth_flow_missing_secrets(tmp_path: Path) -> None:
    """Verify POST /api/auth/oauth/start returns 400 if client secrets are missing."""
    app = create_app()
    client = TestClient(app)

    custom_settings = Settings(GOOGLE_CLIENT_SECRETS_FILE=str(tmp_path / "missing_secrets.json"))

    with patch("app.api.routes.auth.get_settings", return_value=custom_settings):
        response = client.post("/api/auth/oauth/start")
        assert response.status_code == 400
        assert "missing" in response.json()["detail"].lower()


def test_start_oauth_flow_success(tmp_path: Path) -> None:
    """Verify POST /api/auth/oauth/start returns Google authorization URL."""
    app = create_app()
    client = TestClient(app)

    secrets_file = tmp_path / "credentials.json"
    secrets_file.write_text('{"installed": {"client_id": "test"}}', encoding="utf-8")
    custom_settings = Settings(GOOGLE_CLIENT_SECRETS_FILE=str(secrets_file))

    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?client_id=123", "test_state_123")

    with (
        patch("app.api.routes.auth.get_settings", return_value=custom_settings),
        patch("google_auth_oauthlib.flow.Flow.from_client_secrets_file", return_value=mock_flow),
    ):
        response = client.post("/api/auth/oauth/start")
        assert response.status_code == 200

        data = response.json()
        assert "accounts.google.com" in data["authorization_url"]
        assert data["state"] == "test_state_123"
        assert "redirect_uri" in data


def test_oauth_callback_success(tmp_path: Path) -> None:
    """Verify GET /api/auth/oauth/callback exchanges code and writes token.json."""
    app = create_app()
    client = TestClient(app)

    secrets_file = tmp_path / "credentials.json"
    secrets_file.write_text('{"installed": {"client_id": "test"}}', encoding="utf-8")
    token_file = tmp_path / "token.json"

    custom_settings = Settings(
        GOOGLE_CLIENT_SECRETS_FILE=str(secrets_file),
        GOOGLE_TOKEN_CACHE_FILE=str(token_file),
    )

    mock_creds = MagicMock()
    mock_creds.to_json.return_value = json.dumps({"token": "mock_access_token", "refresh_token": "mock_refresh"})

    mock_flow = MagicMock()
    mock_flow.credentials = mock_creds

    with (
        patch("app.api.routes.auth.get_settings", return_value=custom_settings),
        patch("google_auth_oauthlib.flow.Flow.from_client_secrets_file", return_value=mock_flow),
    ):
        response = client.get("/api/auth/oauth/callback?code=mock_google_code&state=test_state&raw_json=true")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "authenticated"
        assert data["token_saved"] is True
        assert token_file.exists()


def test_upload_credentials_oauth(tmp_path: Path) -> None:
    """Verify POST /api/auth/credentials/upload accepts OAuth client secrets JSON."""
    app = create_app()
    client = TestClient(app)

    target_path = tmp_path / "credentials.json"
    custom_settings = Settings(GOOGLE_CLIENT_SECRETS_FILE=str(target_path))

    oauth_payload = {
        "installed": {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    file_bytes = json.dumps(oauth_payload).encode("utf-8")

    with patch("app.api.routes.auth.get_settings", return_value=custom_settings):
        response = client.post(
            "/api/auth/credentials/upload",
            files={"file": ("credentials.json", file_bytes, "application/json")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["file_type"] == "credentials"
        assert target_path.exists()


def test_upload_credentials_service_account(tmp_path: Path) -> None:
    """Verify POST /api/auth/credentials/upload accepts Service Account key JSON."""
    app = create_app()
    client = TestClient(app)

    target_path = tmp_path / "service_account.json"
    custom_settings = Settings(GOOGLE_SERVICE_ACCOUNT_FILE=str(target_path))

    sa_payload = {
        "type": "service_account",
        "project_id": "panopticon-project",
        "private_key_id": "12345",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n",
        "client_email": "sa@panopticon-project.iam.gserviceaccount.com",
    }
    file_bytes = json.dumps(sa_payload).encode("utf-8")

    with patch("app.api.routes.auth.get_settings", return_value=custom_settings):
        response = client.post(
            "/api/auth/credentials/upload",
            files={"file": ("service_account.json", file_bytes, "application/json")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["file_type"] == "service_account"
        assert target_path.exists()
