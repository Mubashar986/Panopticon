"""Unit tests for PanopticonSearchClient and Meilisearch health integration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from meilisearch.errors import (
    MeilisearchApiError,
    MeilisearchCommunicationError,
)

from app.search.client import PanopticonSearchClient, get_search_client
from app.search.exceptions import (
    IndexNotFoundError,
    SearchConnectionError,
)
from app.search.models import IndexStats, MeiliHealthStatus, MeiliVersionInfo


def test_search_client_init_defaults() -> None:
    """Test default client initialization uses settings."""
    client = PanopticonSearchClient()
    assert client.url == "http://localhost:7700"
    assert client.index_name == "panopticon_docs"
    assert client.raw_client is not None


def test_search_client_init_custom() -> None:
    """Test custom client initialization arguments."""
    client = PanopticonSearchClient(
        url="http://custom-host:7700/",
        api_key="custom_key",
        index_name="custom_index",
        timeout=10,
    )
    assert client.url == "http://custom-host:7700"
    assert client.api_key == "custom_key"
    assert client.index_name == "custom_index"
    assert client.timeout == 10


def test_check_health_healthy() -> None:
    """Test check_health returns healthy status when Meilisearch is reachable."""
    client = PanopticonSearchClient()

    mock_raw_client = MagicMock()
    mock_raw_client.health.return_value = {"status": "available"}
    mock_raw_client.get_version.return_value = {
        "pkgVersion": "1.12.0",
        "commitDate": "2026-08-25",
        "commitSha": "abc1234",
    }
    client._client = mock_raw_client

    health: MeiliHealthStatus = client.check_health()

    assert health.is_available is True
    assert health.status == "available"
    assert health.version == "1.12.0"
    assert health.error_message is None
    assert client.is_healthy() is True


def test_check_health_unreachable() -> None:
    """Test check_health handles connection errors gracefully without crashing."""
    client = PanopticonSearchClient()

    mock_raw_client = MagicMock()
    mock_raw_client.health.side_effect = MeilisearchCommunicationError("Connection refused")
    client._client = mock_raw_client

    health: MeiliHealthStatus = client.check_health()

    assert health.is_available is False
    assert health.status == "unreachable"
    assert health.version is None
    assert "Connection refused" in (health.error_message or "")
    assert client.is_healthy() is False


def test_check_health_api_error() -> None:
    """Test check_health handles Meilisearch API errors (e.g. 401 unauthorized)."""
    client = PanopticonSearchClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = '{"message": "Invalid API key"}'
    mock_response.json.return_value = {"message": "Invalid API key"}

    mock_raw_client = MagicMock()
    mock_raw_client.health.side_effect = MeilisearchApiError("Invalid API key", mock_response)
    client._client = mock_raw_client

    health: MeiliHealthStatus = client.check_health()

    assert health.is_available is False
    assert health.status == "api_error"
    assert "API Error" in (health.error_message or "")


def test_get_version_success() -> None:
    """Test get_version returns strongly-typed MeiliVersionInfo."""
    client = PanopticonSearchClient()

    mock_raw_client = MagicMock()
    mock_raw_client.get_version.return_value = {
        "pkgVersion": "1.12.0",
        "commitDate": "2026-08-20",
        "commitSha": "deadbeef",
    }
    client._client = mock_raw_client

    ver: MeiliVersionInfo = client.get_version()
    assert ver.pkg_version == "1.12.0"
    assert ver.commit_date == "2026-08-20"
    assert ver.commit_sha == "deadbeef"


def test_get_version_connection_error_raises_search_connection_error() -> None:
    """Test get_version raises SearchConnectionError on connection loss."""
    client = PanopticonSearchClient()

    mock_raw_client = MagicMock()
    mock_raw_client.get_version.side_effect = MeilisearchCommunicationError("Timeout")
    client._client = mock_raw_client

    with pytest.raises(SearchConnectionError) as exc_info:
        client.get_version()
    assert "Cannot connect to Meilisearch" in str(exc_info.value)


def test_ensure_index_exists() -> None:
    """Test ensure_index returns existing index without recreating."""
    client = PanopticonSearchClient()

    mock_index = MagicMock()
    mock_raw_client = MagicMock()
    mock_raw_client.get_index.return_value = mock_index
    client._client = mock_raw_client

    result = client.ensure_index("panopticon_docs")
    assert result == mock_index
    mock_raw_client.get_index.assert_called_once_with("panopticon_docs")
    mock_raw_client.create_index.assert_not_called()


def test_ensure_index_creates_if_not_found() -> None:
    """Test ensure_index creates index when 404 is received."""
    client = PanopticonSearchClient()

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = '{"message": "Index not found", "code": "index_not_found"}'
    mock_response.json.return_value = {"message": "Index not found", "code": "index_not_found"}

    mock_task = MagicMock()
    mock_task.task_uid = 42

    mock_created_index = MagicMock()

    mock_raw_client = MagicMock()
    mock_raw_client.get_index.side_effect = [
        MeilisearchApiError("Index not found", mock_response),
        mock_created_index,
    ]
    mock_raw_client.create_index.return_value = mock_task
    client._client = mock_raw_client

    result = client.ensure_index("new_index", primary_key="file_id")

    assert result == mock_created_index
    mock_raw_client.create_index.assert_called_once_with("new_index", {"primaryKey": "file_id"})
    mock_raw_client.wait_for_task.assert_called_once_with(42)


def test_get_stats_success() -> None:
    """Test get_stats returns typed IndexStats."""
    client = PanopticonSearchClient()

    mock_index = MagicMock()
    mock_index.get_stats.return_value = {
        "numberOfDocuments": 150,
        "isIndexing": False,
        "fieldDistribution": {"name": 150, "snippet": 140},
    }

    mock_raw_client = MagicMock()
    mock_raw_client.get_index.return_value = mock_index
    client._client = mock_raw_client

    stats: IndexStats = client.get_stats("panopticon_docs")

    assert stats.index_uid == "panopticon_docs"
    assert stats.number_of_documents == 150
    assert stats.is_indexing is False
    assert stats.field_distribution == {"name": 150, "snippet": 140}


def test_get_stats_not_found() -> None:
    """Test get_stats raises IndexNotFoundError on 404."""
    client = PanopticonSearchClient()

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = '{"message": "Index not found"}'
    mock_response.json.return_value = {"message": "Index not found"}

    mock_raw_client = MagicMock()
    mock_raw_client.get_index.side_effect = MeilisearchApiError("Not found", mock_response)
    client._client = mock_raw_client

    with pytest.raises(IndexNotFoundError):
        client.get_stats("missing_index")


def test_get_search_client_factory() -> None:
    """Test get_search_client factory returns client."""
    client = get_search_client()
    assert isinstance(client, PanopticonSearchClient)
