"""Search document schema, Meilisearch index settings, and provisioning helpers."""

from __future__ import annotations

import logging
from typing import Any

from app.search.exceptions import IndexConfigurationError, SearchConnectionError, SearchError
from app.search.models import SearchDocument

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

    try:
        # Resolve client wrapper or raw meilisearch Client
        if hasattr(client, "ensure_index"):
            index = client.ensure_index(index_name, primary_key="id")
            raw_client = client.raw_client
        else:
            raw_client = client
            target_uid = index_name or "panopticon_docs"
            try:
                index = raw_client.get_index(target_uid)
            except Exception:
                task = raw_client.create_index(target_uid, {"primaryKey": "id"})
                raw_client.wait_for_task(task.task_uid)
                index = raw_client.get_index(target_uid)

        logger.info("Applying index settings to '%s'...", index.uid)
        task = index.update_settings(settings_to_apply)

        task_uid = task.task_uid if hasattr(task, "task_uid") else task.get("taskUid")
        if task_uid is not None:
            task_result = raw_client.wait_for_task(task_uid)
            status = (
                task_result.status
                if hasattr(task_result, "status")
                else task_result.get("status")
            )
            if status == "failed":
                error = (
                    task_result.error
                    if hasattr(task_result, "error")
                    else task_result.get("error", "Unknown error")
                )
                raise IndexConfigurationError(
                    f"Meilisearch schema update task {task_uid} failed: {error}"
                )

        current_settings = index.get_settings()
        logger.info("Schema settings successfully verified on '%s'.", index.uid)
        return current_settings

    except (IndexConfigurationError, SearchConnectionError, SearchError):
        raise
    except Exception as exc:
        err_str = str(exc).lower()
        if "connection refused" in err_str or "communicationerror" in type(exc).__name__.lower():
            raise SearchConnectionError(
                f"Cannot connect to Meilisearch while configuring schema: {exc}"
            ) from exc
        raise IndexConfigurationError(f"Failed to configure index schema: {exc}") from exc


def get_index_schema(client: Any, index_name: str | None = None) -> dict[str, Any]:
    """Retrieve current active settings for the index."""
    try:
        if hasattr(client, "raw_client"):
            raw_client = client.raw_client
            target_uid = index_name or client.index_name
        else:
            raw_client = client
            target_uid = index_name or "panopticon_docs"

        index = raw_client.index(target_uid)
        return index.get_settings()
    except Exception as exc:
        raise SearchError(f"Failed fetching index schema: {exc}") from exc


__all__ = [
    "INDEX_SETTINGS",
    "SearchDocument",
    "configure_index_schema",
    "get_index_schema",
]
