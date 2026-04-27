"""LED output adapter with mock-safe state recording."""
from utils.logger import get_logger
import config

logger = get_logger("alerts.led")


class LEDController:
    """Warning/danger/critical LED adapter."""

    def __init__(self):
        self.last_state = "off"
        if not config.HAS_LED:
            logger.warning("LEDController initialized without hardware; using mock adapter")

    def warning(self):
        self.last_state = "warning"
        if not config.HAS_LED:
            logger.info("LED warning skipped; hardware disabled")
            return

    def danger(self):
        self.last_state = "danger"
        if not config.HAS_LED:
            logger.info("LED danger skipped; hardware disabled")
            return

    def critical(self):
        self.last_state = "critical"
        if not config.HAS_LED:
            logger.info("LED critical skipped; hardware disabled")
            return

    def off(self):
        self.last_state = "off"
        if not config.HAS_LED:
            return

    def cleanup(self):
        self.off()
