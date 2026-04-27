import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from alerts.alert_manager import AlertEvent, AlertLevel
from main import DrowsiGuard
from sensors.hardware_monitor import HardwareMonitor
from state_machine import State
from tests.fixtures.websocket_payloads import (
    alert_payload,
    hardware_payload,
    verify_snapshot_payload,
)


def load_webquanli_schemas():
    workspace_root = Path(__file__).resolve().parents[2]
    schema_path = workspace_root / "WebQuanLi" / "app" / "schemas.py"
    spec = importlib.util.spec_from_file_location("webquanli_contract_schemas", schema_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_alert_fixture_matches_webquanli_schema():
    schemas = load_webquanli_schemas()

    parsed = schemas.AlertData(**alert_payload())

    assert parsed.level == "DANGER"


def test_shared_hardware_fixture_matches_webquanli_schema():
    schemas = load_webquanli_schemas()

    parsed = schemas.HardwareData(**hardware_payload())

    assert parsed.camera_effective is True


def test_shared_verify_snapshot_fixture_matches_webquanli_schema():
    schemas = load_webquanli_schemas()

    parsed = schemas.VerifySnapshotData(**verify_snapshot_payload())

    assert parsed.status == "VERIFIED"


class ImmediateThread:
    def __init__(self, target=None, args=None, kwargs=None, **_kwargs):
        self._target = target
        self._args = args or ()
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class WebQuanLiContractTest(unittest.TestCase):
    @patch("main.LocalQueue")
    def setUp(self, mock_local_queue_class):
        self.schemas = load_webquanli_schemas()
        self.original_features = config.FEATURES.copy()
        self.original_demo_mode = config.DEMO_MODE_ALLOW_UNVERIFIED
        config.FEATURES = {
            "camera": False,
            "drowsiness": False,
            "rfid": False,
            "gps": False,
            "buzzer": False,
            "led": False,
            "speaker": False,
            "websocket": False,
            "ota": False,
            "face_verify": False,
        }
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        self.app = DrowsiGuard()
        self.app.local_queue = mock_local_queue_class.return_value
        self.app.state.transition(State.IDLE)

    def tearDown(self):
        config.FEATURES = self.original_features
        config.DEMO_MODE_ALLOW_UNVERIFIED = self.original_demo_mode

    def queued_payload(self, msg_type):
        for call in self.app.local_queue.push.call_args_list:
            queued_type, payload = call[0]
            if queued_type == msg_type:
                return payload
        self.fail("Expected queued payload for %s" % msg_type)

    def test_driver_probe_payload_matches_webquanli_schema(self):
        self.app._emit_driver_probe("UID-123")

        payload = self.queued_payload("driver")
        parsed = self.schemas.DriverData(**payload)

        self.assertEqual(parsed.rfid, "UID-123")

    def test_verified_session_payloads_match_webquanli_schemas(self):
        self.app._start_verified_session("UID-123")

        session_payload = self.queued_payload("session_start")
        verify_payload = self.queued_payload("verify_snapshot")

        parsed_session = self.schemas.SessionStartData(**session_payload)
        parsed_verify = self.schemas.VerifySnapshotData(**verify_payload)

        self.assertEqual(parsed_session.rfid_tag, "UID-123")
        self.assertEqual(parsed_verify.status, "VERIFIED")

    def test_rejection_payload_matches_webquanli_schema(self):
        with patch("time.sleep", return_value=None):
            self.app._reject_verification("UID-123", "NO_ENROLLMENT", "fail-safe: no enrollment")

        payload = self.queued_payload("verify_error")
        parsed = self.schemas.VerifyErrorData(**payload)

        self.assertEqual(parsed.rfid_tag, "UID-123")
        self.assertEqual(parsed.reason, "NO_ENROLLMENT")

    def test_alert_payload_matches_webquanli_schema(self):
        event = AlertEvent(
            AlertLevel.LEVEL_2,
            ear=0.2,
            mar=0.4,
            pitch=-12.0,
            perclos=0.5,
            ai_result={"state": "DROWSY", "confidence": 0.9, "reason": "classifier"},
        )

        self.app._on_alert(event)

        payload = self.queued_payload("alert")
        parsed = self.schemas.AlertData(**payload)

        self.assertEqual(parsed.level, "DANGER")
        self.assertAlmostEqual(parsed.ear, 0.2)

    def test_hardware_snapshot_matches_webquanli_schema(self):
        payload = HardwareMonitor().snapshot()

        parsed = self.schemas.HardwareData(**payload)

        self.assertTrue(hasattr(parsed, "camera"))
        self.assertTrue(hasattr(parsed, "speaker"))

    def test_hardware_snapshot_includes_rfid_status_reason(self):
        class RfidStub:
            is_alive = False

            def status(self):
                return {
                    "enabled": True,
                    "reader_ok": False,
                    "reason": "PERMISSION_DENIED",
                    "device_path": "/dev/input/event2",
                }

        payload = HardwareMonitor(rfid=RfidStub()).snapshot()

        self.assertFalse(payload["rfid_reader_ok"])
        self.assertEqual(payload["details"]["rfid_reason"], "PERMISSION_DENIED")
        self.assertEqual(payload["details"]["rfid_device_path"], "/dev/input/event2")

    def test_ota_status_payload_matches_webquanli_schema(self):
        self.app._on_ota_status({
            "status": "FAILED",
            "filename": "main.py",
            "progress": 0,
            "error": "blocked",
        })

        payload = self.queued_payload("ota_status")
        parsed = self.schemas.OTAStatusData(**payload)

        self.assertEqual(parsed.status, "FAILED")
        self.assertEqual(parsed.filename, "main.py")

    def test_webquanli_test_alert_command_is_handled(self):
        self.app.alert_manager = Mock()
        command = self.schemas.WsCommandOut(action="test_alert", level=2, state="on").model_dump(exclude_none=True)

        self.app._on_backend_command(command)

        self.app.alert_manager._activate_outputs.assert_called_once_with(2)

    def test_webquanli_monitoring_commands_are_handled(self):
        connect = self.schemas.WsCommandOut(action="connect_monitoring").model_dump(exclude_none=True)
        disconnect = self.schemas.WsCommandOut(action="disconnect_monitoring").model_dump(exclude_none=True)

        self.app._on_backend_command(connect)
        self.assertTrue(self.app._monitoring_enabled)

        self.app._on_backend_command(disconnect)
        self.assertFalse(self.app._monitoring_enabled)

    def test_webquanli_sync_driver_registry_command_is_handled(self):
        verifier = Mock()
        self.app.verifier = verifier
        command = self.schemas.WsCommandOut(
            action="sync_driver_registry",
            manifest_url="http://example.test/manifest.json",
        ).model_dump(exclude_none=True)

        with patch("main.threading.Thread", ImmediateThread):
            self.app._on_backend_command(command)

        verifier.sync_from_manifest_url.assert_called_once_with("http://example.test/manifest.json")

    def test_webquanli_update_software_command_is_handled(self):
        ota_handler = Mock()
        self.app.ota_handler = ota_handler
        command = self.schemas.WsCommandOut(
            action="update_software",
            download_url="http://example.test/update.py",
            filename="main.py",
            checksum="a" * 64,
        ).model_dump(exclude_none=True)

        with patch("main.threading.Thread", ImmediateThread):
            self.app._on_backend_command(command)

        ota_handler.handle_update_command.assert_called_once_with({
            "download_url": "http://example.test/update.py",
            "filename": "main.py",
            "checksum": "a" * 64,
        })


if __name__ == "__main__":
    unittest.main()
