import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


class FaceThresholdEvaluationScriptTest(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.temp_dir = self.project_root / "storage" / "_test_face_threshold_eval" / uuid.uuid4().hex
        self.face_data_dir = self.temp_dir / "driver_faces"
        self.registry_path = self.temp_dir / "driver_registry.json"
        self.dataset_dir = self.temp_dir / "dataset"
        self.report_path = self.temp_dir / "report.json"
        self.rfid = "UID-EVAL-001"

        self._write_matrix(self.face_data_dir / self.rfid / "reference.jpg", self._make_face())
        self._write_matrix(self.face_data_dir / self.rfid / "ref_01.jpg", self._make_face(eye_shift=1))
        self._write_matrix(self.dataset_dir / "positives" / "pos_01.jpg", self._make_face())
        self._write_matrix(self.dataset_dir / "negatives" / "neg_01.jpg", self._different_face())
        self._write_text(self.dataset_dir / "no_face" / "no_face_01.jpg", "not-json-image")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_face(self, eye_shift=0, background=40):
        image = [[background for _ in range(48)] for _ in range(48)]
        for y in range(12, 18):
            for x in range(10 + eye_shift, 16 + eye_shift):
                image[y][x] = 220
            for x in range(30 + eye_shift, 36 + eye_shift):
                image[y][x] = 220
        for y in range(28, 31):
            for x in range(18, 30):
                image[y][x] = 255
        for y in range(18, 30):
            for x in range(22, 26):
                image[y][x] = 180
        return image

    def _different_face(self):
        image = [[240 for _ in range(48)] for _ in range(48)]
        for y in range(8, 14):
            for x in range(6, 12):
                image[y][x] = 10
            for x in range(36, 42):
                image[y][x] = 10
        for y in range(34, 40):
            for x in range(12, 36):
                image[y][x] = 20
        return image

    def _write_matrix(self, path: Path, matrix):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(matrix, fh)

    def _write_text(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_evaluator_writes_json_report_with_decisions(self):
        script_path = self.project_root / "scripts" / "evaluate_face_threshold.py"

        completed = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--rfid",
                self.rfid,
                "--dataset",
                str(self.dataset_dir),
                "--threshold",
                "0.785",
                "--json-out",
                str(self.report_path),
                "--face-data-dir",
                str(self.face_data_dir),
                "--registry-path",
                str(self.registry_path),
            ],
            cwd=str(self.project_root),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertTrue(self.report_path.exists())

        with open(self.report_path, "r", encoding="utf-8") as fh:
            report = json.load(fh)

        self.assertEqual(report["rfid"], self.rfid)
        self.assertEqual(report["threshold"], 0.785)
        self.assertIn("summary", report)
        self.assertIn("rows", report)
        self.assertEqual(len(report["rows"]), 3)

        rows = {row["file"]: row for row in report["rows"]}
        self.assertEqual(rows["pos_01.jpg"]["expected"], "positive")
        self.assertEqual(rows["pos_01.jpg"]["decision"], "MATCH")
        self.assertIsInstance(rows["pos_01.jpg"]["score"], float)
        self.assertTrue(rows["pos_01.jpg"]["best_reference"])

        self.assertEqual(rows["neg_01.jpg"]["expected"], "negative")
        self.assertIn(rows["neg_01.jpg"]["decision"], ("MISMATCH", "LOW_CONFIDENCE"))

        self.assertEqual(rows["no_face_01.jpg"]["expected"], "no_face")
        self.assertNotEqual(rows["no_face_01.jpg"]["decision"], "MATCH")
        self.assertGreaterEqual(report["summary"]["passed"], 3)


if __name__ == "__main__":
    unittest.main()
