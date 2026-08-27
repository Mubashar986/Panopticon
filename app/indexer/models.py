"""Domain models for Google Drive file metadata, permissions, labels, and crawl telemetry."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Precompiled regex for stripping illegal control characters from untrusted external strings
_CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Standard Google Workspace MIME types
GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"

SharingStatus = Literal["private", "shared", "domain", "anyone"]


def sanitize_string(val: str | None) -> str | None:
    """Sanitize external untrusted text by stripping null bytes and illegal control characters.

    Args:
        val: Raw string from external API or user input.

    Returns:
        Sanitized string or None if input is None.
    """
    if val is None:
        return None
    cleaned = _CONTROL_CHAR_REGEX.sub("", val).strip()
    return cleaned


class DrivePermission(BaseModel):
    """Normalized Google Drive permission access control list entry."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(..., description="Google Drive permission entry ID")
    role: str = Field(
        ...,
        description="Permission role (owner, organizer, writer, commenter, reader)",
    )
    type: str = Field(
        ...,
        description="Principal type (user, group, domain, anyone)",
    )
    email_address: str | None = Field(
        default=None,
        description="Email address for user or group principals",
    )
    domain: str | None = Field(
        default=None,
        description="Domain name for domain-wide permissions (e.g. company.com)",
    )
    display_name: str | None = Field(
        default=None,
        description="Display name of the user or entity",
    )
    allow_file_discovery: bool | None = Field(
        default=None,
        description="Whether the file is discoverable via search by anyone/domain",
    )

    @field_validator(
        "id",
        "role",
        "type",
        "email_address",
        "domain",
        "display_name",
        mode="before",
    )
    @classmethod
    def clean_permission_strings(cls, v: Any) -> Any:
        """Sanitize untrusted string values from permission payload."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class DriveLabelField(BaseModel):
    """Normalized field value within a Google Drive Label."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(..., description="Unique field ID within the label schema")
    field_type: str = Field(
        default="text",
        description="Field data type (text, selection, user, integer, dateString)",
    )
    values: list[str] = Field(
        default_factory=list, description="Extracted string values for this field"
    )
    display_value: str | None = Field(
        default=None, description="Primary human-readable display string"
    )


class DriveLabel(BaseModel):
    """Normalized Google Drive Workspace Label attached to a file."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(..., description="Unique Google Drive Label ID")
    revision_id: str | None = Field(
        default=None, description="Label schema revision ID if present"
    )
    fields: dict[str, DriveLabelField] = Field(
        default_factory=dict,
        description="Dictionary mapping field ID to normalized field value",
    )

    def get_field_values(self, field_id: str) -> list[str]:
        """Lookup field values by field ID safely."""
        field = self.fields.get(field_id)
        return field.values if field else []

    def get_field_display(self, field_id: str) -> str | None:
        """Lookup display string by field ID safely."""
        field = self.fields.get(field_id)
        return field.display_value if field else None


class DriveFileMetadata(BaseModel):
    """Normalized domain entity representing a Google Drive file discovered during crawl."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(..., description="Google Drive unique file ID")
    name: str = Field(..., description="Document or Sheet title")
    mime_type: str = Field(..., description="MIME type of the file")
    modified_time: datetime | None = Field(
        default=None, description="Last modification timestamp (UTC)"
    )
    created_time: datetime | None = Field(
        default=None, description="Creation timestamp (UTC)"
    )
    owners: list[str] = Field(
        default_factory=list,
        description="List of owner email addresses or display names",
    )
    last_modifying_user: str | None = Field(
        default=None, description="Email or display name of the last editor"
    )
    shared: bool = Field(
        default=False, description="Whether the file is shared with other users"
    )
    web_view_link: str | None = Field(
        default=None, description="Direct URL to open the document in Google Drive"
    )
    icon_link: str | None = Field(
        default=None, description="URL to file type icon"
    )
    size_bytes: int | None = Field(
        default=None, description="File size in bytes if available"
    )
    trashed: bool = Field(
        default=False, description="Whether the file is in Google Drive trash"
    )
    parents: list[str] = Field(
        default_factory=list, description="IDs of parent folders"
    )
    drive_id: str | None = Field(
        default=None, description="ID of the Shared Drive containing this file"
    )
    permissions: list[DrivePermission] = Field(
        default_factory=list,
        description="Normalized Access Control List (ACL) entries for this file",
    )
    sharing_status: str = Field(
        default="private",
        description="Categorical sharing status: private, shared, domain, anyone",
    )
    labels: list[DriveLabel] = Field(
        default_factory=list,
        description="Structured Google Drive Workspace Labels attached to this file",
    )
    project_tags: list[str] = Field(
        default_factory=list,
        description="Flattened list of project tags extracted from labels",
    )
    content_snippet: str | None = Field(
        default=None,
        description="Truncated search preview snippet of document content",
    )
    export_status: str | None = Field(
        default=None,
        description="Outcome status of content export (e.g. success, oversized_metadata_only)",
    )

    @field_validator(
        "id",
        "name",
        "mime_type",
        "last_modifying_user",
        "web_view_link",
        "icon_link",
        "drive_id",
        "sharing_status",
        "content_snippet",
        "export_status",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, v: Any) -> Any:
        """Strip control characters and whitespace from string fields."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v

    @field_validator("owners", "parents", "project_tags", mode="before")
    @classmethod
    def clean_string_lists(cls, v: Any) -> Any:
        """Sanitize list of string values."""
        if isinstance(v, list):
            cleaned: list[str] = []
            for item in v:
                if isinstance(item, str):
                    s = sanitize_string(item)
                    if s:
                        cleaned.append(s)
                elif isinstance(item, dict) and "emailAddress" in item:
                    s = sanitize_string(item.get("emailAddress"))
                    if s:
                        cleaned.append(s)
                elif isinstance(item, dict) and "displayName" in item:
                    s = sanitize_string(item.get("displayName"))
                    if s:
                        cleaned.append(s)
            return cleaned
        return v

    @property
    def is_doc(self) -> bool:
        """Return True if this file is a Google Doc."""
        return self.mime_type == GOOGLE_DOC_MIME_TYPE

    @property
    def is_sheet(self) -> bool:
        """Return True if this file is a Google Sheet."""
        return self.mime_type == GOOGLE_SHEET_MIME_TYPE

    @property
    def primary_owner(self) -> str:
        """Return primary owner email or fallback."""
        if self.owners:
            return self.owners[0]
        return "Shared Drive / Organization"

    def has_project_tag(self, tag: str) -> bool:
        """Check case-insensitively if this file has a specific project tag."""
        target = tag.strip().lower()
        return any(t.strip().lower() == target for t in self.project_tags)


class CrawlStats(BaseModel):
    """Execution metrics and statistics for a completed crawl operation."""

    model_config = ConfigDict(frozen=True)

    pages_fetched: int = Field(default=0, description="Total API pages fetched")
    files_discovered: int = Field(
        default=0, description="Total Docs and Sheets discovered"
    )
    docs_count: int = Field(default=0, description="Number of Google Docs found")
    sheets_count: int = Field(default=0, description="Number of Google Sheets found")
    other_count: int = Field(default=0, description="Number of other MIME types")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Crawl start timestamp",
    )
    end_time: datetime | None = Field(
        default=None, description="Crawl finish timestamp"
    )
    duration_seconds: float = Field(
        default=0.0, description="Total crawl duration in seconds"
    )
