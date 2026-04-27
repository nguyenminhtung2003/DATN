"""Atomic runtime status store shared by main runtime and local dashboard."""
import json
import os
from datetime import datetime, timezone

import config


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_status():
    return {
        "device": {
            "device_id": "unknown",
            "hostname": "",
            "version": getattr(config, "APP_VERSION", "Version3"),
            "strict_mode": not getattr(config, "DEMO_MODE_ALLOW_UNVERIFIED", False),
            "features": dict(getattr(config, "FEATURES", {})),
        },
        "system": {"uptime_seconds": 0, "cpu_temp_c": None, "ram_percent": None, "thermal_warning": False},
        "network": {"eth0_ip": None, "wlan0_ip": None, "ssid": None},
        "bluetooth": {"adapter": False, "speaker_mac": None, "connected": False},
        "audio": {"backend": "auto", "available": False},
        "camera": {"online": False, "fps": 0.0, "snapshot": None, "snapshot_interval": getattr(config, "DASHBOARD_SNAPSHOT_INTERVAL", 0.75)},
        "ai": {
            "state": "UNKNOWN",
            "confidence": 0.0,
            "reason": "",
            "fps": 0.0,
            "target_fps": getattr(config, "AI_TARGET_FPS", 12),
        },
        "driver": {"rfid_tag": None, "name": None, "verify_status": None, "verify_reason": ""},
        "session": {"state": "IDLE", "active": False},
        "alert": {"level": "NONE"},
        "websocket": {"connected": False, "url": ""},
        "queue": {"pending": 0},
        "hardware": {},
        "ota": {"status": None, "filename": None, "progress": 0, "error": None},
        "updated_at": utc_now_iso(),
    }


class RuntimeStatusStore:
    def __init__(self, runtime_dir=None):
        self.runtime_dir = runtime_dir or getattr(config, "RUNTIME_DIR", None)
        if self.runtime_dir is None:
            self.runtime_dir = os.path.join(os.path.dirname(__file__), "runtime")
        self.status_path = os.path.join(str(self.runtime_dir), "status.json")
        self.tmp_path = self.status_path + ".tmp"
        os.makedirs(str(self.runtime_dir), exist_ok=True)

    def write(self, payload):
        merged = default_status()
        self._deep_update(merged, payload or {})
        merged["updated_at"] = utc_now_iso()
        with open(self.tmp_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2, sort_keys=True)
        os.replace(self.tmp_path, self.status_path)
        return merged

    def read(self):
        if not os.path.exists(self.status_path):
            return default_status()
        try:
            with open(self.status_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError):
            return default_status()
        merged = default_status()
        self._deep_update(merged, loaded)
        return merged

    @classmethod
    def _deep_update(cls, target, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                cls._deep_update(target[key], value)
            else:
                target[key] = value
