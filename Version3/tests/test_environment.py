#!/usr/bin/env python3
"""
Environment Check: Validate Jetson Nano environment for DrowsiGuard.
Run on Jetson: python3 tests/test_environment.py
"""
import sys
import os
import subprocess
import pytest

pytestmark = pytest.mark.hardware

def run_cmd(cmd, shell=True):
    try:
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1

def test_environment():
    print("=" * 60)
    print("DrowsiGuard Environment Check — Jetson Nano A02")
    print("=" * 60)
    results = []

    # Python version
    print(f"\n🐍 Python: {sys.version}")
    results.append(("Python 3.6+", sys.version_info >= (3, 6)))

    # Key packages
    packages = {
        "cv2": "OpenCV",
        "mediapipe": "MediaPipe",
        "numpy": "NumPy",
    }
    for mod, name in packages.items():
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "unknown")
            print(f"✅ {name}: {ver}")
            results.append((name, True))
        except ImportError:
            print(f"❌ {name}: NOT INSTALLED")
            results.append((name, False))

    # evdev (for RFID)
    try:
        import evdev
        print(f"✅ evdev: available")
        results.append(("evdev", True))
    except ImportError:
        print(f"❌ evdev: NOT INSTALLED (needed for USB RFID)")
        results.append(("evdev", False))

    # Camera device
    print("\n📷 Camera devices:")
    out, _ = run_cmd("ls -l /dev/video* 2>/dev/null || echo 'No /dev/video* found'")
    print(f"  {out}")

    out, _ = run_cmd("v4l2-ctl --list-devices 2>/dev/null || echo 'v4l2-ctl not available'")
    print(f"  {out}")

    # USB devices (RFID)
    print("\n🔌 USB devices:")
    out, _ = run_cmd("lsusb 2>/dev/null | head -20")
    print(f"  {out}")

    # Input devices
    print("\n⌨️ Input devices:")
    out, _ = run_cmd("ls -l /dev/input/event* 2>/dev/null || echo 'No event devices'")
    print(f"  {out}")

    # Tegra release
    print("\n🖥️ System info:")
    out, _ = run_cmd("cat /etc/nv_tegra_release 2>/dev/null || echo 'Not a Tegra system'")
    print(f"  Tegra: {out}")

    out, _ = run_cmd("free -h | head -3")
    print(f"  Memory:\n  {out}")

    # GStreamer
    print("\n🎬 GStreamer check:")
    out, rc = run_cmd("gst-inspect-1.0 nvarguscamerasrc 2>/dev/null | head -5")
    if rc == 0 and out:
        print(f"  ✅ nvarguscamerasrc available")
        results.append(("GStreamer/nvargus", True))
    else:
        print(f"  ❌ nvarguscamerasrc not found")
        results.append(("GStreamer/nvargus", False))

    # OpenCV GStreamer support
    try:
        import cv2
        build_info = cv2.getBuildInformation()
        has_gst = "GStreamer:                   YES" in build_info
        if has_gst:
            print(f"  ✅ OpenCV built with GStreamer support")
        else:
            print(f"  ⚠️ OpenCV may not have GStreamer support")
        results.append(("OpenCV+GStreamer", has_gst))
    except Exception:
        pass

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}: {name}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("🎉 All checks passed — ready to proceed!")
    else:
        print("⚠️ Some checks failed — install missing dependencies first")

    return all_pass


if __name__ == "__main__":
    success = test_environment()
    sys.exit(0 if success else 1)
