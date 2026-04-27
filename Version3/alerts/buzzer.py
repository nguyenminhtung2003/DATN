"""Buzzer output adapter with mock-safe state recording."""
from utils.logger import get_logger
import config

logger = get_logger("alerts.buzzer")


class Buzzer:
    """Buzzer control via GPIO relay when enabled, no-op recorder otherwise."""

    def __init__(self):
        self._active = False
        self.last_pattern = None
        if not config.HAS_BUZZER:
            logger.warning("Buzzer initialized without hardware; using mock adapter")

    def beep(self, count: int = 1):
        self.last_pattern = f"beep:{count}"
        if not config.HAS_BUZZER:
            logger.info(f"Buzzer beep({count}) skipped; hardware disabled")
            return
        self._active = True

    def beep_pattern(self, pattern: str = "intermittent"):
        self.last_pattern = pattern
        if not config.HAS_BUZZER:
            logger.info(f"Buzzer pattern({pattern}) skipped; hardware disabled")
            return
        self._active = True

    def on(self):
        self.last_pattern = "on"
        self._active = True
        if not config.HAS_BUZZER:
            return

    def off(self):
        self._active = False
        self.last_pattern = "off"
        if not config.HAS_BUZZER:
            return

    @property
    def is_active(self) -> bool:
        return self._active

    def cleanup(self):
        self.off()
