"""Server-Sent Events (SSE) live streaming route handlers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.api.services.event_bus import SyncEvent, get_sync_event_bus

logger = logging.getLogger("panopticon.api.routes.events")

router = APIRouter(tags=["Live Events & SSE"])


@router.get(
    "/api/events/live",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Subscribe to Real-Time Server-Sent Events (SSE) Stream",
    description=(
        "Establishes a persistent Server-Sent Events (SSE) connection broadcasting real-time "
        "sync lifecycle updates, document modifications, crawl progress, and system health heartbeats. "
        "Clients receive standard text/event-stream frames with automatic reconnection support."
    ),
    responses={
        200: {
            "description": "Continuous text/event-stream event feed",
            "content": {"text/event-stream": {}},
        },
    },
)
async def subscribe_live_events(
    request: Request,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Stream real-time sync and document lifecycle events to the connected client."""
    event_bus = get_sync_event_bus()

    async def event_generator() -> AsyncIterator[str]:
        sub_id, queue = event_bus.subscribe()
        logger.info("SSE client connected [%s] (User: %s)", sub_id, current_user.email)

        try:
            # Yield initial connection handshake frame
            initial_event = SyncEvent(
                event_type="connected",
                data={"status": "connected", "subscriber_id": sub_id},
            )
            yield initial_event.to_sse_format()

            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    logger.debug("SSE client [%s] disconnected cleanly.", sub_id)
                    break

                try:
                    # Wait for next event with 15s keep-alive timeout
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    # Send keep-alive heartbeat frame to prevent proxy/browser socket timeouts
                    heartbeat = SyncEvent(
                        event_type="heartbeat",
                        data={"status": "alive"},
                    )
                    yield heartbeat.to_sse_format()

        except (asyncio.CancelledError, GeneratorExit):
            logger.debug("SSE connection cancelled for subscriber [%s]", sub_id)
        finally:
            event_bus.unsubscribe(sub_id)
            logger.info("SSE subscriber [%s] unregistered and cleaned up.", sub_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
