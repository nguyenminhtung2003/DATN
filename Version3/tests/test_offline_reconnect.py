import os
import time
import pytest
from unittest.mock import MagicMock, patch

from storage.local_queue import LocalQueue
from network.ws_client import WSClient
import config
from main import DrowsiGuard
from state_machine import State

def test_offline_reconnect_order(tmp_path):
    """
    1. Fix reconnect ordering: session_start resync phải được gửi/flush trước mọi alert pending.
    """
    db_path = str(tmp_path / "test_queue.db")
    queue = LocalQueue(db_path=db_path)
    
    # 1. Push an alert (simulate occurring before the reconnect)
    queue.push("alert", {"level": "WARNING", "ear": 0.15})
    
    # 2. Push face_mismatch
    queue.push("face_mismatch", {"rfid_tag": "A1B2", "expected": "A1B2"})
    
    # 3. On reconnect, main.py pushes session_start
    queue.push("session_start", {"rfid_tag": "A1B2", "timestamp": 123456789.0})
    
    # Check pending count
    assert queue.pending_count == 3
    
    # Pop batch and assert order
    # Priority: session_start (1) -> alert (3) -> face_mismatch (4)
    batch = queue.pop_batch(limit=10)
    assert len(batch) == 3
    
    # First item should be session_start
    _, payload1 = batch[0]
    assert payload1["type"] == "session_start"
    assert payload1["data"]["rfid_tag"] == "A1B2"
    
    # Second item should be alert
    _, payload2 = batch[1]
    assert payload2["type"] == "alert"
    assert payload2["data"]["level"] == "WARNING"
    
    # Third item should be face_mismatch
    _, payload3 = batch[2]
    assert payload3["type"] == "face_mismatch"


def test_ws_client_on_connect_callback():
    """Verify that WSClient calls the on_connect_callback when connected."""
    callback_called = False
    
    def my_callback():
        nonlocal callback_called
        callback_called = True
        
    client = WSClient(on_connect_callback=my_callback)
    
    # Mock the websocket
    ws_mock = MagicMock()
    
    # Trigger _on_open manually
    client._on_open(ws_mock)
    
    assert callback_called is True


@patch("main.LocalQueue")
def test_reconnect_replays_verify_snapshot_for_active_session(mock_local_queue_class):
    original_features = config.FEATURES.copy()
    original_demo_mode = config.DEMO_MODE_ALLOW_UNVERIFIED
    config.FEATURES = {
        "camera": False,
        "drowsiness": False,
        "rfid": False,
        "gps": False,
        "buzzer": False,
        "led": False,
        "speaker": False,
        "websocket": False,
        "ota": False,
        "face_verify": False,
    }
    config.DEMO_MODE_ALLOW_UNVERIFIED = False

    try:
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        app.state.transition(State.IDLE)
        app._start_verified_session("UID-REPLAY")
        app.local_queue.push.reset_mock()

        app._on_ws_connect()

        push_calls = app.local_queue.push.call_args_list
        assert [call.args[0] for call in push_calls] == ["session_start", "verify_snapshot"]
        assert push_calls[0].args[1]["rfid_tag"] == "UID-REPLAY"
        assert push_calls[1].args[1]["rfid_tag"] == "UID-REPLAY"
        assert push_calls[1].args[1]["status"] == "VERIFIED"
        assert "matched" in push_calls[1].args[1]["message"].lower()
    finally:
        config.FEATURES = original_features
        config.DEMO_MODE_ALLOW_UNVERIFIED = original_demo_mode
