import hashlib
import shutil
import unittest
from pathlib import Path
import uuid

from network.ota_handler import OTAHandler


class OTAHandlerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parents[1] / "storage" / "_test_ota" / uuid.uuid4().hex
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.project_dir = self.tmp / "project"
        self.download_dir = self.tmp / "download"
        self.backup_dir = self.tmp / "backup"
        self.project_dir.mkdir()
        (self.project_dir / "main.py").write_text("VALUE = 'old'\n", encoding="utf-8")
        self.statuses = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _handler(self):
        return OTAHandler(
            on_status=self.statuses.append,
            project_dir=str(self.project_dir),
            download_dir=str(self.download_dir),
            backup_dir=str(self.backup_dir),
            restart_command=None,
        )

    def test_applies_valid_python_update_with_backup_and_statuses(self):
        source = self.tmp / "incoming.py"
        payload = b"VALUE = 'new'\n"
        source.write_bytes(payload)

        result = self._handler().handle_update_command({
            "download_url": source.resolve().as_uri(),
            "filename": "main.py",
            "checksum": hashlib.sha256(payload).hexdigest(),
        })

        self.assertEqual(result["status"], "APPLIED")
        self.assertEqual((self.project_dir / "main.py").read_text(encoding="utf-8"), "VALUE = 'new'\n")
        self.assertTrue(any(path.name.startswith("main.py.") for path in self.backup_dir.iterdir()))
        self.assertEqual([item["status"] for item in self.statuses], ["DOWNLOADING", "VERIFIED", "APPLIED"])

    def test_rejects_path_traversal_filename(self):
        source = self.tmp / "incoming.py"
        source.write_text("VALUE = 'new'\n", encoding="utf-8")

        result = self._handler().handle_update_command({
            "download_url": source.resolve().as_uri(),
            "filename": "../main.py",
        })

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("filename", result["error"].lower())
        self.assertEqual((self.project_dir / "main.py").read_text(encoding="utf-8"), "VALUE = 'old'\n")


if __name__ == "__main__":
    unittest.main()
