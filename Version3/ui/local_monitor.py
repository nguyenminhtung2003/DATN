"""OpenCV local monitor shown directly on the Jetson display/NoMachine.

The monitor is display-only: it never opens the CSI camera and never runs
MediaPipe. The main orchestrator owns those expensive resources and passes
frame/state snapshots into this module.
"""
import time

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None


WINDOW_NAME = "DrowsiGuard Local Monitor"
DEFAULT_PANEL_WIDTH = 340
DEFAULT_EAR_THRESHOLD = 0.24
DEFAULT_MAR_THRESHOLD = 0.45
DEFAULT_PITCH_THRESHOLD = -15.0


class LocalMonitorState:
    FIELDS = (
        "camera_online",
        "camera_fps",
        "camera_frame_id",
        "camera_frame_age_sec",
        "camera_stale",
        "ai_fps",
        "ai_target_fps",
        "face_present",
        "ear",
        "left_ear",
        "right_ear",
        "ear_used",
        "eye_quality_selected",
        "eye_quality_reason",
        "eye_quality_left_usable",
        "eye_quality_right_usable",
        "mar",
        "pitch",
        "perclos",
        "perclos_short",
        "perclos_long",
        "ai_state",
        "ai_confidence",
        "ai_reason",
        "ai_runtime_reason",
        "alert_level",
        "alert_hint",
        "ear_threshold",
        "mar_threshold",
        "pitch_threshold",
        "session_state",
        "session_active",
        "monitoring_enabled",
        "rfid_last_uid",
        "gps_uart_ok",
        "gps_fix_ok",
        "gps_lat",
        "gps_lng",
        "gps_speed",
        "gps_reason",
        "bluetooth_adapter_ok",
        "bluetooth_speaker_connected",
        "speaker_output_ok",
        "websocket_connected",
        "queue_pending",
        "network_summary",
        "cpu_temp_c",
        "ram_percent",
        "calibration_active",
        "calibration_valid",
        "calibration_reason",
        "calibration_sample_count",
        "left_eye_points",
        "right_eye_points",
        "mouth_points",
        "face_bbox",
        "landmark_source_width",
        "landmark_source_height",
    )

    DEFAULTS = {
        "camera_online": False,
        "camera_fps": 0.0,
        "camera_frame_id": 0,
        "camera_frame_age_sec": None,
        "camera_stale": True,
        "ai_fps": 0.0,
        "ai_target_fps": 0.0,
        "face_present": False,
        "ear": 0.0,
        "left_ear": 0.0,
        "right_ear": 0.0,
        "ear_used": 0.0,
        "eye_quality_selected": "none",
        "eye_quality_reason": "",
        "eye_quality_left_usable": False,
        "eye_quality_right_usable": False,
        "mar": 0.0,
        "pitch": 0.0,
        "perclos": 0.0,
        "perclos_short": 0.0,
        "perclos_long": 0.0,
        "ai_state": "UNKNOWN",
        "ai_confidence": 0.0,
        "ai_reason": "",
        "ai_runtime_reason": "",
        "alert_level": "NONE",
        "alert_hint": 0,
        "ear_threshold": DEFAULT_EAR_THRESHOLD,
        "mar_threshold": DEFAULT_MAR_THRESHOLD,
        "pitch_threshold": DEFAULT_PITCH_THRESHOLD,
        "session_state": "UNKNOWN",
        "session_active": False,
        "monitoring_enabled": False,
        "rfid_last_uid": None,
        "gps_uart_ok": False,
        "gps_fix_ok": False,
        "gps_lat": None,
        "gps_lng": None,
        "gps_speed": None,
        "gps_reason": "",
        "bluetooth_adapter_ok": False,
        "bluetooth_speaker_connected": False,
        "speaker_output_ok": False,
        "websocket_connected": False,
        "queue_pending": 0,
        "network_summary": "-",
        "cpu_temp_c": None,
        "ram_percent": None,
        "calibration_active": False,
        "calibration_valid": False,
        "calibration_reason": "",
        "calibration_sample_count": 0,
        "left_eye_points": (),
        "right_eye_points": (),
        "mouth_points": (),
        "face_bbox": None,
        "landmark_source_width": 0,
        "landmark_source_height": 0,
    }

    def __init__(self, **kwargs):
        for field in self.FIELDS:
            value = kwargs.get(field, self.DEFAULTS[field])
            if field in ("left_eye_points", "right_eye_points", "mouth_points"):
                value = list(value or [])
            setattr(self, field, value)

    @classmethod
    def from_runtime_payload(cls, payload):
        payload = payload or {}
        camera = payload.get("camera") or {}
        ai = payload.get("ai") or {}
        alert = payload.get("alert") or {}
        session = payload.get("session") or {}
        driver = payload.get("driver") or {}
        hardware = payload.get("hardware") or {}
        details = hardware.get("details") or {}
        gps = payload.get("gps") or payload.get("latest_gps") or {}
        queue = payload.get("queue") or {}
        system = payload.get("system") or {}
        network = hardware.get("network") or payload.get("network") or {}
        websocket = payload.get("websocket") or {}
        thresholds = ai.get("thresholds") or {}
        features = ai.get("features") or {}
        calibration = payload.get("calibration") or {}
        landmarks = ai.get("landmarks") or {}
        eye_quality = ai.get("eye_quality") or {}
        left_eye_quality = eye_quality.get("left") or {}
        right_eye_quality = eye_quality.get("right") or {}
        source_width, source_height = _source_size(landmarks.get("source_size"))

        return cls(
            camera_online=bool(camera.get("online")),
            camera_fps=_float(camera.get("fps")),
            camera_frame_id=int(camera.get("frame_id") or 0),
            camera_frame_age_sec=_optional_float(camera.get("frame_age_sec")),
            camera_stale=bool(camera.get("stale")),
            ai_fps=_float(ai.get("fps")),
            ai_target_fps=_float(ai.get("target_fps")),
            face_present=bool(ai.get("face_present")),
            ear=_float(ai.get("ear")),
            left_ear=_float(ai.get("left_ear"), _float(ai.get("ear"))),
            right_ear=_float(ai.get("right_ear"), _float(ai.get("ear"))),
            ear_used=_float(ai.get("ear_used"), _float(ai.get("ear"))),
            eye_quality_selected=eye_quality.get("selected") or "none",
            eye_quality_reason=eye_quality.get("reason") or "",
            eye_quality_left_usable=bool(left_eye_quality.get("usable")),
            eye_quality_right_usable=bool(right_eye_quality.get("usable")),
            mar=_float(ai.get("mar")),
            pitch=_float(ai.get("pitch")),
            perclos=_float(ai.get("perclos")),
            perclos_short=_float(features.get("perclos_short"), _float(ai.get("perclos"))),
            perclos_long=_float(features.get("perclos_long"), _float(ai.get("perclos"))),
            ai_state=ai.get("state") or "UNKNOWN",
            ai_confidence=_float(ai.get("confidence")),
            ai_reason=ai.get("reason") or "",
            ai_runtime_reason=ai.get("runtime_reason") or "",
            alert_level=alert.get("level") or "NONE",
            alert_hint=int(_float(ai.get("alert_hint"), 0)),
            ear_threshold=_float(thresholds.get("ear_closed"), DEFAULT_EAR_THRESHOLD),
            mar_threshold=_float(thresholds.get("mar_yawn"), DEFAULT_MAR_THRESHOLD),
            pitch_threshold=_float(thresholds.get("pitch_down"), DEFAULT_PITCH_THRESHOLD),
            session_state=session.get("state") or "UNKNOWN",
            session_active=bool(session.get("active")),
            monitoring_enabled=bool(session.get("monitoring_enabled")),
            rfid_last_uid=driver.get("rfid_tag") or hardware.get("rfid_last_uid"),
            gps_uart_ok=bool(hardware.get("gps_uart_ok") or hardware.get("gps")),
            gps_fix_ok=bool(hardware.get("gps_fix_ok") or gps.get("fix_ok")),
            gps_lat=gps.get("lat"),
            gps_lng=gps.get("lng"),
            gps_speed=gps.get("speed"),
            gps_reason=details.get("gps_reason") or "",
            bluetooth_adapter_ok=bool(hardware.get("bluetooth_adapter_ok") or hardware.get("bluetooth_adapter")),
            bluetooth_speaker_connected=bool(hardware.get("bluetooth_speaker_connected") or hardware.get("bluetooth")),
            speaker_output_ok=bool(hardware.get("speaker_output_ok") or hardware.get("speaker")),
            websocket_connected=bool(websocket.get("connected") or hardware.get("websocket_ok")),
            queue_pending=int(queue.get("pending") or hardware.get("queue_pending") or 0),
            network_summary=_network_summary(network),
            cpu_temp_c=system.get("cpu_temp_c"),
            ram_percent=system.get("ram_percent"),
            calibration_active=bool(calibration.get("active")),
            calibration_valid=bool(calibration.get("valid")),
            calibration_reason=calibration.get("reason") or "",
            calibration_sample_count=int(calibration.get("sample_count") or 0),
            left_eye_points=_point_list(landmarks.get("left_eye_points")),
            right_eye_points=_point_list(landmarks.get("right_eye_points")),
            mouth_points=_point_list(landmarks.get("mouth_points")),
            face_bbox=_bbox(landmarks.get("face_bbox")),
            landmark_source_width=source_width,
            landmark_source_height=source_height,
        )


class LocalMonitorGUI:
    def __init__(self, max_fps=10, width=960, test_keys_enabled=True, window_name=WINDOW_NAME):
        self.max_fps = max(1.0, float(max_fps or 10))
        self.width = max(640, int(width or 960))
        self.test_keys_enabled = bool(test_keys_enabled)
        self.window_name = window_name
        self.enabled = cv2 is not None
        self._last_render_at = None
        self._frame_count = 0

    def update(self, frame, state):
        if not self.enabled:
            return []
        try:
            now = time.monotonic()
            if self._last_render_at is not None and now - self._last_render_at < (1.0 / self.max_fps):
                return []
            self._last_render_at = now

            state = state or LocalMonitorState()
            frame = self._prepare_frame(frame)
            self._frame_count += 1
            if _can_compose_side_panel(frame):
                canvas = compose_monitor_canvas(cv2, np, frame, state, self.width, self._frame_count)
            else:
                canvas = frame
                self._draw_overlay(canvas, state)
            cv2.imshow(self.window_name, canvas)
            return self._read_actions(canvas)
        except Exception:
            self.enabled = False
            return []

    def close(self):
        if cv2 is None:
            return
        try:
            cv2.destroyWindow(self.window_name)
        except Exception:
            pass

    def _prepare_frame(self, frame):
        if frame is None:
            if np is None:
                raise RuntimeError("No frame and numpy unavailable")
            camera_width = max(320, self.width - DEFAULT_PANEL_WIDTH)
            return np.zeros((540, camera_width, 3), dtype=np.uint8)
        return frame.copy()

    def _read_actions(self, frame):
        key = cv2.waitKey(1) & 0xFF
        actions = []
        if key in (ord("q"), 27):
            actions.append("quit")
        elif key == ord("s"):
            if hasattr(cv2, "imwrite"):
                cv2.imwrite("local_monitor_snapshot.jpg", frame)
            actions.append("save_snapshot")
        elif key == ord("r"):
            actions.append("reset_alert")
        elif self.test_keys_enabled and key in (ord("1"), ord("2"), ord("3")):
            actions.append("test_alert_%s" % chr(key))
        elif self.test_keys_enabled and key == ord("g"):
            actions.append("start_demo_session")
        return actions

    def _draw_overlay(self, frame, state):
        x, y = 12, 24
        self._panel(frame, 8, 8, 420, 210)
        self._text(frame, "DrowsiGuard Local Monitor", x, y, color=(255, 255, 255), scale=0.65, thickness=2)
        y += 28
        self._status_line(frame, x, y, "CAMERA", state.camera_online, "FPS %.1f" % state.camera_fps)
        y += 24
        self._status_line(frame, x, y, "SESSION", state.session_active, "%s monitor=%s" % (state.session_state, _onoff(state.monitoring_enabled)))
        y += 24
        self._text(frame, "AI %s  %.0f%%  FPS %.1f/%.1f" % (
            state.ai_state,
            state.ai_confidence * 100.0,
            state.ai_fps,
            state.ai_target_fps,
        ), x, y, color=_state_color(state.ai_state))
        y += 24
        self._text(frame, "EAR %.3f/%.3f  MAR %.3f/%.3f  PERCLOS %.3f" % (
            state.ear,
            state.ear_threshold,
            state.mar,
            state.mar_threshold,
            state.perclos_long or state.perclos,
        ), x, y)
        y += 24
        self._text(frame, "ALERT %s hint=%s" % (state.alert_level, state.alert_hint), x, y, color=_alert_color(state.alert_level), scale=0.65, thickness=2)
        y += 24
        self._text(frame, "FACE %s  RFID %s" % (_onoff(state.face_present), state.rfid_last_uid or "-"), x, y)

    def _panel(self, frame, x1, y1, x2, y2):
        cv2.rectangle(frame, (x1, y1), (x2, y2), (20, 20, 20), -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (230, 230, 230), 1)

    def _text(self, frame, text, x, y, color=(230, 230, 230), scale=0.55, thickness=1):
        cv2.putText(frame, str(text), (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

    def _status_line(self, frame, x, y, label, ok, detail):
        color = (60, 220, 60) if ok else (60, 60, 255)
        self._text(frame, "%s: %s  %s" % (label, "ON" if ok else "OFF", detail), x, y, color=color)


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


def build_panel_lines(state, frame_count=0):
    calibration_text = "CALIBRATED" if state.calibration_valid else "CALIBRATING"
    if state.calibration_reason:
        calibration_text += " %s" % state.calibration_reason

    return [
        "CAM FPS %.1f | AI FPS %.1f | Frames %s" % (state.camera_fps, state.ai_fps, frame_count),
        "Camera frame_id %s | Age %s | %s" % (
            state.camera_frame_id,
            _age_text(state.camera_frame_age_sec),
            "STALE" if state.camera_stale else "LIVE",
        ),
        "AI runtime %s" % (state.ai_runtime_reason or "-"),
        "FACE %s | AI %s | Alert %s | Confidence %.0f%%" % (
            _onoff(state.face_present),
            state.ai_state,
            state.alert_hint,
            state.ai_confidence * 100.0,
        ),
        "EAR %.3f / %.3f | MAR %.3f / %.3f" % (
            state.ear,
            state.ear_threshold,
            state.mar,
            state.mar_threshold,
        ),
        "L/R/USED %.3f / %.3f / %.3f" % (
            state.left_ear,
            state.right_ear,
            state.ear_used,
        ),
        "Eye quality %s | %s" % (
            state.eye_quality_selected,
            state.eye_quality_reason or "-",
        ),
        "Pitch %.1f / %.1f | PERCLOS %.3f / %.3f" % (
            state.pitch,
            state.pitch_threshold,
            state.perclos_short,
            state.perclos_long,
        ),
        "%s | Samples %s" % (calibration_text, state.calibration_sample_count),
        "SESSION %s monitor=%s | RFID %s" % (
            state.session_state,
            _onoff(state.monitoring_enabled),
            state.rfid_last_uid or "-",
        ),
        "GPS UART %s | FIX %s | %s" % (
            _onoff(state.gps_uart_ok),
            _onoff(state.gps_fix_ok),
            _gps_summary(state),
        ),
        "BT %s | Speaker %s | Audio %s" % (
            _onoff(state.bluetooth_adapter_ok),
            _onoff(state.bluetooth_speaker_connected),
            "OK" if state.speaker_output_ok else "FAIL",
        ),
        "WS %s | queue=%s" % (_onoff(state.websocket_connected), state.queue_pending),
        "NET %s" % state.network_summary,
        "TEMP %s C | RAM %s%%" % (_fmt(state.cpu_temp_c), _fmt(state.ram_percent)),
        "Reason: %s" % (state.ai_reason or "-"),
        "Keys: q/Esc quit | s snapshot | r reset | g demo | 1/2/3 speaker",
    ]


def draw_debug_landmarks(cv2_module, frame, state, scale_x=1.0, scale_y=1.0, color=(80, 230, 80)):
    """Draw MediaPipe eye and mouth landmarks on the camera image."""
    def scaled(points):
        return [(int(x * scale_x), int(y * scale_y)) for x, y in (points or [])]

    for attr_name in ("left_eye_points", "right_eye_points", "mouth_points"):
        points = scaled(getattr(state, attr_name, []))
        if len(points) < 2:
            continue
        draw_color = color
        if attr_name == "left_eye_points":
            draw_color = (0, 255, 0) if getattr(state, "eye_quality_left_usable", False) else (0, 230, 255)
        elif attr_name == "right_eye_points":
            draw_color = (0, 255, 0) if getattr(state, "eye_quality_right_usable", False) else (0, 230, 255)
        if np is not None:
            cv2_module.polylines(frame, [np.array(points, dtype=np.int32)], True, draw_color, 1)
        else:
            cv2_module.polylines(frame, [points], True, draw_color, 1)


def compose_monitor_canvas(cv2_module, np_module, frame, state, total_width, frame_count=0):
    source_height, source_width = frame.shape[:2]
    layout = calculate_monitor_layout(source_width, source_height, total_width)
    camera_frame = _resize_for_display(cv2_module, frame, layout["camera_width"])
    color = _state_color(state.ai_state)

    landmark_source_width = state.landmark_source_width or source_width
    landmark_source_height = state.landmark_source_height or source_height
    _draw_face_box(cv2_module, camera_frame, state, color, landmark_source_width, landmark_source_height)
    scale_x = float(camera_frame.shape[1]) / float(landmark_source_width) if landmark_source_width else 1.0
    scale_y = float(camera_frame.shape[0]) / float(landmark_source_height) if landmark_source_height else 1.0
    draw_debug_landmarks(cv2_module, camera_frame, state, scale_x=scale_x, scale_y=scale_y, color=color)

    canvas = np_module.zeros((layout["canvas_height"], layout["canvas_width"], 3), dtype=np_module.uint8)
    canvas[:, :] = (12, 12, 12)
    camera_height, camera_width = camera_frame.shape[:2]
    canvas[0:camera_height, 0:camera_width] = camera_frame
    _draw_info_panel(cv2_module, canvas, layout, build_panel_lines(state, frame_count), state)
    return canvas


def _draw_info_panel(cv2_module, canvas, layout, lines, state):
    color = _state_color(state.ai_state)
    x = layout["panel_x"]
    panel_width = layout["panel_width"]
    panel_height = layout["panel_height"]

    cv2_module.rectangle(canvas, (x, 0), (x + panel_width - 1, panel_height - 1), (18, 18, 18), -1)
    cv2_module.rectangle(canvas, (x, 0), (x + panel_width - 1, panel_height - 1), (230, 230, 230), 1)
    _draw_text(cv2_module, canvas, "DrowsiGuard AI Monitor", x + 16, 32, (255, 255, 255), 0.6, 2)

    y = 62
    for index, line in enumerate(lines):
        text_color = color if index == 1 else (235, 235, 235)
        max_chars = max(24, int((panel_width - 28) / 10))
        for wrapped in _wrap_text(line, max_chars):
            _draw_text(cv2_module, canvas, wrapped, x + 16, y, text_color)
            y += 22

    if state.ai_state not in ("UNKNOWN", "NORMAL"):
        y = min(panel_height - 46, max(y + 8, 176))
        _draw_text(cv2_module, canvas, "AI: %s" % state.ai_state, x + 16, y, color, 0.86, 3)


def _draw_face_box(cv2_module, frame, state, color, source_width, source_height):
    bbox = state.face_bbox
    if not bbox or not source_width or not source_height:
        return
    target_height, target_width = frame.shape[:2]
    scale_x = float(target_width) / float(source_width)
    scale_y = float(target_height) / float(source_height)
    x, y, width, height = bbox
    x1 = int(x * scale_x)
    y1 = int(y * scale_y)
    x2 = int((x + width) * scale_x)
    y2 = int((y + height) * scale_y)
    cv2_module.rectangle(frame, (x1, y1), (x2, y2), color, 2)


def _resize_for_display(cv2_module, frame, target_width):
    height, width = frame.shape[:2]
    if width <= 0 or width == target_width:
        return frame
    target_height = max(240, int(float(height) * (float(target_width) / float(width))))
    return cv2_module.resize(frame, (target_width, target_height), interpolation=cv2_module.INTER_AREA)


def _draw_text(cv2_module, frame, text, x, y, color=(235, 235, 235), scale=0.58, thickness=1):
    cv2_module.putText(frame, str(text), (x, y), cv2_module.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2_module.LINE_AA)


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


def _can_compose_side_panel(frame):
    return np is not None and hasattr(frame, "shape") and hasattr(frame, "__setitem__")


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _age_text(value):
    if value is None:
        return "-"
    return "%.2fs" % float(value)


def _fmt(value):
    if value is None:
        return "-"
    try:
        return "%.1f" % float(value)
    except (TypeError, ValueError):
        return str(value)


def _onoff(value):
    return "ON" if value else "OFF"


def _network_summary(network):
    if not network:
        return "-"
    eth = network.get("eth0_ip")
    wlan = network.get("wlan0_ip")
    ssid = network.get("ssid")
    if eth:
        return "eth0 %s" % eth
    if wlan and ssid:
        return "wifi %s %s" % (ssid, wlan)
    if wlan:
        return "wlan0 %s" % wlan
    return "-"


def _gps_summary(state):
    if state.gps_lat is not None and state.gps_lng is not None:
        speed = "" if state.gps_speed is None else " %.1fkm/h" % _float(state.gps_speed)
        return "%.6f, %.6f%s" % (_float(state.gps_lat), _float(state.gps_lng), speed)
    return state.gps_reason or "-"


def _source_size(value):
    try:
        if value and len(value) >= 2:
            return int(value[0] or 0), int(value[1] or 0)
    except (TypeError, ValueError):
        pass
    return 0, 0


def _point_list(value):
    points = []
    for point in value or []:
        try:
            if len(point) >= 2:
                points.append((int(point[0]), int(point[1])))
        except (TypeError, ValueError):
            continue
    return points


def _bbox(value):
    try:
        if value and len(value) >= 4:
            return (int(value[0]), int(value[1]), int(value[2]), int(value[3]))
    except (TypeError, ValueError):
        pass
    return None


def _state_color(state):
    if state in ("NORMAL",):
        return (80, 230, 80)
    if state in ("BLINK", "EYES_CLOSED"):
        return (0, 230, 255)
    if state in ("YAWNING",):
        return (0, 220, 255)
    if state in ("DROWSY", "HEAD_DOWN", "NO_FACE", "FATIGUE"):
        return (0, 0, 255)
    if state in ("LOW_CONFIDENCE",):
        return (150, 150, 150)
    return (230, 230, 230)


def _alert_color(level):
    if level in ("CRITICAL", "LEVEL_3"):
        return (0, 0, 255)
    if level in ("DANGER", "LEVEL_2"):
        return (0, 80, 255)
    if level in ("WARNING", "LEVEL_1"):
        return (0, 220, 255)
    return (60, 220, 60)
