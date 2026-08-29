"""Integration and unit tests for background Drive sync and re-indexing API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.deps import get_sync_manager_dep
from app.api.schemas.sync import SyncStats
from app.api.services.sync_manager import SyncInProgressError, SyncManager


def test_get_sync_status_idle() -> None:
    """Verify GET /api/sync/status returns idle state and watermark."""
    app = create_app()
    mock_sync_manager = MagicMock(spec=SyncManager)

    mock_sync_manager.get_status.return_value = {
        "is_syncing": False,
        "job_id": None,
        "sync_mode": "incremental",
        "current_phase": "idle",
        "progress_message": "Ready",
        "started_at": None,
        "duration_seconds": 3.12,
        "last_sync_time": "2026-08-28T14:30:00Z",
        "last_sync_stats": {
            "sync_mode": "incremental",
            "added": 5,
            "updated": 2,
            "deleted": 0,
            "unchanged": 40,
            "total_stored": 47,
            "total_indexed": 47,
            "duration_seconds": 3.12,
        },
        "last_error": None,
    }

    app.dependency_overrides[get_sync_manager_dep] = lambda: mock_sync_manager

    client = TestClient(app)
    response = client.get("/api/sync/status")
    assert response.status_code == 200

    data = response.json()
    assert data["is_syncing"] is False
    assert data["current_phase"] == "idle"
    assert data["last_sync_time"] == "2026-08-28T14:30:00Z"
    assert data["last_sync_stats"]["added"] == 5


def test_trigger_sync_success() -> None:
    """Verify POST /api/sync returns 202 Accepted and job identifier."""
    app = create_app()
    mock_sync_manager = MagicMock(spec=SyncManager)

    now_iso = datetime.now(timezone.utc).isoformat()
    mock_sync_manager.trigger_sync.return_value = {
        "status": "started",
        "message": "Incremental sync initiated successfully in background.",
        "job_id": "sync_20260829_120000_123456",
        "sync_mode": "incremental",
        "started_at": now_iso,
    }

    app.dependency_overrides[get_sync_manager_dep] = lambda: mock_sync_manager

    client = TestClient(app)
    response = client.post("/api/sync", json={"full_refresh": False, "export_content": True})
    assert response.status_code == 202

    data = response.json()
    assert data["status"] == "started"
    assert "sync_20260829" in data["job_id"]
    assert data["sync_mode"] == "incremental"
    mock_sync_manager.trigger_sync.assert_called_once_with(
        full_refresh=False, export_content=True, page_size=50
    )


def test_trigger_sync_collision_returns_409() -> None:
    """Verify POST /api/sync returns HTTP 409 Conflict if another sync is running."""
    app = create_app()
    mock_sync_manager = MagicMock(spec=SyncManager)
    mock_sync_manager.trigger_sync.side_effect = SyncInProgressError("A sync job is active.")

    app.dependency_overrides[get_sync_manager_dep] = lambda: mock_sync_manager

    client = TestClient(app)
    response = client.post("/api/sync", json={"full_refresh": True})
    assert response.status_code == 409

    data = response.json()
    assert data["detail"]["error"] == "sync_in_progress"


def test_trigger_reindex_success() -> None:
    """Verify POST /api/sync/reindex returns 202 Accepted."""
    app = create_app()
    mock_sync_manager = MagicMock(spec=SyncManager)

    mock_sync_manager.trigger_reindex.return_value = {
        "status": "started",
        "message": "Local search re-indexing initiated in background.",
        "job_id": "reindex_20260829_120000_654321",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    app.dependency_overrides[get_sync_manager_dep] = lambda: mock_sync_manager

    client = TestClient(app)
    response = client.post("/api/sync/reindex")
    assert response.status_code == 202

    data = response.json()
    assert data["status"] == "started"
    assert "reindex_" in data["job_id"]


def test_trigger_reindex_collision_returns_409() -> None:
    """Verify POST /api/sync/reindex returns 409 Conflict when job is active."""
    app = create_app()
    mock_sync_manager = MagicMock(spec=SyncManager)
    mock_sync_manager.trigger_reindex.side_effect = SyncInProgressError("A job is in progress.")

    app.dependency_overrides[get_sync_manager_dep] = lambda: mock_sync_manager

    client = TestClient(app)
    response = client.post("/api/sync/reindex")
    assert response.status_code == 409


def test_sync_manager_state_transitions() -> None:
    """Unit test SyncManager lifecycle, thread locking, and error capture."""
    manager = SyncManager()

    mock_storage = MagicMock()
    mock_storage.get_watermark.return_value = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)

    # Initial status check
    status = manager.get_status(storage=mock_storage)
    assert status.is_syncing is False
    assert status.current_phase == "idle"
    assert status.last_sync_time == "2026-08-28T12:00:00+00:00"

    # Simulate active sync lock
    with manager._lock:
        manager._is_syncing = True
        manager._job_id = "test_job_1"
        manager._sync_mode = "incremental"
        manager._current_phase = "crawling"
        manager._progress_message = "Scanning Drive..."
        manager._started_at = datetime.now(timezone.utc)

    # Calling trigger_sync while locked should raise SyncInProgressError
    import pytest
    with pytest.raises(SyncInProgressError):
        manager.trigger_sync()

    status_active = manager.get_status(storage=mock_storage)
    assert status_active.is_syncing is True
    assert status_active.current_phase == "crawling"

    # Simulate completion
    with manager._lock:
        manager._is_syncing = False
        manager._current_phase = "idle"
        manager._last_stats = SyncStats(
            sync_mode="incremental",
            added=3,
            updated=1,
            deleted=0,
            unchanged=20,
            total_stored=24,
            total_indexed=24,
            duration_seconds=1.85,
        )

    status_done = manager.get_status(storage=mock_storage)
    assert status_done.is_syncing is False
    assert status_done.last_sync_stats is not None
    assert status_done.last_sync_stats.added == 3
