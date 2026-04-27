"""
DrowsiGuard - Hardware Monitor.
Aggregates health status of connected hardware without faking availability.
"""

import time

import config
from sensors.system_status import read_network_status
from utils.logger import get_logger

logger = get_logger("sensors.hardware_monitor")


class HardwareMonitor:
    """Periodically samples hardware health and creates status payload."""

    def __init__(self, camera=None, rfid=None, gps=None, ws_client=None, speaker=None, bluetooth_manager=None):
        self._camera = camera
        self._rfid = rfid
        self._gps = gps
        self._ws_client = ws_client
        self._speaker = speaker
        self._bluetooth_manager = bluetooth_manager

    def snapshot(self) -> dict:
        """Return current hardware status dict matching the WebQuanLi schema."""
        network = read_network_status()
        bluetooth = self._read_bluetooth_status()
        camera_ok = self._check_camera()
        rfid_status = self._read_rfid_status()
        rfid_ok = bool(rfid_status.get("reader_ok"))
        gps_status = self._read_gps_status()
        gps_uart_ok = bool(gps_status.get("module_ok") or gps_status.get("nmea_seen"))
        gps_fix_ok = bool(gps_status.get("fix_ok"))
        speaker_output_ok = self._check_speaker()
        websocket_ok = self._check_cellular()
        bluetooth_adapter_ok = bool(bluetooth.get("adapter"))
        bluetooth_speaker_connected = bool(bluetooth.get("connected"))
        return {
            "power": True,
            "camera": camera_ok,
            "rfid": rfid_ok,
            "gps": gps_uart_ok,
            "speaker": speaker_output_ok,
            "cellular": websocket_ok,
            "camera_ok": camera_ok,
            "rfid_reader_ok": rfid_ok,
            "gps_uart_ok": gps_uart_ok,
            "gps_fix_ok": gps_fix_ok,
            "bluetooth": bluetooth_speaker_connected,
            "bluetooth_adapter": bluetooth_adapter_ok,
            "bluetooth_adapter_ok": bluetooth_adapter_ok,
            "bluetooth_speaker_connected": bluetooth_speaker_connected,
            "speaker_output_ok": speaker_output_ok,
            "websocket_ok": websocket_ok,
            "wifi": bool(network.get("wlan0_ip") or network.get("ssid")),
            "network": network,
            "details": {
                "gps_reason": gps_status.get("reason"),
                "gps_last_sentence": gps_status.get("last_sentence"),
                "rfid_reason": rfid_status.get("reason"),
                "rfid_device_path": rfid_status.get("device_path"),
                "bluetooth_speaker_mac": bluetooth.get("speaker_mac"),
                "bluetooth_speaker_name": bluetooth.get("name"),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

    def _check_camera(self) -> bool:
        if self._camera is None:
            return False
        try:
            return bool(self._camera.is_alive)
        except Exception:
            return False

    def _check_rfid(self) -> bool:
        if self._rfid is None:
            return False
        try:
            return bool(self._rfid.is_alive)
        except Exception:
            return False

    def _check_gps(self) -> bool:
        if not config.HAS_GPS or self._gps is None:
            return False
        try:
            return bool(self._gps.is_alive)
        except Exception:
            return False

    def _check_speaker(self) -> bool:
        if self._speaker is None:
            return False
        try:
            return bool(self._speaker.is_available)
        except Exception:
            return False

    def _check_cellular(self) -> bool:
        if self._ws_client is None:
            return False
        try:
            return bool(self._ws_client.is_connected)
        except Exception:
            return False

    def _read_bluetooth_status(self) -> dict:
        if self._bluetooth_manager is None:
            return {"adapter": False, "connected": False}
        try:
            return self._bluetooth_manager.status()
        except Exception:
            return {"adapter": False, "connected": False}

    def _read_rfid_status(self) -> dict:
        if self._rfid is None:
            return {"enabled": False, "reader_ok": False, "reason": "DISABLED", "device_path": None}
        try:
            if hasattr(self._rfid, "status"):
                return self._rfid.status()
            return {
                "enabled": True,
                "reader_ok": bool(getattr(self._rfid, "is_alive", False)),
                "reason": "LEGACY",
                "device_path": None,
            }
        except Exception as exc:
            return {
                "enabled": True,
                "reader_ok": False,
                "reason": str(exc),
                "device_path": None,
            }

    def _read_gps_status(self) -> dict:
        if self._gps is None:
            return {"enabled": False, "module_ok": False, "nmea_seen": False, "fix_ok": False, "reason": "DISABLED"}
        try:
            if hasattr(self._gps, "status"):
                return self._gps.status()
            return {
                "enabled": True,
                "module_ok": bool(getattr(self._gps, "is_alive", False)),
                "nmea_seen": False,
                "fix_ok": bool(getattr(getattr(self._gps, "latest", None), "fix_ok", False)),
                "reason": "LEGACY",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "module_ok": False,
                "nmea_seen": False,
                "fix_ok": False,
                "reason": str(exc),
            }
