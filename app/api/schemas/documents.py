"""Document directory catalog request and response schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
)


class DocumentResponseItem(BaseModel):
    """Document catalog item model conforming to Panopticon dashboard contract."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Google Drive document ID")
    name: str = Field(..., description="Document or Sheet title")
    type: str = Field(..., description="Categorical type: 'document', 'spreadsheet', or 'other'")
    mime_type: str = Field(..., description="Google Workspace MIME type")
    owner: str = Field(..., description="Primary owner name or email")
    owners: list[str] = Field(default_factory=list, description="All file owners")
    last_modifying_user: str | None = Field(default=None, description="Last modifying editor")
    modified_time: str | None = Field(default=None, description="ISO 8601 modification timestamp")
    created_time: str | None = Field(default=None, description="ISO 8601 creation timestamp")
    sharing_status: str = Field(default="private", description="Sharing visibility: 'private', 'shared', 'domain', 'anyone'")
    shared_with: str = Field(default="private", description="Sharing scope indicator for UI badges")
    project_tags: list[str] = Field(default_factory=list, description="Extracted Google Drive project label tags")
    snippet: str | None = Field(default=None, description="Document content preview snippet (pointer, not full text)")
    view_url: str | None = Field(default=None, description="Direct URL link to open file in Google Drive")
    icon_link: str | None = Field(default=None, description="File type icon URL")
    size_bytes: int | None = Field(default=None, description="File size in bytes if available")
    export_status: str | None = Field(default=None, description="Export status ('success', 'oversized_metadata_only')")
    export_links: dict[str, str] | None = Field(default=None, description="Convenience direct export URLs")

    @classmethod
    def from_drive_file_metadata(cls, file: DriveFileMetadata) -> DocumentResponseItem:
        """Map internal DriveFileMetadata domain entity to public API DocumentResponseItem."""
        # Determine categorical file type
        if file.mime_type == GOOGLE_DOC_MIME_TYPE:
            file_type = "document"
            export_links: dict[str, str] | None = {
                "pdf": f"https://docs.google.com/document/d/{file.id}/export?format=pdf",
                "docx": f"https://docs.google.com/document/d/{file.id}/export?format=docx",
                "txt": f"https://docs.google.com/document/d/{file.id}/export?format=txt",
            }
        elif file.mime_type == GOOGLE_SHEET_MIME_TYPE:
            file_type = "spreadsheet"
            export_links = {
                "pdf": f"https://docs.google.com/spreadsheets/d/{file.id}/export?format=pdf",
                "xlsx": f"https://docs.google.com/spreadsheets/d/{file.id}/export?format=xlsx",
                "csv": f"https://docs.google.com/spreadsheets/d/{file.id}/export?format=csv",
            }
        else:
            file_type = "other"
            export_links = None

        mod_iso = (
            file.modified_time.astimezone(timezone.utc).isoformat()
            if file.modified_time
            else None
        )
        create_iso = (
            file.created_time.astimezone(timezone.utc).isoformat()
            if file.created_time
            else None
        )

        return cls(
            id=file.id,
            name=file.name,
            type=file_type,
            mime_type=file.mime_type,
            owner=file.primary_owner,
            owners=list(file.owners),
            last_modifying_user=file.last_modifying_user,
            modified_time=mod_iso,
            created_time=create_iso,
            sharing_status=file.sharing_status,
            shared_with=file.sharing_status,
            project_tags=list(file.project_tags),
            snippet=file.content_snippet,
            view_url=file.web_view_link,
            icon_link=file.icon_link,
            size_bytes=file.size_bytes,
            export_status=file.export_status,
            export_links=export_links,
        )


class DocumentListResponse(BaseModel):
    """Paginated document directory catalog response."""

    model_config = ConfigDict(frozen=True)

    total_count: int = Field(default=0, description="Total matching documents stored in repository")
    limit: int = Field(default=50, description="Page limit requested")
    offset: int = Field(default=0, description="Page offset requested")
    processing_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    documents: list[DocumentResponseItem] = Field(
        default_factory=list, description="Ordered document items for the current page"
    )
