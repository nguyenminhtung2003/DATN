"""Canonical WebSocket payload fixtures shared by Version3 and WebQuanLi tests."""


def alert_payload():
    return {
        "level": "DANGER",
        "ear": 0.2,
        "mar": 0.4,
        "pitch": -12.0,
        "perclos": 0.5,
        "ai_state": "DROWSY",
        "ai_confidence": 0.9,
        "ai_reason": "classifier",
    }


def hardware_payload():
    return {
        "power": True,
        "cellular": True,
        "gps": False,
        "camera": True,
        "rfid": True,
        "speaker": True,
        "camera_ok": True,
        "rfid_reader_ok": True,
        "gps_uart_ok": True,
        "gps_fix_ok": False,
        "bluetooth_adapter_ok": True,
        "bluetooth_speaker_connected": False,
        "speaker_output_ok": True,
        "websocket_ok": True,
        "queue_pending": 0,
        "details": {"rfid_reason": "OPEN_OK"},
    }


def verify_snapshot_payload():
    return {
        "rfid_tag": "UID-123",
        "status": "VERIFIED",
        "message": "Face verification matched registered driver",
        "timestamp": 1710000000.0,
    }
