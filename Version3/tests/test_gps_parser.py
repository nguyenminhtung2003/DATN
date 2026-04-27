import unittest
import errno
from unittest.mock import patch

import config
from sensors.gps_reader import GPSReader, parse_nmea_sentence


class GPSParserTest(unittest.TestCase):
    def test_parse_valid_gprmc_sentence(self):
        sentence = "$GPRMC,092204.999,A,4250.5589,N,07106.8278,W,0.13,309.62,120598,,,A*10"

        data = parse_nmea_sentence(sentence)

        self.assertTrue(data.fix_ok)
        self.assertAlmostEqual(data.lat, 42 + 50.5589 / 60, places=6)
        self.assertAlmostEqual(data.lng, -(71 + 6.8278 / 60), places=6)
        self.assertAlmostEqual(data.speed, 0.13 * 1.852, places=3)
        self.assertAlmostEqual(data.heading, 309.62, places=2)

    def test_parse_invalid_or_no_fix_sentence(self):
        sentence = "$GPRMC,092204.999,V,4250.5589,N,07106.8278,W,0.13,309.62,120598,,,A*10"

        data = parse_nmea_sentence(sentence)

        self.assertFalse(data.fix_ok)

    def test_read_once_reports_permission_denied_clearly(self):
        class FakeSerialModule:
            SerialException = Exception

            class Serial:
                def __init__(self, *args, **kwargs):
                    raise PermissionError("Permission denied: '/dev/ttyTHS1'")

        original_has_gps = config.HAS_GPS
        config.HAS_GPS = True
        try:
            with patch.dict("sys.modules", {"serial": FakeSerialModule}):
                result = GPSReader().read_once()
        finally:
            config.HAS_GPS = original_has_gps

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["reason"], "PERMISSION_DENIED")
        self.assertIn("/dev/ttyTHS1", result["detail"])

    def test_read_once_reports_no_nmea_separately_from_no_fix(self):
        class FakeSerialPort:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def readline(self):
                return b"noise\r\n"

        class FakeSerialModule:
            SerialException = Exception

            @staticmethod
            def Serial(*args, **kwargs):
                return FakeSerialPort()

        original_has_gps = config.HAS_GPS
        config.HAS_GPS = True
        try:
            with patch.dict("sys.modules", {"serial": FakeSerialModule}):
                result = GPSReader().read_once()
        finally:
            config.HAS_GPS = original_has_gps

        self.assertEqual(result["status"], "WARN")
        self.assertEqual(result["reason"], "NO_NMEA")

    def test_read_once_reports_nmea_without_fix_separately(self):
        class FakeSerialPort:
            def __init__(self):
                self._lines = [
                    b"$GPRMC,092204.999,V,4250.5589,N,07106.8278,W,0.13,309.62,120598,,,A*10\r\n",
                    b"",
                ]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def readline(self):
                return self._lines.pop(0) if self._lines else b""

        class FakeSerialModule:
            SerialException = Exception

            @staticmethod
            def Serial(*args, **kwargs):
                return FakeSerialPort()

        original_has_gps = config.HAS_GPS
        config.HAS_GPS = True
        try:
            with patch.dict("sys.modules", {"serial": FakeSerialModule}):
                result = GPSReader().read_once()
        finally:
            config.HAS_GPS = original_has_gps

        self.assertEqual(result["status"], "WARN")
        self.assertEqual(result["reason"], "NMEA_NO_FIX")

    def test_read_once_reports_port_busy_clearly(self):
        class FakeSerialModule:
            SerialException = Exception

            @staticmethod
            def Serial(*args, **kwargs):
                raise OSError(errno.EBUSY, "Device or resource busy")

        original_has_gps = config.HAS_GPS
        config.HAS_GPS = True
        try:
            with patch.dict("sys.modules", {"serial": FakeSerialModule}):
                result = GPSReader().read_once()
        finally:
            config.HAS_GPS = original_has_gps

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["reason"], "PORT_BUSY")


if __name__ == "__main__":
    unittest.main()
