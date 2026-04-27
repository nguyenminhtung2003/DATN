import unittest
import os
import sqlite3
import json
import time
from unittest.mock import Mock, patch

# Add parent dir to path so we can import project modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.ws_client import WSClient
from storage.local_queue import LocalQueue
from alerts.alert_manager import AlertLevel
import config

import tempfile

class TestWSQueueHardening(unittest.TestCase):
    def setUp(self):
        self.fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.fd)
        self.queue = LocalQueue(db_path=self.db_path)
        self.client = WSClient(local_queue=self.queue)
        
    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_alert_level_names(self):
        self.assertEqual(AlertLevel.NAMES[1], "WARNING")
        self.assertEqual(AlertLevel.NAMES[2], "DANGER")
        self.assertEqual(AlertLevel.NAMES[3], "CRITICAL")

    def test_reconnect_delay_reset(self):
        self.client._reconnect_delay = 50.0  # Simulate maxed out backoff
        self.client._on_open(Mock())
        self.assertTrue(self.client.is_connected)
        self.assertEqual(self.client._reconnect_delay, config.WS_RECONNECT_BASE)

    def test_on_open_sends_hardware_snapshot_before_queue_flush(self):
        mock_ws = Mock()
        client = WSClient(
            local_queue=self.queue,
            on_connect_snapshot=lambda: {"power": True, "camera": True},
        )

        client._on_open(mock_ws)

        payload = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(payload["type"], "hardware")
        self.assertTrue(payload["data"]["camera"])

    def test_partial_flush_failure(self):
        # Push 3 events
        self.queue.push("event1", {"data": 1})
        self.queue.push("event2", {"data": 2})
        self.queue.push("event3", {"data": 3})
        
        self.assertEqual(self.queue.pending_count, 3)
        
        # Setup mock WebSocket
        mock_ws = Mock()
        
        # We want send to succeed for the first 2 calls, then raise Exception on the 3rd
        call_count = [0]
        def mock_send(data):
            call_count[0] += 1
            if call_count[0] == 3:
                raise ConnectionError("Simulated drop")
            return None
            
        mock_ws.send.side_effect = mock_send
        self.client.ws = mock_ws
        self.client._connected = True
        self.client._running = True
        
        # We manually run ONE iteration of the flush loop logic without the while True
        batch = self.client._local_queue.pop_batch(limit=20)
        sent_ids = []
        try:
            for db_id, payload in batch:
                self.client.ws.send(json.dumps(payload))
                sent_ids.append(db_id)
        except Exception:
            pass # Simulated WS loop catching the error
        finally:
            if sent_ids:
                self.client._local_queue.mark_sent(sent_ids)
                self.client._local_queue.cleanup_sent()
        
        # Verify 2 events were sent
        self.assertEqual(call_count[0], 3) # it called 3 times, failed on 3rd
        self.assertEqual(len(sent_ids), 2)
        
        # Verify exactly 1 pending remains in the queue!
        self.assertEqual(self.queue.pending_count, 1)
        
        # Verify it's event3
        remaining = self.queue.pop_batch(limit=20)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0][1]["type"], "event3")

    def test_hardware_snapshots_are_coalesced_to_latest_unsent_event(self):
        self.queue.push("hardware", {"camera": False, "sequence": 1})
        self.queue.push("hardware", {"camera": True, "sequence": 2})
        self.queue.push("hardware", {"camera": True, "sequence": 3})

        self.assertEqual(self.queue.pending_count, 1)
        remaining = self.queue.pop_batch(limit=20)
        self.assertEqual(remaining[0][1]["type"], "hardware")
        self.assertEqual(remaining[0][1]["data"]["sequence"], 3)

    def test_direct_flush_loop(self):
        """
        Integration-like test: Starts flush_loop as an actual thread
        but breaks it after a short time to verify it drains the queue properly.
        This tests the actual concurrency behavior closely reflecting real production.
        """
        import threading
        
        # Push 10 events
        for i in range(10):
            self.queue.push(f"event{i}", {"idx": i})
            
        self.assertEqual(self.queue.pending_count, 10)
        
        # Mock WebSocket that succeeds for all
        mock_ws = Mock()
        self.client.ws = mock_ws
        self.client._connected = True
        self.client._running = True
        
        # Start the flush loop in a separate thread
        flush_thread = threading.Thread(target=self.client._flush_loop)
        flush_thread.daemon = True
        flush_thread.start()
        
        # Give it a tiny moment to flush one batch
        time.sleep(0.5)
        
        # Stop the loop cleanly
        self.client._running = False
        flush_thread.join(timeout=1.0)
        
        # All 10 events should have been popped and sent
        self.assertEqual(mock_ws.send.call_count, 10)
        self.assertEqual(self.queue.pending_count, 0)

if __name__ == "__main__":
    unittest.main()
