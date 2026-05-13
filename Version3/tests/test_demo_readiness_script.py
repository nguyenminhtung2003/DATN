import subprocess
import sys
from pathlib import Path


def test_identity_sim_mode_runs_fixed_demo_checks():
    version3_root = Path(__file__).resolve().parents[1]
    script = version3_root / "scripts" / "test_demo_readiness.py"

    result = subprocess.run(
        [sys.executable, str(script), "--mode", "identity-sim"],
        cwd=str(version3_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "correct-face-pass: PASS" in result.stdout
    assert "wrong-face-reject: PASS" in result.stdout
    assert "no-face-reject: PASS" in result.stdout
    assert "low-confidence-reject: PASS" in result.stdout
    assert "rfid-session-end: PASS" in result.stdout
