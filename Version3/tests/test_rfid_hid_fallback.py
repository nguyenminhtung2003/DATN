import importlib

import config
from sensors import rfid_reader


def test_keyboard_wedge_decimal_uid_decodes_with_enter():
    keycodes = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 28]

    decoded = [rfid_reader.decode_hid_key_event(1, code, 1) for code in keycodes]

    assert decoded == ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "\n"]


def test_keyboard_wedge_keypad_digits_are_supported():
    keycodes = [79, 80, 81, 75, 76, 77, 71, 72, 73, 82, 96]

    decoded = [rfid_reader.decode_hid_key_event(1, code, 1) for code in keycodes]

    assert decoded == ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "\n"]


def test_non_keydown_events_are_ignored():
    assert rfid_reader.decode_hid_key_event(1, 2, 0) is None
    assert rfid_reader.decode_hid_key_event(0, 2, 1) is None


def test_rfid_device_path_can_be_set_from_environment(monkeypatch):
    monkeypatch.setenv("DROWSIGUARD_RFID_DEVICE_PATH", "/dev/input/event9")

    try:
        reloaded = importlib.reload(config)
        assert reloaded.RFID_DEVICE_PATH == "/dev/input/event9"
    finally:
        monkeypatch.delenv("DROWSIGUARD_RFID_DEVICE_PATH", raising=False)
        importlib.reload(config)


def test_rfid_status_reports_not_started_with_configured_path():
    reader = rfid_reader.RFIDReader(device_path="/dev/input/event2")

    status = reader.status()

    assert status["enabled"] is True
    assert status["reader_ok"] is False
    assert status["reason"] == "NOT_STARTED"
    assert status["device_path"] == "/dev/input/event2"


def test_evdev_auto_detect_supports_input_device_fn_attribute(monkeypatch):
    class FakeEvdevModule:
        @staticmethod
        def list_devices():
            return ["/dev/input/event2"]

    class FakeInputDevice:
        def __init__(self, path):
            self.fn = path
            self.name = "IC Reader"
            self.phys = "usb-demo"

    FakeEvdevModule.InputDevice = FakeInputDevice
    monkeypatch.setattr(rfid_reader, "HAS_EVDEV", True)
    monkeypatch.setattr(rfid_reader, "evdev", FakeEvdevModule, raising=False)
    monkeypatch.setattr(rfid_reader, "InputDevice", FakeInputDevice, raising=False)

    reader = rfid_reader.RFIDReader()

    assert reader._find_device() == "/dev/input/event2"
    assert reader.status()["device_path"] == "/dev/input/event2"
