import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from main import DrowsiGuard
from state_machine import State


class MainPlanCompletionTest(unittest.TestCase):
    @patch("main.LocalQueue")
    def setUp(self, mock_local_queue_class):
        self.original_features = config.FEATURES.copy()
        self.original_demo_mode = config.DEMO_MODE_ALLOW_UNVERIFIED
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
        self.app = DrowsiGuard()
        self.app.local_queue = mock_local_queue_class.return_value
        self.app.state.transition(State.IDLE)
        self.app.runtime_store = Mock()
        self.app.bluetooth_manager = Mock()
        self.app.bluetooth_manager.status.return_value = {
            "adapter": True,
            "speaker_mac": "AA:BB",
            "connected": True,
        }

    def tearDown(self):
        config.FEATURES = self.original_features
        config.DEMO_MODE_ALLOW_UNVERIFIED = self.original_demo_mode

    @patch("main.read_network_status", return_value={"eth0_ip": "192.168.2.31", "wlan0_ip": "172.20.10.5", "ssid": "Hotspot"})
    @patch("main.read_system_status", return_value={"hostname": "jetson", "uptime_seconds": 42, "cpu_temp_c": 70.0, "ram_percent": 33.3})
    def test_runtime_status_reports_driver_verify_status_separately_from_ai_state(self, *_mocks):
        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._start_verified_session("UID-123")
        self.app._last_ai_result = {"state": "DROWSY", "confidence": 0.91, "reason": "eyes closed"}

        self.app._publish_runtime_status()

        payload = self.app.runtime_store.write.call_args[0][0]
        self.assertEqual(payload["driver"]["rfid_tag"], "UID-123")
        self.assertEqual(payload["driver"]["verify_status"], "VERIFIED")
        self.assertEqual(payload["ai"]["state"], "DROWSY")
        self.assertTrue(payload["device"]["strict_mode"])

    @patch("main.read_network_status", return_value={"eth0_ip": None, "wlan0_ip": None, "ssid": None})
    @patch("main.read_system_status", return_value={"hostname": "jetson", "uptime_seconds": 42, "cpu_temp_c": 70.0, "ram_percent": 33.3})
    def test_low_ai_fps_increases_snapshot_interval(self, *_mocks):
        self.app._ai_fps = 6.5
        baseline = self.app.snapshot_writer.min_interval

        self.app._publish_runtime_status()

        self.assertGreater(self.app.snapshot_writer.min_interval, baseline)

    @patch("main.read_network_status", return_value={"eth0_ip": None, "wlan0_ip": None, "ssid": None})
    @patch("main.read_system_status", return_value={"hostname": "jetson", "uptime_seconds": 42, "cpu_temp_c": 81.0, "ram_percent": 33.3})
    def test_critical_temperature_reduces_effective_ai_target_fps(self, *_mocks):
        self.app._publish_runtime_status()

        self.assertEqual(self.app._effective_ai_target_fps, 8)

    def test_monitoring_commands_toggle_runtime_mode(self):
        self.app._monitoring_enabled = False

        self.app._on_backend_command({"action": "connect_monitoring"})
        self.assertTrue(self.app._monitoring_enabled)

        self.app._on_backend_command({"action": "disconnect_monitoring"})
        self.assertFalse(self.app._monitoring_enabled)

    @patch("main.read_network_status", return_value={"eth0_ip": None, "wlan0_ip": None, "ssid": None})
    @patch("main.read_system_status", return_value={"hostname": "jetson", "uptime_seconds": 42, "cpu_temp_c": 70.0, "ram_percent": 33.3})
    def test_runtime_status_includes_monitoring_enabled_flag(self, *_mocks):
        self.app._monitoring_enabled = True

        self.app._publish_runtime_status()

        payload = self.app.runtime_store.write.call_args[0][0]
        self.assertTrue(payload["session"]["monitoring_enabled"])


if __name__ == "__main__":
    unittest.main()
