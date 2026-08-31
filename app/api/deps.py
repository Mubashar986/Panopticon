"""Dependency injection providers for authentication, clients, and domain services."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.services.sync_manager import SyncManager, get_sync_manager
from app.indexer.storage import CrawlStorage, get_crawl_storage
from app.search.client import PanopticonSearchClient, get_search_client
from app.search.service import SearchService, get_search_service


class AuthenticatedUser(BaseModel):
    """User identity model returned by the authentication dependency seam."""

    model_config = ConfigDict(frozen=True)

    user_id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    display_name: str = Field(..., description="Human-readable name")
    roles: list[str] = Field(default_factory=lambda: ["search_user"], description="Granted security roles")
    is_authenticated: bool = Field(default=True, description="Authentication validity flag")


class LocalDevUser(AuthenticatedUser):
    """Default stub identity for local development (Task 4.3)."""

    user_id: str = "local_dev_user"
    email: str = "developer@local.panopticon"
    display_name: str = "Local Developer"
    roles: list[str] = ["admin", "search_user"]
    is_authenticated: bool = True


def get_current_user() -> AuthenticatedUser:
    """Pluggable authentication dependency seam.

    In local mode (Phase 1), this function returns a default LocalDevUser with zero
    external authentication overhead. When the team adds OAuth2/JWT authentication later,
    this dependency can be replaced or overridden via FastAPI dependency injection
    without modifying any API route handlers.
    """
    return LocalDevUser()


def get_search_client_dep() -> PanopticonSearchClient:
    """Provide an initialized PanopticonSearchClient instance."""
    return get_search_client()


def get_search_service_dep(
    client: Annotated[PanopticonSearchClient, Depends(get_search_client_dep)],
) -> SearchService:
    """Provide a SearchService instance wired to the current PanopticonSearchClient."""
    return get_search_service(search_client=client)


def get_sync_manager_dep() -> SyncManager:
    """Provide the global SyncManager singleton instance."""
    return get_sync_manager()


def get_crawl_storage_dep() -> CrawlStorage:
    """Provide the CrawlStorage repository instance."""
    return get_crawl_storage()


# Type aliases for clean FastAPI route parameter annotations
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service_dep)]
SearchClientDep = Annotated[PanopticonSearchClient, Depends(get_search_client_dep)]
SyncManagerDep = Annotated[SyncManager, Depends(get_sync_manager_dep)]
CrawlStorageDep = Annotated[CrawlStorage, Depends(get_crawl_storage_dep)]

