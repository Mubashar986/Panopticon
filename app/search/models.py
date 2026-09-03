"""Data models for Meilisearch client, health checks, stats, documents, and search responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.indexer.models import GOOGLE_DOC_MIME_TYPE, GOOGLE_SHEET_MIME_TYPE, DriveFileMetadata


class MeiliVersionInfo(BaseModel):
    """Meilisearch server version metadata."""

    pkg_version: str = Field(description="Meilisearch server semver release version")
    commit_date: str | None = Field(default=None, description="Git commit date of the engine binary")
    commit_sha: str | None = Field(default=None, description="Git commit hash of the engine binary")


class MeiliHealthStatus(BaseModel):
    """Health check status and connectivity diagnostics for Meilisearch."""

    is_available: bool = Field(description="True if Meilisearch responds with HTTP 200 to /health")
    status: str = Field(default="unknown", description="Reported health status string (e.g., 'available')")
    host: str = Field(description="Target host URL configured for Meilisearch")
    version: str | None = Field(default=None, description="Engine version string if reachable")
    error_message: str | None = Field(default=None, description="Error details if connection failed")


class IndexStats(BaseModel):
    """Document and indexing statistics for a Meilisearch index."""

    index_uid: str = Field(description="Index identifier UID")
    is_indexing: bool = Field(default=False, description="True if background indexing task is running")
    number_of_documents: int = Field(default=0, description="Total indexed document count")
    field_distribution: dict[str, int] = Field(default_factory=dict, description="Field count distribution")


class SearchDocument(BaseModel):
    """Normalized document model indexed into Meilisearch for Panopticon search."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    id: str = Field(..., description="Unique document ID (Google Drive file ID)")
    name: str = Field(..., description="Document or Sheet title")
    mime_type: str = Field(..., description="MIME type of the file")
    file_type: str = Field(
        ...,
        description="Categorical type: 'document', 'spreadsheet', or 'other'",
    )
    modified_time: str | None = Field(
        default=None, description="ISO 8601 formatted last modification timestamp"
    )
    created_time: str | None = Field(
        default=None, description="ISO 8601 formatted creation timestamp"
    )
    primary_owner: str = Field(
        default="Shared Drive / Organization",
        description="Primary owner email or display name",
    )
    owners: list[str] = Field(
        default_factory=list, description="List of all owner emails/names"
    )
    last_modifying_user: str | None = Field(
        default=None, description="Last modifying user email or name"
    )
    sharing_status: str = Field(
        default="private",
        description="Sharing visibility: 'private', 'shared', 'domain', 'anyone'",
    )
    project_tags: list[str] = Field(
        default_factory=list,
        description="Extracted project tags from Google Drive Labels",
    )
    content_snippet: str | None = Field(
        default=None,
        description="Extracted text snippet for full-text search fallback",
    )
    export_status: str | None = Field(
        default=None,
        description="Content export status ('success', 'oversized_metadata_only', None)",
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
    vectors: dict[str, list[float]] | None = Field(
        default=None,
        alias="_vectors",
        description="Pre-computed embeddings dictionary keyed by embedder name",
    )

    @classmethod
    def from_drive_metadata(
        cls,
        drive_file: DriveFileMetadata,
        vector: list[float] | None = None,
    ) -> SearchDocument:
        """Construct a SearchDocument instance from a crawled DriveFileMetadata entity."""
        if drive_file.mime_type == GOOGLE_DOC_MIME_TYPE:
            cat_type = "document"
        elif drive_file.mime_type == GOOGLE_SHEET_MIME_TYPE:
            cat_type = "spreadsheet"
        else:
            cat_type = "other"

        mod_time_str = (
            drive_file.modified_time.isoformat()
            if drive_file.modified_time is not None
            else None
        )
        created_time_str = (
            drive_file.created_time.isoformat()
            if drive_file.created_time is not None
            else None
        )

        vectors_dict = {"default": vector} if vector is not None else None

        return cls(
            id=drive_file.id,
            name=drive_file.name,
            mime_type=drive_file.mime_type,
            file_type=cat_type,
            modified_time=mod_time_str,
            created_time=created_time_str,
            primary_owner=drive_file.primary_owner,
            owners=list(drive_file.owners),
            last_modifying_user=drive_file.last_modifying_user,
            sharing_status=drive_file.sharing_status,
            project_tags=list(drive_file.project_tags),
            content_snippet=drive_file.content_snippet,
            export_status=drive_file.export_status,
            web_view_link=drive_file.web_view_link,
            icon_link=drive_file.icon_link,
            size_bytes=drive_file.size_bytes,
            vectors=vectors_dict,
        )

    def to_meili_dict(self) -> dict[str, Any]:
        """Serialize document to JSON-compatible dictionary for Meilisearch ingestion."""
        d = self.model_dump(by_alias=True)
        if not d.get("_vectors"):
            d.pop("_vectors", None)
        return d


class ChunkSearchDocument(BaseModel):
    """Normalized paragraph-level chunk indexed into Meilisearch for dense vector retrieval."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    id: str = Field(..., description="Unique chunk ID (e.g. chk_...)")
    file_id: str = Field(..., description="Parent Google Drive file ID")
    file_name: str = Field(default="", description="Parent document title")
    version_id: str | None = Field(default=None, description="Associated document version ID")
    chunk_index: int = Field(default=0, description="Sequential index within document")
    section_heading: str | None = Field(default=None, description="Section heading anchor if present")
    content_text: str = Field(..., description="Plain text content of the paragraph chunk")
    char_start: int = Field(default=0, description="Character start offset in full text")
    char_end: int = Field(default=0, description="Character end offset in full text")
    word_count: int = Field(default=0, description="Word count of the chunk")
    web_view_link: str | None = Field(default=None, description="Direct Google Drive link")
    vectors: dict[str, list[float]] | None = Field(
        default=None,
        alias="_vectors",
        description="Pre-computed embeddings dictionary keyed by embedder name",
    )

    def to_meili_dict(self) -> dict[str, Any]:
        """Serialize chunk to JSON-compatible dictionary for Meilisearch."""
        d = self.model_dump(by_alias=True)
        if not d.get("_vectors"):
            d.pop("_vectors", None)
        return d


class IngestionResult(BaseModel):
    """Execution metrics for an ingestion or synchronization run."""

    model_config = ConfigDict(frozen=True)

    indexed_count: int = Field(default=0, description="Total documents successfully upserted")
    deleted_count: int = Field(default=0, description="Total orphaned/deleted documents purged")
    total_stored: int = Field(default=0, description="Total active documents stored in search index")
    batch_count: int = Field(default=0, description="Number of batch HTTP chunks sent")
    duration_seconds: float = Field(default=0.0, description="Total ingestion duration in seconds")
    is_full_sync: bool = Field(default=True, description="Whether this was a full index refresh")


MatchSource = Literal["tag", "title", "content", "owner"]
ConfidenceLevel = Literal["high", "medium", "low"]


class SearchHit(BaseModel):
    """Normalized search result hit representing a matching document pointer."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(..., description="Unique Google Drive document ID")
    name: str = Field(..., description="Document or Sheet title")
    mime_type: str = Field(..., description="MIME type of the file")
    file_type: str = Field(..., description="Categorical type: 'document', 'spreadsheet', or 'other'")
    primary_owner: str = Field(default="Shared Drive / Organization", description="Primary owner email or name")
    owners: list[str] = Field(default_factory=list, description="List of owner emails")
    last_modifying_user: str | None = Field(default=None, description="Last editor email or name")
    modified_time: str | None = Field(default=None, description="ISO 8601 modification timestamp")
    created_time: str | None = Field(default=None, description="ISO 8601 creation timestamp")
    sharing_status: str = Field(default="private", description="Sharing visibility status")
    project_tags: list[str] = Field(default_factory=list, description="Associated project label tags")
    content_snippet: str | None = Field(default=None, description="Cleaned document content snippet")
    export_status: str | None = Field(default=None, description="Export outcome status")
    web_view_link: str | None = Field(default=None, description="Direct URL to open file in Google Drive")
    icon_link: str | None = Field(default=None, description="File icon URL")
    size_bytes: int | None = Field(default=None, description="File size in bytes")

    matched_via: MatchSource = Field(
        default="content",
        description="Attribute where query matched ('tag', 'title', 'content', 'owner')",
    )
    confidence: ConfidenceLevel = Field(
        default="low",
        description="Relevance confidence level ('high', 'medium', 'low')",
    )
    highlighted_name: str | None = Field(
        default=None,
        description="Title with <em>...</em> HTML highlight tags around matched query terms",
    )
    highlighted_snippet: str | None = Field(
        default=None,
        description="Content snippet with <em>...</em> HTML highlight tags around matched terms",
    )


class SearchResult(BaseModel):
    """Paginated search query response container."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(..., description="Original search query string")
    hits: list[SearchHit] = Field(default_factory=list, description="Ordered list of matching document hits")
    total_hits: int = Field(default=0, description="Total matching documents in index")
    processing_time_ms: float = Field(default=0.0, description="Meilisearch execution duration in milliseconds")
    limit: int = Field(default=20, description="Requested page hit limit")
    offset: int = Field(default=0, description="Requested hit offset")
    facet_distribution: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="Distribution counts for filterable facets"
    )


__all__ = [
    "ChunkSearchDocument",
    "ConfidenceLevel",
    "IndexStats",
    "IngestionResult",
    "MatchSource",
    "MeiliHealthStatus",
    "MeiliVersionInfo",
    "SearchDocument",
    "SearchHit",
    "SearchResult",
]
