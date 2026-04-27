from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_systemd_services_load_local_env_file():
    main_service = (ROOT / "drowsiguard.service.template").read_text(encoding="utf-8")
    dashboard_service = (ROOT / "drowsiguard-dashboard.service.template").read_text(encoding="utf-8")

    assert "EnvironmentFile=-@APP_DIR@/drowsiguard.env" in main_service
    assert "EnvironmentFile=-@APP_DIR@/drowsiguard.env" in dashboard_service


def test_env_example_contains_demo_hardware_knobs():
    env_example = (ROOT / "drowsiguard.env.example").read_text(encoding="utf-8")

    assert "DROWSIGUARD_WS_URL" in env_example
    assert "DROWSIGUARD_FEATURE_SPEAKER" in env_example
    assert "DROWSIGUARD_RFID_DEVICE_PATH" in env_example
    assert "DROWSIGUARD_BLUETOOTH_SPEAKER_MAC" in env_example
    assert "DROWSIGUARD_DASHBOARD_PORT" in env_example
    assert "DROWSIGUARD_DASHBOARD_SERVICE_CONTROL" in env_example
