import os

from audio.bluetooth_manager import BluetoothManager
from alerts.speaker import Speaker


def test_bluetooth_manager_parses_connected_speaker_status():
    outputs = {
        ("bluetoothctl", "list"): "Controller 00:11:22:33:44:55 jetson [default]\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"): (
            "Device AA:BB:CC:DD:EE:FF Car Speaker\n"
            "\tName: Car Speaker\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tConnected: yes\n"
        ),
    }

    def runner(args, timeout=5):
        return outputs.get(tuple(args), "")

    manager = BluetoothManager(speaker_mac="AA:BB:CC:DD:EE:FF", command_runner=runner)

    status = manager.status()

    assert status["adapter"] is True
    assert status["speaker_mac"] == "AA:BB:CC:DD:EE:FF"
    assert status["paired"] is True
    assert status["trusted"] is True
    assert status["connected"] is True
    assert status["name"] == "Car Speaker"


def test_bluetooth_manager_falls_back_to_hciconfig_when_bluetoothctl_list_is_empty():
    outputs = {
        ("bluetoothctl", "list"): "",
        ("hciconfig", "-a"): (
            "hci0:   Type: Primary  Bus: USB\n"
            "        BD Address: 00:1A:7D:DA:71:13  ACL MTU: 310:10  SCO MTU: 64:8\n"
            "        UP RUNNING\n"
        ),
    }

    def runner(args, timeout=5):
        return outputs.get(tuple(args), "")

    manager = BluetoothManager(command_runner=runner)

    status = manager.status()

    assert status["adapter"] is True


def test_bluetooth_manager_falls_back_to_interactive_info_when_direct_info_is_empty():
    outputs = {
        ("bluetoothctl", "list"): "Controller 00:11:22:33:44:55 jetson [default]\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"): "",
    }
    interactive_outputs = {
        ("info AA:BB:CC:DD:EE:FF",): (
            "Device AA:BB:CC:DD:EE:FF Car Speaker\n"
            "\tName: Car Speaker\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tConnected: yes\n"
        ),
    }

    def runner(args, timeout=5):
        return outputs.get(tuple(args), "")

    def interactive_runner(commands, timeout=5):
        return interactive_outputs.get(tuple(commands), "")

    manager = BluetoothManager(
        speaker_mac="AA:BB:CC:DD:EE:FF",
        command_runner=runner,
        interactive_runner=interactive_runner,
    )

    status = manager.status()

    assert status["connected"] is True
    assert status["paired"] is True
    assert status["trusted"] is True


def test_bluetooth_manager_falls_back_to_hcitool_connection_when_bluez_reports_disconnected():
    outputs = {
        ("bluetoothctl", "list"): "Controller 00:11:22:33:44:55 jetson [default]\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"): "Waiting to connect to bluetoothd...\n",
        ("hcitool", "con"): "Connections:\n\t< ACL AA:BB:CC:DD:EE:FF handle 68 state 1 lm MASTER\n",
        ("pactl", "list", "sinks", "short"): "",
        ("pactl", "list", "cards", "short"): "",
    }
    interactive_outputs = {
        ("info AA:BB:CC:DD:EE:FF",): (
            "Device AA:BB:CC:DD:EE:FF Car Speaker\n"
            "\tName: Car Speaker\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tConnected: no\n"
        ),
    }

    def runner(args, timeout=5):
        return outputs.get(tuple(args), "")

    def interactive_runner(commands, timeout=5):
        return interactive_outputs.get(tuple(commands), "")

    manager = BluetoothManager(
        speaker_mac="AA:BB:CC:DD:EE:FF",
        command_runner=runner,
        interactive_runner=interactive_runner,
    )

    status = manager.status()

    assert status["name"] == "Car Speaker"
    assert status["connected"] is True


def test_bluetooth_manager_falls_back_to_pulseaudio_sink_when_bluez_reports_disconnected():
    outputs = {
        ("bluetoothctl", "list"): "Controller 00:11:22:33:44:55 jetson [default]\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"): (
            "Device AA:BB:CC:DD:EE:FF Car Speaker\n"
            "\tName: Car Speaker\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tConnected: no\n"
        ),
        ("hcitool", "con"): "Connections:\n",
        ("pactl", "list", "sinks", "short"): (
            "1\tbluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink\tmodule-bluez5-device.c\n"
        ),
        ("pactl", "list", "cards", "short"): "",
    }

    def runner(args, timeout=5):
        return outputs.get(tuple(args), "")

    manager = BluetoothManager(speaker_mac="AA:BB:CC:DD:EE:FF", command_runner=runner)

    status = manager.status()

    assert status["connected"] is True


def test_bluetooth_manager_reports_disconnected_when_no_source_confirms_connection():
    outputs = {
        ("bluetoothctl", "list"): "Controller 00:11:22:33:44:55 jetson [default]\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"): (
            "Device AA:BB:CC:DD:EE:FF Car Speaker\n"
            "\tName: Car Speaker\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tConnected: no\n"
        ),
        ("hcitool", "con"): "Connections:\n",
        ("pactl", "list", "sinks", "short"): "0\talsa_output.platform-sound.analog-stereo\n",
        ("pactl", "list", "cards", "short"): "",
    }

    def runner(args, timeout=5):
        return outputs.get(tuple(args), "")

    manager = BluetoothManager(speaker_mac="AA:BB:CC:DD:EE:FF", command_runner=runner)

    status = manager.status()

    assert status["connected"] is False


def test_bluetooth_manager_caches_status_within_ttl():
    calls = []
    now = [100.0]

    outputs = {
        ("bluetoothctl", "list"): "Controller 00:11:22:33:44:55 jetson [default]\n",
        ("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"): (
            "Device AA:BB:CC:DD:EE:FF Car Speaker\n"
            "\tName: Car Speaker\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tConnected: yes\n"
        ),
    }

    def runner(args, timeout=5):
        calls.append(tuple(args))
        return outputs.get(tuple(args), "")

    manager = BluetoothManager(
        speaker_mac="AA:BB:CC:DD:EE:FF",
        command_runner=runner,
        cache_ttl=5.0,
        time_func=lambda: now[0],
    )

    first = manager.status()
    second = manager.status()
    now[0] += 6.0
    third = manager.status()

    assert first == second == third
    assert calls.count(("bluetoothctl", "info", "AA:BB:CC:DD:EE:FF")) == 2


def test_bluetooth_manager_discovers_connected_speaker_when_mac_is_not_configured():
    outputs = {
        ("bluetoothctl", "list"): "Controller 00:11:22:33:44:55 jetson [default]\n",
        ("bluetoothctl", "devices", "Connected"): "Device 7C:E9:13:33:93:BE soundcore Select 4 Go\n",
        ("bluetoothctl", "info", "7C:E9:13:33:93:BE"): (
            "Device 7C:E9:13:33:93:BE soundcore Select 4 Go\n"
            "\tName: soundcore Select 4 Go\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tConnected: yes\n"
        ),
    }

    def runner(args, timeout=5):
        return outputs.get(tuple(args), "")

    manager = BluetoothManager(speaker_mac="", command_runner=runner)

    status = manager.status()

    assert status["adapter"] is True
    assert status["speaker_mac"] == "7C:E9:13:33:93:BE"
    assert status["name"] == "soundcore Select 4 Go"
    assert status["connected"] is True


def test_speaker_uses_configured_audio_file_and_backend(monkeypatch):
    calls = []
    audio_file = "D:/CodingAntigravity/CodeJetsonNano/Version3/storage/_test_speaker_level2.wav"
    with open(audio_file, "wb") as fh:
        fh.write(b"RIFFdemo")

    def fake_popen(args):
        calls.append(args)

        class Process:
            def poll(self):
                return None

            def terminate(self):
                calls.append(["terminate"])

        return Process()

    speaker = Speaker(
        enabled=True,
        backend="paplay",
        alert_files={2: audio_file},
        popen=fake_popen,
    )
    try:
        speaker.play_alert(2)
        speaker.stop()

        assert calls[0] == ["paplay", audio_file]
        assert calls[1] == ["terminate"]
        assert speaker.last_level == 2
    finally:
        if os.path.exists(audio_file):
            os.remove(audio_file)
