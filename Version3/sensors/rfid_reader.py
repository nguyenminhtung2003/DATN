"""
DrowsiGuard — RFID Reader (USB HID Keyboard-like Device)
This is NOT an SPI/UART MFRC522. It's a USB reader that behaves like
a keyboard, typing the UID as keystrokes followed by Enter.

Implementation uses Linux evdev to capture input exclusively,
preventing the UID from leaking into random terminal/UI fields.
"""
import glob
import errno
import os
import struct
import threading
import time

from utils.logger import get_logger
import config

logger = get_logger("sensors.rfid_reader")

# Try importing evdev (Linux only)
try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False
    logger.warning("evdev not available — RFID reader will not work on this platform")


EV_KEY = 1
KEY_DOWN = 1
KEY_ENTER_CODES = {28, 96}
KEY_MAP = {
    11: "0", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9",
    82: "0", 79: "1", 80: "2", 81: "3", 75: "4", 76: "5", 77: "6", 71: "7", 72: "8", 73: "9",
    30: "A", 48: "B", 46: "C", 32: "D", 18: "E", 33: "F",
}
RAW_INPUT_EVENT = struct.Struct("llHHI")


def classify_input_error(exc: Exception) -> str:
    err_no = getattr(exc, "errno", None)
    message = str(exc).lower()
    if isinstance(exc, PermissionError) or err_no in (errno.EACCES, errno.EPERM) or "permission denied" in message:
        return "PERMISSION_DENIED"
    if err_no == errno.ENODEV or "no such device" in message:
        return "NO_DEVICE"
    return "READ_ERROR"


def input_device_path(device) -> str:
    return getattr(device, "path", None) or getattr(device, "fn", None)


def decode_hid_key_event(event_type: int, keycode: int, value: int):
    """Decode key events from USB keyboard-wedge RFID readers."""
    if event_type != EV_KEY or value != KEY_DOWN:
        return None
    if keycode in KEY_ENTER_CODES:
        return "\n"
    return KEY_MAP.get(keycode)


class RawHIDInputDevice:
    """Minimal /dev/input/event* reader used when python-evdev is unavailable."""

    def __init__(self, path: str):
        self.path = path

    def read_loop(self):
        with open(self.path, "rb", buffering=0) as fh:
            while True:
                raw = fh.read(RAW_INPUT_EVENT.size)
                if len(raw) != RAW_INPUT_EVENT.size:
                    return
                _, _, event_type, keycode, value = RAW_INPUT_EVENT.unpack(raw)
                yield event_type, keycode, value


class RFIDReader:
    """USB HID RFID reader via Linux evdev.

    Responsibilities:
    - Read UID from USB HID input events
    - Debounce repeated scans
    - Emit rfid_scanned callback
    - Does NOT open camera or run face verification
    """

    def __init__(self, device_path: str = None, callback=None):
        """
        Args:
            device_path: e.g. "/dev/input/event3". If None, will attempt auto-detect.
            callback: function(uid: str) called when a card is scanned.
        """
        self._device_path = device_path or config.RFID_DEVICE_PATH
        self._callback = callback
        self._debounce_sec = config.RFID_DEBOUNCE_SEC
        self._grab_exclusive = config.RFID_GRAB_EXCLUSIVE
        self._running = False
        self._thread = None
        self._device = None
        self._last_device_path = self._device_path
        self._last_status_reason = "NOT_STARTED"
        self._last_uid = None
        self._last_scan_time = 0.0

    def start(self):
        if not HAS_EVDEV:
            logger.warning("evdev not installed; using raw HID fallback for keyboard-like RFID")
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True,
                                        name="rfid-reader")
        self._thread.start()
        logger.info("RFID reader thread started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        if self._device and self._grab_exclusive:
            try:
                self._device.ungrab()
            except Exception:
                pass
        logger.info("RFID reader stopped")

    @property
    def is_alive(self) -> bool:
        return self._running and self._device is not None

    def status(self) -> dict:
        enabled = bool(getattr(config, "FEATURES", {}).get("rfid", True))
        return {
            "enabled": enabled,
            "reader_ok": bool(self._device is not None),
            "reason": self._last_status_reason if enabled else "DISABLED",
            "device_path": self._last_device_path,
        }

    def _find_device(self) -> str:
        """Auto-detect RFID reader from /dev/input/event* devices."""
        if self._device_path:
            self._last_device_path = self._device_path
            return self._device_path

        if not HAS_EVDEV:
            candidates = []
            for pattern in ("/dev/input/by-id/*", "/dev/input/event*"):
                candidates.extend(glob.glob(pattern))
            for path in candidates:
                name = os.path.basename(path).lower()
                if any(kw in name for kw in ["rfid", "reader", "card", "hid", "keyboard"]):
                    resolved = os.path.realpath(path)
                    self._last_device_path = resolved
                    logger.info(f"Found RFID HID candidate: {resolved} via {path}")
                    return resolved
            if candidates:
                self._last_status_reason = "NO_DEVICE"
                logger.warning("No RFID HID candidate found. Set DROWSIGUARD_RFID_DEVICE_PATH to the event path.")
            else:
                self._last_status_reason = "NO_DEVICE"
                logger.error("No /dev/input devices found for RFID")
            return None

        logger.info("Auto-detecting RFID USB HID device...")
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            name_lower = dev.name.lower()
            # Common USB RFID reader identifiers
            if any(kw in name_lower for kw in ["rfid", "hid", "card", "reader", "rf"]):
                path = input_device_path(dev)
                self._last_device_path = path
                logger.info(f"Found RFID device: {path} ({dev.name})")
                return path
                logger.info(f"Found RFID device: {dev.path} — {dev.name}")
                return dev.path

        # Fallback: list all devices for manual selection
        if devices:
            self._last_status_reason = "NO_DEVICE"
            logger.warning("No RFID-specific device found. Available input devices:")
            for dev in devices:
                logger.warning(f"  {dev.path}: {dev.name} (phys={dev.phys})")
        else:
            self._last_status_reason = "NO_DEVICE"
            logger.error("No input devices found at all")
        return None

    def _read_loop(self):
        while self._running:
            try:
                path = self._find_device()
                if not path:
                    logger.error("RFID device not found, retrying in 5s...")
                    time.sleep(5.0)
                    continue

                if HAS_EVDEV:
                    self._device = InputDevice(path)
                    self._last_device_path = path
                    self._last_status_reason = "OPEN_OK"
                    logger.info(f"RFID reader opened: {self._device.name} at {path}")
                else:
                    self._device = RawHIDInputDevice(path)
                    self._last_device_path = path
                    self._last_status_reason = "OPEN_OK"
                    logger.info(f"RFID raw HID reader opened at {path}")

                if HAS_EVDEV and self._grab_exclusive:
                    try:
                        self._device.grab()
                        logger.info("Exclusive grab acquired on RFID device")
                    except Exception as e:
                        logger.warning(f"Could not grab device exclusively: {e}")

                uid_buffer = []

                if HAS_EVDEV:
                    self._read_evdev_events(uid_buffer)
                else:
                    self._read_raw_events(uid_buffer)

            except OSError as e:
                self._last_status_reason = classify_input_error(e)
                logger.warning(f"RFID device error: {e}, reconnecting in 3s...")
                self._device = None
                time.sleep(3.0)
            except Exception as e:
                self._last_status_reason = classify_input_error(e)
                logger.error(f"RFID unexpected error: {e}")
                self._device = None
                time.sleep(3.0)

    def _read_evdev_events(self, uid_buffer):
        for event in self._device.read_loop():
            if not self._running:
                break

            if event.type != ecodes.EV_KEY:
                continue

            key_event = categorize(event)
            decoded = decode_hid_key_event(event.type, key_event.scancode, key_event.keystate)
            self._process_decoded_key(decoded, uid_buffer)

    def _read_raw_events(self, uid_buffer):
        for event_type, keycode, value in self._device.read_loop():
            if not self._running:
                break
            decoded = decode_hid_key_event(event_type, keycode, value)
            self._process_decoded_key(decoded, uid_buffer)

    def _process_decoded_key(self, decoded, uid_buffer):
        if decoded is None:
            return
        if decoded == "\n":
            uid = "".join(uid_buffer).strip()
            uid_buffer.clear()
            if uid:
                self._process_uid(uid)
            return
        uid_buffer.append(decoded)

    def _process_uid(self, uid: str):
        now = time.time()
        # Debounce
        if uid == self._last_uid and (now - self._last_scan_time) < self._debounce_sec:
            logger.debug(f"RFID debounce: ignoring repeated scan of {uid}")
            return

        self._last_uid = uid
        self._last_scan_time = now
        logger.info(f"RFID scanned: UID={uid}")

        if self._callback:
            try:
                self._callback(uid)
            except Exception as e:
                logger.error(f"RFID callback error: {e}")
