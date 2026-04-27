#!/usr/bin/env python3
"""
DrowsiGuard deployment healthcheck.

This check is intentionally safe on development machines: hardware checks are
reported as WARN unless the related feature flag is enabled and the dependency
is expected to exist on the target Jetson.
"""

import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from audio.bluetooth_manager import BluetoothManager


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _vendored_module_available(name: str) -> bool:
    root = Path(__file__).resolve().parent / "third_party" / name
    return (root / "__init__.py").exists()


def _writable_parent(path: str) -> bool:
    parent = Path(path).expanduser().resolve().parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".drowsiguard_healthcheck"
        probe.write_text("ok", encoding="utf-8")
        if probe.exists():
            probe.unlink()
        return True
    except OSError:
        return False


def _file_exists(path):
    return bool(path and Path(path).expanduser().exists())


def _command_available(name: str) -> bool:
    return shutil.which(name) is not None


def _port_available(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return sock.connect_ex(("127.0.0.1", int(port))) != 0
    finally:
        sock.close()


def _http_get_status_code(url, timeout=1.0):
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
        try:
            return response.getcode()
        finally:
            response.close()
    except Exception:
        return None


def _clock_synchronized():
    if not _command_available("timedatectl"):
        return None
    try:
        output = subprocess.check_output(
            ["timedatectl", "show", "-p", "SystemClockSynchronized", "--value"],
            stderr=subprocess.STDOUT,
            timeout=2,
            universal_newlines=True,
        ).strip().lower()
    except Exception:
        try:
            output = subprocess.check_output(
                ["timedatectl", "status"],
                stderr=subprocess.STDOUT,
                timeout=2,
                universal_newlines=True,
            ).lower()
        except Exception:
            return None
        for line in output.splitlines():
            if "system clock synchronized:" in line:
                output = line.rsplit(":", 1)[-1].strip()
                break
        else:
            return None
    if output in ("yes", "true", "1"):
        return True
    if output in ("no", "false", "0"):
        return False
    return None


def _clock_status():
    synchronized = _clock_synchronized()
    if synchronized is None:
        return ("WARN", "clock_sync", "unable to query system clock synchronization")
    if synchronized:
        return ("PASS", "clock_sync", "system clock synchronized")
    return ("WARN", "clock_sync", "system clock is not synchronized; set time before WebQuanLi demo")


def _dashboard_port_status(port):
    if _port_available(port):
        return ("PASS", "dashboard_port", str(port))
    health_code = _http_get_status_code("http://127.0.0.1:%s/api/health" % port)
    status_code = _http_get_status_code("http://127.0.0.1:%s/api/status" % port)
    if health_code == 200 or status_code == 200:
        return ("PASS", "dashboard_port", "%s serving dashboard" % port)
    return ("WARN", "dashboard_port", "%s busy; dashboard health endpoint not reachable" % port)


def _rfid_dependency_status():
    if _module_available("evdev"):
        return ("PASS", "rfid_dependency", "evdev available")
    return ("PASS", "rfid_dependency", "raw HID fallback available; evdev optional")


def _record(results, status: str, name: str, detail: str):
    results.append((status, name, detail))


def run_healthcheck(quick: bool = False) -> int:
    results = []

    _record(
        results,
        "PASS" if config.DEVICE_ID else "FAIL",
        "device_id",
        config.DEVICE_ID or "DROWSIGUARD_DEVICE_ID is empty",
    )

    ws_url = getattr(config, "WS_SERVER_URL", "")
    if not ws_url:
        _record(results, "FAIL", "websocket_url", "DROWSIGUARD_WS_URL is empty")
    elif "SERVER_IP" in ws_url:
        _record(results, "WARN", "websocket_url", "replace SERVER_IP before Jetson demo")
    elif ws_url.startswith(("ws://", "wss://")):
        _record(results, "PASS", "websocket_url", ws_url)
    else:
        _record(results, "FAIL", "websocket_url", "must start with ws:// or wss://")

    strict = not getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False)
    _record(
        results,
        "PASS" if strict else "WARN",
        "strict_mode",
        "DROWSIGUARD_DEMO_MODE=false" if strict else "demo mode allows unverified sessions",
    )

    _record(
        results,
        "PASS" if _writable_parent(config.QUEUE_DB_PATH) else "FAIL",
        "queue_db",
        config.QUEUE_DB_PATH,
    )
    _record(
        results,
        "PASS" if _writable_parent(config.FACE_REGISTRY_PATH) else "FAIL",
        "face_registry",
        config.FACE_REGISTRY_PATH,
    )

    if config.FEATURES.get("camera"):
        _record(
            results,
            "PASS" if _module_available("cv2") else "WARN",
            "camera_dependency",
            "cv2 available" if _module_available("cv2") else "OpenCV not installed in this environment",
        )
    if config.FEATURES.get("drowsiness"):
        _record(
            results,
            "PASS" if _module_available("mediapipe") else "WARN",
            "mediapipe_dependency",
            "mediapipe available" if _module_available("mediapipe") else "mediapipe missing; install on Jetson for face mesh",
        )
    if config.FEATURES.get("websocket"):
        websocket_available = _module_available("websocket")
        vendored_websocket = _vendored_module_available("websocket")
        _record(
            results,
            "PASS" if (websocket_available or vendored_websocket) else "WARN",
            "websocket_dependency",
            "websocket-client available"
            if websocket_available
            else "vendored websocket client available"
            if vendored_websocket
            else "websocket-client missing; install package or keep vendored fallback",
        )
    if not quick and _command_available("timedatectl"):
        _record(results, *_clock_status())
    if config.FEATURES.get("rfid"):
        _record(results, *_rfid_dependency_status())
    if config.FEATURES.get("gps"):
        _record(results, "PASS", "gps_feature", f"enabled on {config.GPS_PORT}")
    elif not quick:
        _record(results, "WARN", "gps_feature", "disabled via DROWSIGUARD_FEATURE_GPS")

    _record(
        results,
        "PASS" if _writable_parent(os.path.join(config.RUNTIME_DIR, "status.json")) else "FAIL",
        "runtime_dir",
        config.RUNTIME_DIR,
    )

    bluetooth_status = BluetoothManager().status()
    _record(
        results,
        "PASS" if bluetooth_status.get("adapter") else "WARN",
        "bluetooth_adapter",
        "detected" if bluetooth_status.get("adapter") else "no bluetooth controller visible",
    )
    if config.BLUETOOTH_SPEAKER_MAC:
        _record(
            results,
            "PASS" if bluetooth_status.get("connected") else "WARN",
            "bluetooth_speaker",
            config.BLUETOOTH_SPEAKER_MAC,
        )
    elif not quick:
        _record(results, "WARN", "bluetooth_speaker", "DROWSIGUARD_BLUETOOTH_SPEAKER_MAC is empty")

    audio_files = [config.AUDIO_ALERT_LEVEL1, config.AUDIO_ALERT_LEVEL2, config.AUDIO_ALERT_LEVEL3]
    missing_audio = [path for path in audio_files if not _file_exists(path)]
    _record(
        results,
        "PASS" if not missing_audio else "WARN",
        "audio_files",
        "all alert audio files exist" if not missing_audio else "missing: " + ", ".join(missing_audio),
    )
    backend = getattr(config, "AUDIO_BACKEND", "auto")
    if backend == "auto":
        backend_ok = _command_available("paplay") or _command_available("aplay")
        backend_detail = "paplay/aplay auto-detect ready" if backend_ok else "paplay/aplay not found in PATH"
    else:
        backend_ok = _command_available(backend)
        backend_detail = backend if backend_ok else f"{backend} not found in PATH"
    _record(
        results,
        "PASS" if backend_ok else "WARN",
        "audio_backend",
        backend_detail,
    )

    _record(results, *_dashboard_port_status(config.DASHBOARD_PORT))

    width = max(len(name) for _, name, _ in results)
    for status, name, detail in results:
        print(f"{status:4} {name:<{width}} {detail}")

    return 1 if any(status == "FAIL" for status, _, _ in results) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DrowsiGuard deployment healthcheck")
    parser.add_argument("--quick", action="store_true", help="skip optional disabled hardware warnings")
    args = parser.parse_args()
    return run_healthcheck(quick=args.quick)


if __name__ == "__main__":
    raise SystemExit(main())
