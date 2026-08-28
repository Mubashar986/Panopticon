"""Search document schema, Meilisearch index settings, and provisioning helpers."""

from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
)
from app.search.exceptions import IndexConfigurationError, SearchConnectionError, SearchError

logger = logging.getLogger("panopticon.search.schema")

# Canonical Meilisearch index settings for Panopticon
INDEX_SETTINGS: dict[str, Any] = {
    "searchableAttributes": [
        "project_tags",
        "name",
        "content_snippet",
        "primary_owner",
        "owners",
        "last_modifying_user",
    ],
    "filterableAttributes": [
        "file_type",
        "mime_type",
        "sharing_status",
        "project_tags",
        "primary_owner",
        "owners",
        "export_status",
    ],
    "sortableAttributes": [
        "modified_time",
        "created_time",
        "name",
    ],
    "displayedAttributes": [
        "id",
        "name",
        "mime_type",
        "file_type",
        "modified_time",
        "created_time",
        "primary_owner",
        "owners",
        "last_modifying_user",
        "sharing_status",
        "project_tags",
        "content_snippet",
        "export_status",
        "web_view_link",
        "icon_link",
        "size_bytes",
    ],
    "rankingRules": [
        "words",
        "typo",
        "proximity",
        "attribute",
        "sort",
        "exactness",
    ],
    "typoTolerance": {
        "enabled": True,
        "minWordSizeForTypos": {
            "oneTypo": 4,
            "twoTypos": 8,
        },
        "disableOnWords": [],
        "disableOnAttributes": [],
    },
}


class SearchDocument(BaseModel):
    """Normalized document model indexed into Meilisearch for Panopticon search."""

    model_config = ConfigDict(frozen=True, extra="ignore")

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

    @classmethod
    def from_drive_metadata(cls, drive_file: DriveFileMetadata) -> SearchDocument:
        """Construct a SearchDocument instance from a crawled DriveFileMetadata entity."""
        # Derive categorical file type
        if drive_file.mime_type == GOOGLE_DOC_MIME_TYPE:
            cat_type = "document"
        elif drive_file.mime_type == GOOGLE_SHEET_MIME_TYPE:
            cat_type = "spreadsheet"
        else:
            cat_type = "other"

        # Format timestamps to ISO strings
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
        )

    def to_meili_dict(self) -> dict[str, Any]:
        """Serialize document to JSON-compatible dictionary for Meilisearch ingestion."""
        return self.model_dump()


def configure_index_schema(
    client: Any,
    index_name: str | None = None,
    settings_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotently apply Panopticon index settings (searchable, filterable, sortable, ranking rules).

    Args:
        client: PanopticonSearchClient or meilisearch.Client instance.
        index_name: Target index UID. Defaults to configured index name.
        settings_dict: Optional custom settings. Defaults to INDEX_SETTINGS.

    Returns:
        The updated settings dictionary returned by Meilisearch.

    Raises:
        SearchConnectionError: If Meilisearch is unreachable.
        IndexConfigurationError: If applying the schema settings fails.
    """
    settings_to_apply = settings_dict or INDEX_SETTINGS
    target_uid = index_name or getattr(client, "index_name", "panopticon_docs")

    try:
        # Ensure index exists with primary key 'id'
        if hasattr(client, "ensure_index"):
            index = client.ensure_index(target_uid, primary_key="id")
            raw_client = getattr(client, "raw_client", client)
        else:
            index = client.index(target_uid)
            raw_client = client

        logger.info("Applying index settings to '%s'...", target_uid)
        task = index.update_settings(settings_to_apply)

        # Wait for task completion
        task_uid = task.task_uid if hasattr(task, "task_uid") else task.get("taskUid")
        if task_uid is not None:
            task_result = raw_client.wait_for_task(task_uid)
            status = (
                task_result.status
                if hasattr(task_result, "status")
                else task_result.get("status")
            )
            if status == "failed":
                error_details = (
                    task_result.error
                    if hasattr(task_result, "error")
                    else task_result.get("error", "Unknown error")
                )
                raise IndexConfigurationError(
                    f"Meilisearch schema update task {task_uid} failed: {error_details}"
                )

        logger.info("Successfully applied index schema to '%s'.", target_uid)
        return index.get_settings()

    except IndexConfigurationError:
        raise
    except Exception as exc:
        err_msg = str(exc)
        if "connection refused" in err_msg.lower() or "communicationerror" in type(exc).__name__.lower():
            raise SearchConnectionError(
                f"Cannot connect to Meilisearch to configure schema: {exc}"
            ) from exc
        raise IndexConfigurationError(
            f"Failed to configure Meilisearch schema for index '{target_uid}': {exc}"
        ) from exc


def get_index_schema(
    client: Any,
    index_name: str | None = None,
) -> dict[str, Any]:
    """Retrieve current settings for the search index."""
    target_uid = index_name or getattr(client, "index_name", "panopticon_docs")
    try:
        if hasattr(client, "raw_client"):
            index = client.raw_client.index(target_uid)
        elif hasattr(client, "index"):
            index = client.index(target_uid)
        else:
            index = client.get_index(target_uid)
        return index.get_settings()
    except Exception as exc:
        raise SearchError(f"Failed to retrieve index settings for '{target_uid}': {exc}") from exc
