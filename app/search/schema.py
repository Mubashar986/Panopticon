"""Search document schema, Meilisearch index settings, and provisioning helpers."""

from __future__ import annotations

import logging
from typing import Any, cast

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


CHUNK_INDEX_NAME = "panopticon_chunks"

CHUNK_INDEX_SETTINGS: dict[str, Any] = {
    "searchableAttributes": [
        "section_heading",
        "content_text",
        "file_name",
    ],
    "filterableAttributes": [
        "file_id",
        "section_heading",
    ],
    "displayedAttributes": [
        "id",
        "file_id",
        "file_name",
        "section_heading",
        "content_text",
        "char_start",
        "char_end",
        "word_count",
        "web_view_link",
    ],
}


def enable_vector_store(client: Any) -> bool:
    """Idempotently enable the experimental vector store feature on Meilisearch (v1.3 - v1.12)."""
    import httpx

    try:
        url = getattr(client, "url", None)
        api_key = getattr(client, "api_key", None)
        if not url:
            if hasattr(client, "config") and hasattr(client.config, "url"):
                url = client.config.url
                api_key = client.config.api_key
            else:
                from app.core.config import get_settings
                url = get_settings().MEILI_HOST
                api_key = get_settings().MEILI_MASTER_KEY

        base_url = str(url).rstrip("/")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        with httpx.Client(timeout=5.0) as http_client:
            res = http_client.patch(
                f"{base_url}/experimental-features",
                json={"vectorStore": True},
                headers=headers,
            )
            if res.status_code in (200, 201):
                logger.info("Meilisearch vectorStore experimental feature successfully asserted.")
                return True
            logger.debug("PATCH /experimental-features returned status %s: %s", res.status_code, res.text)
            return False
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not toggle experimental vectorStore: %s", exc)
        return False


def configure_index_schema(
    client: Any,
    index_name: str | None = None,
    settings_dict: dict[str, Any] | None = None,
    dimension: int | None = None,
) -> dict[str, Any]:
    """Idempotently apply Panopticon index settings (searchable, filterable, sortable, ranking rules, embedders).

    Args:
        client: PanopticonSearchClient or meilisearch.Client instance.
        index_name: Target index UID. Defaults to configured index name.
        settings_dict: Optional custom settings. Defaults to INDEX_SETTINGS.
        dimension: Optional vector dimensionality for the userProvided embedder.

    Returns:
        The updated settings dictionary returned by Meilisearch.

    Raises:
        SearchConnectionError: If Meilisearch is unreachable.
        IndexConfigurationError: If applying the schema settings fails.
    """
    enable_vector_store(client)

    base_settings = settings_dict or INDEX_SETTINGS
    settings_to_apply = dict(base_settings)
    if dimension is not None:
        settings_to_apply["embedders"] = {
            "default": {
                "source": "userProvided",
                "dimensions": dimension,
            }
        }

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
            except Exception:  # noqa: BLE001
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
        return cast(dict[str, Any], current_settings)

    except (IndexConfigurationError, SearchConnectionError, SearchError):
        raise
    except Exception as exc:
        err_str = str(exc).lower()
        if "connection refused" in err_str or "communicationerror" in type(exc).__name__.lower():
            raise SearchConnectionError(
                f"Cannot connect to Meilisearch while configuring schema: {exc}"
            ) from exc
        raise IndexConfigurationError(f"Failed to configure index schema: {exc}") from exc


def configure_chunk_index_schema(
    client: Any,
    index_name: str | None = None,
    dimension: int = 128,
) -> dict[str, Any]:
    """Configure schema, attributes, and userProvided embedders for the chunk index.

    Args:
        client: PanopticonSearchClient or meilisearch.Client instance.
        index_name: Target index UID. Defaults to CHUNK_INDEX_NAME ('panopticon_chunks').
        dimension: Vector dimensionality for the userProvided embedder (default: 128).

    Returns:
        The updated settings dictionary returned by Meilisearch.
    """
    enable_vector_store(client)

    target_uid = index_name or CHUNK_INDEX_NAME
    chunk_settings = dict(CHUNK_INDEX_SETTINGS)
    chunk_settings["embedders"] = {
        "default": {
            "source": "userProvided",
            "dimensions": dimension,
        }
    }

    try:
        if hasattr(client, "ensure_index"):
            index = client.ensure_index(target_uid, primary_key="id")
            raw_client = client.raw_client
        else:
            raw_client = client
            try:
                index = raw_client.get_index(target_uid)
            except Exception:  # noqa: BLE001
                task = raw_client.create_index(target_uid, {"primaryKey": "id"})
                raw_client.wait_for_task(task.task_uid)
                index = raw_client.get_index(target_uid)

        logger.info("Applying chunk index settings to '%s' (dimension=%d)...", index.uid, dimension)
        task = index.update_settings(chunk_settings)

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
                    f"Meilisearch chunk schema update task {task_uid} failed: {error}"
                )

        current_settings = index.get_settings()
        logger.info("Chunk schema settings successfully verified on '%s'.", index.uid)
        return cast(dict[str, Any], current_settings)

    except (IndexConfigurationError, SearchConnectionError, SearchError):
        raise
    except Exception as exc:
        err_str = str(exc).lower()
        if "connection refused" in err_str or "communicationerror" in type(exc).__name__.lower():
            raise SearchConnectionError(
                f"Cannot connect to Meilisearch while configuring chunk schema: {exc}"
            ) from exc
        raise IndexConfigurationError(f"Failed to configure chunk index schema: {exc}") from exc


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
        return cast(dict[str, Any], index.get_settings())
    except Exception as exc:
        raise SearchError(f"Failed fetching index schema: {exc}") from exc


__all__ = [
    "CHUNK_INDEX_NAME",
    "CHUNK_INDEX_SETTINGS",
    "INDEX_SETTINGS",
    "SearchDocument",
    "configure_chunk_index_schema",
    "configure_index_schema",
    "enable_vector_store",
    "get_index_schema",
]
