import unittest
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class VerifySnapshotContractTest(unittest.TestCase):
    def test_verify_snapshot_schema_accepts_demo_status(self):
        from app.schemas import VerifySnapshotData

        data = VerifySnapshotData(
            rfid_tag="UID-123",
            status="DEMO_VERIFIED",
            message="Demo mode: verification bypassed",
            snapshot_path="/static/verification_snapshots/UID-123.jpg",
        )

        self.assertEqual(data.rfid_tag, "UID-123")
        self.assertEqual(data.status, "DEMO_VERIFIED")
        self.assertEqual(data.message, "Demo mode: verification bypassed")
        self.assertEqual(data.snapshot_path, "/static/verification_snapshots/UID-123.jpg")

    def test_verify_error_schema_accepts_friendly_message(self):
        from app.schemas import VerifyErrorData

        data = VerifyErrorData(
            rfid_tag="UID-123",
            reason="LOW_CONFIDENCE",
            message="Khong du tin cay, hay giu mat on dinh",
        )

        self.assertEqual(data.rfid_tag, "UID-123")
        self.assertEqual(data.reason, "LOW_CONFIDENCE")
        self.assertEqual(data.message, "Khong du tin cay, hay giu mat on dinh")

    def test_dashboard_maps_verify_failures_to_friendly_labels(self):
        template_path = Path(__file__).resolve().parents[1] / "templates" / "dashboard.html"
        template = template_path.read_text(encoding="utf-8")

        self.assertIn("function verifyReasonLabel", template)
        self.assertIn("'NO_FACE_FRAME': 'Vui long nhin vao camera'", template)
        self.assertIn("'LOW_CONFIDENCE': 'Khong du tin cay, hay giu mat on dinh'", template)
        self.assertIn("'MISMATCH': 'Sai danh tinh tai xe'", template)
        self.assertIn("'NO_ENROLLMENT': 'Tai xe chua co anh dang ky'", template)
        self.assertIn("showVerifyStatus({", template)


if __name__ == "__main__":
    unittest.main()
