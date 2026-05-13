import healthcheck
import config


def test_healthcheck_reports_demo_gate_fields(monkeypatch, capsys, tmp_path):
    face_root = tmp_path / "driver_faces"
    driver_dir = face_root / "0199190080"
    driver_dir.mkdir(parents=True)
    (driver_dir / "reference.jpg").write_text("ref")
    (driver_dir / "ref_01.jpg").write_text("ref")

    monkeypatch.setattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False)
    monkeypatch.setattr(
        config,
        "FEATURES",
        {
            "camera": True,
            "drowsiness": True,
            "rfid": True,
            "gps": False,
            "websocket": True,
            "face_verify": True,
            "bluetooth": False,
            "speaker": False,
            "audio_prompt": False,
        },
    )
    monkeypatch.setattr(config, "FACE_VERIFY_THRESHOLD", 0.785)
    monkeypatch.setattr(config, "FACE_DATA_DIR", str(face_root))
    monkeypatch.setattr(config, "RFID_DEVICE_PATH", str(tmp_path / "event0"))
    monkeypatch.setattr(config, "WS_SERVER_URL", "ws://demo-host:8000/ws/jetson/JETSON-001")
    monkeypatch.setattr(config, "DASHBOARD_PORT", 8080)
    monkeypatch.setattr(config, "QUEUE_DB_PATH", str(tmp_path / "queue.db"))
    monkeypatch.setattr(config, "FACE_REGISTRY_PATH", str(tmp_path / "face_registry.json"))
    monkeypatch.setattr(config, "RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(healthcheck, "_module_available", lambda name: True)
    monkeypatch.setattr(healthcheck, "_vendored_module_available", lambda name: True)
    monkeypatch.setattr(healthcheck, "_writable_parent", lambda path: True)
    monkeypatch.setattr(healthcheck, "_file_exists", lambda path: True)
    monkeypatch.setattr(healthcheck, "_command_available", lambda name: True)
    monkeypatch.setattr(healthcheck, "_dashboard_port_status", lambda port: ("PASS", "dashboard_port", "8080 serving dashboard"))

    exit_code = healthcheck.run_healthcheck(quick=True)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "strict_mode" in output
    assert "DROWSIGUARD_DEMO_MODE=false" in output
    assert "face_verify" in output
    assert "DROWSIGUARD_FEATURE_FACE_VERIFY=true" in output
    assert "face_threshold" in output
    assert "0.785" in output
    assert "face_reference_count" in output
    assert "0199190080 references=2" in output
    assert "camera_alive" in output
    assert "rfid_reader" in output
    assert "dashboard_reachability" in output
