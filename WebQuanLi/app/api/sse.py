import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_user
from app.models import User
from app.core.event_bus import event_bus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sse"])


@router.get("/sse/vehicle/{device_id}")
async def vehicle_sse_stream(
    device_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    """SSE stream for a specific vehicle. Browser subscribes via HTMX hx-ext='sse'."""
    channel = f"vehicle:{device_id}"

    async def event_generator():
        queue = await event_bus.subscribe(channel)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30)
                    event_type = payload.get("event", "message")
                    data = json.dumps(payload.get("data", {}), ensure_ascii=False)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(channel, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
