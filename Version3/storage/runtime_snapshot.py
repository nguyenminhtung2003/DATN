"""Low-rate camera snapshot writer for the local dashboard."""
import os
import time

import config

try:
    import cv2
except ImportError:
    cv2 = None


class RuntimeSnapshotWriter:
    def __init__(self, runtime_dir=None, min_interval=None, quality=None):
        self.runtime_dir = runtime_dir or getattr(config, "RUNTIME_DIR", None)
        if self.runtime_dir is None:
            self.runtime_dir = os.path.join(os.path.dirname(__file__), "runtime")
        self.snapshot_path = os.path.join(str(self.runtime_dir), "latest.jpg")
        self.tmp_path = self.snapshot_path + ".tmp"
        self.min_interval = min_interval or getattr(config, "DASHBOARD_SNAPSHOT_INTERVAL", 0.75)
        self.quality = int(quality or getattr(config, "DASHBOARD_SNAPSHOT_QUALITY", 65))
        self._last_write = 0.0
        os.makedirs(str(self.runtime_dir), exist_ok=True)

    def maybe_write(self, frame, now=None):
        if frame is None or cv2 is None:
            return None
        now = now if now is not None else time.monotonic()
        if now - self._last_write < self.min_interval:
            return self.snapshot_path
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        if not ok:
            return None
        with open(self.tmp_path, "wb") as fh:
            fh.write(encoded.tobytes())
        os.replace(self.tmp_path, self.snapshot_path)
        self._last_write = now
        return self.snapshot_path
