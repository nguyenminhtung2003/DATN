import importlib.util
import threading
import time
from pathlib import Path


def load_script():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "local_ai_monitor.py"
    spec = importlib.util.spec_from_file_location("local_ai_monitor", str(script_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overlay_lines_include_camera_and_ai_metrics():
    monitor = load_script()

    class Metrics:
        face_present = True
        ear = 0.23
        left_ear = 0.22
        right_ear = 0.24
        ear_used = 0.23
        eye_quality = {"usable": True, "selected": "both", "reason": "OK"}
        mar = 0.41
        pitch = -7.5

    lines = monitor.build_overlay_lines(
        metrics=Metrics(),
        perclos=0.12,
        ai_result={"state": "NORMAL", "confidence": 0.91, "reason": "stable"},
        camera_fps=28.4,
        ai_fps=10.2,
        frame_count=42,
    )

    assert "CAM FPS 28.4" in lines[0]
    assert any("AI NORMAL" in line for line in lines)
    assert any("EAR 0.230" in line and "MAR 0.410" in line for line in lines)
    assert any("L/R/USED" in line and "0.220" in line and "0.240" in line for line in lines)
    assert any("Eye quality both" in line for line in lines)


def test_pipeline_uses_project_config():
    monitor = load_script()

    pipeline = monitor.get_camera_pipeline()

    assert "nvarguscamerasrc" in pipeline
    assert "appsink" in pipeline


def test_layout_places_info_panel_outside_camera_region():
    monitor = load_script()

    layout = monitor.calculate_monitor_layout(
        frame_width=1280,
        frame_height=720,
        total_width=960,
        panel_width=340,
    )

    assert layout["camera_x"] == 0
    assert layout["panel_x"] == layout["camera_width"]
    assert layout["panel_x"] >= layout["camera_width"]
    assert layout["canvas_width"] == layout["camera_width"] + layout["panel_width"]
    assert layout["camera_height"] == layout["canvas_height"]


def test_panel_displays_thresholds_and_calibration_status():
    monitor = load_script()

    class Metrics:
        face_present = True
        ear = 0.28
        mar = 0.12
        pitch = 0.0

    lines = monitor.build_overlay_lines(
        metrics=Metrics(),
        perclos=0.1,
        ai_result={
            "state": "NORMAL",
            "confidence": 0.9,
            "alert_hint": 0,
            "reason": "stable",
            "thresholds": {"ear_closed": 0.24, "mar_yawn": 0.45, "pitch_down": -15.0},
            "features": {"perclos_short": 0.0, "perclos_long": 0.1},
        },
        calibration={"valid": True, "sample_count": 40},
        camera_fps=10.0,
        ai_fps=10.0,
        frame_count=1,
    )

    assert any("EAR" in line and "0.24" in line for line in lines)
    assert any("CALIBRATED" in line for line in lines)


def test_draws_eye_and_mouth_landmarks_when_present():
    monitor = load_script()

    class FakeCv2:
        LINE_AA = 16
        FONT_HERSHEY_SIMPLEX = 0

        def __init__(self):
            self.polylines_calls = []

        def polylines(self, frame, points, is_closed, color, thickness):
            self.polylines_calls.append((points, is_closed, color, thickness))

        def putText(self, *args, **kwargs):
            pass

    class Metrics:
        left_eye_points = [(1, 1), (2, 1), (3, 1)]
        right_eye_points = [(1, 3), (2, 3), (3, 3)]
        mouth_points = [(1, 5), (2, 6), (3, 5)]

    fake_cv2 = FakeCv2()
    monitor.draw_debug_landmarks(fake_cv2, None, Metrics(), scale_x=1.0, scale_y=1.0, color=(0, 255, 0))

    assert len(fake_cv2.polylines_calls) == 3


def test_async_bluetooth_status_does_not_block_camera_loop():
    monitor = load_script()
    entered = threading.Event()
    release = threading.Event()

    class SlowBluetoothManager:
        def status(self):
            entered.set()
            release.wait(1.0)
            return {"connected": True}

    poller = monitor.AsyncBluetoothStatus(SlowBluetoothManager(), interval_sec=0.0)
    started = time.monotonic()
    status = poller.poll()
    elapsed = time.monotonic() - started

    try:
        assert elapsed < 0.1
        assert status["connected"] is False
        assert entered.wait(0.2)
    finally:
        release.set()
