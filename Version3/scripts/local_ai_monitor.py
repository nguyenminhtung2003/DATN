#!/usr/bin/env python3
"""Standalone camera + AI monitor for manual Jetson testing.

This script intentionally avoids the full DrowsiGuard orchestrator. It does not
start RFID, GPS, WebSocket, dashboard, queue sync, or audio outputs. Use it when
you only want to verify the CSI camera and drowsiness AI on the Jetson display.
"""
import os
import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import config


WINDOW_NAME = "DrowsiGuard AI Monitor"
DEFAULT_PANEL_WIDTH = 340


class AsyncBluetoothStatus:
    """Poll Bluetooth in the background so camera rendering never blocks."""

    def __init__(self, manager, interval_sec=10.0):
        self._manager = manager
        self._interval_sec = float(interval_sec or 10.0)
        self._lock = threading.Lock()
        self._status = {"connected": False}
        self._last_started = 0.0
        self._thread = None

    def poll(self):
        now = time.monotonic()
        with self._lock:
            status = dict(self._status)
            running = bool(self._thread and self._thread.is_alive())
            should_start = (not running) and (now - self._last_started >= self._interval_sec)
            if should_start:
                self._last_started = now
                self._thread = threading.Thread(target=self._refresh)
                self._thread.daemon = True
                self._thread.start()
        return status

    def _refresh(self):
        try:
            status = self._manager.status()
        except Exception:
            status = {}
        with self._lock:
            self._status = dict(status or {})


def get_camera_pipeline():
    """Return the same CSI camera pipeline used by the main project."""
    return config.GSTREAMER_PIPELINE


def build_overlay_lines(metrics, perclos, ai_result, camera_fps, ai_fps, frame_count, calibration=None, speaker_status=None):
    """Build text lines for the monitor overlay.

    Kept separate from OpenCV drawing so the displayed data stays easy to test.
    """
    state = (ai_result or {}).get("state", "UNKNOWN")
    confidence = float((ai_result or {}).get("confidence", 0.0) or 0.0)
    reason = (ai_result or {}).get("reason", "") or ""
    alert_hint = int((ai_result or {}).get("alert_hint", 0) or 0)
    thresholds = (ai_result or {}).get("thresholds", {}) or {}
    features = (ai_result or {}).get("features", {}) or {}
    face_present = bool(getattr(metrics, "face_present", False))
    ear = float(getattr(metrics, "ear", 0.0) or 0.0)
    left_ear = float(getattr(metrics, "left_ear", ear) or 0.0)
    right_ear = float(getattr(metrics, "right_ear", ear) or 0.0)
    ear_used = float(getattr(metrics, "ear_used", ear) or 0.0)
    eye_quality = getattr(metrics, "eye_quality", {}) or {}
    mar = float(getattr(metrics, "mar", 0.0) or 0.0)
    pitch = float(getattr(metrics, "pitch", 0.0) or 0.0)
    perclos = float(perclos or 0.0)
    calibration = calibration or {}
    speaker_status = speaker_status or {}
    calibration_text = "CALIBRATED" if calibration.get("valid") else "CALIBRATING"
    if calibration.get("reason") and not calibration.get("valid"):
        calibration_text += " %s" % calibration.get("reason")

    return [
        "CAM FPS %.1f | AI FPS %.1f | Frames %s" % (camera_fps, ai_fps, frame_count),
        "FACE %s | AI %s | Alert %s | Confidence %.0f%%" % (
            "ON" if face_present else "OFF",
            state,
            alert_hint,
            confidence * 100.0,
        ),
        "EAR %.3f / %.3f | MAR %.3f / %.3f" % (
            ear,
            float(thresholds.get("ear_closed", config.EAR_THRESHOLD) or config.EAR_THRESHOLD),
            mar,
            float(thresholds.get("mar_yawn", config.MAR_THRESHOLD) or config.MAR_THRESHOLD),
        ),
        "L/R/USED %.3f / %.3f / %.3f" % (left_ear, right_ear, ear_used),
        "Eye quality %s | %s" % (
            eye_quality.get("selected", "none"),
            eye_quality.get("reason", "-"),
        ),
        "Pitch %.1f / %.1f | PERCLOS %.3f / %.3f" % (
            pitch,
            float(thresholds.get("pitch_down", config.PITCH_DELTA_THRESHOLD) or config.PITCH_DELTA_THRESHOLD),
            float(features.get("perclos_short", perclos) or 0.0),
            float(features.get("perclos_long", perclos) or 0.0),
        ),
        "%s | Samples %s" % (calibration_text, calibration.get("sample_count", 0)),
        "Speaker BT %s | Audio %s" % (
            "ON" if speaker_status.get("connected") else "OFF",
            "OK" if speaker_status.get("output_ok", True) else "FAIL",
        ),
        "Reason: %s" % (reason or "-"),
        "Keys: q/Esc quit | s snapshot | c recal | 1/2/3 speaker",
    ]


def calculate_monitor_layout(frame_width, frame_height, total_width, panel_width=DEFAULT_PANEL_WIDTH):
    """Return a side-panel layout where text never covers camera pixels."""
    frame_width = max(1, int(frame_width or 1))
    frame_height = max(1, int(frame_height or 1))
    total_width = max(640, int(total_width or 960))
    panel_width = min(max(280, int(panel_width or DEFAULT_PANEL_WIDTH)), total_width - 320)
    camera_width = max(320, total_width - panel_width)
    camera_height = max(240, int(float(frame_height) * (float(camera_width) / float(frame_width))))
    return {
        "camera_x": 0,
        "camera_y": 0,
        "camera_width": camera_width,
        "camera_height": camera_height,
        "panel_x": camera_width,
        "panel_y": 0,
        "panel_width": panel_width,
        "panel_height": camera_height,
        "canvas_width": camera_width + panel_width,
        "canvas_height": camera_height,
    }


def _state_color(state):
    if state in ("NORMAL",):
        return (80, 230, 80)
    if state in ("BLINK", "EYES_CLOSED"):
        return (0, 230, 255)
    if state in ("YAWNING",):
        return (0, 220, 255)
    if state in ("DROWSY", "HEAD_DOWN", "NO_FACE"):
        return (0, 0, 255)
    if state in ("LOW_CONFIDENCE",):
        return (150, 150, 150)
    return (230, 230, 230)


def _draw_text(cv2, frame, text, x, y, color=(235, 235, 235), scale=0.58, thickness=1):
    cv2.putText(frame, str(text), (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def _wrap_text(text, max_chars):
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_face_box(cv2, frame, metrics, color, source_width, source_height):
    bbox = getattr(metrics, "face_bbox", None)
    if not bbox or not source_width or not source_height:
        return
    target_height, target_width = frame.shape[:2]
    scale_x = float(target_width) / float(source_width)
    scale_y = float(target_height) / float(source_height)
    x, y, w, h = bbox
    x1 = int(x * scale_x)
    y1 = int(y * scale_y)
    x2 = int((x + w) * scale_x)
    y2 = int((y + h) * scale_y)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)


def draw_debug_landmarks(cv2, frame, metrics, scale_x=1.0, scale_y=1.0, color=(80, 230, 80)):
    """Draw MediaPipe eye and mouth landmarks on the camera image."""
    try:
        import numpy as np
    except Exception:
        np = None

    def scaled(points):
        return [(int(x * scale_x), int(y * scale_y)) for x, y in (points or [])]

    for attr_name in ("left_eye_points", "right_eye_points", "mouth_points"):
        points = scaled(getattr(metrics, attr_name, []))
        if len(points) < 2:
            continue
        if np is not None:
            cv2.polylines(frame, [np.array(points, dtype=np.int32)], True, color, 1)
        else:
            cv2.polylines(frame, [points], True, color, 1)


def _draw_info_panel(cv2, canvas, layout, lines, ai_result):
    state = (ai_result or {}).get("state", "UNKNOWN")
    color = _state_color(state)
    x = layout["panel_x"]
    panel_width = layout["panel_width"]
    panel_height = layout["panel_height"]

    cv2.rectangle(canvas, (x, 0), (x + panel_width - 1, panel_height - 1), (18, 18, 18), -1)
    cv2.rectangle(canvas, (x, 0), (x + panel_width - 1, panel_height - 1), (230, 230, 230), 1)
    _draw_text(cv2, canvas, "DrowsiGuard AI Monitor", x + 16, 32, (255, 255, 255), 0.6, 2)

    y = 62
    for index, line in enumerate(lines):
        text_color = color if index == 1 else (235, 235, 235)
        max_chars = max(24, int((panel_width - 28) / 10))
        for wrapped in _wrap_text(line, max_chars):
            _draw_text(cv2, canvas, wrapped, x + 16, y, text_color)
            y += 22

    if state not in ("UNKNOWN", "NORMAL"):
        y = min(panel_height - 46, max(y + 8, 176))
        _draw_text(cv2, canvas, "AI: %s" % state, x + 16, y, color, 0.86, 3)


def compose_monitor_canvas(cv2, np, frame, lines, ai_result, metrics, total_width):
    source_height, source_width = frame.shape[:2]
    layout = calculate_monitor_layout(source_width, source_height, total_width)
    camera_frame = _resize_for_display(cv2, frame, layout["camera_width"])
    color = _state_color((ai_result or {}).get("state", "UNKNOWN"))
    _draw_face_box(cv2, camera_frame, metrics, color, source_width, source_height)
    scale_x = float(camera_frame.shape[1]) / float(source_width) if source_width else 1.0
    scale_y = float(camera_frame.shape[0]) / float(source_height) if source_height else 1.0
    draw_debug_landmarks(cv2, camera_frame, metrics, scale_x=scale_x, scale_y=scale_y, color=color)

    canvas = np.zeros((layout["canvas_height"], layout["canvas_width"], 3), dtype=np.uint8)
    canvas[:, :] = (12, 12, 12)
    camera_height, camera_width = camera_frame.shape[:2]
    canvas[0:camera_height, 0:camera_width] = camera_frame
    _draw_info_panel(cv2, canvas, layout, lines, ai_result)
    return canvas


def _resize_for_display(cv2, frame, target_width):
    if not target_width:
        return frame
    height, width = frame.shape[:2]
    if width <= 0 or width == target_width:
        return frame
    target_height = max(240, int(float(height) * (float(target_width) / float(width))))
    return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)


def run():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        print("Missing OpenCV/numpy dependency: %s" % exc)
        return 2

    from camera.face_analyzer import FaceAnalyzer
    from ai.drowsiness_classifier import DrowsinessClassifier
    from ai.calibration import DriverCalibrator
    from alerts.speaker import Speaker
    from audio.bluetooth_manager import BluetoothManager

    display_width = int(os.getenv("DROWSIGUARD_LOCAL_AI_WIDTH", "960"))
    pipeline = get_camera_pipeline()

    print("Starting standalone AI monitor")
    print("DISPLAY=%s" % os.getenv("DISPLAY", ""))
    print("Pipeline: %s" % pipeline)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, display_width, int((display_width - DEFAULT_PANEL_WIDTH) * 9 / 16))

    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("ERROR: Could not open CSI camera. Stop other camera users and restart nvargus-daemon.")
        cv2.destroyWindow(WINDOW_NAME)
        return 3

    analyzer = FaceAnalyzer()
    classifier = DrowsinessClassifier()
    calibrator = DriverCalibrator()
    speaker = Speaker()
    bluetooth_manager = BluetoothManager()
    bluetooth_status = AsyncBluetoothStatus(
        bluetooth_manager,
        interval_sec=float(os.getenv("DROWSIGUARD_LOCAL_AI_BT_INTERVAL", "10")),
    )
    frame_count = 0
    ai_count = 0
    fps_timer = time.monotonic()
    camera_fps = 0.0
    ai_fps = 0.0
    last_metrics = None
    last_result = dict(classifier.last_result)
    last_perclos = 0.0
    calibration = calibrator.profile.to_dict(active=True)
    speaker_status = {"connected": False, "output_ok": True}

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                frame = np.zeros((540, max(320, display_width - DEFAULT_PANEL_WIDTH), 3), dtype=np.uint8)
                last_result = {
                    "state": "UNKNOWN",
                    "confidence": 0.0,
                    "reason": "Camera opened but no frame was read",
                }
            else:
                frame_count += 1
                metrics = analyzer.analyze(frame)
                last_metrics = metrics
                last_perclos = analyzer.perclos
                now = time.time()
                if not calibration.get("valid") and calibration.get("active", True):
                    calibrator.add(metrics, now)
                    profile = calibrator.profile
                    if profile.valid or calibrator.complete(now):
                        classifier.set_profile(profile)
                        calibration = profile.to_dict(active=False)
                        print("Calibration applied valid=%s reason=%s samples=%s" % (
                            profile.valid,
                            profile.reason,
                            profile.sample_count,
                        ))
                    else:
                        calibration = profile.to_dict(active=True)
                        if calibration.get("reason") == "NOT_ENOUGH_SAMPLES":
                            calibration["reason"] = "COLLECTING"
                last_result = classifier.update({
                    "face_present": metrics.face_present,
                    "ear": metrics.ear,
                    "left_ear": getattr(metrics, "left_ear", metrics.ear),
                    "right_ear": getattr(metrics, "right_ear", metrics.ear),
                    "ear_used": getattr(metrics, "ear_used", metrics.ear),
                    "mar": metrics.mar,
                    "pitch": metrics.pitch,
                    "perclos": last_perclos,
                    "face_bbox": metrics.face_bbox,
                    "face_quality": getattr(metrics, "face_quality", {}),
                    "eye_quality": getattr(metrics, "eye_quality", {}),
                })
                ai_count += 1

            elapsed = time.monotonic() - fps_timer
            if elapsed >= 1.0:
                camera_fps = frame_count / elapsed
                ai_fps = ai_count / elapsed
                frame_count = 0
                ai_count = 0
                fps_timer = time.monotonic()
                bt_status = bluetooth_status.poll()
                speaker_status = {
                    "connected": bool(bt_status.get("connected")),
                    "output_ok": bool(getattr(speaker, "is_available", False)),
                }

            lines = build_overlay_lines(
                metrics=last_metrics,
                perclos=last_perclos,
                ai_result=last_result,
                camera_fps=camera_fps,
                ai_fps=ai_fps,
                frame_count=frame_count,
                calibration=calibration,
                speaker_status=speaker_status,
            )
            canvas = compose_monitor_canvas(cv2, np, frame, lines, last_result, last_metrics, display_width)
            cv2.imshow(WINDOW_NAME, canvas)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("s"):
                out_path = "local_ai_monitor_snapshot.jpg"
                cv2.imwrite(out_path, canvas)
                print("Saved %s" % out_path)
            if key == ord("c"):
                calibrator.reset()
                classifier.reset_state()
                calibration = calibrator.profile.to_dict(active=True)
                print("Calibration reset")
            if key in (ord("1"), ord("2"), ord("3")):
                level = int(chr(key))
                ok = speaker.play_alert(level)
                speaker_status["output_ok"] = bool(ok)
                print("Speaker test level %s ok=%s" % (level, ok))
    finally:
        cap.release()
        analyzer.release()
        speaker.cleanup()
        cv2.destroyWindow(WINDOW_NAME)

    return 0


if __name__ == "__main__":
    sys.exit(run())
