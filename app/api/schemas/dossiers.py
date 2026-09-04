"""API Request and Response schemas for Project Dossiers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.documents import DocumentResponseItem
from app.indexer.models import (
    Dossier,
    DossierMember,
    DossierRole,
    DossierStatus,
    DossierSummary,
    DriveFileMetadata,
    sanitize_string,
    slugify,
)


class DossierCreateRequest(BaseModel):
    """Payload for creating a new project dossier."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1, max_length=120, description="Project dossier display name")
    slug: str | None = Field(default=None, max_length=120, description="Optional custom URL-safe slug")
    description: str | None = Field(default=None, max_length=2000, description="Detailed project description")
    color: str | None = Field(default="#2563EB", max_length=30, description="Badge accent color")
    icon: str | None = Field(default="folder", max_length=50, description="Lucide icon name")
    initial_file_ids: list[str] = Field(default_factory=list, description="Google Drive file IDs to associate immediately")

    @field_validator("name", "slug", "description", "color", "icon", mode="before")
    @classmethod
    def clean_strings(cls, v: Any) -> Any:
        """Strip control characters from input."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class DossierUpdateRequest(BaseModel):
    """Payload for updating an existing project dossier."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=120, description="New display name")
    slug: str | None = Field(default=None, max_length=120, description="New URL-safe slug")
    description: str | None = Field(default=None, max_length=2000, description="New description")
    color: str | None = Field(default=None, max_length=30, description="New accent color")
    icon: str | None = Field(default=None, max_length=50, description="New icon name")
    status: DossierStatus | None = Field(default=None, description="Status: 'active' or 'archived'")

    @field_validator("name", "slug", "description", "color", "icon", mode="before")
    @classmethod
    def clean_strings(cls, v: Any) -> Any:
        """Strip control characters from input."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class DossierAddItemsRequest(BaseModel):
    """Payload for associating Google Drive files with a dossier."""

    model_config = ConfigDict(extra="ignore")

    file_ids: list[str] = Field(..., min_length=1, description="List of Google Drive file IDs to associate")

    @field_validator("file_ids", mode="before")
    @classmethod
    def clean_file_ids(cls, v: Any) -> Any:
        """Ensure file IDs are cleaned strings."""
        if isinstance(v, list):
            cleaned = []
            for item in v:
                if isinstance(item, str):
                    c = sanitize_string(item)
                    if c:
                        cleaned.append(c)
            return cleaned
        return v


class DossierAddMemberRequest(BaseModel):
    """Payload for adding or updating a member's role in a dossier."""

    model_config = ConfigDict(extra="ignore")

    user_email: str = Field(..., min_length=3, max_length=255, description="Email address of the user")
    role: DossierRole = Field(default="viewer", description="Access role: 'admin', 'editor', or 'viewer'")

    @field_validator("user_email", mode="before")
    @classmethod
    def clean_email(cls, v: Any) -> Any:
        """Sanitize email string."""
        if isinstance(v, str):
            c = sanitize_string(v)
            return c.lower() if c else v
        return v


class DossierMemberResponse(BaseModel):
    """API response model representing a dossier member."""

    model_config = ConfigDict(frozen=True)

    id: str
    dossier_id: str
    user_email: str
    role: str
    added_at: str

    @classmethod
    def from_domain(cls, member: DossierMember) -> DossierMemberResponse:
        """Construct from DossierMember domain entity."""
        return cls(
            id=member.id,
            dossier_id=member.dossier_id,
            user_email=member.user_email,
            role=member.role,
            added_at=member.added_at.isoformat(),
        )


class DossierResponse(BaseModel):
    """API response model representing a single dossier entity."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    slug: str
    description: str | None
    color: str | None
    icon: str | None
    status: str
    created_by: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, dossier: Dossier) -> DossierResponse:
        """Construct from Dossier domain entity."""
        return cls(
            id=dossier.id,
            name=dossier.name,
            slug=dossier.slug,
            description=dossier.description,
            color=dossier.color,
            icon=dossier.icon,
            status=dossier.status,
            created_by=dossier.created_by,
            created_at=dossier.created_at.isoformat(),
            updated_at=dossier.updated_at.isoformat(),
        )


class DossierSummaryResponse(BaseModel):
    """Summary card representation of a dossier including item and member counts."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    slug: str
    description: str | None
    color: str | None
    icon: str | None
    status: str
    item_count: int
    member_count: int
    created_by: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, summary: DossierSummary) -> DossierSummaryResponse:
        """Construct from DossierSummary domain entity."""
        return cls(
            id=summary.id,
            name=summary.name,
            slug=summary.slug,
            description=summary.description,
            color=summary.color,
            icon=summary.icon,
            status=summary.status,
            item_count=summary.item_count,
            member_count=summary.member_count,
            created_by=summary.created_by,
            created_at=summary.created_at.isoformat(),
            updated_at=summary.updated_at.isoformat(),
        )


class DossierListResponse(BaseModel):
    """Paginated list response of project dossiers."""

    model_config = ConfigDict(frozen=True)

    items: list[DossierSummaryResponse]
    total: int
    limit: int
    offset: int


class DossierDetailResponse(BaseModel):
    """Full detail view of a dossier, including member list and attached document cards."""

    model_config = ConfigDict(frozen=True)

    dossier: DossierResponse
    items: list[DocumentResponseItem]
    members: list[DossierMemberResponse]
    item_count: int
    member_count: int


class DossierItemsModifiedResponse(BaseModel):
    """Response returned when files are added or removed from a dossier."""

    model_config = ConfigDict(frozen=True)

    dossier_id: str
    modified_count: int
    total_items: int
    message: str
