#!/usr/bin/env python3
"""
Local face enrollment helper for demo mode.

Examples:
    python scripts/enroll_face.py --rfid UID-123 --image path/to/face.jpg
    python scripts/enroll_face.py --rfid UID-123 --name "Nguyen Van A"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import cv2
except ImportError:
    cv2 = None

import config
from camera.face_verifier import FaceVerifier


def parse_args():
    parser = argparse.ArgumentParser(description="Enroll a local reference face for one RFID tag.")
    parser.add_argument("--rfid", required=True, help="RFID UID of the driver")
    parser.add_argument("--image", help="Path to an existing face image")
    parser.add_argument("--name", help="Optional driver name to store in the local registry")
    parser.add_argument("--camera-index", type=int, default=0, help="Camera index for manual capture (default: 0)")
    parser.add_argument("--no-crop", action="store_true", help="Keep the full frame instead of best-effort face crop")
    return parser.parse_args()


def enroll_from_image(verifier: FaceVerifier, args) -> int:
    ok = verifier.enroll_driver_from_file(args.rfid, args.image, driver_name=args.name)
    if not ok:
        print(f"Enrollment failed for RFID {args.rfid}")
        return 1

    print(f"Enrolled RFID {args.rfid}")
    print(f"Reference image: {verifier.registry.reference_path(args.rfid)}")
    print(f"Registry file: {config.FACE_REGISTRY_PATH}")
    return 0


def enroll_from_camera(verifier: FaceVerifier, args) -> int:
    if cv2 is None:
        print("OpenCV is not available. Use --image for manual enrollment.")
        return 1

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(f"Cannot open camera index {args.camera_index}. Use --image instead.")
        return 1

    print("Press SPACE to capture, Q to quit.")
    saved = False
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to grab frame from camera.")
                return 1

            preview = frame.copy()
            cv2.putText(
                preview,
                "SPACE = capture | Q = quit",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            cv2.imshow("Driver Enrollment", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                face_image = frame if args.no_crop else (verifier.detect_and_crop_face(frame) or frame)
                saved = verifier.enroll_driver(args.rfid, face_image, driver_name=args.name)
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not saved:
        print(f"Enrollment cancelled or failed for RFID {args.rfid}")
        return 1

    print(f"Enrolled RFID {args.rfid}")
    print(f"Reference image: {verifier.registry.reference_path(args.rfid)}")
    print(f"Registry file: {config.FACE_REGISTRY_PATH}")
    return 0


def main():
    args = parse_args()
    verifier = FaceVerifier()

    if args.image:
        sys.exit(enroll_from_image(verifier, args))

    sys.exit(enroll_from_camera(verifier, args))


if __name__ == "__main__":
    main()
