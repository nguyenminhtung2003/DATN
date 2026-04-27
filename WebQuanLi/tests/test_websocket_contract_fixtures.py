import importlib.util
from pathlib import Path

import pytest

from app.schemas import AlertData, HardwareData, VerifySnapshotData


def _load_version3_payloads():
    workspace_root = Path(__file__).resolve().parents[2]
    fixture_path = workspace_root / "Version3" / "tests" / "fixtures" / "websocket_payloads.py"
    spec = importlib.util.spec_from_file_location("version3_websocket_payloads", fixture_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def payloads():
    return _load_version3_payloads()


def test_webquanli_accepts_version3_alert_fixture(payloads):
    AlertData(**payloads.alert_payload())


def test_webquanli_accepts_version3_hardware_fixture(payloads):
    HardwareData(**payloads.hardware_payload())


def test_webquanli_accepts_version3_verify_snapshot_fixture(payloads):
    VerifySnapshotData(**payloads.verify_snapshot_payload())
