"""Asynchronous Pub/Sub Event Bus for real-time Server-Sent Events (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("panopticon.api.event_bus")


class SyncEvent(BaseModel):
    """Structured event model broadcast over Server-Sent Events (SSE)."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], description="Unique event identifier")
    event_type: str = Field(..., description="Categorical event type (e.g. 'sync_started', 'file_modified')")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload dictionary")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of event generation",
    )

    def to_sse_format(self) -> str:
        """Format the event into a standard W3C text/event-stream frame."""
        payload = json.dumps(self.data)
        return f"event: {self.event_type}\nid: {self.id}\ndata: {payload}\n\n"


class SyncEventBus:
    """Thread-safe in-memory publish-subscribe broker for real-time event distribution."""

    def __init__(self, max_queue_size: int = 200) -> None:
        self._subscribers: dict[str, asyncio.Queue[SyncEvent]] = {}
        self._lock = threading.Lock()
        self.max_queue_size = max_queue_size

    @property
    def subscriber_count(self) -> int:
        """Return the number of currently active subscribers."""
        with self._lock:
            return len(self._subscribers)

    def subscribe(self) -> tuple[str, asyncio.Queue[SyncEvent]]:
        """Register a new subscriber and return a dedicated event queue.

        Returns:
            tuple[str, asyncio.Queue[SyncEvent]]: Unique subscriber ID and dedicated async queue.
        """
        sub_id = uuid.uuid4().hex
        queue: asyncio.Queue[SyncEvent] = asyncio.Queue(maxsize=self.max_queue_size)
        with self._lock:
            self._subscribers[sub_id] = queue
        logger.debug("Registered SSE subscriber [%s]. Total active: %d", sub_id, len(self._subscribers))
        return sub_id, queue

    def unsubscribe(self, sub_id: str) -> None:
        """Remove a subscriber and cleanup its event queue.

        Args:
            sub_id: Unique subscriber ID returned by subscribe().
        """
        with self._lock:
            if sub_id in self._subscribers:
                del self._subscribers[sub_id]
                logger.debug("Unregistered SSE subscriber [%s]. Total active: %d", sub_id, len(self._subscribers))

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> SyncEvent:
        """Broadcast an event to all active subscriber queues in a thread-safe manner.

        Args:
            event_type: Name of event (e.g. 'file_modified', 'sync_completed').
            data: Payload dictionary to send with the event.

        Returns:
            SyncEvent: The generated and dispatched event.
        """
        event = SyncEvent(event_type=event_type, data=data or {})
        with self._lock:
            queues = list(self._subscribers.values())

        if not queues:
            return event

        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue is full; dropping oldest event to maintain real-time responsiveness.")
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

        logger.debug("Published event [%s] to %d active subscribers", event_type, len(queues))
        return event

    def clear(self) -> None:
        """Clear all registered subscribers (used primarily for test cleanup)."""
        with self._lock:
            self._subscribers.clear()


# Module-level singleton instance
_GLOBAL_EVENT_BUS: SyncEventBus | None = None
_INIT_LOCK = threading.Lock()


def get_sync_event_bus() -> SyncEventBus:
    """Return the global SyncEventBus singleton instance."""
    global _GLOBAL_EVENT_BUS
    if _GLOBAL_EVENT_BUS is None:
        with _INIT_LOCK:
            if _GLOBAL_EVENT_BUS is None:
                _GLOBAL_EVENT_BUS = SyncEventBus()
    return _GLOBAL_EVENT_BUS
