#!/usr/bin/env python3
"""
Standalone readiness checker for the current camera-only stage and later
full-hardware smoke checks on Jetson Nano.

Usage:
  python3 scripts/test_demo_readiness.py --mode simulate
  python3 scripts/test_demo_readiness.py --mode identity-sim
  python3 scripts/test_demo_readiness.py --mode hardware
"""
import argparse
import glob
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _install_host_safe_mocks():
    for module_name in ("cv2", "numpy", "evdev", "smbus2", "mediapipe"):
        sys.modules.setdefault(module_name, MagicMock())


def run_simulation():
    """Exercise the reconnect + alert + session flow without real hardware."""
    _install_host_safe_mocks()

    import config
    from main import DrowsiGuard
    from state_machine import State

    original_features = dict(config.FEATURES)
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
        with patch("main.LocalQueue") as local_queue_class:
            app = DrowsiGuard()
            app.local_queue = local_queue_class.return_value
            app.state.transition(State.IDLE, "simulation bootstrap")
            app.state.transition(State.VERIFYING_DRIVER, "simulation verify phase")

            print("[SIM] Starting verified session replay smoke...")
            app._start_verified_session("SIM-UID-001")
            app.local_queue.push.reset_mock()

            app._on_ws_connect()
            app._on_alert(SimpleNamespace(
                level=2,
                ear=0.18,
                mar=0.63,
                pitch=-8.0,
                perclos=0.42,
                ai_state="DROWSY",
                ai_confidence=0.91,
                ai_reason="simulation smoke",
            ))
            app._end_session()

            queued = _queued_events(app)

            print("[SIM] Queued events:")
            for item in queued:
                print("  - {type}: {data}".format(**item))

            expected_types = [item["type"] for item in queued]
            required = {"session_start", "verify_snapshot", "alert", "session_end"}
            missing = sorted(required.difference(expected_types))
            if missing:
                print("[SIM] FAIL: missing events -> {0}".format(", ".join(missing)))
                return 1

            print("[SIM] PASS: reconnect/session/alert flow is ready for demo simulation.")
            return 0
    finally:
        config.FEATURES = original_features
        config.DEMO_MODE_ALLOW_UNVERIFIED = original_demo_mode


def _queued_events(app):
    events = []
    for mock_call in app.local_queue.push.call_args_list:
        args = mock_call[0]
        if len(args) >= 2:
            events.append({"type": args[0], "data": args[1]})
        else:
            events.append({"type": "unrecognized", "data": {"args": tuple(args)}})
    return events


def _has_event(events, event_type, key=None, value=None):
    for event in events:
        if event["type"] != event_type:
            continue
        if key is None:
            return True
        data = event["data"] if isinstance(event["data"], dict) else {}
        if data.get(key) == value:
            return True
    return False


def _new_identity_app(config, DrowsiGuard, State, local_queue_class):
    app = DrowsiGuard()
    app.local_queue = local_queue_class.return_value
    app.state.transition(State.IDLE, "identity simulation bootstrap")
    app.local_queue.push.reset_mock()
    return app


def _configure_identity_verifier(app, VerifyResult, result, frame_available=True):
    verifier = MagicMock()
    verifier.has_enrollment.return_value = True
    verifier.extract_face.side_effect = lambda frame, bbox: frame
    verifier.verify.return_value = result
    app.verifier = verifier
    app.frame_buffer = MagicMock()
    if frame_available:
        app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)
    else:
        app.frame_buffer.get_good_face_frame.return_value = (None, None, 0)


def _run_verify_case(name, app, State, expected_checks):
    app.state.transition(State.VERIFYING_DRIVER, "identity simulation verify phase")
    with patch("time.sleep", return_value=None):
        app._verify_driver("SIM-UID-001")

    events = _queued_events(app)
    missing = []
    for description, check in expected_checks:
        if not check(events, app):
            missing.append(description)

    if missing:
        print("[IDENTITY] {0}: FAIL -> {1}".format(name, ", ".join(missing)))
        for event in events:
            print("  - {type}: {data}".format(**event))
        return False

    print("[IDENTITY] {0}: PASS".format(name))
    return True


def run_identity_simulation():
    """Exercise fixed identity-verification demo cases without real hardware."""
    _install_host_safe_mocks()

    import config
    from camera.face_verifier import VerifyResult
    from main import DrowsiGuard
    from state_machine import State

    original_features = dict(config.FEATURES)
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
        with patch("main.LocalQueue") as local_queue_class:
            print("[IDENTITY] Running fixed demo identity checks...")
            all_passed = True

            app = _new_identity_app(config, DrowsiGuard, State, local_queue_class)
            _configure_identity_verifier(app, VerifyResult, VerifyResult.MATCH)
            all_passed = _run_verify_case("correct-face-pass", app, State, [
                ("verify_snapshot VERIFIED", lambda events, _app: _has_event(events, "verify_snapshot", "status", "VERIFIED")),
                ("session_start", lambda events, _app: _has_event(events, "session_start")),
                ("state RUNNING", lambda _events, app: app.state.state == State.RUNNING),
            ]) and all_passed

            app = _new_identity_app(config, DrowsiGuard, State, local_queue_class)
            _configure_identity_verifier(app, VerifyResult, VerifyResult.MISMATCH)
            all_passed = _run_verify_case("wrong-face-reject", app, State, [
                ("face_mismatch", lambda events, _app: _has_event(events, "face_mismatch")),
                ("no session_start", lambda events, _app: not _has_event(events, "session_start")),
                ("state IDLE", lambda _events, app: app.state.state == State.IDLE),
            ]) and all_passed

            app = _new_identity_app(config, DrowsiGuard, State, local_queue_class)
            _configure_identity_verifier(app, VerifyResult, VerifyResult.MATCH, frame_available=False)
            all_passed = _run_verify_case("no-face-reject", app, State, [
                ("verify_error NO_FACE_FRAME", lambda events, _app: _has_event(events, "verify_error", "reason", "NO_FACE_FRAME")),
                ("no session_start", lambda events, _app: not _has_event(events, "session_start")),
                ("state IDLE", lambda _events, app: app.state.state == State.IDLE),
            ]) and all_passed

            app = _new_identity_app(config, DrowsiGuard, State, local_queue_class)
            _configure_identity_verifier(app, VerifyResult, VerifyResult.LOW_CONFIDENCE)
            all_passed = _run_verify_case("low-confidence-reject", app, State, [
                ("verify_error LOW_CONFIDENCE", lambda events, _app: _has_event(events, "verify_error", "reason", "LOW_CONFIDENCE")),
                ("no face_mismatch", lambda events, _app: not _has_event(events, "face_mismatch")),
                ("no session_start", lambda events, _app: not _has_event(events, "session_start")),
                ("state IDLE", lambda _events, app: app.state.state == State.IDLE),
            ]) and all_passed

            app = _new_identity_app(config, DrowsiGuard, State, local_queue_class)
            app.state.transition(State.VERIFYING_DRIVER, "identity simulation session start")
            app._start_verified_session("SIM-UID-001")
            app.local_queue.push.reset_mock()
            app._monitoring_enabled = True
            app._on_rfid_scan("SIM-UID-001")
            events = _queued_events(app)
            if _has_event(events, "session_end") and app.state.state == State.IDLE:
                print("[IDENTITY] rfid-session-end: PASS")
            else:
                all_passed = False
                print("[IDENTITY] rfid-session-end: FAIL")
                for event in events:
                    print("  - {type}: {data}".format(**event))

            if all_passed:
                print("[IDENTITY] PASS: fixed demo identity checks are ready.")
                return 0
            print("[IDENTITY] FAIL: one or more fixed demo identity checks failed.")
            return 1
    finally:
        config.FEATURES = original_features
        config.DEMO_MODE_ALLOW_UNVERIFIED = original_demo_mode


def run_hardware_probe():
    """Run safe read-only checks against the actual Jetson environment."""
    import config
    import healthcheck
    from sensors.gps_reader import GPSReader

    print("[HW] Running quick healthcheck...")
    healthcheck_exit = healthcheck.run_healthcheck(quick=True)

    print("[HW] Checking RFID input visibility...")
    event_devices = glob.glob("/dev/input/event*")
    print("  - event devices: {0}".format(", ".join(event_devices) if event_devices else "none"))
    if config.RFID_DEVICE_PATH:
        print("  - configured RFID path: {0}".format(config.RFID_DEVICE_PATH))
        print("  - exists: {0}".format(os.path.exists(config.RFID_DEVICE_PATH)))
    else:
        print("  - configured RFID path: auto-detect")

    print("[HW] Checking GPS probe...")
    if config.FEATURES.get("gps"):
        gps_result = GPSReader().read_once()
        print("  - GPS result: {0}".format(gps_result))
    else:
        print("  - GPS feature is disabled; enable DROWSIGUARD_FEATURE_GPS=true after wiring NEO-6M.")

    if healthcheck_exit == 0:
        print("[HW] PASS: no blocking failures in quick hardware readiness.")
    else:
        print("[HW] FAIL: quick hardware readiness reported blocking failures.")
    return healthcheck_exit


def main():
    parser = argparse.ArgumentParser(description="Separate smoke checker for DrowsiGuard demo readiness")
    parser.add_argument(
        "--mode",
        choices=("simulate", "identity-sim", "hardware"),
        default="simulate",
        help="simulate: host-safe event flow, identity-sim: fixed identity checks, hardware: read-only Jetson probes",
    )
    args = parser.parse_args()

    if args.mode == "hardware":
        return run_hardware_probe()
    if args.mode == "identity-sim":
        return run_identity_simulation()
    return run_simulation()


if __name__ == "__main__":
    raise SystemExit(main())
