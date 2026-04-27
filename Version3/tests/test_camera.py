#!/usr/bin/env python3
"""
Hardware Test: CSI Camera (IMX219-77 IR)
Validates camera opens via GStreamer, captures frames, and measures FPS.
Run on Jetson: python3 tests/test_camera.py
"""
import sys
import os
import time
import pytest

pytestmark = pytest.mark.hardware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

def test_camera():
    import cv2

    print("=" * 50)
    print("CSI Camera Test (IMX219-77 IR)")
    print("=" * 50)

    print(f"\nGStreamer pipeline:\n  {config.GSTREAMER_PIPELINE}\n")

    print("Opening camera...")
    cap = cv2.VideoCapture(config.GSTREAMER_PIPELINE, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("FAIL: Could not open camera via GStreamer")
        print("Trying fallback: /dev/video0 ...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("FAIL: Fallback also failed")
            return False

    print("SUCCESS: Camera opened")

    # Capture test frames
    frame_count = 0
    start = time.monotonic()
    duration = 5.0

    print(f"Capturing frames for {duration}s...")
    while (time.monotonic() - start) < duration:
        ret, frame = cap.read()
        if ret and frame is not None:
            frame_count += 1
        else:
            print(f"  WARNING: Frame read failed at count={frame_count}")

    elapsed = time.monotonic() - start
    fps = frame_count / elapsed if elapsed > 0 else 0

    print(f"\nResults:")
    print(f"  Frames captured: {frame_count}")
    print(f"  Duration: {elapsed:.2f}s")
    print(f"  FPS: {fps:.1f}")
    print(f"  Frame size: {frame.shape if frame_count > 0 else 'N/A'}")

    cap.release()

    if fps >= 10:
        print("\nPASS: Camera is working (FPS >= 10)")
        return True
    else:
        print(f"\nWARNING: FPS is low ({fps:.1f}), expected >= 10")
        return False


if __name__ == "__main__":
    success = test_camera()
    sys.exit(0 if success else 1)
