"""Bluetooth speaker status/reconnect helper for Jetson local dashboard."""
import subprocess
import time

import config


def default_command_runner(args, timeout=5):
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=timeout)
        return output.decode("utf-8", errors="replace")
    except Exception:
        return ""


def default_interactive_runner(commands, timeout=5):
    try:
        process = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        script = "\n".join(commands + ["quit"]) + "\n"
        output, _ = process.communicate(script, timeout=timeout)
        return output or ""
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        return ""


class BluetoothManager:
    def __init__(
        self,
        speaker_mac=None,
        command_runner=None,
        interactive_runner=None,
        cache_ttl=5.0,
        time_func=None,
    ):
        self.speaker_mac = speaker_mac or getattr(config, "BLUETOOTH_SPEAKER_MAC", "")
        self._run = command_runner or default_command_runner
        self._run_interactive = interactive_runner or default_interactive_runner
        self._cache_ttl = float(cache_ttl)
        self._time = time_func or time.monotonic
        self._cached_status = None
        self._cached_at = 0.0

    def status(self, force_refresh=False):
        now = self._time()
        if (
            not force_refresh
            and self._cached_status is not None
            and self._cache_ttl > 0
            and now - self._cached_at < self._cache_ttl
        ):
            return dict(self._cached_status)

        result = self._read_status()
        self._cached_status = dict(result)
        self._cached_at = now
        return result

    def _read_status(self):
        adapter = self._has_adapter()
        result = {
            "adapter": adapter,
            "speaker_mac": self.speaker_mac or None,
            "paired": False,
            "trusted": False,
            "connected": False,
            "name": None,
        }
        speaker_mac = self.speaker_mac
        discovered_name = None
        if not speaker_mac:
            discovered = self._discover_connected_device()
            if not discovered:
                return result
            speaker_mac, discovered_name = discovered
            result["speaker_mac"] = speaker_mac
            result["connected"] = True
            result["name"] = discovered_name

        if not speaker_mac:
            return result

        info = self._run(["bluetoothctl", "info", speaker_mac])
        parsed = self._parse_info(info)
        if not info.strip() or not self._has_device_info(info):
            interactive_info = self._run_interactive(["info %s" % speaker_mac])
            interactive_parsed = self._parse_info(interactive_info)
            if self._has_device_info(interactive_info):
                info = interactive_info
                parsed = interactive_parsed
        result.update(parsed)
        result["speaker_mac"] = speaker_mac
        if discovered_name and not result["name"]:
            result["name"] = discovered_name
        if discovered_name and "Connected:" not in info:
            result["connected"] = True
        if not result["connected"] and self._has_active_connection(speaker_mac):
            result["connected"] = True
        return result

    def _has_adapter(self):
        controllers = self._run(["bluetoothctl", "list"])
        if not controllers.strip():
            controllers = self._run_interactive(["list"])
        if "Controller " in controllers:
            return True

        hci_status = self._run(["hciconfig", "-a"])
        return "hci" in hci_status.lower() and ("UP RUNNING" in hci_status or "BD Address:" in hci_status)

    def _discover_connected_device(self):
        output = self._run(["bluetoothctl", "devices", "Connected"])
        if not output.strip() or "Too many arguments" in output:
            output = self._run_interactive(["devices"])
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line.startswith("Device "):
                continue
            parts = line.split(maxsplit=2)
            if len(parts) >= 2:
                name = parts[2].strip() if len(parts) > 2 else None
                return parts[1], name
        return None

    @staticmethod
    def _has_device_info(output):
        return "Device " in output or "Name:" in output or "Connected:" in output

    def _has_active_connection(self, speaker_mac):
        normalized = speaker_mac.upper()
        compact = normalized.replace(":", "_")

        hcitool_output = self._run(["hcitool", "con"])
        if normalized in hcitool_output.upper():
            return True

        sinks_output = self._run(["pactl", "list", "sinks", "short"])
        cards_output = self._run(["pactl", "list", "cards", "short"])
        pulse_output = (sinks_output + "\n" + cards_output).upper()
        return normalized in pulse_output or compact in pulse_output

    def reconnect(self):
        if not self.speaker_mac:
            return {"ok": False, "error": "DROWSIGUARD_BLUETOOTH_SPEAKER_MAC is empty"}
        self._run(["bluetoothctl", "power", "on"])
        self._run(["bluetoothctl", "trust", self.speaker_mac])
        output = self._run(["bluetoothctl", "connect", self.speaker_mac], timeout=15)
        status = self.status(force_refresh=True)
        status["ok"] = status["connected"] or "Connection successful" in output
        status["output"] = output.strip()
        return status

    @staticmethod
    def _parse_info(output):
        parsed = {
            "paired": False,
            "trusted": False,
            "connected": False,
            "name": None,
        }
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line.startswith("Name:"):
                parsed["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("Paired:"):
                parsed["paired"] = line.lower().endswith("yes")
            elif line.startswith("Trusted:"):
                parsed["trusted"] = line.lower().endswith("yes")
            elif line.startswith("Connected:"):
                parsed["connected"] = line.lower().endswith("yes")
        return parsed
