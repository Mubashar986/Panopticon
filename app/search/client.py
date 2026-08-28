"""Panopticon Meilisearch Client adapter with health checks and resilience."""

from __future__ import annotations

import logging
from typing import Any
import meilisearch
from meilisearch.errors import (
    MeilisearchApiError,
    MeilisearchCommunicationError,
    MeilisearchError,
    MeilisearchTimeoutError,
)

from app.core.config import Settings, get_settings
from app.search.exceptions import (
    IndexConfigurationError,
    IndexNotFoundError,
    SearchAuthError,
    SearchConnectionError,
    SearchError,
)
from app.search.models import IndexStats, MeiliHealthStatus, MeiliVersionInfo

logger = logging.getLogger("panopticon.search")


class PanopticonSearchClient:
    """Adapter wrapping official Meilisearch Python SDK with resilience and domain typing."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        index_name: str | None = None,
        timeout: int | float | None = 5,
    ) -> None:
        settings: Settings = get_settings()
        self.url = (url or settings.MEILI_HOST).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.MEILI_MASTER_KEY
        self.index_name = index_name or settings.MEILI_INDEX_NAME
        self.timeout = timeout

        self._client = meilisearch.Client(
            url=self.url,
            api_key=self.api_key if self.api_key else None,
            timeout=self.timeout,
        )

    @property
    def raw_client(self) -> meilisearch.Client:
        """Access underlying Meilisearch SDK client instance."""
        return self._client

    def check_health(self) -> MeiliHealthStatus:
        """Check Meilisearch server connectivity and health."""
        try:
            health_response = self._client.health()
            status_str = (
                health_response.get("status", "available")
                if isinstance(health_response, dict)
                else getattr(health_response, "status", "available")
            )

            version_str: str | None = None
            try:
                ver = self._client.get_version()
                version_str = ver.get("pkgVersion") if isinstance(ver, dict) else getattr(ver, "pkg_version", None)
            except Exception as ver_err:
                logger.debug("Could not retrieve Meilisearch version: %s", ver_err)

            return MeiliHealthStatus(
                is_available=True,
                status=str(status_str),
                host=self.url,
                version=version_str,
                error_message=None,
            )
        except MeilisearchCommunicationError as comm_err:
            logger.warning("Meilisearch server unreachable at %s: %s", self.url, comm_err)
            return MeiliHealthStatus(
                is_available=False,
                status="unreachable",
                host=self.url,
                version=None,
                error_message=f"Connection refused or unreachable at {self.url}: {comm_err}",
            )
        except MeilisearchApiError as api_err:
            logger.warning("Meilisearch API error during health check: %s", api_err)
            return MeiliHealthStatus(
                is_available=False,
                status="api_error",
                host=self.url,
                version=None,
                error_message=f"API Error ({api_err.status_code}): {api_err.message}",
            )
        except Exception as exc:
            logger.warning("Unexpected error checking Meilisearch health: %s", exc)
            return MeiliHealthStatus(
                is_available=False,
                status="error",
                host=self.url,
                version=None,
                error_message=str(exc),
            )

    def is_healthy(self) -> bool:
        """Return True if Meilisearch instance is reachable and healthy."""
        return self.check_health().is_available

    def get_version(self) -> MeiliVersionInfo:
        """Get Meilisearch engine version details."""
        try:
            ver = self._client.get_version()
            if isinstance(ver, dict):
                return MeiliVersionInfo(
                    pkg_version=ver.get("pkgVersion", "unknown"),
                    commit_date=ver.get("commitDate"),
                    commit_sha=ver.get("commitSha"),
                )
            return MeiliVersionInfo(
                pkg_version=getattr(ver, "pkg_version", "unknown"),
                commit_date=getattr(ver, "commit_date", None),
                commit_sha=getattr(ver, "commit_sha", None),
            )
        except MeilisearchCommunicationError as e:
            raise SearchConnectionError(f"Cannot connect to Meilisearch at {self.url}: {e}") from e
        except MeilisearchApiError as e:
            raise SearchAuthError(f"Meilisearch API error ({e.status_code}): {e.message}") from e
        except Exception as e:
            raise SearchError(f"Error querying Meilisearch version: {e}") from e

    def ensure_index(
        self,
        index_uid: str | None = None,
        primary_key: str = "id",
    ) -> Any:
        """Ensure that the search index exists, creating it with the primary key if absent."""
        uid = index_uid or self.index_name
        try:
            return self._client.get_index(uid)
        except MeilisearchApiError as api_err:
            if api_err.status_code == 404 or "index_not_found" in getattr(api_err, "code", ""):
                try:
                    task = self._client.create_index(uid, {"primaryKey": primary_key})
                    self._client.wait_for_task(task.task_uid)
                    return self._client.get_index(uid)
                except Exception as create_err:
                    raise IndexConfigurationError(
                        f"Failed creating index '{uid}': {create_err}"
                    ) from create_err
            raise SearchError(f"Error accessing index '{uid}': {api_err.message}") from api_err
        except MeilisearchCommunicationError as comm_err:
            raise SearchConnectionError(
                f"Cannot connect to Meilisearch at {self.url}: {comm_err}"
            ) from comm_err

    def get_stats(self, index_uid: str | None = None) -> IndexStats:
        """Fetch index document and indexing statistics."""
        uid = index_uid or self.index_name
        try:
            index = self._client.get_index(uid)
            raw_stats = index.get_stats()
            if isinstance(raw_stats, dict):
                return IndexStats(
                    index_uid=uid,
                    is_indexing=raw_stats.get("isIndexing", False),
                    number_of_documents=raw_stats.get("numberOfDocuments", 0),
                    field_distribution=raw_stats.get("fieldDistribution", {}),
                )
            return IndexStats(
                index_uid=uid,
                is_indexing=getattr(raw_stats, "is_indexing", False),
                number_of_documents=getattr(raw_stats, "number_of_documents", 0),
                field_distribution=getattr(raw_stats, "field_distribution", {}),
            )
        except MeilisearchApiError as api_err:
            if api_err.status_code == 404:
                raise IndexNotFoundError(f"Index '{uid}' not found") from api_err
            raise SearchError(f"Error fetching stats for index '{uid}': {api_err.message}") from api_err
    def configure_schema(
        self,
        index_uid: str | None = None,
        settings_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Configure and apply schema, ranking rules, and facets to the index."""
        from app.search.schema import configure_index_schema

        uid = index_uid or self.index_name
        return configure_index_schema(client=self, index_name=uid, settings_dict=settings_dict)

    def get_schema_settings(self, index_uid: str | None = None) -> dict[str, Any]:
        """Fetch active settings for the index."""
        from app.search.schema import get_index_schema

        uid = index_uid or self.index_name
        return get_index_schema(client=self, index_name=uid)


def get_search_client(
    url: str | None = None,
    api_key: str | None = None,
    index_name: str | None = None,
) -> PanopticonSearchClient:
    """Factory helper returning a configured PanopticonSearchClient instance."""
    return PanopticonSearchClient(url=url, api_key=api_key, index_name=index_name)
