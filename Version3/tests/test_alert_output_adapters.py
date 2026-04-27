import unittest
from types import SimpleNamespace
from unittest.mock import patch

import config
from alerts.buzzer import Buzzer
from alerts.led import LEDController
from alerts.speaker import Speaker
from sensors.hardware_monitor import HardwareMonitor


class AlertOutputAdapterTest(unittest.TestCase):
    def setUp(self):
        self.original_buzzer = config.HAS_BUZZER
        self.original_led = config.HAS_LED
        self.original_speaker = config.HAS_SPEAKER
        config.HAS_BUZZER = False
        config.HAS_LED = False
        config.HAS_SPEAKER = False

    def tearDown(self):
        config.HAS_BUZZER = self.original_buzzer
        config.HAS_LED = self.original_led
        config.HAS_SPEAKER = self.original_speaker

    def test_mock_alert_outputs_record_last_state_without_hardware(self):
        buzzer = Buzzer()
        led = LEDController()
        speaker = Speaker()

        buzzer.beep_pattern("continuous")
        led.critical()
        speaker.play_alert(3)

        self.assertEqual(buzzer.last_pattern, "continuous")
        self.assertEqual(led.last_state, "critical")
        self.assertEqual(speaker.last_level, 3)
        self.assertFalse(speaker.is_available)

    def test_hardware_monitor_reads_speaker_adapter_availability(self):
        speaker = Speaker()
        monitor = HardwareMonitor(speaker=speaker)

        snapshot = monitor.snapshot()

        self.assertFalse(snapshot["speaker"])

    def test_hardware_monitor_reports_explicit_device_status_fields(self):
        class Device:
            is_alive = True

        class GPS:
            is_alive = True
            latest = SimpleNamespace(fix_ok=False)

            def status(self):
                return {
                    "enabled": True,
                    "module_ok": True,
                    "nmea_seen": True,
                    "fix_ok": False,
                    "reason": "NO_FIX",
                }

        class SpeakerStub:
            is_available = True

        class BluetoothStub:
            def status(self):
                return {
                    "adapter": True,
                    "speaker_mac": "7C:E9:13:33:93:BE",
                    "connected": False,
                    "name": "soundcore Select 4 Go",
                }

        class WS:
            is_connected = True

        monitor = HardwareMonitor(
            camera=Device(),
            rfid=Device(),
            gps=GPS(),
            ws_client=WS(),
            speaker=SpeakerStub(),
            bluetooth_manager=BluetoothStub(),
        )

        snapshot = monitor.snapshot()

        self.assertTrue(snapshot["camera_ok"])
        self.assertTrue(snapshot["rfid_reader_ok"])
        self.assertTrue(snapshot["gps_uart_ok"])
        self.assertFalse(snapshot["gps_fix_ok"])
        self.assertTrue(snapshot["bluetooth_adapter_ok"])
        self.assertFalse(snapshot["bluetooth_speaker_connected"])
        self.assertTrue(snapshot["speaker_output_ok"])
        self.assertTrue(snapshot["websocket_ok"])
        self.assertEqual(snapshot["details"]["bluetooth_speaker_name"], "soundcore Select 4 Go")

    @patch("alerts.speaker.shutil.which", return_value=None)
    def test_enabled_speaker_is_unavailable_without_detectable_backend(self, _mock_which):
        speaker = Speaker(enabled=True, backend="auto")

        self.assertFalse(speaker.is_available)

    def test_enabled_speaker_does_not_spawn_process_for_missing_audio_file(self):
        calls = []

        def fake_popen(args):
            calls.append(args)
            raise AssertionError("playback should not start without a valid file")

        speaker = Speaker(
            enabled=True,
            backend="aplay",
            alert_files={1: "/tmp/does-not-exist.wav"},
            popen=fake_popen,
        )

        self.assertFalse(speaker.play_alert(1))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
