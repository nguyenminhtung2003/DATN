from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_logs_do_not_claim_version1():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    config_source = (ROOT / "config.py").read_text(encoding="utf-8")

    assert "DrowsiGuard V1" not in main_source
    assert "DrowsiGuard V1" not in config_source
    assert "APP_VERSION" in main_source
