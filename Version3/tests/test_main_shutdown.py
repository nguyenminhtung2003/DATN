import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from main import DrowsiGuard, shutdown_event


class MainShutdownStateTest(unittest.TestCase):
    @patch("main.LocalQueue")
    def test_constructor_clears_previous_shutdown_event(self, _mock_local_queue_class):
        original_features = config.FEATURES.copy()
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
        shutdown_event.set()
        try:
            DrowsiGuard()
            self.assertFalse(shutdown_event.is_set())
        finally:
            shutdown_event.clear()
            config.FEATURES = original_features


if __name__ == "__main__":
    unittest.main()
