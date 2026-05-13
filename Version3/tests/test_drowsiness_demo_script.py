import subprocess
import sys
import unittest
from pathlib import Path


class DrowsinessDemoScriptTest(unittest.TestCase):
    def test_drowsiness_demo_mode_reports_required_alert_payload_fields(self):
        project_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/test_demo_readiness.py",
                "--mode",
                "drowsiness-demo",
            ],
            cwd=str(project_root),
            text=True,
            capture_output=True,
            check=False,
        )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, output)
        self.assertIn("[DROWSINESS] PASS", output)

        for scenario in (
            "normal-baseline",
            "closed-eyes-warning",
            "yawn-warning",
            "head-down-warning",
            "recovery-normal",
        ):
            self.assertIn(scenario, output)

        for field in ("level", "ear", "mar", "perclos", "ai_state", "ai_confidence"):
            self.assertIn(field, output)


if __name__ == "__main__":
    unittest.main()
