"""Unit and integration tests for Server-Sent Events (SSE) live event stream and SyncEventBus."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import LocalDevUser
from app.api.routes.events import subscribe_live_events
from app.api.services.event_bus import SyncEvent, SyncEventBus, get_sync_event_bus
from app.api.services.sync_manager import SyncManager


@pytest.fixture(autouse=True)
def clean_event_bus():
    """Ensure event bus is cleared before and after each test."""
    bus = get_sync_event_bus()
    bus.clear()
    yield
    bus.clear()


def test_sync_event_model():
    """Verify SyncEvent serialization into standard W3C SSE text frames."""
    event = SyncEvent(
        id="evt_12345",
        event_type="file_modified",
        data={"file_id": "doc_999", "name": "Project Falcon Spec"},
        timestamp="2026-08-31T14:30:00Z",
    )
    sse_text = event.to_sse_format()
    assert sse_text.startswith("event: file_modified\n")
    assert "id: evt_12345\n" in sse_text
    assert '"file_id": "doc_999"' in sse_text
    assert sse_text.endswith("\n\n")


def test_sync_event_bus_subscription_lifecycle():
    """Verify subscribing and unsubscribing queues from SyncEventBus."""
    bus = SyncEventBus()
    assert bus.subscriber_count == 0

    sub_id, queue = bus.subscribe()
    assert bus.subscriber_count == 1
    assert isinstance(queue, asyncio.Queue)

    # Publish an event
    event = bus.publish("test_event", {"message": "hello"})
    assert queue.qsize() == 1
    received = queue.get_nowait()
    assert received.event_type == "test_event"
    assert received.data["message"] == "hello"

    # Unsubscribe
    bus.unsubscribe(sub_id)
    assert bus.subscriber_count == 0


def test_sync_event_bus_multiple_subscribers():
    """Verify broadcast to multiple concurrent subscriber queues."""
    bus = SyncEventBus()
    sub1_id, q1 = bus.subscribe()
    sub2_id, q2 = bus.subscribe()
    sub3_id, q3 = bus.subscribe()
    assert bus.subscriber_count == 3

    bus.publish("sync_progress", {"phase": "crawling"})

    assert q1.qsize() == 1
    assert q2.qsize() == 1
    assert q3.qsize() == 1

    assert q1.get_nowait().data["phase"] == "crawling"
    assert q2.get_nowait().data["phase"] == "crawling"
    assert q3.get_nowait().data["phase"] == "crawling"

    bus.unsubscribe(sub2_id)
    assert bus.subscriber_count == 2

    bus.publish("sync_completed", {"duration": 2.5})
    assert q1.qsize() == 1
    assert q2.qsize() == 0  # Unsubscribed
    assert q3.qsize() == 1


def test_sync_event_bus_queue_full_protection():
    """Verify queue full does not crash or block when max size is reached."""
    bus = SyncEventBus(max_queue_size=2)
    sub_id, queue = bus.subscribe()

    bus.publish("e1", {"n": 1})
    bus.publish("e2", {"n": 2})
    assert queue.qsize() == 2

    # Third publish should drop oldest and succeed without throwing
    bus.publish("e3", {"n": 3})
    assert queue.qsize() <= 2


@pytest.mark.asyncio
async def test_live_events_route_and_generator():
    """Verify subscribe_live_events returns StreamingResponse and yields SSE frames cleanly."""
    mock_request = MagicMock()
    # Simulate: connect -> read connected frame -> read broadcast event -> disconnect
    mock_request.is_disconnected = AsyncMock(side_effect=[False, False, True])

    user = LocalDevUser()
    response = await subscribe_live_events(mock_request, user)

    assert response.status_code == 200
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache, no-transform"
    assert response.headers["Connection"] == "keep-alive"

    generator = response.body_iterator

    # 1. Read first frame (handshake)
    first_frame = await anext(generator)
    assert "event: connected" in first_frame
    assert "subscriber_id" in first_frame

    # 2. Publish an event and verify generator yields the formatted frame
    get_sync_event_bus().publish("sync_started", {"job_id": "job_abc_123"})
    second_frame = await anext(generator)
    assert "event: sync_started" in second_frame
    assert "job_abc_123" in second_frame


def test_sync_manager_emits_lifecycle_events():
    """Verify SyncManager triggers publish calls on sync start, progress, and finish."""
    bus = get_sync_event_bus()
    sub_id, queue = bus.subscribe()

    mgr = SyncManager()

    with patch.object(mgr, "_run_sync_worker"):
        res = mgr.trigger_sync(full_refresh=False)
        assert res.status == "started"

    # Verify sync_started event was received in queue
    assert queue.qsize() >= 1
    event = queue.get_nowait()
    assert event.event_type == "sync_started"
    assert event.data["job_id"] == res.job_id
