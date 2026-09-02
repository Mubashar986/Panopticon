"""Domain models for Google Drive file metadata, permissions, labels, and crawl telemetry."""

from __future__ import annotations

import re
import uuid
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


class SyncResult(BaseModel):
    """Summary of changes applied during an incremental or bootstrap synchronization cycle."""

    model_config = ConfigDict(frozen=True)

    added_count: int = Field(default=0, description="Number of new files discovered and stored")
    updated_count: int = Field(default=0, description="Number of modified files updated")
    deleted_count: int = Field(default=0, description="Number of deleted or trashed files purged")
    unchanged_count: int = Field(default=0, description="Number of existing files up to date")
    total_stored: int = Field(default=0, description="Total active files currently in local storage")
    duration_seconds: float = Field(default=0.0, description="Elapsed sync duration in seconds")
    watermark_used: datetime | None = Field(default=None, description="Watermark timestamp used for delta query")
    new_watermark: datetime = Field(..., description="New watermark timestamp committed")
    is_full_refresh: bool = Field(default=False, description="Whether this was a full bootstrap sync")


class DocumentVersion(BaseModel):
    """Immutable snapshot of a document at a specific point in time."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(
        default_factory=lambda: f"ver_{uuid.uuid4().hex[:12]}",
        description="Unique version snapshot ID",
    )
    file_id: str = Field(..., description="Google Drive unique file ID")
    version_number: int = Field(
        default=1, description="1-indexed monotonic version number for this file"
    )
    content_hash: str = Field(..., description="SHA-256 hex digest of snapshot text")
    snapshot_text: str = Field(
        ..., description="Sanitized plain text content of document at this version"
    )
    modified_time: datetime | None = Field(
        default=None, description="Google Drive UTC modified timestamp"
    )
    editor: str | None = Field(
        default=None, description="User who made the modification"
    )
    char_count: int = Field(
        default=0, description="Character count of snapshot text"
    )
    word_count: int = Field(
        default=0, description="Word count of snapshot text"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Local ingestion timestamp (UTC)",
    )

    @field_validator("id", "file_id", "content_hash", "editor", mode="before")
    @classmethod
    def clean_version_strings(cls, v: Any) -> Any:
        """Strip control characters and whitespace from string fields."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v

    @field_validator("snapshot_text", mode="before")
    @classmethod
    def clean_snapshot_text(cls, v: Any) -> Any:
        """Sanitize snapshot text."""
        if isinstance(v, str):
            return sanitize_string(v) or ""
        return v


class DocumentDiff(BaseModel):
    """Structured delta record between two document versions."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(
        default_factory=lambda: f"diff_{uuid.uuid4().hex[:12]}",
        description="Unique diff record ID",
    )
    file_id: str = Field(..., description="Google Drive unique file ID")
    from_version_id: str | None = Field(
        default=None,
        description="Prior version ID (None for initial version)",
    )
    to_version_id: str = Field(..., description="Target version ID")
    patch_text: str = Field(..., description="Unified diff patch text")
    ai_summary: str | None = Field(
        default=None,
        description="Natural language summary of modifications",
    )
    lines_added: int = Field(
        default=0, description="Number of added lines in patch"
    )
    lines_removed: int = Field(
        default=0, description="Number of removed lines in patch"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Local diff generation timestamp (UTC)",
    )

    @field_validator("id", "file_id", "from_version_id", "to_version_id", "ai_summary", mode="before")
    @classmethod
    def clean_diff_strings(cls, v: Any) -> Any:
        """Strip control characters from identifier and summary strings."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class DiffResult(BaseModel):
    """Structured outcome of a text diff computation."""

    model_config = ConfigDict(frozen=True)

    has_changes: bool = Field(
        ..., description="Whether differences exist between old and new text"
    )
    patch_text: str = Field(
        default="", description="Unified diff patch string"
    )
    lines_added: int = Field(
        default=0, description="Total count of added lines (+)"
    )
    lines_removed: int = Field(
        default=0, description="Total count of deleted lines (-)"
    )
    hunks_count: int = Field(
        default=0, description="Number of distinct diff hunks (@@ blocks)"
    )


class DocumentChunk(BaseModel):
    """Domain entity representing a contextual semantic passage of an exported document."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique chunk identifier (e.g. chk_<hash/uuid>)")
    file_id: str = Field(..., description="Google Drive file ID")
    version_id: str | None = Field(
        default=None, description="DocumentVersion ID this chunk was extracted from"
    )
    chunk_index: int = Field(
        ..., description="Zero-based sequential index of the chunk within the document"
    )
    section_heading: str | None = Field(
        default=None, description="Extracted section heading or title context"
    )
    content_text: str = Field(
        ..., description="Text content of the chunk with metadata context anchor"
    )
    char_start: int = Field(
        default=0, description="Character offset start in original document text"
    )
    char_end: int = Field(
        default=0, description="Character offset end in original document text"
    )
    word_count: int = Field(
        default=0, description="Number of whitespace-delimited words in content"
    )
    embedding: list[float] | None = Field(
        default=None, description="Dense vector embedding representation"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Chunk generation timestamp (UTC)",
    )

    @field_validator("id", "file_id", "version_id", "section_heading", mode="before")
    @classmethod
    def clean_chunk_strings(cls, v: Any) -> Any:
        """Strip control characters from identifier and heading strings."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class AgentThread(BaseModel):
    """Domain model representing a multi-turn conversation thread."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(
        default_factory=lambda: f"th_{uuid.uuid4().hex[:12]}",
        description="Unique thread identifier",
    )
    title: str = Field(
        default="New Conversation",
        description="Human-readable title of the conversation thread",
    )
    model: str | None = Field(
        default=None,
        description="Primary LLM model used for this thread",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Thread creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Thread last activity timestamp (UTC)",
    )
    message_count: int = Field(
        default=0,
        description="Total messages in this thread",
    )

    @field_validator("id", "title", "model", mode="before")
    @classmethod
    def clean_thread_strings(cls, v: Any) -> Any:
        """Strip control characters from thread strings."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class AgentMessage(BaseModel):
    """Domain model representing a single conversational turn in a thread."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(
        default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}",
        description="Unique message turn identifier",
    )
    thread_id: str = Field(
        ...,
        description="Parent conversation thread identifier",
    )
    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Role of the message sender",
    )
    content: str = Field(
        ...,
        description="Natural language content of the message",
    )
    trace_json: str | None = Field(
        default=None,
        description="JSON-encoded execution trace of tool calls",
    )
    citations_json: str | None = Field(
        default=None,
        description="JSON-encoded list of verified document citations",
    )
    model: str | None = Field(
        default=None,
        description="Model ID that generated the message",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Execution duration in milliseconds",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message creation timestamp (UTC)",
    )

    @field_validator("id", "thread_id", "content", mode="before")
    @classmethod
    def clean_message_strings(cls, v: Any) -> Any:
        """Strip control characters from message strings."""
        if isinstance(v, str):
            return sanitize_string(v)
        return v




