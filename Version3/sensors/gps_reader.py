"""
DrowsiGuard — GPS Reader (BLOCKED — Hardware Not Available)
Reads GPS GY-NEO 6M V2 from UART, parses NMEA ($GPRMC, $GPGGA).
STATUS: BLOCKED BY MISSING HARDWARE
"""
import threading
import errno
import os
import select
import time

from utils.logger import get_logger
import config

logger = get_logger("sensors.gps_reader")


class _StdlibSerial:
    """Small UART reader fallback used when pyserial is unavailable."""

    def __init__(self, port, baudrate, timeout=1.0):
        import termios

        self._termios = termios
        self._timeout = timeout
        self._fd = os.open(port, os.O_RDONLY | os.O_NOCTTY)
        attrs = termios.tcgetattr(self._fd)
        baud = getattr(termios, "B%s" % int(baudrate), termios.B9600)
        attrs[4] = baud
        attrs[5] = baud
        attrs[0] = attrs[0] & ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON)
        attrs[1] = attrs[1] & ~termios.OPOST
        attrs[2] = attrs[2] | termios.CS8
        attrs[3] = attrs[3] & ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
        termios.tcsetattr(self._fd, termios.TCSANOW, attrs)

    def readline(self):
        chunks = []
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            readable, _, _ = select.select([self._fd], [], [], max(0.0, deadline - time.time()))
            if not readable:
                break
            chunk = os.read(self._fd, 1)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk == b"\n":
                break
        return b"".join(chunks)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _open_serial(port, baudrate, timeout=1.0):
    try:
        import serial
    except ImportError:
        return _StdlibSerial(port, baudrate, timeout=timeout)
    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)


def classify_serial_error(exc: Exception) -> str:
    err_no = getattr(exc, "errno", None)
    message = str(exc).lower()
    if isinstance(exc, PermissionError) or err_no in (errno.EACCES, errno.EPERM) or "permission denied" in message:
        return "PERMISSION_DENIED"
    if err_no == errno.EBUSY or "device or resource busy" in message or "resource busy" in message:
        return "PORT_BUSY"
    return "READ_ERROR"


class GPSData:
    __slots__ = ("lat", "lng", "speed", "heading", "fix_ok", "timestamp")

    def __init__(self):
        self.lat = 0.0
        self.lng = 0.0
        self.speed = 0.0
        self.heading = 0.0
        self.fix_ok = False
        self.timestamp = 0.0


def _parse_degrees(raw: str, hemisphere: str) -> float:
    if not raw:
        return 0.0
    dot = raw.find(".")
    degree_digits = dot - 2 if dot >= 0 else len(raw) - 2
    degrees = float(raw[:degree_digits])
    minutes = float(raw[degree_digits:])
    value = degrees + minutes / 60.0
    if hemisphere in ("S", "W"):
        value *= -1
    return value


def parse_nmea_sentence(sentence: str) -> GPSData:
    """Parse a GPRMC/GPGGA NMEA sentence into GPSData."""
    data = GPSData()
    if not sentence:
        return data

    payload = sentence.strip().split("*", 1)[0]
    parts = payload.split(",")
    if not parts:
        return data

    kind = parts[0].lstrip("$")
    try:
        if kind.endswith("GPRMC") or kind.endswith("RMC"):
            if len(parts) < 10 or parts[2] != "A":
                return data
            data.lat = _parse_degrees(parts[3], parts[4])
            data.lng = _parse_degrees(parts[5], parts[6])
            data.speed = float(parts[7] or 0.0) * 1.852
            data.heading = float(parts[8] or 0.0)
            data.fix_ok = True
            data.timestamp = time.time()
        elif kind.endswith("GPGGA") or kind.endswith("GGA"):
            if len(parts) < 7 or int(parts[6] or 0) <= 0:
                return data
            data.lat = _parse_degrees(parts[2], parts[3])
            data.lng = _parse_degrees(parts[4], parts[5])
            data.fix_ok = True
            data.timestamp = time.time()
    except (TypeError, ValueError, IndexError):
        return GPSData()
    return data


class GPSReader:
    """GPS UART reader for NEO-6M."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._latest = GPSData()
        self._module_ok = False
        self._nmea_seen = False
        self._last_nmea_sentence = ""
        self._last_status_reason = "NOT_STARTED"
        self._serial_port = None
        logger.info("GPSReader initialized")

    def start(self):
        if not config.HAS_GPS:
            logger.info("GPS disabled via config (HAS_GPS=False)")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info(f"GPS auto-started reading on {config.GPS_PORT} at {config.GPS_BAUDRATE}")

    def _read_loop(self):
        while self._running:
            try:
                if self._serial_port is None:
                    self._serial_port = _open_serial(config.GPS_PORT, config.GPS_BAUDRATE, timeout=1.0)
                    self._module_ok = True
                    self._last_status_reason = "UART_OPEN"
                
                line = self._serial_port.readline()
                if line:
                    try:
                        sentence = line.decode('ascii', errors='ignore').strip()
                        if sentence.startswith(("$GP", "$GN")):
                            self._nmea_seen = True
                            self._last_nmea_sentence = sentence[:12]
                            self._last_status_reason = "NMEA_NO_FIX"
                        if sentence.startswith('$GPRMC') or sentence.startswith('$GPGGA'):
                            data = parse_nmea_sentence(sentence)
                            if data.fix_ok:
                                self._latest = data
                                self._last_status_reason = "FIX_OK"
                    except Exception as e:
                        pass
                elif not self._nmea_seen:
                    self._last_status_reason = "NO_NMEA"
            except Exception as e:
                self._module_ok = False
                self._last_status_reason = classify_serial_error(e)
                if self._serial_port:
                    self._serial_port.close()
                    self._serial_port = None
                time.sleep(2.0)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._serial_port:
            self._serial_port.close()
            self._serial_port = None
        logger.info("GPS stopped")

    @property
    def latest(self) -> GPSData:
        return self._latest

    @property
    def is_alive(self) -> bool:
        return self._module_ok

    def status(self) -> dict:
        if not config.HAS_GPS:
            return {
                "enabled": False,
                "module_ok": False,
                "nmea_seen": False,
                "fix_ok": False,
                "reason": "DISABLED",
            }
        return {
            "enabled": True,
            "module_ok": bool(self._module_ok),
            "nmea_seen": bool(self._nmea_seen),
            "fix_ok": bool(getattr(self._latest, "fix_ok", False)),
            "reason": self._last_status_reason,
            "last_sentence": self._last_nmea_sentence,
        }

    def read_once(self) -> dict:
        """Single read for testing."""
        if not config.HAS_GPS:
            return {"status": "BLOCKED", "reason": "GPS disabled via config"}

        try:
            with _open_serial(config.GPS_PORT, config.GPS_BAUDRATE, timeout=2.0) as ser:
                nmea_seen = False
                for _ in range(20):
                    line = ser.readline()
                    if line:
                        sentence = line.decode('ascii', errors='ignore').strip()
                        if sentence.startswith(("$GP", "$GN")):
                            nmea_seen = True
                        if sentence.startswith('$GPRMC') or sentence.startswith('$GPGGA'):
                            data = parse_nmea_sentence(sentence)
                            if data.fix_ok:
                                return {
                                    "status": "OK",
                                    "lat": data.lat,
                                    "lng": data.lng,
                                    "speed": data.speed,
                                    "heading": data.heading
                                }
                if nmea_seen:
                    return {"status": "WARN", "reason": "NMEA_NO_FIX", "detail": "NMEA seen but no valid RMC/GGA fix"}
                return {"status": "WARN", "reason": "NO_NMEA", "detail": "No NMEA sentences read from GPS UART"}
        except PermissionError as e:
            return {"status": "ERROR", "reason": "PERMISSION_DENIED", "detail": str(e)}
        except ImportError as e:
            return {"status": "ERROR", "reason": "DEPENDENCY_MISSING", "detail": str(e)}
        except Exception as e:
            return {"status": "ERROR", "reason": classify_serial_error(e), "detail": str(e)}
