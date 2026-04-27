"""Speaker/audio output adapter with Bluetooth-friendly backends."""
import os
import shutil
import subprocess

from utils.logger import get_logger
import config

logger = get_logger("alerts.speaker")


class Speaker:
    """Audio alert playback through paplay/aplay, with mock-safe state recording."""

    def __init__(self, enabled=None, backend=None, alert_files=None, popen=None):
        self.enabled = config.HAS_SPEAKER if enabled is None else bool(enabled)
        self.backend = backend or getattr(config, "AUDIO_BACKEND", "auto")
        self.alert_files = alert_files or {
            1: config.AUDIO_ALERT_LEVEL1,
            2: config.AUDIO_ALERT_LEVEL2,
            3: config.AUDIO_ALERT_LEVEL3,
        }
        self.last_level = None
        self.last_command = None
        self._last_process = None
        self._popen = popen or subprocess.Popen
        if not self.enabled:
            logger.warning("Speaker initialized without hardware; using mock adapter")

    @property
    def is_available(self):
        return bool(self.enabled and self._resolve_backend())

    def play_alert(self, level):
        self.last_level = level
        if not self.enabled:
            logger.info("Speaker alert level=%s skipped; hardware disabled", level)
            return False

        sound_path = self.alert_files.get(int(level))
        if not sound_path:
            logger.warning("No audio file configured for alert level=%s", level)
            return False
        if not os.path.exists(sound_path):
            logger.warning("Audio file does not exist for alert level=%s: %s", level, sound_path)
            return False

        backend = self._resolve_backend()
        if not backend:
            logger.warning("No usable audio backend found for speaker playback")
            return False

        command = self._build_command(sound_path, backend=backend)
        self.last_command = command
        try:
            self.stop()
            self._last_process = self._popen(command)
            return True
        except Exception as exc:
            logger.error("Speaker playback failed: %s", exc)
            return False

    def _build_command(self, sound_path, backend=None):
        backend = backend or self._resolve_backend()
        if backend == "paplay":
            return ["paplay", sound_path]
        return ["aplay", sound_path]

    def _resolve_backend(self):
        if self.backend in ("paplay", "aplay"):
            return self.backend if self._command_available(self.backend) else None
        if self._command_available("paplay"):
            return "paplay"
        if self._command_available("aplay"):
            return "aplay"
        return None

    def _command_available(self, command_name):
        if self._popen is not subprocess.Popen:
            return True
        return shutil.which(command_name) is not None

    def stop(self):
        if self._last_process and self._last_process.poll() is None:
            self._last_process.terminate()
        self._last_process = None

    def test_tone(self):
        return self.play_alert(1)

    def status(self):
        return {
            "enabled": self.enabled,
            "available": self.is_available,
            "backend": self._resolve_backend() or self.backend,
            "last_level": self.last_level,
            "files": {
                str(level): {
                    "path": path,
                    "exists": os.path.exists(path),
                }
                for level, path in self.alert_files.items()
            },
        }

    def cleanup(self):
        self.stop()
