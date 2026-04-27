import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LocalMonitorGUITest(unittest.TestCase):
    def test_state_from_payload_extracts_runtime_values(self):
        from ui.local_monitor import LocalMonitorState

        payload = {
            "camera": {"fps": 29.7, "online": True, "frame_id": 88, "frame_age_sec": 0.25, "stale": False},
            "ai": {
                "fps": 11.8,
                "target_fps": 12.0,
                "state": "DROWSY",
                "confidence": 0.92,
                "reason": "eyes closed",
                "ear": 0.17,
                "left_ear": 0.16,
                "right_ear": 0.18,
                "ear_used": 0.17,
                "eye_quality": {"usable": True, "selected": "both", "reason": "OK"},
                "mar": 0.33,
                "pitch": -8.5,
                "perclos": 0.41,
                "face_present": True,
            },
            "alert": {"level": "DANGER"},
            "session": {"state": "RUNNING", "active": True, "monitoring_enabled": True},
            "driver": {"rfid_tag": "UID-123"},
            "hardware": {
                "gps_uart_ok": True,
                "gps_fix_ok": False,
                "rfid_reader_ok": True,
                "bluetooth_adapter_ok": True,
                "bluetooth_speaker_connected": True,
                "speaker_output_ok": True,
                "websocket_ok": False,
                "network": {"eth0_ip": "192.168.2.17", "wlan0_ip": None, "ssid": None},
                "details": {"gps_reason": "NMEA_NO_FIX"},
            },
            "queue": {"pending": 3},
            "system": {"cpu_temp_c": 55.0, "ram_percent": 48.2},
        }

        state = LocalMonitorState.from_runtime_payload(payload)

        self.assertEqual(state.camera_fps, 29.7)
        self.assertEqual(state.camera_frame_id, 88)
        self.assertEqual(state.camera_frame_age_sec, 0.25)
        self.assertFalse(state.camera_stale)
        self.assertEqual(state.ai_state, "DROWSY")
        self.assertEqual(state.left_ear, 0.16)
        self.assertEqual(state.right_ear, 0.18)
        self.assertEqual(state.ear_used, 0.17)
        self.assertEqual(state.eye_quality_selected, "both")
        self.assertEqual(state.alert_level, "DANGER")
        self.assertEqual(state.rfid_last_uid, "UID-123")
        self.assertTrue(state.gps_uart_ok)
        self.assertFalse(state.gps_fix_ok)
        self.assertEqual(state.gps_reason, "NMEA_NO_FIX")
        self.assertEqual(state.network_summary, "eth0 192.168.2.17")

    def test_gui_returns_key_actions_without_reopening_camera(self):
        from ui import local_monitor

        fake_cv2 = SimpleNamespace(
            FONT_HERSHEY_SIMPLEX=0,
            LINE_AA=16,
            INTER_AREA=3,
            resize=Mock(side_effect=lambda frame, size, interpolation=None: frame),
            rectangle=Mock(),
            putText=Mock(),
            imshow=Mock(),
            waitKey=Mock(return_value=ord("q")),
            destroyWindow=Mock(),
            imwrite=Mock(return_value=True),
        )
        frame = SimpleNamespace(shape=(480, 640, 3), copy=lambda: frame)

        with patch.object(local_monitor, "cv2", fake_cv2), patch.object(local_monitor, "time") as fake_time:
            fake_time.monotonic.side_effect = [0.0, 1.0]
            gui = local_monitor.LocalMonitorGUI(max_fps=10, width=320, test_keys_enabled=True)
            actions = gui.update(frame, local_monitor.LocalMonitorState())

        self.assertEqual(actions, ["quit"])
        self.assertFalse(hasattr(fake_cv2, "VideoCapture"))

    def test_gui_disables_itself_when_opencv_is_unavailable(self):
        from ui import local_monitor

        with patch.object(local_monitor, "cv2", None):
            gui = local_monitor.LocalMonitorGUI(max_fps=10, width=320)
            actions = gui.update(None, local_monitor.LocalMonitorState())

        self.assertEqual(actions, [])
        self.assertFalse(gui.enabled)

    def test_layout_places_panel_outside_camera_region(self):
        from ui import local_monitor

        layout = local_monitor.calculate_monitor_layout(
            frame_width=1280,
            frame_height=720,
            total_width=960,
        )

        self.assertEqual(layout["camera_x"], 0)
        self.assertEqual(layout["panel_x"], layout["camera_width"])
        self.assertEqual(layout["canvas_width"], layout["camera_width"] + layout["panel_width"])

    def test_state_extracts_thresholds_calibration_and_landmarks(self):
        from ui.local_monitor import LocalMonitorState

        payload = {
            "ai": {
                "state": "YAWNING",
                "alert_hint": 1,
                "thresholds": {"ear_closed": 0.24, "mar_yawn": 0.45, "pitch_down": -15.0},
                "features": {"perclos_short": 0.1, "perclos_long": 0.2},
                "landmarks": {
                    "left_eye_points": [(1, 1), (2, 1), (3, 1)],
                    "right_eye_points": [(1, 3), (2, 3), (3, 3)],
                    "mouth_points": [(1, 5), (2, 6), (3, 5)],
                    "face_bbox": (10, 20, 100, 120),
                    "source_size": (640, 480),
                },
            },
            "calibration": {"valid": True, "sample_count": 40, "reason": "OK"},
        }

        state = LocalMonitorState.from_runtime_payload(payload)

        self.assertEqual(state.alert_hint, 1)
        self.assertEqual(state.ear_threshold, 0.24)
        self.assertEqual(state.mar_threshold, 0.45)
        self.assertTrue(state.calibration_valid)
        self.assertEqual(state.left_eye_points, [(1, 1), (2, 1), (3, 1)])
        self.assertEqual(state.face_bbox, (10, 20, 100, 120))

    def test_overlay_lines_include_ai_and_system_status(self):
        from ui import local_monitor

        state = local_monitor.LocalMonitorState(
            camera_fps=11.2,
            ai_fps=10.5,
            ai_state="DROWSY",
            alert_hint=2,
            ai_confidence=0.86,
            ear=0.2,
            left_ear=0.19,
            right_ear=0.21,
            ear_used=0.2,
            eye_quality_selected="both",
            eye_quality_reason="OK",
            mar=0.12,
            pitch=-3.0,
            perclos=0.3,
            ear_threshold=0.24,
            mar_threshold=0.45,
            pitch_threshold=-15.0,
            perclos_short=0.2,
            perclos_long=0.3,
            calibration_valid=True,
            calibration_sample_count=35,
            websocket_connected=True,
            bluetooth_speaker_connected=True,
            speaker_output_ok=True,
            gps_fix_ok=False,
            rfid_last_uid="UID-123",
        )

        lines = local_monitor.build_panel_lines(state, frame_count=7)

        self.assertTrue(any("AI DROWSY" in line for line in lines))
        self.assertTrue(any("EAR" in line and "0.240" in line for line in lines))
        self.assertTrue(any("L/R/USED" in line and "0.190" in line and "0.210" in line for line in lines))
        self.assertTrue(any("Eye quality both" in line for line in lines))
        self.assertTrue(any("CALIBRATED" in line for line in lines))
        self.assertTrue(any("WS ON" in line for line in lines))

    def test_local_monitor_panel_displays_camera_freshness(self):
        from ui import local_monitor

        state = local_monitor.LocalMonitorState(
            camera_fps=29.9,
            camera_frame_id=123,
            camera_frame_age_sec=0.18,
            camera_stale=False,
            ai_runtime_reason="WAITING_SESSION",
        )

        lines = local_monitor.build_panel_lines(state, frame_count=5)

        self.assertTrue(any("Camera frame_id 123" in line for line in lines))
        self.assertTrue(any("Age 0.18s" in line and "LIVE" in line for line in lines))
        self.assertTrue(any("WAITING_SESSION" in line for line in lines))

    def test_draws_debug_landmarks_when_present(self):
        from ui import local_monitor

        class FakeCv2:
            def __init__(self):
                self.polylines_calls = []

            def polylines(self, frame, points, is_closed, color, thickness):
                self.polylines_calls.append((points, is_closed, color, thickness))

        state = local_monitor.LocalMonitorState(
            left_eye_points=[(1, 1), (2, 1), (3, 1)],
            right_eye_points=[(1, 3), (2, 3), (3, 3)],
            mouth_points=[(1, 5), (2, 6), (3, 5)],
        )

        fake_cv2 = FakeCv2()
        local_monitor.draw_debug_landmarks(fake_cv2, object(), state, scale_x=1.0, scale_y=1.0, color=(0, 255, 0))

        self.assertEqual(len(fake_cv2.polylines_calls), 3)

    def test_draws_eye_landmarks_with_eye_quality_colors(self):
        from ui import local_monitor

        class FakeCv2:
            def __init__(self):
                self.polylines_calls = []

            def polylines(self, frame, points, is_closed, color, thickness):
                self.polylines_calls.append((points, is_closed, color, thickness))

        state = local_monitor.LocalMonitorState(
            left_eye_points=[(1, 1), (2, 1), (3, 1)],
            right_eye_points=[(1, 3), (2, 3), (3, 3)],
            mouth_points=[(1, 5), (2, 6), (3, 5)],
            eye_quality_left_usable=False,
            eye_quality_right_usable=True,
        )

        fake_cv2 = FakeCv2()
        local_monitor.draw_debug_landmarks(fake_cv2, object(), state, scale_x=1.0, scale_y=1.0, color=(0, 255, 0))

        colors = [call[2] for call in fake_cv2.polylines_calls]
        self.assertIn((0, 230, 255), colors)
        self.assertIn((0, 255, 0), colors)


if __name__ == "__main__":
    unittest.main()
