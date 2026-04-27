"""
DrowsiGuard — CSI Camera Capture (Single Owner)
Only this module opens the physical camera via GStreamer.
All other modules MUST read from FrameBuffer.
"""
import threading
import time

try:
    import cv2
except ImportError:
    cv2 = None

from utils.logger import get_logger
import config

logger = get_logger("camera.capture")


class CSICamera:
    """Single-owner CSI camera using GStreamer pipeline on Jetson Nano."""

    def __init__(self, pipeline: str = None, target_fps: int = None):
        self._pipeline = pipeline or config.GSTREAMER_PIPELINE
        self._target_fps = target_fps or config.CAMERA_FPS
        self._cap = None
        self._running = False
        self._lock = threading.Lock()
        self._frame = None
        self._frame_id = 0
        self._timestamp = 0.0
        self._fps_actual = 0.0
        self._thread = None
        self._reconnect_delay = config.CAMERA_RECONNECT_DELAY

    # ── Public API ──────────────────────────────────────────

    def start(self):
        """Open camera and begin capture thread."""
        if self._running:
            logger.warning("Camera already running")
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True,
                                        name="camera-capture")
        self._thread.start()
        logger.info("Camera capture thread started")

    def stop(self):
        """Stop capture and release camera."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        self._release()
        logger.info("Camera stopped")

    def read(self):
        """Return (frame, frame_id, timestamp) or (None, 0, 0)."""
        with self._lock:
            if self._frame is not None:
                return self._frame.copy(), self._frame_id, self._timestamp
        return None, 0, 0.0

    @property
    def is_alive(self) -> bool:
        return self._running and self._cap is not None and self._cap.isOpened()

    @property
    def fps(self) -> float:
        return self._fps_actual

    @property
    def frame_id(self) -> int:
        return self._frame_id

    # ── Internal ────────────────────────────────────────────

    def _open(self) -> bool:
        if cv2 is None:
            logger.error("OpenCV is not installed; CSI camera cannot open")
            return False
        self._release()
        logger.info("Opening CSI camera via GStreamer...")
        try:
            self._cap = cv2.VideoCapture(self._pipeline, cv2.CAP_GSTREAMER)
            if self._cap.isOpened():
                logger.info("Camera opened successfully")
                return True
            else:
                logger.error("cv2.VideoCapture opened but isOpened() is False")
                return False
        except Exception as e:
            logger.error(f"Failed to open camera: {e}")
            return False

    def _release(self):
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _capture_loop(self):
        fps_counter = 0
        fps_timer = time.monotonic()

        while self._running:
            # Ensure camera is open
            if self._cap is None or not self._cap.isOpened():
                if not self._open():
                    logger.warning(f"Camera not available, reconnecting in {self._reconnect_delay}s...")
                    time.sleep(self._reconnect_delay)
                    continue

            ret, frame = self._cap.read()
            if not ret or frame is None:
                logger.warning("Camera read failed, will reconnect")
                self._release()
                continue

            now = time.monotonic()
            with self._lock:
                self._frame = frame
                self._frame_id += 1
                self._timestamp = time.time()

            # FPS tracking
            fps_counter += 1
            elapsed = now - fps_timer
            if elapsed >= 1.0:
                self._fps_actual = fps_counter / elapsed
                fps_counter = 0
                fps_timer = now

        self._release()
