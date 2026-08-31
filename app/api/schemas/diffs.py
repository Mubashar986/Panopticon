"""Pydantic API response schemas for document versions and diff records."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DocumentVersionResponse(BaseModel):
    """Schema representing a single document historical snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique version snapshot ID")
    file_id: str = Field(..., description="Google Drive file ID")
    version_number: int = Field(..., description="Sequential version index (1, 2, ...)")
    content_hash: str = Field(..., description="SHA-256 hash of extracted plain text")
    editor: str | None = Field(default=None, description="Email or name of modifying user")
    modified_time: datetime | None = Field(default=None, description="Drive modification timestamp")
    char_count: int = Field(default=0, description="Character count in snapshot")
    word_count: int = Field(default=0, description="Word count in snapshot")
    created_at: datetime = Field(..., description="Local creation timestamp (UTC)")


class DocumentDiffResponse(BaseModel):
    """Schema representing a structured difference between two snapshots."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique diff record ID")
    file_id: str = Field(..., description="Google Drive file ID")
    from_version_id: str | None = Field(default=None, description="Prior version ID")
    to_version_id: str = Field(..., description="Target version ID")
    patch_text: str = Field(..., description="Unified diff patch text")
    ai_summary: str | None = Field(default=None, description="1-sentence semantic AI summary")
    lines_added: int = Field(default=0, description="Number of lines added (+)")
    lines_removed: int = Field(default=0, description="Number of lines removed (-)")
    created_at: datetime = Field(..., description="Diff creation timestamp (UTC)")


class VersionHistoryResponse(BaseModel):
    """Paginated list of version snapshots for a document."""

    file_id: str = Field(..., description="Google Drive file ID")
    total: int = Field(..., description="Total version snapshots available")
    items: list[DocumentVersionResponse] = Field(..., description="List of version snapshots")


class DiffListResponse(BaseModel):
    """List of diff delta records for a document."""

    file_id: str = Field(..., description="Google Drive file ID")
    total: int = Field(..., description="Total diff records available")
    items: list[DocumentDiffResponse] = Field(..., description="List of diff records")
