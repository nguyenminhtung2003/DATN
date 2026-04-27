import healthcheck


def test_dashboard_port_status_passes_when_dashboard_is_serving(monkeypatch):
    monkeypatch.setattr(healthcheck, "_port_available", lambda port: False)
    monkeypatch.setattr(healthcheck, "_http_get_status_code", lambda url, timeout=1.0: 200)

    status, name, detail = healthcheck._dashboard_port_status(8080)

    assert status == "PASS"
    assert name == "dashboard_port"
    assert detail == "8080 serving dashboard"


def test_dashboard_port_status_warns_when_port_is_busy_for_unknown_service(monkeypatch):
    monkeypatch.setattr(healthcheck, "_port_available", lambda port: False)
    monkeypatch.setattr(healthcheck, "_http_get_status_code", lambda url, timeout=1.0: None)

    status, name, detail = healthcheck._dashboard_port_status(8080)

    assert status == "WARN"
    assert name == "dashboard_port"
    assert detail == "8080 busy; dashboard health endpoint not reachable"


def test_clock_status_warns_when_system_clock_is_not_synchronized(monkeypatch):
    monkeypatch.setattr(healthcheck, "_clock_synchronized", lambda: False)

    status, name, detail = healthcheck._clock_status()

    assert status == "WARN"
    assert name == "clock_sync"
    assert "not synchronized" in detail


def test_clock_synchronized_falls_back_to_timedatectl_status(monkeypatch):
    calls = []

    def fake_check_output(args, **kwargs):
        calls.append(args)
        if args[:2] == ["timedatectl", "show"]:
            raise RuntimeError("old timedatectl")
        return "       System clock synchronized: no\n"

    monkeypatch.setattr(healthcheck, "_command_available", lambda name: name == "timedatectl")
    monkeypatch.setattr(healthcheck.subprocess, "check_output", fake_check_output)

    assert healthcheck._clock_synchronized() is False
    assert calls[0][:2] == ["timedatectl", "show"]
    assert calls[1] == ["timedatectl", "status"]


def test_rfid_dependency_status_allows_raw_hid_fallback(monkeypatch):
    monkeypatch.setattr(healthcheck, "_module_available", lambda name: False)

    status, name, detail = healthcheck._rfid_dependency_status()

    assert status == "PASS"
    assert name == "rfid_dependency"
    assert "raw HID fallback" in detail


def test_run_healthcheck_reports_mediapipe_and_audio_backend(monkeypatch, capsys):
    monkeypatch.setattr(healthcheck.config, "FEATURES", {
        "camera": False,
        "drowsiness": True,
        "rfid": False,
        "gps": False,
        "buzzer": False,
        "led": False,
        "speaker": False,
        "websocket": True,
        "ota": True,
        "face_verify": True,
    })
    monkeypatch.setattr(healthcheck.config, "WS_SERVER_URL", "ws://demo-host/ws")
    monkeypatch.setattr(healthcheck.config, "BLUETOOTH_SPEAKER_MAC", "")
    monkeypatch.setattr(healthcheck, "_module_available", lambda name: name != "mediapipe")
    monkeypatch.setattr(healthcheck, "_writable_parent", lambda path: True)
    monkeypatch.setattr(healthcheck, "_file_exists", lambda path: True)
    monkeypatch.setattr(healthcheck, "_dashboard_port_status", lambda port: ("PASS", "dashboard_port", str(port)))
    monkeypatch.setattr(healthcheck, "_command_available", lambda name: name == "paplay")

    class FakeBluetoothManager:
        def status(self):
            return {"adapter": True, "connected": False}

    monkeypatch.setattr(healthcheck, "BluetoothManager", FakeBluetoothManager)

    exit_code = healthcheck.run_healthcheck(quick=True)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "mediapipe_dependency" in output
    assert "audio_backend" in output
