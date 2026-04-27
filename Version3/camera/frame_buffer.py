"""
DrowsiGuard — Frame Buffer (Shared Read-Only Access)
Holds the latest frame and latest good-face frame for consumers.
Only CameraProducer writes here. All other modules read only.
"""
import threading
import time

from utils.logger import get_logger

logger = get_logger("camera.frame_buffer")


class FrameBuffer:
    """Thread-safe shared frame store.

    Attributes updated by the camera producer:
        latest_frame       — most recent raw frame
        latest_timestamp   — time.time() of latest frame
        latest_frame_id    — monotonic frame counter

    Attributes updated by face_analyzer when a good face is detected:
        latest_good_face_frame — frame containing a well-detected face
        latest_face_bbox       — (x, y, w, h) of the face region
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._timestamp = 0.0
        self._frame_id = 0

        self._good_face_frame = None
        self._good_face_ts = 0.0
        self._face_bbox = None

    # ── Producer writes ─────────────────────────────────────

    def update_frame(self, frame, frame_id: int, timestamp: float):
        with self._lock:
            self._frame = frame
            self._frame_id = frame_id
            self._timestamp = timestamp

    def update_good_face(self, frame, bbox: tuple, timestamp: float = None):
        with self._lock:
            self._good_face_frame = frame
            self._face_bbox = bbox
            self._good_face_ts = timestamp or time.time()

    # ── Consumer reads ──────────────────────────────────────

    def get_frame(self):
        """Return (frame_copy, frame_id, timestamp) or (None, 0, 0.0)."""
        with self._lock:
            if self._frame is not None:
                return self._frame.copy(), self._frame_id, self._timestamp
        return None, 0, 0.0

    def get_good_face_frame(self):
        """Return (frame_copy, bbox, timestamp) or (None, None, 0.0)."""
        with self._lock:
            if self._good_face_frame is not None:
                return self._good_face_frame.copy(), self._face_bbox, self._good_face_ts
        return None, None, 0.0

    @property
    def has_recent_frame(self) -> bool:
        """True if a frame arrived in the last 2 seconds."""
        with self._lock:
            return (time.time() - self._timestamp) < 2.0 if self._timestamp else False

    @property
    def frame_age(self) -> float:
        """Seconds since last frame update."""
        with self._lock:
            return time.time() - self._timestamp if self._timestamp else float("inf")
