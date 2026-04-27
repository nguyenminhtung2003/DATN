import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.event_bus import EventBus


class EventBusCacheTest(unittest.TestCase):
    def test_new_subscriber_receives_cached_vehicle_state_without_stale_connection(self):
        async def run():
            bus = EventBus()
            await bus.publish("vehicle:jetson-001", "connection", {"status": "online"})
            await bus.publish("vehicle:jetson-001", "hardware", {"camera": True})

            queue = await bus.subscribe("vehicle:jetson-001")
            first = await asyncio.wait_for(queue.get(), timeout=1)
            return first, queue.empty()

        first, queue_is_empty = asyncio.run(run())

        self.assertEqual(first, {"event": "hardware", "data": {"camera": True}})
        self.assertTrue(queue_is_empty)


if __name__ == "__main__":
    unittest.main()
