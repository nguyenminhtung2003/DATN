import unittest
import os
import sys

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


if __name__ == "__main__":
    unittest.main()
