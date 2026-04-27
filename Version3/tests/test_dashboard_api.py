import shutil
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from alerts.speaker import Speaker
from dashboard.app import create_app
from storage.runtime_status import RuntimeStatusStore


def make_runtime_dir():
    path = Path(__file__).resolve().parents[1] / "storage" / "_test_dashboard" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_dashboard_status_api_reads_runtime_status():
    runtime_dir = make_runtime_dir()
    store = RuntimeStatusStore(runtime_dir)
    store.write({
        "device": {"device_id": "JETSON-LOCAL", "strict_mode": True},
        "ai": {"state": "DROWSY", "confidence": 0.91},
        "websocket": {"connected": True, "url": "ws://demo/ws"},
        "driver": {"rfid_tag": "UID-001", "verify_status": "VERIFIED"},
        "session": {"state": "RUNNING", "active": True},
        "alert": {"level": "WARNING"},
        "queue": {"pending": 3},
        "ota": {"status": "IDLE"},
    })

    try:
        class BluetoothManagerStub:
            def status(self):
                return {"adapter": True, "connected": True, "speaker_mac": "AA:BB"}

        client = TestClient(create_app(runtime_dir=runtime_dir, bluetooth_manager=BluetoothManagerStub()))
        response = client.get("/api/status")

        assert response.status_code == 200
        assert response.json()["device"]["device_id"] == "JETSON-LOCAL"
        assert response.json()["device"]["strict_mode"] is True
        assert response.json()["ai"]["state"] == "DROWSY"
        assert response.json()["websocket"]["connected"] is True
        assert response.json()["driver"]["verify_status"] == "VERIFIED"
        assert response.json()["session"]["state"] == "RUNNING"
        assert response.json()["alert"]["level"] == "WARNING"
        assert response.json()["queue"]["pending"] == 3
        assert response.json()["ota"]["status"] == "IDLE"
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_health_endpoint_returns_fast_probe():
    runtime_dir = make_runtime_dir()
    RuntimeStatusStore(runtime_dir).write({
        "device": {"device_id": "JETSON-LOCAL"},
        "websocket": {"connected": False},
    })

    try:
        client = TestClient(create_app(runtime_dir=runtime_dir))
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
            "service": "drowsiguard-dashboard",
            "device_id": "JETSON-LOCAL",
        }
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_audio_test_endpoint_uses_speaker_adapter():
    runtime_dir = make_runtime_dir()
    calls = []
    audio_file = runtime_dir / "level1.wav"
    audio_file.write_bytes(b"RIFFdemo")

    def fake_popen(args):
        calls.append(args)

        class Process:
            def poll(self):
                return 0

            def terminate(self):
                pass

        return Process()

    speaker = Speaker(
        enabled=True,
        backend="aplay",
        alert_files={1: str(audio_file)},
        popen=fake_popen,
    )

    try:
        client = TestClient(create_app(runtime_dir=runtime_dir, speaker=speaker))
        response = client.post("/api/audio/test/1")

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert calls == [["aplay", str(audio_file)]]
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_snapshot_endpoint_does_not_require_file_response(monkeypatch):
    runtime_dir = make_runtime_dir()
    image_bytes = b"\xff\xd8demo-jpeg\xff\xd9"
    (runtime_dir / "latest.jpg").write_bytes(image_bytes)

    def broken_file_response(*args, **kwargs):
        raise AssertionError("FileResponse should not be required for snapshots")

    monkeypatch.setattr("dashboard.app.FileResponse", broken_file_response, raising=False)

    try:
        client = TestClient(create_app(runtime_dir=runtime_dir))
        response = client.get("/api/camera/latest.jpg")

        assert response.status_code == 200
        assert response.content == image_bytes
        assert response.headers["content-type"] == "image/jpeg"
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_alerts_test_alias_uses_speaker_adapter():
    runtime_dir = make_runtime_dir()
    calls = []
    audio_file = runtime_dir / "level2.wav"
    audio_file.write_bytes(b"RIFFdemo")

    def fake_popen(args):
        calls.append(args)

        class Process:
            def poll(self):
                return 0

            def terminate(self):
                pass

        return Process()

    speaker = Speaker(
        enabled=True,
        backend="aplay",
        alert_files={2: str(audio_file)},
        popen=fake_popen,
    )

    try:
        client = TestClient(create_app(runtime_dir=runtime_dir, speaker=speaker))
        response = client.post("/api/alerts/test/2")

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["level"] == 2
        assert calls == [["aplay", str(audio_file)]]
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_root_shows_operational_sections():
    runtime_dir = make_runtime_dir()

    class BluetoothManagerStub:
        def status(self):
            return {"adapter": False, "connected": False}

    try:
        client = TestClient(create_app(runtime_dir=runtime_dir, bluetooth_manager=BluetoothManagerStub()))
        response = client.get("/")

        assert response.status_code == 200
        assert "WebSocket" in response.text
        assert "Driver" in response.text
        assert "Session" in response.text
        assert "Queue" in response.text
        assert "OTA" in response.text
        assert "Bluetooth" in response.text
        assert "Restart Main Service" not in response.text
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_network_status_endpoint_reads_runtime_status():
    runtime_dir = make_runtime_dir()
    RuntimeStatusStore(runtime_dir).write({
        "network": {"eth0_ip": "192.168.2.31", "wlan0_ip": "172.20.10.5", "ssid": "Hotspot"},
    })

    class BluetoothManagerStub:
        def status(self):
            return {"adapter": False, "connected": False}

    try:
        client = TestClient(create_app(runtime_dir=runtime_dir, bluetooth_manager=BluetoothManagerStub()))
        response = client.get("/api/network/status")

        assert response.status_code == 200
        assert response.json()["eth0_ip"] == "192.168.2.31"
        assert response.json()["wlan0_ip"] == "172.20.10.5"
        assert response.json()["ssid"] == "Hotspot"
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_service_restart_endpoint_uses_service_controller():
    runtime_dir = make_runtime_dir()
    calls = []

    class BluetoothManagerStub:
        def status(self):
            return {"adapter": False, "connected": False}

    class ServiceControllerStub:
        def restart_main(self):
            calls.append("restart")
            return {"ok": True, "service": "drowsiguard.service"}

    try:
        client = TestClient(create_app(
            runtime_dir=runtime_dir,
            bluetooth_manager=BluetoothManagerStub(),
            service_controller=ServiceControllerStub(),
        ))
        response = client.post("/api/service/restart-main")

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["service"] == "drowsiguard.service"
        assert calls == ["restart"]
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_dashboard_service_restart_endpoint_is_disabled_by_default():
    runtime_dir = make_runtime_dir()

    class BluetoothManagerStub:
        def status(self):
            return {"adapter": False, "connected": False}

    try:
        client = TestClient(create_app(runtime_dir=runtime_dir, bluetooth_manager=BluetoothManagerStub()))
        response = client.post("/api/service/restart-main")

        assert response.status_code == 200
        assert response.json()["ok"] is False
        assert "disabled" in response.json()["error"]
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)
