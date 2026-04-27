import asyncio
import json
import logging
from typing import Dict, Set
from asyncio import Queue

logger = logging.getLogger(__name__)


class EventBus:
    """In-memory event bus bridging WebSocket → SSE.

    WebSocket handler publishes events; SSE endpoints subscribe
    to a per-vehicle queue and stream them to the browser.
    """

    def __init__(self):
        self._subscribers: Dict[str, Set[Queue]] = {}
        self._vehicle_state: Dict[str, dict] = {}

    async def subscribe(self, channel: str) -> Queue:
        # Giới hạn hàng đợi để chống nghẽn bộ nhớ (Backpressure)
        q: Queue = Queue(maxsize=50)
        self._subscribers.setdefault(channel, set()).add(q)
        # Send cached state on new subscription
        if channel in self._vehicle_state:
            for event_type, data in self._vehicle_state[channel].items():
                if event_type == "connection":
                    continue
                await q.put({"event": event_type, "data": data})
        return q

    def unsubscribe(self, channel: str, q: Queue):
        if channel in self._subscribers:
            self._subscribers[channel].discard(q)

    async def publish(self, channel: str, event_type: str, data: dict):
        # Cache latest state
        self._vehicle_state.setdefault(channel, {})[event_type] = data

        payload = {"event": event_type, "data": data}
        if channel in self._subscribers:
            dead_queues = []
            for q in self._subscribers[channel]:
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    # Rơi vào QueueFull (Browser load chặm), bỏ qua frame cũ nhất và push frame mới (Drop Policy)
                    try:
                        q.get_nowait()
                        q.task_done()
                        q.put_nowait(payload)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        pass
            for q in dead_queues:
                self._subscribers[channel].discard(q)

    def get_state(self, channel: str) -> dict:
        return self._vehicle_state.get(channel, {})


event_bus = EventBus()
