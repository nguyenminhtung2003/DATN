import healthcheck


def test_healthcheck_reports_vendored_websocket_dependency(monkeypatch, capsys):
    real_module_available = healthcheck._module_available

    def fake_module_available(name):
        if name == "websocket":
            return False
        return real_module_available(name)

    monkeypatch.setattr(healthcheck, "_module_available", fake_module_available)
    monkeypatch.setattr(healthcheck, "_writable_parent", lambda path: True)
    monkeypatch.setattr(healthcheck, "_file_exists", lambda path: True)
    monkeypatch.setattr(healthcheck, "_command_available", lambda name: True)
    monkeypatch.setattr(healthcheck, "_dashboard_port_status", lambda port: ("PASS", "dashboard_port", str(port)))
    monkeypatch.setattr(
        healthcheck.BluetoothManager,
        "status",
        lambda self: {"adapter": False, "connected": False},
    )

    exit_code = healthcheck.run_healthcheck(quick=True)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "websocket_dependency" in output
    assert "vendored websocket client available" in output
