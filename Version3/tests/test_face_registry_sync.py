import json
import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from camera.face_verifier import FaceVerifier, VerifyResult
from storage.driver_registry import DriverRegistry


class FaceRegistrySyncTest(unittest.TestCase):
    def setUp(self):
        test_tmp_root = Path(__file__).resolve().parents[1] / "storage" / "_test_face_registry"
        test_tmp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = str(test_tmp_root / f"face-registry-{uuid.uuid4().hex}")
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        self.original_face_data_dir = config.FACE_DATA_DIR
        self.original_registry_path = getattr(config, "FACE_REGISTRY_PATH", None)
        self.original_threshold = config.FACE_VERIFY_THRESHOLD

        config.FACE_DATA_DIR = os.path.join(self.temp_dir, "driver_faces")
        config.FACE_REGISTRY_PATH = os.path.join(self.temp_dir, "driver_registry.json")
        config.FACE_VERIFY_THRESHOLD = 0.80

        self.verifier = FaceVerifier()
        self.registry = DriverRegistry()

    def tearDown(self):
        config.FACE_DATA_DIR = self.original_face_data_dir
        config.FACE_REGISTRY_PATH = self.original_registry_path
        config.FACE_VERIFY_THRESHOLD = self.original_threshold
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_face(self, eye_shift=0, mouth_offset=0, background=40):
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

    def _write_matrix_file(self, path: Path, matrix):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(matrix, fh)

    def test_verify_returns_no_enrollment_when_registry_empty(self):
        probe = self._make_face()
        self.assertEqual(self.verifier.verify(probe, "UID-001"), VerifyResult.BLOCKED)

    def test_enroll_driver_creates_registry_and_reference_image(self):
        probe = self._make_face()

        enrolled = self.verifier.enroll_driver("UID-001", probe, driver_name="Driver Demo")

        self.assertTrue(enrolled)
        self.assertTrue(os.path.exists(config.FACE_REGISTRY_PATH))
        self.assertTrue(os.path.exists(os.path.join(config.FACE_DATA_DIR, "UID-001", "reference.jpg")))

        with open(config.FACE_REGISTRY_PATH, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["drivers"][0]["rfid_tag"], "UID-001")
        self.assertEqual(manifest["drivers"][0]["name"], "Driver Demo")

    def test_verify_matches_same_reference_image(self):
        probe = self._make_face()
        self.verifier.enroll_driver("UID-001", probe, driver_name="Driver Demo")

        result = self.verifier.verify(self._make_face(), "UID-001")

        self.assertEqual(result, VerifyResult.MATCH)

    def test_verify_rejects_clearly_different_face(self):
        probe = self._make_face()
        other = self._make_face(eye_shift=8, mouth_offset=6, background=5)
        self.verifier.enroll_driver("UID-001", probe, driver_name="Driver Demo")

        result = self.verifier.verify(other, "UID-001")

        self.assertIn(result, (VerifyResult.MISMATCH, VerifyResult.LOW_CONFIDENCE))

    def test_sync_from_manifest_downloads_new_faces_and_removes_stale_entries(self):
        source_dir = Path(self.temp_dir) / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        img_a = source_dir / "a.face"
        img_b = source_dir / "b.face"
        self._write_matrix_file(img_a, self._make_face())
        self._write_matrix_file(img_b, self._make_face(eye_shift=4))

        stale_dir = Path(config.FACE_DATA_DIR) / "STALE-UID"
        stale_dir.mkdir(parents=True, exist_ok=True)
        self._write_matrix_file(stale_dir / "reference.jpg", self._make_face(background=100))

        self.registry.sync_from_manifest({
            "device_id": "JETSON-001",
            "generated_at": "2026-04-17T22:00:00Z",
            "drivers": [
                {
                    "name": "Driver A",
                    "rfid_tag": "UID-A",
                    "face_image_url": img_a.resolve().as_uri(),
                },
                {
                    "name": "Driver B",
                    "rfid_tag": "UID-B",
                    "face_image_url": img_b.resolve().as_uri(),
                },
            ],
        })

        self.assertTrue((Path(config.FACE_DATA_DIR) / "UID-A" / "reference.jpg").exists())
        self.assertTrue((Path(config.FACE_DATA_DIR) / "UID-B" / "reference.jpg").exists())
        self.assertFalse(stale_dir.exists())

        with open(config.FACE_REGISTRY_PATH, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual({driver["rfid_tag"] for driver in manifest["drivers"]}, {"UID-A", "UID-B"})


if __name__ == "__main__":
    unittest.main()
