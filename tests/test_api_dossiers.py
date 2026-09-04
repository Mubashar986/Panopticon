"""Integration and contract tests for /api/dossiers REST API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.deps import get_crawl_storage_dep
from app.indexer.models import DriveFileMetadata, GOOGLE_DOC_MIME_TYPE, GOOGLE_SHEET_MIME_TYPE
from app.indexer.storage import CrawlStorage


@pytest.fixture
def storage(tmp_path: Path) -> CrawlStorage:
    """Create an isolated test storage instance with seed files."""
    db_path = tmp_path / "test_api_dossiers.db"
    store = CrawlStorage(db_path=db_path)

    # Seed files
    store.upsert_files([
        DriveFileMetadata(
            id="doc_falcon_spec",
            name="Falcon Architecture Specification",
            mime_type=GOOGLE_DOC_MIME_TYPE,
            created_time=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            modified_time=datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc),
            owners=["alex@company.com"],
            last_modifying_user="alex@company.com",
            shared=True,
            sharing_status="domain",
            project_tags=["Falcon"],
            content_snippet="Falcon architecture spec excerpt...",
        ),
        DriveFileMetadata(
            id="sheet_falcon_budget",
            name="Falcon Budget Q4",
            mime_type=GOOGLE_SHEET_MIME_TYPE,
            created_time=datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc),
            modified_time=datetime(2026, 8, 26, 11, 0, tzinfo=timezone.utc),
            owners=["finance@company.com"],
            last_modifying_user="finance@company.com",
            shared=False,
            sharing_status="private",
            project_tags=["Falcon", "Budget"],
            content_snippet="Q4 Budget allocation...",
        ),
    ])
    return store


@pytest.fixture
def client(storage: CrawlStorage) -> TestClient:
    """Create a FastAPI test client with injected CrawlStorage."""
    app = create_app()
    app.dependency_overrides[get_crawl_storage_dep] = lambda: storage
    return TestClient(app)


def test_create_dossier_endpoint(client: TestClient) -> None:
    """Test POST /api/dossiers creates a new dossier and auto-registers creator as admin."""
    payload = {
        "name": "Project Falcon Launch",
        "description": "Primary dossier for Falcon Q4 release",
        "color": "#2563EB",
        "icon": "rocket",
        "initial_file_ids": ["doc_falcon_spec"],
    }
    response = client.post("/api/dossiers", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("dos_")
    assert data["name"] == "Project Falcon Launch"
    assert data["slug"] == "project-falcon-launch"
    assert data["color"] == "#2563EB"
    assert data["status"] == "active"


def test_create_dossier_validation_error(client: TestClient) -> None:
    """Test POST /api/dossiers rejects empty name with 422."""
    response = client.post("/api/dossiers", json={"name": ""})
    assert response.status_code == 422


def test_list_dossiers_endpoint(client: TestClient) -> None:
    """Test GET /api/dossiers returns paginated summaries with item and member counts."""
    # Create two dossiers
    client.post("/api/dossiers", json={"name": "Dossier One", "initial_file_ids": ["doc_falcon_spec"]})
    client.post("/api/dossiers", json={"name": "Dossier Two"})

    response = client.get("/api/dossiers")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Check that counts exist in summary
    d1 = next(item for item in data["items"] if item["name"] == "Dossier One")
    assert d1["item_count"] == 1
    assert d1["member_count"] >= 1


def test_get_dossier_by_id_and_by_slug(client: TestClient) -> None:
    """Test GET /api/dossiers/{id} resolves by both UUID and URL slug."""
    create_res = client.post(
        "/api/dossiers",
        json={"name": "Security Audit 2026", "initial_file_ids": ["sheet_falcon_budget"]},
    )
    assert create_res.status_code == 201
    created = create_res.json()
    dossier_id = created["id"]
    slug = created["slug"]

    # Fetch by ID
    res_id = client.get(f"/api/dossiers/{dossier_id}")
    assert res_id.status_code == 200
    detail_id = res_id.json()
    assert detail_id["dossier"]["id"] == dossier_id
    assert detail_id["item_count"] == 1
    assert len(detail_id["items"]) == 1
    assert detail_id["items"][0]["id"] == "sheet_falcon_budget"

    # Fetch by Slug
    res_slug = client.get(f"/api/dossiers/{slug}")
    assert res_slug.status_code == 200
    detail_slug = res_slug.json()
    assert detail_slug["dossier"]["slug"] == slug


def test_get_dossier_not_found(client: TestClient) -> None:
    """Test GET /api/dossiers/{id} returns 404 for unknown IDs."""
    response = client.get("/api/dossiers/dos_nonexistent")
    assert response.status_code == 404


def test_update_dossier_endpoint(client: TestClient) -> None:
    """Test PATCH /api/dossiers/{id} updates metadata and status."""
    create_res = client.post("/api/dossiers", json={"name": "Draft Project"})
    dossier_id = create_res.json()["id"]

    update_res = client.patch(
        f"/api/dossiers/{dossier_id}",
        json={
            "name": "Finalized Project",
            "description": "Updated description",
            "status": "archived",
            "color": "#10B981",
        },
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["name"] == "Finalized Project"
    assert data["description"] == "Updated description"
    assert data["status"] == "archived"
    assert data["color"] == "#10B981"


def test_delete_dossier_endpoint(client: TestClient) -> None:
    """Test DELETE /api/dossiers/{id} deletes the container with 204."""
    create_res = client.post("/api/dossiers", json={"name": "To Be Deleted"})
    dossier_id = create_res.json()["id"]

    del_res = client.delete(f"/api/dossiers/{dossier_id}")
    assert del_res.status_code == 204

    # Verify 404 afterwards
    get_res = client.get(f"/api/dossiers/{dossier_id}")
    assert get_res.status_code == 404


def test_add_and_remove_items_endpoint(client: TestClient) -> None:
    """Test POST and DELETE on /api/dossiers/{id}/items."""
    create_res = client.post("/api/dossiers", json={"name": "Items Integration Test"})
    dossier_id = create_res.json()["id"]

    # Add items
    add_res = client.post(
        f"/api/dossiers/{dossier_id}/items",
        json={"file_ids": ["doc_falcon_spec", "sheet_falcon_budget"]},
    )
    assert add_res.status_code == 200
    assert add_res.json()["modified_count"] == 2
    assert add_res.json()["total_items"] == 2

    # List items
    list_res = client.get(f"/api/dossiers/{dossier_id}/items")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 2

    # Remove one item
    del_item_res = client.delete(f"/api/dossiers/{dossier_id}/items/doc_falcon_spec")
    assert del_item_res.status_code == 200
    assert del_item_res.json()["total_items"] == 1

    # Verify remaining
    list_res2 = client.get(f"/api/dossiers/{dossier_id}/items")
    assert list_res2.json()["total"] == 1
    assert list_res2.json()["items"][0]["id"] == "sheet_falcon_budget"


def test_members_management_endpoints(client: TestClient) -> None:
    """Test POST and DELETE on /api/dossiers/{id}/members."""
    create_res = client.post("/api/dossiers", json={"name": "Members Project"})
    dossier_id = create_res.json()["id"]

    # Add editor member
    add_res = client.post(
        f"/api/dossiers/{dossier_id}/members",
        json={"user_email": "engineer@company.com", "role": "editor"},
    )
    assert add_res.status_code == 200
    assert add_res.json()["user_email"] == "engineer@company.com"
    assert add_res.json()["role"] == "editor"

    # Remove member
    del_res = client.delete(f"/api/dossiers/{dossier_id}/members/engineer@company.com")
    assert del_res.status_code == 200

    # Remove non-existent member returns 404
    del_404 = client.delete(f"/api/dossiers/{dossier_id}/members/nobody@company.com")
    assert del_404.status_code == 404
