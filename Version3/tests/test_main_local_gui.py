import os
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from main import AsyncStatusAdapter, DrowsiGuard, shutdown_event
from state_machine import State


def disabled_features():
    return {
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


class MainLocalGUITest(unittest.TestCase):
    def setUp(self):
        self.original_features = config.FEATURES.copy()
        self.original_gui_enabled = config.LOCAL_GUI_ENABLED
        self.original_gui_fps = config.LOCAL_GUI_FPS
        self.original_gui_width = config.LOCAL_GUI_WIDTH
        self.original_gui_keys = config.LOCAL_GUI_TEST_KEYS
        self.original_gui_autostart = getattr(config, "LOCAL_GUI_AUTOSTART_SESSION", None)
        self.original_demo_mode = config.DEMO_MODE_ALLOW_UNVERIFIED
        config.FEATURES = disabled_features()
        config.LOCAL_GUI_ENABLED = False
        config.LOCAL_GUI_AUTOSTART_SESSION = False
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        shutdown_event.clear()

    def tearDown(self):
        config.FEATURES = self.original_features
        config.LOCAL_GUI_ENABLED = self.original_gui_enabled
        config.LOCAL_GUI_FPS = self.original_gui_fps
        config.LOCAL_GUI_WIDTH = self.original_gui_width
        config.LOCAL_GUI_TEST_KEYS = self.original_gui_keys
        if self.original_gui_autostart is None:
            try:
                delattr(config, "LOCAL_GUI_AUTOSTART_SESSION")
            except AttributeError:
                pass
        else:
            config.LOCAL_GUI_AUTOSTART_SESSION = self.original_gui_autostart
        config.DEMO_MODE_ALLOW_UNVERIFIED = self.original_demo_mode
        shutdown_event.clear()

    @patch("main.LocalQueue")
    def make_app(self, mock_local_queue_class):
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        app.runtime_store = Mock()
        app.state.transition(State.IDLE)
        return app

    @patch("main.LocalQueue")
    def test_constructor_creates_local_gui_when_enabled(self, _mock_local_queue_class):
        config.LOCAL_GUI_ENABLED = True
        config.LOCAL_GUI_FPS = 8
        config.LOCAL_GUI_WIDTH = 800
        config.LOCAL_GUI_TEST_KEYS = False

        with patch("main.LocalMonitorGUI") as gui_class:
            app = DrowsiGuard()

        gui_class.assert_called_once_with(max_fps=8, width=800, test_keys_enabled=False)
        self.assertIs(app.local_gui, gui_class.return_value)

    @patch("main.LocalQueue")
    def test_local_gui_quit_action_sets_shutdown_event(self, _mock_local_queue_class):
        app = DrowsiGuard()
        app.local_gui = Mock()
        app.local_gui.update.return_value = ["quit"]
        app._last_runtime_payload = {"camera": {}, "ai": {}, "hardware": {}}

        app._update_local_gui(frame=object())

        self.assertTrue(shutdown_event.is_set())

    @patch("main.LocalQueue")
    def test_local_gui_actions_reset_alert_test_speaker_and_start_demo(self, mock_local_queue_class):
        config.DEMO_MODE_ALLOW_UNVERIFIED = True
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        app.state.transition(State.IDLE)
        app.alert_manager = Mock()

        app._handle_local_gui_actions(["reset_alert", "test_alert_2", "start_demo_session"])

        self.assertGreaterEqual(app.alert_manager.reset.call_count, 1)
        app.alert_manager._activate_outputs.assert_called_once_with(2)
        self.assertTrue(app._session_active)
        self.assertEqual(app._current_driver_uid, "LOCAL-GUI-DEMO")
        self.assertEqual(app.state.state, State.RUNNING)

    @patch("main.LocalQueue")
    def test_start_demo_session_from_idle_enters_running_via_verifying_driver(self, mock_local_queue_class):
        config.DEMO_MODE_ALLOW_UNVERIFIED = True
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        app.state.transition(State.IDLE)

        ok = app._start_demo_session("LOCAL-GUI-DEMO", "local test")

        self.assertTrue(ok)
        self.assertTrue(app._session_active)
        self.assertEqual(app._current_driver_uid, "LOCAL-GUI-DEMO")
        self.assertEqual(app.state.state, State.RUNNING)

    @patch("main.LocalQueue")
    def test_start_demo_session_does_not_mark_active_when_transition_fails(self, mock_local_queue_class):
        config.DEMO_MODE_ALLOW_UNVERIFIED = True
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value

        ok = app._start_demo_session("LOCAL-GUI-DEMO", "blocked from booting")

        self.assertFalse(ok)
        self.assertFalse(app._session_active)
        self.assertIsNone(app._current_driver_uid)
        self.assertEqual(app.state.state, State.BOOTING)

    @patch("main.LocalQueue")
    def test_local_gui_autostart_starts_demo_session_when_demo_and_gui_enabled(self, mock_local_queue_class):
        config.DEMO_MODE_ALLOW_UNVERIFIED = True
        config.LOCAL_GUI_ENABLED = True
        config.LOCAL_GUI_AUTOSTART_SESSION = True
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        app.state.transition(State.IDLE)

        started = app._maybe_autostart_local_gui_session()

        self.assertTrue(started)
        self.assertTrue(app._monitoring_enabled)
        self.assertTrue(app._session_active)
        self.assertEqual(app.state.state, State.RUNNING)

    @patch("main.LocalQueue")
    def test_local_gui_autostart_does_not_run_in_strict_service_mode(self, mock_local_queue_class):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        config.LOCAL_GUI_ENABLED = True
        config.LOCAL_GUI_AUTOSTART_SESSION = True
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        app.state.transition(State.IDLE)

        started = app._maybe_autostart_local_gui_session()

        self.assertFalse(started)
        self.assertFalse(app._session_active)
        self.assertEqual(app.state.state, State.IDLE)

    @patch("main.LocalQueue")
    def test_local_monitor_payload_includes_latest_gps_fix(self, _mock_local_queue_class):
        app = DrowsiGuard()
        app.gps = Mock()
        app.gps.latest = Mock(lat=10.762622, lng=106.660172, speed=38.5, heading=90.0, fix_ok=True)

        payload = app._build_local_monitor_payload()

        self.assertEqual(payload["gps"]["lat"], 10.762622)
        self.assertEqual(payload["gps"]["lng"], 106.660172)
        self.assertTrue(payload["gps"]["fix_ok"])

    @patch("main.LocalQueue")
    def test_runtime_status_includes_camera_frame_id_age_and_stale(self, _mock_local_queue_class):
        app = DrowsiGuard()
        app.camera = Mock(is_alive=True, fps=12.3, frame_id=42)
        app.frame_buffer = Mock(frame_age=0.4)

        payload = app._build_local_monitor_payload()

        self.assertEqual(payload["camera"]["frame_id"], 42)
        self.assertAlmostEqual(payload["camera"]["frame_age_sec"], 0.4)
        self.assertFalse(payload["camera"]["stale"])

    @patch("main.LocalQueue")
    def test_ai_runtime_reason_uses_recent_frame_buffer_when_status_has_no_frame(self, mock_local_queue_class):
        config.DEMO_MODE_ALLOW_UNVERIFIED = True
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        config.FEATURES["drowsiness"] = True
        app.face_analyzer = object()
        app.frame_buffer = Mock(has_recent_frame=True)
        app.state.transition(State.IDLE)
        app._start_demo_session("LOCAL-GUI-DEMO", "local test")

        self.assertEqual(app._ai_runtime_reason(), "RUNNING")

    @patch("main.LocalQueue")
    def test_local_monitor_payload_includes_calibration_payload(self, _mock_local_queue_class):
        app = DrowsiGuard()

        payload = app._build_local_monitor_payload()

        self.assertIn("calibration", payload)
        self.assertIn("ear_closed_threshold", payload["calibration"])
        self.assertIn("mar_yawn_threshold", payload["calibration"])
        self.assertIn("pitch_down_threshold", payload["calibration"])

    @patch("main.LocalQueue")
    def test_local_monitor_payload_includes_eye_quality_payload(self, _mock_local_queue_class):
        app = DrowsiGuard()
        app._last_metrics = Mock(
            face_present=True,
            ear=0.28,
            left_ear=0.27,
            right_ear=0.29,
            ear_used=0.28,
            mar=0.12,
            pitch=0.0,
            face_quality={"usable": True},
            eye_quality={"usable": True, "selected": "both", "reason": "OK"},
            left_eye_points=[],
            right_eye_points=[],
            mouth_points=[],
            face_bbox=None,
        )

        payload = app._build_local_monitor_payload()

        self.assertEqual(payload["ai"]["left_ear"], 0.27)
        self.assertEqual(payload["ai"]["right_ear"], 0.29)
        self.assertEqual(payload["ai"]["ear_used"], 0.28)
        self.assertEqual(payload["ai"]["eye_quality"]["selected"], "both")

    @patch("main.LocalQueue")
    def test_demo_session_resets_calibration_classifier_and_alerts(self, mock_local_queue_class):
        app = DrowsiGuard()
        app.local_queue = mock_local_queue_class.return_value
        app.state.transition(State.IDLE)
        app.alert_manager = Mock()
        app.ai_classifier = Mock()

        app._start_demo_session("LOCAL-GUI-DEMO", "test")

        self.assertIsNotNone(app.calibrator)
        app.ai_classifier.reset_state.assert_called_once()
        app.alert_manager.reset.assert_called_once()

    def test_async_status_adapter_does_not_block_on_slow_bluetooth_status(self):
        entered = threading.Event()
        release = threading.Event()

        class SlowBluetooth:
            def status(self, force_refresh=False):
                entered.set()
                release.wait(1.0)
                return {"connected": True}

        adapter = AsyncStatusAdapter(SlowBluetooth(), default_status={"connected": False}, interval_sec=0.0)
        started = time.monotonic()
        status = adapter.status()
        elapsed = time.monotonic() - started

        try:
            self.assertLess(elapsed, 0.1)
            self.assertFalse(status["connected"])
            self.assertTrue(entered.wait(0.2))
        finally:
            release.set()

    def test_async_status_adapter_supports_slow_callable_status_reader(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_reader():
            entered.set()
            release.wait(1.0)
            return {"eth0_ip": "192.168.2.17"}

        adapter = AsyncStatusAdapter(slow_reader, default_status={"eth0_ip": None}, interval_sec=0.0)
        started = time.monotonic()
        status = adapter.status()
        elapsed = time.monotonic() - started

        try:
            self.assertLess(elapsed, 0.1)
            self.assertIsNone(status["eth0_ip"])
            self.assertTrue(entered.wait(0.2))
        finally:
            release.set()


if __name__ == "__main__":
    unittest.main()
