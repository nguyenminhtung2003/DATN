#!/usr/bin/env python3
"""
Host-safe smoke test for local face enrollment and registry sync.
"""
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from camera.face_verifier import FaceVerifier, VerifyResult
from storage.driver_registry import DriverRegistry


def make_face(eye_shift=0, mouth_offset=0, background=40):
    image = [[background for _ in range(48)] for _ in range(48)]
    for y in range(12, 18):
        for x in range(10 + eye_shift, 16 + eye_shift):
            image[y][x] = 220
        for x in range(30 + eye_shift, 36 + eye_shift):
            image[y][x] = 220
    for y in range(28 + mouth_offset, 31 + mouth_offset):
        for x in range(18, 30):
            image[y][x] = 255
    for y in range(18, 30):
        for x in range(22, 26):
            image[y][x] = 180
    return image


def write_matrix(path: Path, matrix):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(matrix, fh)


def main():
    temp_root = Path(config.OTA_PROJECT_DIR) / "storage" / "_smoke_face_registry" / uuid.uuid4().hex
    temp_root.mkdir(parents=True, exist_ok=True)

    original_face_data_dir = config.FACE_DATA_DIR
    original_registry_path = config.FACE_REGISTRY_PATH
    original_threshold = config.FACE_VERIFY_THRESHOLD

    try:
        config.FACE_DATA_DIR = str(temp_root / "driver_faces")
        config.FACE_REGISTRY_PATH = str(temp_root / "driver_registry.json")
        config.FACE_VERIFY_THRESHOLD = 0.80

        verifier = FaceVerifier()
        registry = DriverRegistry()

        probe = make_face()
        other = make_face(eye_shift=8, mouth_offset=6, background=5)
        verifier.enroll_driver("UID-SMOKE", probe, driver_name="Smoke Driver")

        if verifier.verify(make_face(), "UID-SMOKE") != VerifyResult.MATCH:
            raise RuntimeError("Expected MATCH for enrolled face")

        mismatch = verifier.verify(other, "UID-SMOKE")
        if mismatch not in (VerifyResult.MISMATCH, VerifyResult.LOW_CONFIDENCE):
            raise RuntimeError(f"Unexpected result for mismatched face: {mismatch}")

        source_dir = temp_root / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        img_a = source_dir / "driver_a.face"
        write_matrix(img_a, make_face(eye_shift=4))

        registry.sync_from_manifest({
            "device_id": config.DEVICE_ID,
            "generated_at": "2026-04-17T22:00:00Z",
            "drivers": [
                {
                    "name": "Driver A",
                    "rfid_tag": "UID-A",
                    "face_image_url": img_a.resolve().as_uri(),
                }
            ],
        })

        if not Path(config.FACE_REGISTRY_PATH).exists():
            raise RuntimeError("Expected driver registry manifest to exist after sync")

        print("SMOKE FACE REGISTRY SYNC: PASS")
        print(f"Registry file: {config.FACE_REGISTRY_PATH}")
        print(f"Face data dir: {config.FACE_DATA_DIR}")
    finally:
        config.FACE_DATA_DIR = original_face_data_dir
        config.FACE_REGISTRY_PATH = original_registry_path
        config.FACE_VERIFY_THRESHOLD = original_threshold
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
