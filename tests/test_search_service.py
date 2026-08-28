"""Unit tests for SearchService, typo tolerance, ranking rules, and match attribution."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from app.search.client import PanopticonSearchClient
from app.search.exceptions import IndexNotFoundError, SearchConnectionError, SearchError
from app.search.service import SearchHit, SearchResult, SearchService


def test_search_service_typo_tolerance() -> None:
    """Test searching with typo 'Falcn' returns matching 'Falcon' document."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.ensure_index.return_value = mock_index

    # Simulated Meilisearch response for "Falcn"
    mock_index.search.return_value = {
        "hits": [
            {
                "id": "doc_1",
                "name": "Project Falcon Architecture",
                "mime_type": "application/vnd.google-apps.document",
                "file_type": "document",
                "primary_owner": "lead@company.com",
                "owners": ["lead@company.com"],
                "last_modifying_user": "dev@company.com",
                "modified_time": "2026-08-28T12:00:00+00:00",
                "created_time": "2026-08-20T10:00:00+00:00",
                "sharing_status": "domain",
                "project_tags": ["Falcon"],
                "content_snippet": "System architecture for Falcon...",
                "web_view_link": "https://docs.google.com/doc_1",
                "_formatted": {
                    "name": "Project <em>Falcon</em> Architecture",
                    "project_tags": ["<em>Falcon</em>"],
                },
            }
        ],
        "estimatedTotalHits": 1,
        "processingTimeMs": 8.5,
        "facetDistribution": {"file_type": {"document": 1}},
    }

    service = SearchService(search_client=mock_client)
    res = service.search(query="Falcn")

    assert res.query == "Falcn"
    assert res.total_hits == 1
    assert res.processing_time_ms == 8.5
    assert len(res.hits) == 1

    hit = res.hits[0]
    assert hit.id == "doc_1"
    assert hit.name == "Project Falcon Architecture"
    assert hit.matched_via == "tag"
    assert hit.confidence == "high"
    assert hit.highlighted_name == "Project <em>Falcon</em> Architecture"


def test_search_service_ranking_priority() -> None:
    """Test match attribution and ranking order: tag matches before title matches."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.ensure_index.return_value = mock_index

    # Meilisearch returns tag hit first, then title hit, then body-only hit
    mock_index.search.return_value = {
        "hits": [
            {
                "id": "hit_tag",
                "name": "General Overview",
                "mime_type": "application/vnd.google-apps.document",
                "file_type": "document",
                "project_tags": ["Phoenix"],
                "content_snippet": "General notes...",
                "_formatted": {
                    "name": "General Overview",
                    "project_tags": ["<em>Phoenix</em>"],
                },
            },
            {
                "id": "hit_title",
                "name": "Phoenix Roadmap",
                "mime_type": "application/vnd.google-apps.spreadsheet",
                "file_type": "spreadsheet",
                "project_tags": [],
                "content_snippet": "Roadmap dates...",
                "_formatted": {
                    "name": "<em>Phoenix</em> Roadmap",
                    "project_tags": [],
                },
            },
            {
                "id": "hit_body",
                "name": "Meeting Minutes",
                "mime_type": "application/vnd.google-apps.document",
                "file_type": "document",
                "project_tags": [],
                "content_snippet": "...discussed the phoenix plan...",
                "_formatted": {
                    "name": "Meeting Minutes",
                    "content_snippet": "...discussed the <em>phoenix</em> plan...",
                },
            },
        ],
        "estimatedTotalHits": 3,
        "processingTimeMs": 12.0,
    }

    service = SearchService(search_client=mock_client)
    res = service.search(query="Phoenix")

    assert len(res.hits) == 3
    assert res.hits[0].matched_via == "tag"
    assert res.hits[0].confidence == "high"

    assert res.hits[1].matched_via == "title"
    assert res.hits[1].confidence == "medium"

    assert res.hits[2].matched_via == "content"
    assert res.hits[2].confidence == "low"


def test_search_service_facet_filtering() -> None:
    """Test building and passing facet filter expressions to Meilisearch."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.ensure_index.return_value = mock_index
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}

    service = SearchService(search_client=mock_client)
    service.search(
        query="Budget",
        file_type="spreadsheet",
        sharing_status="domain",
        project_tag="Falcon",
        primary_owner="lead@company.com",
    )

    # Verify search params passed to Meilisearch index
    call_args = mock_index.search.call_args
    assert call_args is not None
    query_passed = call_args[0][0]
    opt_params = call_args[0][1]

    assert query_passed == "Budget"
    assert 'file_type = "spreadsheet"' in opt_params["filter"]
    assert 'sharing_status = "domain"' in opt_params["filter"]
    assert 'project_tags = "Falcon"' in opt_params["filter"]
    assert 'primary_owner = "lead@company.com"' in opt_params["filter"]


def test_search_service_sort_parameter() -> None:
    """Test passing sort criteria."""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.ensure_index.return_value = mock_index
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}

    service = SearchService(search_client=mock_client)
    service.search(query="Test", sort_by="modified_time:desc")

    opt_params = mock_index.search.call_args[0][1]
    assert opt_params["sort"] == ["modified_time:desc"]


def test_search_service_connection_error() -> None:
    """Test raising SearchConnectionError when Meilisearch connection fails."""
    mock_client = MagicMock()
    mock_client.ensure_index.side_effect = Exception("Connection refused on 7700")

    service = SearchService(search_client=mock_client)
    with pytest.raises(SearchConnectionError):
        service.search(query="Test")


def test_search_service_index_not_found() -> None:
    """Test raising IndexNotFoundError when index does not exist."""
    mock_client = MagicMock()
    mock_client.ensure_index.side_effect = Exception("index_not_found error")

    service = SearchService(search_client=mock_client)
    with pytest.raises(IndexNotFoundError):
        service.search(query="Test")


def test_panopticon_search_client_search_delegation() -> None:
    """Test PanopticonSearchClient.search helper delegates to SearchService."""
    client = PanopticonSearchClient()
    mock_raw = MagicMock()
    mock_index = MagicMock()
    mock_index.search.return_value = {
        "hits": [
            {
                "id": "1",
                "name": "Doc 1",
                "mime_type": "text/plain",
                "file_type": "other",
            }
        ],
        "estimatedTotalHits": 1,
    }
    mock_raw.index.return_value = mock_index
    mock_raw.get_index.return_value = mock_index
    client._client = mock_raw

    result = client.search(query="Doc")
    assert result.total_hits == 1
    assert len(result.hits) == 1
    assert result.hits[0].id == "1"
