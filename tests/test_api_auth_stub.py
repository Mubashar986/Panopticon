"""Tests for the pluggable API authentication seam (Task 4.3)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.deps import AuthenticatedUser, LocalDevUser, get_current_user, get_search_service_dep
from app.search.models import SearchResult


def test_default_auth_provides_local_dev_user() -> None:
    """Verify get_current_user returns a valid LocalDevUser instance in Phase 1."""
    user = get_current_user()
    assert isinstance(user, LocalDevUser)
    assert user.user_id == "local_dev_user"
    assert user.email == "developer@local.panopticon"
    assert user.display_name == "Local Developer"
    assert user.is_authenticated is True
    assert "search_user" in user.roles


def test_auth_dependency_override_seam() -> None:
    """Verify overriding get_current_user works seamlessly across routes without modifying handlers."""
    app = create_app()

    mock_service = MagicMock()
    mock_service.search.return_value = SearchResult(
        query="Project",
        hits=[],
        total_hits=0,
        processing_time_ms=0.5,
        limit=10,
        offset=0,
        facet_distribution={},
    )

    custom_team_user = AuthenticatedUser(
        user_id="google_oauth_12345",
        email="lead.developer@company.com",
        display_name="Lead Developer",
        roles=["admin", "search_user"],
        is_authenticated=True,
    )

    # Plug in custom user via dependency injection seam
    app.dependency_overrides[get_search_service_dep] = lambda: mock_service
    app.dependency_overrides[get_current_user] = lambda: custom_team_user

    client = TestClient(app)
    response = client.get("/api/search?q=Project")
    assert response.status_code == 200
    assert response.json()["total_hits"] == 0
