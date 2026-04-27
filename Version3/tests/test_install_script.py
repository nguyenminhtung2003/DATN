from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_script_supports_offline_dependency_skips():
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "DROWSIGUARD_SKIP_APT" in script
    assert "DROWSIGUARD_SKIP_PIP" in script
    assert "Skipping apt dependency installation" in script
    assert "Skipping pip dependency installation" in script


def test_install_script_creates_local_env_from_example_when_missing():
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "drowsiguard.env.example" in script
    assert "drowsiguard.env" in script
    assert "Creating local environment file" in script


def test_install_script_assigns_runtime_ownership_to_service_user():
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert 'SERVICE_USER="${DROWSIGUARD_SERVICE_USER' in script
    assert 'chown -R "$SERVICE_USER:$SERVICE_USER"' in script
    assert '"$SCRIPT_DIR/storage"' in script
    assert '"$SCRIPT_DIR/drowsiguard.env"' in script


def test_install_script_defaults_service_user_to_nano():
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert '${SUDO_USER:-nano}' in script


def test_install_script_installs_runtime_python_packages_for_demo():
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "python3-websocket" in script
    assert "python3-evdev" in script


def test_install_script_installs_hardware_udev_rules():
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "99-drowsiguard-hardware.rules" in script
    assert 'KERNEL=="ttyTHS1"' in script
    assert 'ENV{ID_VENDOR_ID}=="ffff"' in script
    assert 'ENV{ID_MODEL_ID}=="0035"' in script
    assert "udevadm trigger" in script
