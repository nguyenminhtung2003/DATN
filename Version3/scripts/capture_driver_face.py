#!/usr/bin/env python3
"""Capture a driver face image for manual WebQuanLi upload.

This helper only captures and saves images. It does not write to the local
driver registry and does not call the WebQuanLi API.
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import cv2
except ImportError:
    cv2 = None

import config
from camera.face_verifier import FaceVerifier


WINDOW_NAME = "DrowsiGuard Face Capture"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "storage" / "enrollment_captures"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Capture a driver face image for manual upload to WebQuanLi."
    )
    parser.add_argument(
        "--label",
        default="driver",
        help="Short label used in output filenames, e.g. driver name or RFID.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where captured images are saved.",
    )
    parser.add_argument(
        "--pipeline",
        default=None,
        help="Optional OpenCV/GStreamer pipeline. Defaults to config.GSTREAMER_PIPELINE.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=None,
        help="Use a simple OpenCV camera index instead of the CSI GStreamer pipeline.",
    )
    parser.add_argument(
        "--no-crop",
        action="store_true",
        help="Save the full frame as the upload image instead of face-cropping.",
    )
    parser.add_argument(
        "--no-desktop-copy",
        action="store_true",
        help="Do not copy the upload image to ~/Desktop/drowsiguard_face_captures.",
    )
    return parser.parse_args()


def safe_label(value: str) -> str:
    cleaned = []
    for char in str(value or "driver").strip():
        if char.isalnum() or char in ("-", "_"):
            cleaned.append(char)
        elif char.isspace():
            cleaned.append("_")
    label = "".join(cleaned).strip("_")
    return label or "driver"


def open_capture(args):
    if cv2 is None:
        raise RuntimeError("OpenCV is not available on this Python environment.")

    if args.camera_index is not None:
        return cv2.VideoCapture(args.camera_index)

    pipeline = args.pipeline or config.GSTREAMER_PIPELINE
    return cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)


def draw_preview(frame, label):
    preview = frame.copy()
    lines = [
        "SPACE: capture",
        "Q/ESC: quit",
        "Label: %s" % label,
        "Source: %sx%s" % (frame.shape[1], frame.shape[0]),
    ]
    y = 28
    for line in lines:
        cv2.putText(
            preview,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        y += 28
    return preview


def save_capture(frame, verifier, args):
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    label = safe_label(args.label)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    stem = "%s_%s" % (label, timestamp)
    full_path = output_dir / ("%s_full.jpg" % stem)
    upload_path = output_dir / ("%s_upload.jpg" % stem)

    if not cv2.imwrite(str(full_path), frame):
        raise RuntimeError("Failed to save full frame: %s" % full_path)

    upload_image = frame
    cropped = False
    if not args.no_crop:
        crop = verifier.detect_and_crop_face(frame)
        if crop is not None and not verifier._is_empty_image(crop):
            upload_image = crop
            cropped = True

    if not cv2.imwrite(str(upload_path), upload_image):
        raise RuntimeError("Failed to save upload image: %s" % upload_path)

    desktop_copy = None
    if not args.no_desktop_copy:
        desktop_dir = Path.home() / "Desktop"
        if desktop_dir.exists():
            desktop_target_dir = desktop_dir / "drowsiguard_face_captures"
            desktop_target_dir.mkdir(parents=True, exist_ok=True)
            desktop_copy = desktop_target_dir / upload_path.name
            shutil.copyfile(str(upload_path), str(desktop_copy))

    return {
        "upload_path": upload_path,
        "full_path": full_path,
        "desktop_copy": desktop_copy,
        "cropped": cropped,
    }


def capture_loop(args) -> int:
    verifier = FaceVerifier()
    cap = open_capture(args)
    if not cap.isOpened():
        print("ERROR: Cannot open camera.")
        print("If main.py is running, stop it first so this script can use the camera.")
        print("Configured pipeline:")
        print(args.pipeline or config.GSTREAMER_PIPELINE)
        return 1

    label = safe_label(args.label)
    print("Camera opened.")
    print("Press SPACE to capture, Q or ESC to quit.")
    print("Output directory: %s" % Path(args.output_dir).expanduser())

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("ERROR: Camera opened but no frame was read.")
                return 1

            cv2.imshow(WINDOW_NAME, draw_preview(frame, label))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                print("Capture cancelled.")
                return 1
            if key == ord(" "):
                result = save_capture(frame, verifier, args)
                print("")
                print("Saved upload image: %s" % result["upload_path"])
                print("Saved full frame:   %s" % result["full_path"])
                if result["desktop_copy"]:
                    print("Desktop copy:       %s" % result["desktop_copy"])
                if result["cropped"]:
                    print("Crop status:        face crop detected")
                else:
                    print("Crop status:        no crop used; upload image is full frame")
                print("")
                print("Upload the *_upload.jpg file to WebQuanLi for the driver.")
                return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main():
    args = parse_args()
    try:
        return capture_loop(args)
    except KeyboardInterrupt:
        print("Capture cancelled.")
        return 1
    except Exception as exc:
        print("ERROR: %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
