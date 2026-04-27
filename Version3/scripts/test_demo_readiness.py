#!/usr/bin/env python3
"""
Standalone readiness checker for the current camera-only stage and later
full-hardware smoke checks on Jetson Nano.

Usage:
  python3 scripts/test_demo_readiness.py --mode simulate
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

            queued = [
                {"type": call.args[0], "data": call.args[1]}
                for call in app.local_queue.push.call_args_list
            ]

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
        choices=("simulate", "hardware"),
        default="simulate",
        help="simulate: host-safe event flow, hardware: read-only Jetson probes",
    )
    args = parser.parse_args()

    if args.mode == "hardware":
        return run_hardware_probe()
    return run_simulation()


if __name__ == "__main__":
    raise SystemExit(main())
