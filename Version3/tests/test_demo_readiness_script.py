import subprocess
import sys
import importlib.util
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


def test_env_file_loader_sets_missing_runtime_env(monkeypatch, tmp_path):
    version3_root = Path(__file__).resolve().parents[1]
    script = version3_root / "scripts" / "test_demo_readiness.py"
    spec = importlib.util.spec_from_file_location("test_demo_readiness_module", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    env_file = tmp_path / "drowsiguard.env"
    env_file.write_text(
        "\n".join(
            [
                "DROWSIGUARD_WS_URL=ws://example.test/ws",
                "DROWSIGUARD_DEMO_MODE=false",
                "EMPTY_LINE_AFTER=this",
                "",
                "# comment",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("DROWSIGUARD_WS_URL", raising=False)
    monkeypatch.setenv("DROWSIGUARD_DEMO_MODE", "true")

    assert module._load_env_file(str(env_file)) is True
    assert module._load_env_file(str(tmp_path / "missing.env")) is False
    assert "ws://example.test/ws" == __import__("os").environ["DROWSIGUARD_WS_URL"]
    assert "true" == __import__("os").environ["DROWSIGUARD_DEMO_MODE"]
