"""Search query parameters and JSON response contract schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.search.models import SearchHit, SearchResult


class SearchItemResponse(BaseModel):
    """Document search hit response model conforming to Panopticon dashboard contract."""

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
    sharing_status: str = Field(default="private", description="Sharing visibility: 'private', 'shared', 'domain'")
    shared_with: str = Field(default="private", description="Sharing scope indicator for UI badges")
    project_tags: list[str] = Field(default_factory=list, description="Extracted Google Drive project label tags")
    snippet: str | None = Field(default=None, description="Document content snippet (pointer, not full text)")
    view_url: str | None = Field(default=None, description="Direct URL link to open file in Google Drive")
    icon_link: str | None = Field(default=None, description="File type icon URL")
    size_bytes: int | None = Field(default=None, description="File size in bytes if available")
    export_status: str | None = Field(default=None, description="Export status ('success', 'oversized_metadata_only')")
    export_links: dict[str, str] | None = Field(default=None, description="Convenience export URLs if applicable")
    matched_via: Literal["tag", "title", "content", "owner"] = Field(
        default="content", description="Match source attribute"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low", description="Match attribution confidence score"
    )
    highlighted_name: str | None = Field(default=None, description="Title containing HTML highlight tags")
    highlighted_snippet: str | None = Field(default=None, description="Snippet containing HTML highlight tags")

    @classmethod
    def from_search_hit(cls, hit: SearchHit) -> SearchItemResponse:
        """Map internal search domain SearchHit to public API SearchItemResponse."""
        # Generate convenience export links for Google Docs & Sheets
        export_links: dict[str, str] | None = None
        if hit.mime_type == "application/vnd.google-apps.document":
            export_links = {
                "pdf": f"https://docs.google.com/document/d/{hit.id}/export?format=pdf",
                "docx": f"https://docs.google.com/document/d/{hit.id}/export?format=docx",
                "txt": f"https://docs.google.com/document/d/{hit.id}/export?format=txt",
            }
        elif hit.mime_type == "application/vnd.google-apps.spreadsheet":
            export_links = {
                "pdf": f"https://docs.google.com/spreadsheets/d/{hit.id}/export?format=pdf",
                "xlsx": f"https://docs.google.com/spreadsheets/d/{hit.id}/export?format=xlsx",
                "csv": f"https://docs.google.com/spreadsheets/d/{hit.id}/export?format=csv",
            }

        return cls(
            id=hit.id,
            name=hit.name,
            type=hit.file_type,
            mime_type=hit.mime_type,
            owner=hit.primary_owner,
            owners=list(hit.owners),
            last_modifying_user=hit.last_modifying_user,
            modified_time=hit.modified_time,
            created_time=hit.created_time,
            sharing_status=hit.sharing_status,
            shared_with=hit.sharing_status,
            project_tags=list(hit.project_tags),
            snippet=hit.content_snippet,
            view_url=hit.web_view_link,
            icon_link=hit.icon_link,
            size_bytes=hit.size_bytes,
            export_status=hit.export_status,
            export_links=export_links,
            matched_via=hit.matched_via,
            confidence=hit.confidence,
            highlighted_name=hit.highlighted_name,
            highlighted_snippet=hit.highlighted_snippet,
        )


class SearchResponse(BaseModel):
    """Paginated search query response payload."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(..., description="Search query string executed")
    total_hits: int = Field(default=0, description="Estimated total matching documents found in index")
    processing_time_ms: float = Field(default=0.0, description="Meilisearch execution time in milliseconds")
    limit: int = Field(default=20, description="Page limit requested")
    offset: int = Field(default=0, description="Page offset requested")
    facet_distribution: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="Counts of matching results across filter facets"
    )
    results: list[SearchItemResponse] = Field(
        default_factory=list, description="Ordered matching document result items"
    )

    @classmethod
    def from_search_result(cls, result: SearchResult) -> SearchResponse:
        """Map internal SearchResult domain model to public API SearchResponse."""
        return cls(
            query=result.query,
            total_hits=result.total_hits,
            processing_time_ms=result.processing_time_ms,
            limit=result.limit,
            offset=result.offset,
            facet_distribution=result.facet_distribution,
            results=[SearchItemResponse.from_search_hit(hit) for hit in result.hits],
        )
