"""Unit tests for Panopticon Google Drive authentication subsystem."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials as OAuth2Credentials
from google.oauth2.service_account import Credentials as SACredentials

from app.core.auth import (
    AuthConfigurationError,
    ConsentFlowError,
    DomainWideDelegationProvider,
    DriveAuthProvider,
    DrivePermissionDeniedError,
    DriveQuotaExceededError,
    DriveRateLimitError,
    MissingCredentialsFileError,
    MissingServiceAccountFileError,
    PersonalOAuthProvider,
    get_auth_provider,
)
from app.core.config import Settings

# ---------------------------------------------------------------------------
# Base Interface & Exceptions
# ---------------------------------------------------------------------------


def test_base_provider_default_scopes():
    """Verify default read-only Drive scopes are assigned."""
    class DummyProvider(DriveAuthProvider):
        @property
        def provider_name(self) -> str:
            return "Dummy"

        def get_credentials(self):
            return None  # type: ignore

    provider = DummyProvider()
    assert "https://www.googleapis.com/auth/drive.readonly" in provider.scopes
    assert "https://www.googleapis.com/auth/drive.labels.readonly" in provider.scopes


def test_base_provider_custom_scopes():
    """Verify custom scopes can override defaults."""
    class DummyProvider(DriveAuthProvider):
        @property
        def provider_name(self) -> str:
            return "Dummy"

        def get_credentials(self):
            return None  # type: ignore

    custom = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
    provider = DummyProvider(scopes=custom)
    assert provider.scopes == custom


def test_action_card_formatting_on_missing_credentials(tmp_path: Path):
    """Verify Action Card is rendered inside MissingCredentialsFileError."""
    fake_path = tmp_path / "credentials.json"
    err = MissingCredentialsFileError(fake_path)
    assert "DEVELOPER ACTION CARD" in str(err)
    assert str(fake_path) in str(err)


def test_action_card_formatting_on_missing_service_account(tmp_path: Path):
    """Verify Action Card is rendered inside MissingServiceAccountFileError."""
    fake_path = tmp_path / "service_account.json"
    err = MissingServiceAccountFileError(fake_path)
    assert "DEVELOPER ACTION CARD" in str(err)
    assert "Domain-Wide Delegation" in str(err)


def test_rate_limit_and_quota_exceptions():
    """Verify rate limit and quota exception attributes."""
    rl_err = DriveRateLimitError("Rate limited", retry_after_seconds=30.0)
    assert rl_err.retry_after_seconds == 30.0
    assert "Rate limited" in str(rl_err)

    quota_err = DriveQuotaExceededError("Daily limit reached")
    assert "Daily limit reached" in str(quota_err)

    perm_err = DrivePermissionDeniedError("Forbidden scope")
    assert "Forbidden scope" in str(perm_err)


# ---------------------------------------------------------------------------
# PersonalOAuthProvider Tests
# ---------------------------------------------------------------------------


def test_oauth_provider_valid_cached_token(tmp_path: Path):
    """Verify valid cached token.json is returned without network calls."""
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "dummy_access_token"}', encoding="utf-8")
    creds_file = tmp_path / "credentials.json"

    provider = PersonalOAuthProvider(credentials_path=creds_file, token_path=token_file)

    mock_creds = MagicMock(spec=OAuth2Credentials)
    mock_creds.valid = True

    with patch(
        "app.core.auth.oauth.OAuth2Credentials.from_authorized_user_file",
        return_value=mock_creds,
    ) as mock_from_file:
        result = provider.get_credentials()
        mock_from_file.assert_called_once_with(str(token_file), provider.scopes)
        assert result == mock_creds


def test_oauth_provider_expired_token_auto_refresh(tmp_path: Path):
    """Verify expired token with refresh_token is refreshed and persisted."""
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "expired_token"}', encoding="utf-8")
    creds_file = tmp_path / "credentials.json"

    provider = PersonalOAuthProvider(credentials_path=creds_file, token_path=token_file)

    mock_creds = MagicMock(spec=OAuth2Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "valid_refresh_token"
    mock_creds.to_json.return_value = '{"token": "new_refreshed_token"}'

    with patch(
        "app.core.auth.oauth.OAuth2Credentials.from_authorized_user_file",
        return_value=mock_creds,
    ), patch("app.core.auth.oauth.Request"):
        result = provider.get_credentials()
        mock_creds.refresh.assert_called_once()
        assert result == mock_creds
        assert token_file.read_text(encoding="utf-8") == '{"token": "new_refreshed_token"}'


def test_oauth_provider_missing_credentials_file_raises_action_card(tmp_path: Path):
    """Verify missing credentials.json raises MissingCredentialsFileError when no token exists."""
    token_file = tmp_path / "token.json"
    creds_file = tmp_path / "non_existent_credentials.json"

    provider = PersonalOAuthProvider(credentials_path=creds_file, token_path=token_file)

    with pytest.raises(MissingCredentialsFileError) as exc_info:
        provider.get_credentials()

    assert "Google OAuth client secrets file not found" in str(exc_info.value)
    assert "DEVELOPER ACTION CARD" in str(exc_info.value)


def test_oauth_provider_interactive_consent_flow(tmp_path: Path):
    """Verify InstalledAppFlow runs with offline access and saves token.json."""
    token_file = tmp_path / "token.json"
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {"client_id": "dummy"}}', encoding="utf-8")

    provider = PersonalOAuthProvider(credentials_path=creds_file, token_path=token_file)

    mock_flow = MagicMock()
    mock_creds = MagicMock(spec=OAuth2Credentials)
    mock_creds.to_json.return_value = '{"token": "brand_new_token"}'
    mock_flow.run_local_server.return_value = mock_creds

    with patch(
        "app.core.auth.oauth.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow,
    ) as mock_from_secrets:
        result = provider.get_credentials()

        mock_from_secrets.assert_called_once_with(
            str(creds_file), scopes=provider.scopes
        )
        mock_flow.run_local_server.assert_called_once_with(
            port=0, access_type="offline", prompt="consent"
        )
        assert result == mock_creds
        assert token_file.read_text(encoding="utf-8") == '{"token": "brand_new_token"}'


def test_oauth_provider_consent_flow_failure(tmp_path: Path):
    """Verify consent flow exceptions are wrapped in ConsentFlowError."""
    token_file = tmp_path / "token.json"
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}', encoding="utf-8")

    provider = PersonalOAuthProvider(credentials_path=creds_file, token_path=token_file)

    mock_flow = MagicMock()
    mock_flow.run_local_server.side_effect = RuntimeError("Browser cancelled")

    with patch(
        "app.core.auth.oauth.InstalledAppFlow.from_client_secrets_file",
        return_value=mock_flow,
    ):
        with pytest.raises(ConsentFlowError) as exc_info:
            provider.get_credentials()
        assert "Failed to complete OAuth consent flow" in str(exc_info.value)


# ---------------------------------------------------------------------------
# DomainWideDelegationProvider Tests
# ---------------------------------------------------------------------------


def test_sa_provider_missing_file_raises_action_card(tmp_path: Path):
    """Verify missing service account file raises MissingServiceAccountFileError."""
    sa_file = tmp_path / "non_existent_sa.json"
    provider = DomainWideDelegationProvider(service_account_path=sa_file)

    with pytest.raises(MissingServiceAccountFileError) as exc_info:
        provider.get_credentials()

    assert "Google Service Account key file not found" in str(exc_info.value)
    assert "DEVELOPER ACTION CARD" in str(exc_info.value)


def test_sa_provider_standard_credentials(tmp_path: Path):
    """Verify standard service account credentials loaded without impersonation."""
    sa_file = tmp_path / "service_account.json"
    sa_file.write_text('{"type": "service_account"}', encoding="utf-8")

    provider = DomainWideDelegationProvider(
        service_account_path=sa_file, subject_email=None
    )

    mock_creds = MagicMock(spec=SACredentials)

    with patch(
        "app.core.auth.service_account.service_account.Credentials.from_service_account_file",
        return_value=mock_creds,
    ) as mock_sa_loader:
        result = provider.get_credentials()
        mock_sa_loader.assert_called_once_with(str(sa_file), scopes=provider.scopes)
        assert result == mock_creds
        mock_creds.with_subject.assert_not_called()


def test_sa_provider_with_subject_delegation(tmp_path: Path):
    """Verify service account credentials apply .with_subject() for user impersonation."""
    sa_file = tmp_path / "service_account.json"
    sa_file.write_text('{"type": "service_account"}', encoding="utf-8")

    delegated_email = "workspace_admin@company.com"
    provider = DomainWideDelegationProvider(
        service_account_path=sa_file, subject_email=delegated_email
    )

    mock_creds = MagicMock(spec=SACredentials)
    delegated_creds = MagicMock(spec=SACredentials)
    mock_creds.with_subject.return_value = delegated_creds

    with patch(
        "app.core.auth.service_account.service_account.Credentials.from_service_account_file",
        return_value=mock_creds,
    ):
        result = provider.get_credentials()
        mock_creds.with_subject.assert_called_once_with(delegated_email)
        assert result == delegated_creds


# ---------------------------------------------------------------------------
# Factory Tests
# ---------------------------------------------------------------------------


def test_factory_returns_oauth_provider():
    """Verify get_auth_provider returns PersonalOAuthProvider for 'oauth' mode."""
    settings = Settings(DRIVE_AUTH_MODE="oauth")
    provider = get_auth_provider(settings)
    assert isinstance(provider, PersonalOAuthProvider)
    assert provider.provider_name == "PersonalOAuthProvider"


def test_factory_returns_sa_provider():
    """Verify get_auth_provider returns DomainWideDelegationProvider for 'service_account' mode."""
    settings = Settings(
        DRIVE_AUTH_MODE="service_account",
        GOOGLE_DELEGATED_USER_EMAIL="user@example.com",
    )
    provider = get_auth_provider(settings)
    assert isinstance(provider, DomainWideDelegationProvider)
    assert provider.provider_name == "DomainWideDelegationProvider"
    assert provider.subject_email == "user@example.com"


def test_factory_invalid_mode_raises_config_error():
    """Verify get_auth_provider raises AuthConfigurationError on invalid mode."""
    settings = Settings()
    object.__setattr__(settings, "DRIVE_AUTH_MODE", "invalid_mode")

    with pytest.raises(AuthConfigurationError) as exc_info:
        get_auth_provider(settings)
    assert "Unsupported DRIVE_AUTH_MODE: 'invalid_mode'" in str(exc_info.value)
