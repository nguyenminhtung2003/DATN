#!/usr/bin/env python3
"""
DrowsiGuard Version3 — Main Orchestrator
Entry point for the drowsiness warning system on Jetson Nano A02.

Execution order follows jetson_execution_tasks.md:
1. Initialize logging
2. Initialize state machine (BOOTING)
3. Start camera pipeline (single owner)
4. Start face analyzer (drowsiness)
5. Start alert manager
6. Start RFID reader (USB HID)
7. Transition to IDLE
8. Main loop: process frames, update alerts, handle RFID events

Deferred modules: GPS, WebSocket, OTA, Face Verification (full), Speaker/Buzzer/LED
"""
import signal
import sys
import time
import threading
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from utils.logger import setup_logger, get_logger
from state_machine import StateMachine, State
from camera.capture import CSICamera
from camera.frame_buffer import FrameBuffer
from camera.face_analyzer import FaceAnalyzer
from camera.face_verifier import FaceVerifier, VerifyResult
from alerts.alert_manager import AlertManager, AlertLevel
from alerts.buzzer import Buzzer
from alerts.led import LEDController
from alerts.speaker import Speaker
from sensors.rfid_reader import RFIDReader
from sensors.gps_reader import GPSReader
from sensors.hardware_monitor import HardwareMonitor
from network.ws_client import WSClient
from network.ota_handler import OTAHandler
from storage.local_queue import LocalQueue
from storage.runtime_status import RuntimeStatusStore
from storage.runtime_snapshot import RuntimeSnapshotWriter
from sensors.system_status import read_network_status, read_system_status
from audio.bluetooth_manager import BluetoothManager
from ai.drowsiness_classifier import DrowsinessClassifier, AIState
from ai.calibration import CalibrationProfile, DriverCalibrator
from ai.threshold_policy import ThresholdPolicy
from ui.local_monitor import LocalMonitorGUI, LocalMonitorState

# ─── Setup ──────────────────────────────────────────────────
root_logger = setup_logger(
    level=config.LOG_LEVEL,
    log_file=config.LOG_FILE,
)
logger = get_logger("main")

# ─── Globals ────────────────────────────────────────────────
shutdown_event = threading.Event()


class AsyncStatusAdapter:
    """Return cached status immediately and refresh slow hardware checks in the background."""

    def __init__(self, reader, default_status=None, interval_sec=10.0):
        self._reader = reader
        self._status = dict(default_status or {})
        self._interval_sec = float(interval_sec or 10.0)
        self._lock = threading.Lock()
        self._thread = None
        self._last_started = 0.0

    def status(self, force_refresh=False):
        if force_refresh:
            status = self._read_status(force_refresh=True)
            with self._lock:
                self._status = dict(status or {})
            return dict(status or {})

        now = time.monotonic()
        with self._lock:
            status = dict(self._status)
            running = bool(self._thread and self._thread.is_alive())
            if not running and now - self._last_started >= self._interval_sec:
                self._last_started = now
                self._thread = threading.Thread(target=self._refresh, daemon=True, name="AsyncStatusRefresh")
                self._thread.start()
        return status

    def reconnect(self):
        reconnect = getattr(self._reader, "reconnect", None)
        if not callable(reconnect):
            return {"ok": False, "error": "reconnect not supported"}
        result = reconnect()
        with self._lock:
            self._status = dict(result or {})
        return result

    def _refresh(self):
        try:
            status = self._read_status(force_refresh=False)
        except Exception:
            status = {}
        with self._lock:
            self._status = dict(status or {})

    def _read_status(self, force_refresh=False):
        status_method = getattr(self._reader, "status", None)
        if callable(status_method):
            try:
                return status_method(force_refresh=force_refresh)
            except TypeError:
                return status_method()
        if callable(self._reader):
            return self._reader()
        return {}


class AsyncSnapshotWriter:
    """Encode dashboard snapshots off the main camera/GUI loop."""

    def __init__(self, writer):
        self._writer = writer
        self._thread = None
        self._lock = threading.Lock()
        self._last_requested = 0.0

    @property
    def min_interval(self):
        return self._writer.min_interval

    @min_interval.setter
    def min_interval(self, value):
        self._writer.min_interval = value

    @property
    def snapshot_path(self):
        return self._writer.snapshot_path

    def maybe_write(self, frame):
        if frame is None:
            return None
        now = time.monotonic()
        with self._lock:
            if now - self._last_requested < self._writer.min_interval:
                return self._writer.snapshot_path
            if self._thread and self._thread.is_alive():
                return self._writer.snapshot_path
            self._last_requested = now
            frame_copy = frame.copy()
            self._thread = threading.Thread(
                target=self._write_snapshot,
                args=(frame_copy, now),
                daemon=True,
                name="AsyncSnapshotWriter",
            )
            self._thread.start()
        return self._writer.snapshot_path

    def _write_snapshot(self, frame, now):
        try:
            self._writer.maybe_write(frame, now=now)
        except Exception as exc:
            logger.warning("Async snapshot write failed: %s", exc)


class DrowsiGuard:
    """Main orchestrator for the drowsiness warning system."""

    def __init__(self):
        shutdown_event.clear()
        logger.info("=" * 60)
        logger.info("DrowsiGuard %s starting...", getattr(config, "APP_VERSION", "Version3"))
        logger.info(f"Device ID: {config.DEVICE_ID}")
        
        if getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False):
            logger.warning("!!! WARNING: DEMO MODE IS ENABLED !!!")
            logger.warning("Unverified sessions will be ALLOWED. Do not use in production.")
        else:
            logger.info("SECURITY: Strict Mode IS ENABLED. Unverified sessions will be REJECTED.")
            
        logger.info(f"Features: {config.FEATURES}")
        logger.info("=" * 60)

        # State Machine
        self.state = StateMachine(on_transition=self._on_state_change)

        # Camera (single owner)
        self.camera = CSICamera()
        self.frame_buffer = FrameBuffer()

        # Drowsiness
        self.face_analyzer = FaceAnalyzer() if config.FEATURES["drowsiness"] else None
        self.ai_classifier = DrowsinessClassifier() if config.AI_CLASSIFIER_ENABLED else None
        self.calibrator = DriverCalibrator()
        self._calibration_profile = CalibrationProfile.fallback(reason="NOT_STARTED")
        self._calibration_applied = False

        # Alert hardware (scaffold — blocked)
        self.buzzer = Buzzer() if config.FEATURES["buzzer"] else None
        self.led = LEDController() if config.FEATURES["led"] else None
        self.speaker = Speaker() if config.FEATURES["speaker"] else None

        # Alert Manager
        self.alert_manager = AlertManager(
            buzzer=self.buzzer,
            led=self.led,
            speaker=self.speaker,
            on_alert=self._on_alert,
        )

        # RFID
        self.rfid = RFIDReader(callback=self._on_rfid_scan) if config.FEATURES["rfid"] else None

        # GPS (blocked)
        self.gps = GPSReader() if config.FEATURES["gps"] else None

        # Storage
        self.local_queue = LocalQueue()

        # Network
        self.ws_client = WSClient(
            on_command=self._on_backend_command,
            local_queue=self.local_queue,
            on_connect_snapshot=lambda: self.hw_monitor.snapshot(),
            on_connect_callback=self._on_ws_connect,
        ) if config.FEATURES["websocket"] else None

        self.ota_handler = OTAHandler(on_status=self._on_ota_status) if config.FEATURES.get("ota", True) else None
        self.bluetooth_manager = AsyncStatusAdapter(
            BluetoothManager(),
            default_status={
                "adapter": False,
                "speaker_mac": getattr(config, "BLUETOOTH_SPEAKER_MAC", "") or None,
                "paired": False,
                "trusted": False,
                "connected": False,
                "name": None,
            },
            interval_sec=float(getattr(config, "BLUETOOTH_STATUS_INTERVAL", 10.0)),
        )
        self.runtime_store = RuntimeStatusStore()
        self.snapshot_writer = AsyncSnapshotWriter(RuntimeSnapshotWriter())
        self.network_status = AsyncStatusAdapter(
            read_network_status,
            default_status={"eth0_ip": None, "wlan0_ip": None, "ssid": None},
            interval_sec=float(getattr(config, "NETWORK_STATUS_INTERVAL", 5.0)),
        )
        self.local_gui = None
        self._last_runtime_payload = {}
        if getattr(config, "LOCAL_GUI_ENABLED", False):
            self.local_gui = LocalMonitorGUI(
                max_fps=getattr(config, "LOCAL_GUI_FPS", 10),
                width=getattr(config, "LOCAL_GUI_WIDTH", 960),
                test_keys_enabled=getattr(config, "LOCAL_GUI_TEST_KEYS", True),
            )

        # Hardware monitor
        self.hw_monitor = HardwareMonitor(
            camera=self.camera,
            rfid=self.rfid,
            gps=self.gps,
            ws_client=self.ws_client,
            speaker=self.speaker,
            bluetooth_manager=self.bluetooth_manager,
        )
        self.hw_status = AsyncStatusAdapter(
            self.hw_monitor,
            default_status={},
            interval_sec=float(getattr(config, "HW_REPORT_INTERVAL", 5.0)),
        )

        # Face Verifier (scaffold)
        self.verifier = FaceVerifier() if config.FEATURES["face_verify"] else None

        # Session state
        self._current_driver_uid = None
        self._last_rfid_uid = None
        self._session_active = False
        self._session_start_time = 0.0
        self._last_reverify_time = 0.0
        self._reverify_fail_count = 0
        self._last_metrics = None
        self._last_ai_result = {
            "state": AIState.UNKNOWN,
            "confidence": 0.0,
            "reason": "No samples yet",
            "alert_hint": 0,
            "thresholds": self._ai_thresholds_payload(),
            "features": {},
        }
        self._last_verify_status = None
        self._last_verify_reason = ""
        self._last_hardware_status = {}
        self._last_ota_status = None
        self._monitoring_enabled = bool(
            getattr(config, "MONITORING_AUTOSTART", False)
            or not config.FEATURES.get("websocket", False)
        )

        # Performance tracking
        self._frame_count = 0
        self._ai_fps = 0.0
        self._effective_ai_target_fps = float(config.AI_TARGET_FPS)

    def run(self):
        """Main entry point."""
        try:
            self._boot()
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Shutdown requested via Ctrl+C")
        except Exception as e:
            logger.critical(f"Fatal error: {e}", exc_info=True)
        finally:
            self._shutdown()

    # ── Boot Sequence ───────────────────────────────────────

    def _boot(self):
        logger.info("BOOT: Starting camera...")
        self.camera.start()
        # Wait for camera to be ready
        for i in range(10):
            time.sleep(0.5)
            if self.camera.is_alive:
                break
        if not self.camera.is_alive:
            logger.error("BOOT: Camera failed to start!")
        else:
            logger.info(f"BOOT: Camera alive, FPS={self.camera.fps:.1f}")

        if self.rfid:
            logger.info("BOOT: Starting RFID reader...")
            self.rfid.start()

        if self.gps:
            logger.info("BOOT: Starting GPS...")
            self.gps.start()

        if self.ws_client:
            logger.info("BOOT: Starting WebSocket...")
            self.ws_client.start()

        # Transition to IDLE
        self.state.transition(State.IDLE, "boot complete")
        self._maybe_autostart_local_gui_session()

    # ── Main Loop ───────────────────────────────────────────

    def _main_loop(self):
        logger.info("Entering main loop")
        ai_fps_counter = 0
        ai_fps_timer = time.monotonic()
        hw_report_timer = time.monotonic()
        status_report_timer = 0.0

        while not shutdown_event.is_set():
            loop_start = time.monotonic()

            if time.monotonic() - hw_report_timer >= config.HW_REPORT_INTERVAL:
                hw_status = self.hw_status.status()
                hw_status["queue_pending"] = self.local_queue.pending_count
                self._last_hardware_status = hw_status
                self.local_queue.push("hardware", hw_status)
                hw_report_timer = time.monotonic()

            # Read frame from camera
            frame, frame_id, ts = self.camera.read()
            if frame is not None:
                self.frame_buffer.update_frame(frame, frame_id, ts)
                self.snapshot_writer.maybe_write(frame)

            # Only process drowsiness in RUNNING state
            if self.state.state == State.RUNNING and frame is not None and self.face_analyzer:
                metrics = self.face_analyzer.analyze(frame)
                perclos = self.face_analyzer.perclos
                self._last_metrics = metrics
                self._update_calibration_from_metrics(metrics)
                if self.ai_classifier:
                    self._last_ai_result = self.ai_classifier.update({
                        "face_present": metrics.face_present,
                        "ear": metrics.ear,
                        "left_ear": getattr(metrics, "left_ear", metrics.ear),
                        "right_ear": getattr(metrics, "right_ear", metrics.ear),
                        "ear_used": getattr(metrics, "ear_used", metrics.ear),
                        "mar": metrics.mar,
                        "pitch": metrics.pitch,
                        "perclos": perclos,
                        "face_bbox": metrics.face_bbox,
                        "face_quality": getattr(metrics, "face_quality", {}),
                        "eye_quality": getattr(metrics, "eye_quality", {}),
                    })

                # Update good face frame for verifier
                if metrics.face_present and metrics.face_bbox:
                    self.frame_buffer.update_good_face(frame, metrics.face_bbox)

                # Feed alert manager
                self.alert_manager.update(metrics, perclos, ai_result=self._last_ai_result)

                ai_fps_counter += 1

                # Log periodic metrics
                self._frame_count += 1
                if self._frame_count % (config.AI_TARGET_FPS * 10) == 0:
                    elapsed = time.monotonic() - ai_fps_timer
                    self._ai_fps = ai_fps_counter / elapsed if elapsed > 0 else 0
                    ai_fps_counter = 0
                    ai_fps_timer = time.monotonic()
                    logger.info(
                        f"Metrics: AI_FPS={self._ai_fps:.1f} "
                        f"CAM_FPS={self.camera.fps:.1f} "
                        f"EAR={metrics.ear:.3f} MAR={metrics.mar:.3f} "
                        f"Pitch={metrics.pitch:.1f} PERCLOS={perclos:.2f} "
                        f"Alert={self.alert_manager.current_level_name} "
                        f"Queue={self.local_queue.pending_count}"
                    )

            self._maybe_reverify()
            
            if self.gps and getattr(config, "GPS_SEND_INTERVAL", 0) > 0:
                if not hasattr(self, "_gps_report_timer"):
                    self._gps_report_timer = time.monotonic()
                if time.monotonic() - self._gps_report_timer >= config.GPS_SEND_INTERVAL:
                    self._gps_report_timer = time.monotonic()
                    latest = getattr(self.gps, "latest", None)
                    if latest and getattr(latest, "fix_ok", False):
                        self.local_queue.push("gps", {
                            "lat": latest.lat,
                            "lng": latest.lng,
                            "speed": latest.speed,
                            "heading": latest.heading,
                            "fix_ok": latest.fix_ok,
                            "timestamp": latest.timestamp,
                        })

            if time.monotonic() - status_report_timer >= 1.0:
                self._publish_runtime_status()
                status_report_timer = time.monotonic()

            self._update_local_gui(frame)

            # Pace to target FPS
            frame_interval = 1.0 / max(1.0, float(self._effective_ai_target_fps or config.AI_TARGET_FPS))
            elapsed = time.monotonic() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ── Callbacks ───────────────────────────────────────────

    def _on_rfid_scan(self, uid: str):
        """Handle RFID card scan. Module responsibility stays clean."""
        logger.info(f"💳 [RFID IN] Scanning UID={uid}, current_state={self.state.state}")

        self._last_rfid_uid = uid

        if not self._monitoring_enabled:
            logger.info("RFID scan ignored because monitoring is not connected from WebQuanLi")
            return

        if self.state.state == State.IDLE:
            self._set_verify_status("VERIFYING", "RFID scanned; awaiting face verification")
            self._emit_driver_probe(uid)
            self.state.transition(State.VERIFYING_DRIVER, f"RFID scan UID={uid}")
            self._verify_driver(uid)
        elif self.state.state == State.RUNNING:
            # End session
            logger.info(f"💳 [RFID IN] Scan during RUNNING — ending session for UID={uid}")
            self._end_session()

    def _verify_driver(self, uid: str):
        """Verify driver face after RFID scan."""
        if not self.verifier:
            if getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False):
                logger.warning("Face verifier not available — DEMO MODE: entering RUNNING without verification")
                self.local_queue.push("verify_error", {"rfid_tag": uid, "reason": "MISSING_VERIFIER", "timestamp": time.time()})
                self._start_demo_session(uid, "Demo mode: face verifier is not available, session allowed")
            else:
                logger.warning("Face verifier not available and DEMO_MODE_ALLOW_UNVERIFIED is False. Rejecting session.")
                self._reject_verification(uid, "MISSING_VERIFIER", "fail-safe: verify missing")
            return

        if self._verifier_has_enrollment(uid) is False:
            logger.info(f"UID={uid} has no local enrollment")
            if getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False):
                self.local_queue.push("verify_error", {"rfid_tag": uid, "reason": "NO_ENROLLMENT", "timestamp": time.time()})
                self._start_demo_session(uid, "Demo mode: no enrollment available for this RFID")
            else:
                self._reject_verification(uid, "NO_ENROLLMENT", "fail-safe: no enrollment")
            return

        face_frame, bbox = self._acquire_face_crop()
        if self._is_empty_frame(face_frame):
            logger.warning(f"No usable face crop captured for UID={uid}")
            if getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False):
                self.local_queue.push("verify_error", {"rfid_tag": uid, "reason": "NO_FACE_FRAME", "timestamp": time.time()})
                self._start_demo_session(uid, "Demo mode: face frame not available, session allowed")
            else:
                self._reject_verification(uid, "NO_FACE_FRAME", "fail-safe: no face frame")
            return

        result = self.verifier.verify(face_frame, uid)

        if result == VerifyResult.MATCH:
            self._start_verified_session(uid)
        elif result == VerifyResult.MISMATCH:
            self._set_verify_status("MISMATCH", "Face does not match registered driver")
            logger.warning(f"❌ [VERIFY FAIL] Face mismatch UID={uid}!")
            self.state.transition(State.MISMATCH_ALERT, f"face mismatch UID={uid}")
            self.local_queue.push("verify_snapshot", {
                "rfid_tag": uid,
                "status": "MISMATCH",
                "message": "Face does not match registered driver",
                "timestamp": time.time(),
            })
            self.local_queue.push("face_mismatch", {"rfid_tag": uid, "expected": "unknown", "timestamp": time.time()})
            time.sleep(3.0)
            self.state.transition(State.IDLE, "mismatch cleared")
        elif result in (VerifyResult.BLOCKED, VerifyResult.LOW_CONFIDENCE):
            reason = "NO_ENROLLMENT" if result == VerifyResult.BLOCKED else "LOW_CONFIDENCE"
            if getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False):
                self.local_queue.push("verify_error", {"rfid_tag": uid, "reason": reason, "timestamp": time.time()})
                logger.info(f"Verify returned {result} — DEMO MODE: allowing session")
                self._start_demo_session(uid, f"Demo mode: verification returned {result}, session allowed")
            else:
                logger.warning(f"Verify returned {result} — DEMO_MODE_ALLOW_UNVERIFIED is False. Rejecting session.")
                self._reject_verification(uid, reason, f"fail-safe: {result}")
        else:
            self._set_verify_status("UNKNOWN_ERROR", f"verify inconclusive: {result}")
            logger.warning(f"Verify returned {result} — staying in IDLE")
            self._reject_verification(uid, "UNKNOWN_ERROR", f"verify inconclusive: {result}")

    def _emit_driver_probe(self, uid: str):
        self.local_queue.push("driver", {
            "name": "",
            "rfid": uid,
        })

    def _reset_ai_session_state(self):
        self.calibrator = DriverCalibrator()
        self._calibration_profile = CalibrationProfile.fallback(reason="COLLECTING")
        self._calibration_applied = False
        if self.ai_classifier and hasattr(self.ai_classifier, "reset_state"):
            self.ai_classifier.reset_state()
        if self.ai_classifier and hasattr(self.ai_classifier, "set_profile"):
            self.ai_classifier.set_profile(self._calibration_profile)
        if self.alert_manager and hasattr(self.alert_manager, "reset"):
            self.alert_manager.reset()
        self._last_ai_result = {
            "state": AIState.UNKNOWN,
            "confidence": 0.0,
            "reason": "Calibration collecting",
            "alert_hint": 0,
            "thresholds": self._ai_thresholds_payload(),
            "features": {},
        }

    def _update_calibration_from_metrics(self, metrics):
        if not self.calibrator:
            return
        now = time.time()
        if self._calibration_applied:
            return
        if metrics is not None:
            self.calibrator.add(metrics, now)
        profile = self.calibrator.profile
        if profile.valid or self.calibrator.complete(now):
            self._calibration_profile = profile
            self._calibration_applied = True
            if self.ai_classifier and hasattr(self.ai_classifier, "set_profile"):
                self.ai_classifier.set_profile(profile)
            if self.alert_manager and profile.valid and hasattr(self.alert_manager, "set_calibrated_thresholds"):
                self.alert_manager.set_calibrated_thresholds(
                    profile.ear_open_median,
                    profile.pitch_neutral,
                    profile=profile,
                )
            logger.info(
                "Calibration applied: valid=%s reason=%s samples=%s EAR=%.3f MAR=%.3f pitch_down=%.1f",
                profile.valid,
                profile.reason,
                profile.sample_count,
                profile.ear_closed_threshold,
                profile.mar_yawn_threshold,
                profile.pitch_down_threshold,
            )

    def _ai_thresholds_payload(self):
        profile = self._calibration_profile or CalibrationProfile.fallback(reason="FALLBACK")
        return ThresholdPolicy.from_profile(profile).to_dict()

    def _calibration_payload(self):
        if self.calibrator and not self._calibration_applied:
            profile = self.calibrator.profile
            active = bool(self._session_active)
            payload = profile.to_dict(active=active)
            if active and payload["reason"] == "NOT_ENOUGH_SAMPLES":
                payload["reason"] = "COLLECTING"
            return payload
        profile = self._calibration_profile or CalibrationProfile.fallback(reason="NOT_STARTED")
        return profile.to_dict(active=False)

    def _camera_runtime_payload(self, include_snapshot=False):
        frame_age = self._camera_frame_age()
        stale_after = float(getattr(config, "CAMERA_STALE_SECONDS", 2.0) or 2.0)
        payload = {
            "online": bool(getattr(self.camera, "is_alive", False)),
            "fps": round(float(getattr(self.camera, "fps", 0.0) or 0.0), 2),
            "frame_id": int(getattr(self.camera, "frame_id", 0) or 0),
            "frame_age_sec": round(frame_age, 2) if frame_age is not None else None,
            "stale": bool(frame_age is None or frame_age > stale_after),
        }
        if include_snapshot:
            payload["snapshot"] = "latest.jpg"
            payload["snapshot_interval"] = round(float(self.snapshot_writer.min_interval), 2)
        return payload

    def _camera_frame_age(self):
        age = getattr(self.frame_buffer, "frame_age", None)
        try:
            age = float(age)
        except (TypeError, ValueError):
            return None
        if age == float("inf") or age < 0:
            return None
        return age

    def _ai_runtime_reason(self, frame=None):
        if not config.FEATURES.get("drowsiness", True) or not self.face_analyzer:
            return "DROWSINESS_DISABLED"
        if self.state.state != State.RUNNING:
            if not self._monitoring_enabled:
                return "MONITOR_OFF"
            if self.state.state == State.IDLE:
                return "IDLE"
            return "WAITING_SESSION"
        if frame is None:
            if bool(getattr(self.frame_buffer, "has_recent_frame", False)):
                return "RUNNING"
            return "NO_CAMERA_FRAME"
        return "RUNNING"

    def _landmarks_payload(self, metrics=None, frame=None):
        metrics = metrics or self._last_metrics
        if metrics is None:
            return {}
        source_size = None
        shape = getattr(frame, "shape", None)
        if shape and len(shape) >= 2:
            height, width = shape[:2]
            source_size = (int(width), int(height))
        return {
            "left_eye_points": list(getattr(metrics, "left_eye_points", []) or []),
            "right_eye_points": list(getattr(metrics, "right_eye_points", []) or []),
            "mouth_points": list(getattr(metrics, "mouth_points", []) or []),
            "face_bbox": getattr(metrics, "face_bbox", None),
            "source_size": source_size,
        }

    def _start_verified_session(self, uid: str):
        self._reset_ai_session_state()
        self._current_driver_uid = uid
        self._session_active = True
        self._last_reverify_time = time.monotonic()
        self._reverify_fail_count = 0
        self._set_verify_status("VERIFIED", "Face verification matched registered driver")
        logger.info(f"🟢 [SESSION START] Driver verified! UID={uid}")
        self.state.transition(State.RUNNING, f"driver verified UID={uid}")
        self._session_start_time = time.time()
        self.local_queue.push("verify_snapshot", {
            "rfid_tag": uid,
            "status": "VERIFIED",
            "message": "Face verification matched registered driver",
            "timestamp": time.time(),
        })
        self.local_queue.push("session_start", {"rfid_tag": uid, "timestamp": self._session_start_time})

    def _start_demo_session(self, uid: str, message: str):
        if self.state.state == State.IDLE:
            if not self.state.transition(State.VERIFYING_DRIVER, f"local demo requested UID={uid}"):
                return False
        elif self.state.state != State.VERIFYING_DRIVER:
            logger.warning(f"Demo session blocked from state {self.state.state}")
            return False

        self._reset_ai_session_state()
        logger.info(f"🟢 [SESSION START] UID={uid} (Demo mode)")
        if not self.state.transition(State.RUNNING, f"demo session started UID={uid}"):
            return False

        self._current_driver_uid = uid
        self._session_active = True
        self._last_reverify_time = time.monotonic()
        self._reverify_fail_count = 0
        self._set_verify_status("DEMO_VERIFIED", message)
        self._session_start_time = time.time()
        self.local_queue.push("verify_snapshot", {
            "rfid_tag": uid,
            "status": "DEMO_VERIFIED",
            "message": message,
            "timestamp": time.time(),
        })
        self.local_queue.push("session_start", {"rfid_tag": uid, "timestamp": self._session_start_time})
        return True

    def _reject_verification(self, uid: str, reason: str, state_reason: str):
        self._set_verify_status(reason, state_reason)
        self.local_queue.push("verify_error", {"rfid_tag": uid, "reason": reason, "timestamp": time.time()})
        time.sleep(2.0)
        self.state.transition(State.IDLE, state_reason)

    def _verifier_has_enrollment(self, uid: str):
        has_enrollment = getattr(self.verifier, "has_enrollment", None)
        if callable(has_enrollment):
            try:
                return has_enrollment(uid)
            except TypeError:
                return None
        return None

    def _acquire_face_crop(self):
        face_frame, bbox, _ = self.frame_buffer.get_good_face_frame()
        if not self._is_empty_frame(face_frame):
            crop = self.verifier.extract_face(face_frame, bbox)
            if not self._is_empty_frame(crop):
                return crop, bbox

        if not config.FEATURES.get("camera", True) or not self.face_analyzer:
            return None, None

        deadline = time.monotonic() + getattr(config, "FACE_VERIFY_ACQUIRE_TIMEOUT_SEC", 1.5)
        poll_interval = getattr(config, "FACE_VERIFY_ACQUIRE_POLL_SEC", 0.15)

        while time.monotonic() < deadline:
            frame, _, _ = self._read_latest_frame()
            if frame is None:
                time.sleep(poll_interval)
                continue

            try:
                metrics = self.face_analyzer.analyze(frame)
            except Exception as exc:
                logger.warning(f"Face acquisition failed during verification: {exc}")
                break

            if metrics.face_present and metrics.face_bbox:
                self.frame_buffer.update_good_face(frame, metrics.face_bbox)
                crop = self.verifier.extract_face(frame, metrics.face_bbox)
                if not self._is_empty_frame(crop):
                    return crop, metrics.face_bbox

            time.sleep(poll_interval)

        return None, None

    def _maybe_reverify(self, now=None):
        if self.state.state != State.RUNNING or not self._session_active:
            return
        now = now if now is not None else time.monotonic()
        interval = config.REVERIFY_FAST_INTERVAL if self._reverify_fail_count else config.REVERIFY_INTERVAL
        if now - self._last_reverify_time < interval:
            return
        self._last_reverify_time = now
        self._run_reverification_once()

    def _run_reverification_once(self) -> bool:
        if self.state.state != State.RUNNING or not self._current_driver_uid:
            return True

        ok, reason = self._verify_active_driver_once()
        if ok:
            self._reverify_fail_count = 0
            self._set_verify_status("VERIFIED", "Periodic reverification matched active driver")
            self.local_queue.push("verify_snapshot", {
                "rfid_tag": self._current_driver_uid,
                "status": "VERIFIED",
                "message": "Periodic reverification matched active driver",
                "timestamp": time.time(),
            })
            return True

        self._reverify_fail_count += 1
        self._set_verify_status(reason, f"Periodic reverification failed: {reason}")
        self.local_queue.push("verify_error", {
            "rfid_tag": self._current_driver_uid,
            "reason": reason,
            "timestamp": time.time(),
        })
        logger.warning(
            f"Reverification failed UID={self._current_driver_uid} "
            f"reason={reason} count={self._reverify_fail_count}"
        )

        if self._reverify_fail_count >= config.REVERIFY_MAX_CONSECUTIVE_FAILS:
            uid = self._current_driver_uid
            self.state.transition(State.MISMATCH_ALERT, f"reverify failed UID={uid}")
            self.local_queue.push("face_mismatch", {
                "rfid_tag": uid,
                "expected": uid,
                "timestamp": time.time(),
            })
            self._end_session()
        return False

    def _verify_active_driver_once(self):
        uid = self._current_driver_uid
        if not self.verifier:
            return False, "MISSING_VERIFIER"
        if self._verifier_has_enrollment(uid) is False:
            return False, "NO_ENROLLMENT"

        face_frame, _ = self._acquire_face_crop()
        if self._is_empty_frame(face_frame):
            return False, "NO_FACE_FRAME"

        result = self.verifier.verify(face_frame, uid)
        if result == VerifyResult.MATCH:
            return True, "MATCH"
        if result == VerifyResult.MISMATCH:
            return False, "MISMATCH"
        if result == VerifyResult.LOW_CONFIDENCE:
            return False, "LOW_CONFIDENCE"
        if result == VerifyResult.BLOCKED:
            return False, "NO_ENROLLMENT"
        return False, "UNKNOWN_ERROR"

    def _read_latest_frame(self):
        if not hasattr(self.frame_buffer, "get_frame"):
            return None, 0, 0.0
        try:
            payload = self.frame_buffer.get_frame()
        except Exception:
            return None, 0, 0.0
        if isinstance(payload, tuple) and len(payload) == 3:
            return payload
        return None, 0, 0.0

    @staticmethod
    def _is_empty_frame(frame) -> bool:
        if frame is None:
            return True
        size = getattr(frame, "size", None)
        if isinstance(size, (int, float)) and size == 0:
            return True
        try:
            return len(frame) == 0
        except Exception:
            return False

    def _end_session(self):
        """End current driving session."""
        uid = self._current_driver_uid
        self._current_driver_uid = None
        self._session_active = False
        self.alert_manager.reset()
        self.state.transition(State.IDLE, "session ended")
        self.local_queue.push("session_end", {"rfid_tag": uid or "unknown", "timestamp": time.time()})
        logger.info(f"⬛ [SESSION END] Session ended for UID={uid}")

    def _set_verify_status(self, status: str, reason: str = ""):
        self._last_verify_status = status
        self._last_verify_reason = reason or ""

    def _build_performance_profile(self, cpu_temp_c=None):
        target_fps = float(config.AI_TARGET_FPS)
        snapshot_interval = float(getattr(config, "DASHBOARD_SNAPSHOT_INTERVAL", 0.75))

        if self._ai_fps and self._ai_fps < getattr(config, "AI_MIN_STABLE_FPS", 7.0):
            snapshot_interval = max(snapshot_interval, float(getattr(config, "DASHBOARD_SNAPSHOT_SLOW_INTERVAL", 1.5)))

        if cpu_temp_c is not None and cpu_temp_c >= config.AI_THERMAL_CRITICAL_C:
            target_fps = min(target_fps, float(getattr(config, "AI_THROTTLED_TARGET_FPS", 8.0)))
            snapshot_interval = max(snapshot_interval, float(getattr(config, "DASHBOARD_SNAPSHOT_SLOW_INTERVAL", 1.5)))
            
        if self.ws_client and not getattr(self.ws_client, "is_connected", False):
            snapshot_interval = max(snapshot_interval, float(getattr(config, "DASHBOARD_SNAPSHOT_SLOW_INTERVAL", 1.5)))

        return {
            "target_fps": target_fps,
            "snapshot_interval": snapshot_interval,
            "thermal_warning": bool(cpu_temp_c is not None and cpu_temp_c >= config.AI_THERMAL_WARN_C),
        }

    def _apply_performance_profile(self, cpu_temp_c=None):
        profile = self._build_performance_profile(cpu_temp_c=cpu_temp_c)
        self._effective_ai_target_fps = profile["target_fps"]
        self.snapshot_writer.min_interval = profile["snapshot_interval"]
        return profile

    def _on_alert(self, event):
        """Handle alert level change from AlertManager."""
        logger.info(f"🔔 [ALERT CHANGE] level={AlertLevel.NAMES[event.level]} "
                     f"EAR={event.ear:.3f} MAR={event.mar:.3f} Pitch={event.pitch:.1f}")
        payload = {
            "level": AlertLevel.NAMES[event.level],
            "ear": round(event.ear, 3) if event.ear is not None else None,
            "mar": round(event.mar, 3) if event.mar is not None else None,
            "pitch": round(event.pitch, 1) if event.pitch is not None else None,
            "perclos": round(event.perclos, 3) if event.perclos is not None else None,
            "ai_state": getattr(event, "ai_state", AIState.UNKNOWN),
            "ai_confidence": getattr(event, "ai_confidence", getattr(event, "confidence", 0.0)),
            "ai_reason": getattr(event, "ai_reason", getattr(event, "reason", "")),
        }
        
        if self.gps and getattr(self.gps, "latest", None) and getattr(self.gps.latest, "fix_ok", False):
            latest = self.gps.latest
            payload.update({
                "lat": latest.lat,
                "lng": latest.lng,
                "speed": latest.speed,
                "gps_fix_ok": latest.fix_ok
            })

        payload["timestamp"] = time.time()
        self.local_queue.push("alert", payload)

    def _publish_runtime_status(self):
        metrics = self._last_metrics
        ai_result = self._last_ai_result or {}
        system_status = read_system_status()
        network_status = self.network_status.status()
        performance = self._apply_performance_profile(system_status.get("cpu_temp_c"))
        bluetooth_status = self.bluetooth_manager.status()
        if self.speaker and hasattr(self.speaker, "status"):
            speaker_status = self.speaker.status()
        else:
            speaker_status = {
                "enabled": False,
                "available": False,
                "backend": getattr(config, "AUDIO_BACKEND", "auto"),
            }

        hardware = dict(self._last_hardware_status or {})
        hardware["thermal_warning"] = performance["thermal_warning"]
        hardware["bluetooth"] = bool(bluetooth_status.get("connected"))
        hardware["bluetooth_adapter"] = bool(bluetooth_status.get("adapter"))
        hardware["bluetooth_adapter_ok"] = bool(bluetooth_status.get("adapter"))
        hardware["bluetooth_speaker_connected"] = bool(bluetooth_status.get("connected"))
        hardware["speaker_output_ok"] = bool(speaker_status.get("available")) and bool(
            getattr(self.alert_manager, "speaker_output_ok", True)
        )
        hardware["websocket_ok"] = bool(self.ws_client.is_connected) if self.ws_client else False
        hardware["wifi"] = bool(network_status.get("wlan0_ip") or network_status.get("ssid"))

        payload = {
            "device": {
                "device_id": config.DEVICE_ID,
                "hostname": system_status.get("hostname", ""),
                "version": getattr(config, "APP_VERSION", "Version3"),
                "strict_mode": not getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False),
                "features": dict(config.FEATURES),
            },
            "system": {
                "hostname": system_status.get("hostname", ""),
                "uptime_seconds": system_status.get("uptime_seconds", 0),
                "cpu_temp_c": system_status.get("cpu_temp_c"),
                "ram_percent": system_status.get("ram_percent"),
                "thermal_warning": performance["thermal_warning"],
            },
            "network": network_status,
            "bluetooth": bluetooth_status,
            "audio": speaker_status,
            "camera": self._camera_runtime_payload(include_snapshot=True),
            "ai": {
                "state": ai_result.get("state", AIState.UNKNOWN),
                "confidence": ai_result.get("confidence", 0.0),
                "reason": ai_result.get("reason", ""),
                "alert_hint": ai_result.get("alert_hint", 0),
                "thresholds": ai_result.get("thresholds", self._ai_thresholds_payload()),
                "features": ai_result.get("features", {}),
                "durations": ai_result.get("durations", {}),
                "fps": round(float(self._ai_fps or 0.0), 2),
                "target_fps": round(float(self._effective_ai_target_fps or config.AI_TARGET_FPS), 2),
                "ear": round(float(getattr(metrics, "ear", 0.0) or 0.0), 3),
                "left_ear": round(float(getattr(metrics, "left_ear", getattr(metrics, "ear", 0.0)) or 0.0), 3),
                "right_ear": round(float(getattr(metrics, "right_ear", getattr(metrics, "ear", 0.0)) or 0.0), 3),
                "ear_used": round(float(getattr(metrics, "ear_used", getattr(metrics, "ear", 0.0)) or 0.0), 3),
                "mar": round(float(getattr(metrics, "mar", 0.0) or 0.0), 3),
                "pitch": round(float(getattr(metrics, "pitch", 0.0) or 0.0), 1),
                "perclos": round(float(self.face_analyzer.perclos if self.face_analyzer else 0.0), 3),
                "face_present": bool(getattr(metrics, "face_present", False)),
                "face_quality": getattr(metrics, "face_quality", {}),
                "eye_quality": getattr(metrics, "eye_quality", {}),
                "runtime_reason": self._ai_runtime_reason(),
            },
            "calibration": self._calibration_payload(),
            "driver": {
                "rfid_tag": self._current_driver_uid,
                "name": None,
                "verify_status": self._last_verify_status,
                "verify_reason": self._last_verify_reason,
            },
            "session": {
                "state": self.state.state,
                "active": bool(self._session_active),
                "monitoring_enabled": bool(self._monitoring_enabled),
                "reverify_fail_count": self._reverify_fail_count,
            },
            "alert": {
                "level": self.alert_manager.current_level_name,
            },
            "websocket": {
                "connected": bool(self.ws_client.is_connected) if self.ws_client else False,
                "url": config.WS_SERVER_URL,
            },
            "queue": {
                "pending": self.local_queue.pending_count,
            },
            "gps": self._latest_gps_payload(),
            "hardware": hardware,
            "ota": self._last_ota_status,
        }
        self._last_runtime_payload = payload
        try:
            self.runtime_store.write(payload)
        except Exception as exc:
            logger.warning(f"Runtime status write failed: {exc}")

    def _build_local_monitor_payload(self, frame=None):
        payload = dict(self._last_runtime_payload or {})

        payload["camera"] = self._camera_runtime_payload(include_snapshot=True)

        metrics = self._last_metrics
        ai_result = self._last_ai_result or {}
        ai = dict(payload.get("ai") or {})
        ai.update({
            "state": ai_result.get("state", AIState.UNKNOWN),
            "confidence": ai_result.get("confidence", 0.0),
            "reason": ai_result.get("reason", ""),
            "alert_hint": ai_result.get("alert_hint", 0),
            "thresholds": ai_result.get("thresholds", self._ai_thresholds_payload()),
            "features": ai_result.get("features", {}),
            "durations": ai_result.get("durations", {}),
            "fps": round(float(self._ai_fps or 0.0), 2),
            "target_fps": round(float(self._effective_ai_target_fps or config.AI_TARGET_FPS), 2),
            "ear": round(float(getattr(metrics, "ear", 0.0) or 0.0), 3),
            "left_ear": round(float(getattr(metrics, "left_ear", getattr(metrics, "ear", 0.0)) or 0.0), 3),
            "right_ear": round(float(getattr(metrics, "right_ear", getattr(metrics, "ear", 0.0)) or 0.0), 3),
            "ear_used": round(float(getattr(metrics, "ear_used", getattr(metrics, "ear", 0.0)) or 0.0), 3),
            "mar": round(float(getattr(metrics, "mar", 0.0) or 0.0), 3),
            "pitch": round(float(getattr(metrics, "pitch", 0.0) or 0.0), 1),
            "perclos": round(float(self.face_analyzer.perclos if self.face_analyzer else 0.0), 3),
            "face_present": bool(getattr(metrics, "face_present", False)),
            "face_quality": getattr(metrics, "face_quality", {}),
            "eye_quality": getattr(metrics, "eye_quality", {}),
            "landmarks": self._landmarks_payload(metrics, frame=frame),
            "runtime_reason": self._ai_runtime_reason(frame=frame),
        })
        payload["ai"] = ai
        payload["calibration"] = self._calibration_payload()

        session = dict(payload.get("session") or {})
        session.update({
            "state": self.state.state,
            "active": bool(self._session_active),
            "monitoring_enabled": bool(self._monitoring_enabled),
        })
        payload["session"] = session

        driver = dict(payload.get("driver") or {})
        driver["rfid_tag"] = self._current_driver_uid or self._last_rfid_uid
        payload["driver"] = driver

        alert = dict(payload.get("alert") or {})
        alert["level"] = self.alert_manager.current_level_name
        payload["alert"] = alert

        hardware = dict(payload.get("hardware") or {})
        hardware.update(self._last_hardware_status or {})
        if self._last_rfid_uid:
            hardware["rfid_last_uid"] = self._last_rfid_uid
        payload["hardware"] = hardware

        websocket = dict(payload.get("websocket") or {})
        websocket["connected"] = bool(self.ws_client.is_connected) if self.ws_client else False
        payload["websocket"] = websocket

        payload["gps"] = self._latest_gps_payload()

        queue = dict(payload.get("queue") or {})
        queue["pending"] = self.local_queue.pending_count
        payload["queue"] = queue
        return payload

    def _latest_gps_payload(self):
        latest = getattr(self.gps, "latest", None) if self.gps else None
        if not latest:
            return {"fix_ok": False}
        return {
            "lat": getattr(latest, "lat", None),
            "lng": getattr(latest, "lng", None),
            "speed": getattr(latest, "speed", None),
            "heading": getattr(latest, "heading", None),
            "fix_ok": bool(getattr(latest, "fix_ok", False)),
            "timestamp": getattr(latest, "timestamp", None),
        }

    def _update_local_gui(self, frame):
        if not self.local_gui:
            return
        payload = self._build_local_monitor_payload(frame=frame)
        state = LocalMonitorState.from_runtime_payload(payload)
        actions = self.local_gui.update(frame, state)
        self._handle_local_gui_actions(actions)

    def _handle_local_gui_actions(self, actions):
        for action in actions or []:
            if action == "quit":
                logger.info("[LOCAL GUI] Quit requested")
                shutdown_event.set()
            elif action == "reset_alert":
                logger.info("[LOCAL GUI] Reset alert requested")
                self.alert_manager.reset()
            elif action.startswith("test_alert_"):
                try:
                    level = int(action.rsplit("_", 1)[1])
                except (TypeError, ValueError):
                    continue
                logger.info(f"[LOCAL GUI] Test alert level {level}")
                self.alert_manager._activate_outputs(level)
            elif action == "start_demo_session":
                if not getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False):
                    logger.warning("[LOCAL GUI] Demo session blocked because DROWSIGUARD_DEMO_MODE is false")
                    continue
                if self._session_active:
                    logger.info("[LOCAL GUI] Demo session ignored because a session is already active")
                    continue
                if self.state.state != State.IDLE:
                    logger.warning(f"[LOCAL GUI] Demo session blocked from state {self.state.state}")
                    continue
                self._monitoring_enabled = True
                self._start_demo_session("LOCAL-GUI-DEMO", "Local GUI demo session")

    def _maybe_autostart_local_gui_session(self):
        if not getattr(config, "LOCAL_GUI_ENABLED", False):
            return False
        if not getattr(config, "LOCAL_GUI_AUTOSTART_SESSION", False):
            return False
        if not getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False):
            logger.warning("[LOCAL GUI] Autostart ignored because DROWSIGUARD_DEMO_MODE is false")
            return False
        if self._session_active:
            return False
        if self.state.state != State.IDLE:
            return False
        self._monitoring_enabled = True
        return bool(self._start_demo_session("LOCAL-GUI-DEMO", "Local GUI auto demo session"))

    def _on_state_change(self, old_state, new_state, reason):
        """Log state transitions."""
        logger.info(f"🔄 [STATE] {old_state} -> {new_state} ({reason})")

    def _on_backend_command(self, command: dict):
        """Handle commands from backend via WebSocket."""
        action = command.get("action")
        logger.info(f"📥 [COMMAND] Backend command received: {action}")
        
        if action == "test_alert":
            level = command.get("level", 1)
            state = command.get("state", "on")
            
            if state == "on":
                logger.info(f"🚨 [COMMAND] TEST ALERT ON: Level {level} 🚨")
                logger.info(f"🔊 BEEP BEEP BEEP (Testing Level {level}) 🔊")
                self.alert_manager._activate_outputs(level)
            else:
                logger.info("⏹️ [COMMAND] TEST ALERT OFF ⏹️")
                self.alert_manager._activate_outputs(0)
                
        elif action == "connect_monitoring":
            self._monitoring_enabled = True
            logger.info("[COMMAND] Monitoring enabled from WebQuanLi")

        elif action == "disconnect_monitoring":
            self._monitoring_enabled = False
            logger.info("[COMMAND] Monitoring disabled from WebQuanLi")
            self.alert_manager._activate_outputs(0)
            if self._session_active:
                self._end_session()

        elif action == "update_software":
            download_url = command.get("download_url")
            filename = command.get("filename")
            checksum = command.get("checksum")
            logger.warning(f"[COMMAND] OTA Update requested: file={filename}, url={download_url}")
            if self.state.state == State.RUNNING:
                self._on_ota_status({
                    "status": "FAILED",
                    "filename": filename,
                    "progress": 0,
                    "error": "OTA blocked while session is RUNNING",
                })
                return
            if not self.ota_handler:
                self._on_ota_status({
                    "status": "FAILED",
                    "filename": filename,
                    "progress": 0,
                    "error": "OTA handler unavailable",
                })
                return

            def _apply_ota():
                self.ota_handler.handle_update_command({
                    "download_url": download_url,
                    "filename": filename,
                    "checksum": checksum,
                })

            threading.Thread(target=_apply_ota, daemon=True, name="OTAApply").start()
            return
        elif action == "sync_driver_registry":
            manifest_url = command.get("manifest_url")
            if not self.verifier:
                logger.warning("Driver registry sync requested but verifier is unavailable")
                return
            if not manifest_url:
                logger.warning("Driver registry sync requested without manifest_url")
                return

            def _sync_registry():
                try:
                    self.verifier.sync_from_manifest_url(manifest_url)
                    logger.info("Driver registry sync completed")
                except Exception as exc:
                    logger.error(f"Driver registry sync failed: {exc}", exc_info=True)

            threading.Thread(target=_sync_registry, daemon=True, name="DriverRegistrySync").start()

    def _on_ota_status(self, status: dict):
        self._last_ota_status = dict(status or {})
        self.local_queue.push("ota_status", {
            "status": status.get("status"),
            "filename": status.get("filename"),
            "progress": status.get("progress", 0),
            "error": status.get("error"),
        })

    def _on_ws_connect(self):
        """Triggered when WS reconnects. Resync session if active."""
        if self._session_active and self._current_driver_uid:
            logger.info("Resyncing active session to WebQuanLi...")
            self.local_queue.push("session_start", {
                "rfid_tag": self._current_driver_uid,
                "timestamp": self._session_start_time
            })
            if self._last_verify_status in ("VERIFIED", "DEMO_VERIFIED"):
                self.local_queue.push("verify_snapshot", {
                    "rfid_tag": self._current_driver_uid,
                    "status": self._last_verify_status,
                    "message": self._last_verify_reason,
                    "timestamp": time.time(),
                })

    # ── Shutdown ────────────────────────────────────────────

    def _shutdown(self):
        logger.info("Shutting down DrowsiGuard...")
        shutdown_event.set()

        if self._session_active:
            self._end_session()

        self.camera.stop()
        if self.face_analyzer:
            self.face_analyzer.release()

        if self.rfid:
            self.rfid.stop()
        if self.gps:
            self.gps.stop()
        if self.ws_client:
            self.ws_client.stop()
        if self.buzzer:
            self.buzzer.cleanup()
        if self.led:
            self.led.cleanup()
        if self.speaker:
            self.speaker.cleanup()
        if self.local_gui:
            self.local_gui.close()

        logger.info("DrowsiGuard stopped")


def _signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, shutting down...")
    shutdown_event.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    app = DrowsiGuard()
    app.run()
