"""
DrowsiGuard — Face Analyzer (MediaPipe Face Mesh)
Computes EAR, MAR, Head Pose (pitch), confidence, and PERCLOS.
Runs on frames from FrameBuffer. Does NOT own camera.
"""
import math
import time
from collections import deque

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mediapipe as mp
except ImportError:
    mp = None

from utils.logger import get_logger
import config

logger = get_logger("camera.face_analyzer")

# ─── Landmark Indices ────────────────────────────────────
# Left eye
L_EYE = [362, 385, 387, 263, 373, 380]
# Right eye
R_EYE = [33, 160, 158, 133, 153, 144]
# Mouth
MOUTH = [13, 14, 78, 308, 81, 311]
MOUTH_OUTLINE = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
MOUTH_MAR_CORE = [78, 308, 13, 14]
# Head pose reference points (nose tip, chin, left/right eye corner, left/right mouth corner)
POSE_POINTS = [1, 152, 33, 263, 61, 291]

# 3D model points (generic face model) for solvePnP
_MODEL_POINTS_RAW = [
    (0.0, 0.0, 0.0),        # Nose tip
    (0.0, -330.0, -65.0),   # Chin
    (-225.0, 170.0, -135.0),  # Left eye left corner
    (225.0, 170.0, -135.0),   # Right eye right corner
    (-150.0, -150.0, -125.0), # Left mouth corner
    (150.0, -150.0, -125.0),  # Right mouth corner
]
MODEL_POINTS = np.array(_MODEL_POINTS_RAW, dtype=np.float64) if np is not None else _MODEL_POINTS_RAW


def _dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def _ema(prev, cur, alpha):
    if prev is None:
        return cur
    return alpha * cur + (1 - alpha) * prev


def _normalize_pitch_angle(angle):
    if angle > 90.0:
        return angle - 180.0
    if angle < -90.0:
        return angle + 180.0
    return angle


def _mouth_aspect_ratio(left_corner, right_corner, upper_lip, lower_lip):
    mouth_width = _dist(left_corner, right_corner)
    mouth_opening = _dist(upper_lip, lower_lip)
    if mouth_width < 1e-6:
        return 0.0
    return mouth_opening / mouth_width


def _empty_eye_quality(reason="NO_FACE"):
    side = {"usable": False, "score": 0.0, "reason": reason, "glare_ratio": 0.0}
    return {
        "left": dict(side),
        "right": dict(side),
        "selected": "none",
        "usable": False,
        "reason": reason,
        "ear_used": 0.0,
    }


def _eye_bbox(points, margin=2):
    if not points:
        return (0, 0, 0, 0)
    xs = [int(p[0]) for p in points]
    ys = [int(p[1]) for p in points]
    x1 = min(xs) - int(margin)
    y1 = min(ys) - int(margin)
    x2 = max(xs) + int(margin)
    y2 = max(ys) + int(margin)
    return (x1, y1, max(0, x2 - x1), max(0, y2 - y1))


def _glare_ratio(frame, bbox):
    if np is None or frame is None or not hasattr(frame, "shape") or not bbox:
        return 0.0
    height, width = frame.shape[:2]
    x, y, box_w, box_h = bbox
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(width, int(x + box_w))
    y2 = min(height, int(y + box_h))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    crop = frame[y1:y2, x1:x2]
    if not hasattr(crop, "size") or crop.size <= 0:
        return 0.0
    if len(crop.shape) == 3:
        brightness = crop.max(axis=2)
    else:
        brightness = crop
    threshold = int(getattr(config, "EYE_GLARE_PIXEL_THRESHOLD", 245))
    return float((brightness >= threshold).sum()) / float(brightness.size)


def _eye_side_quality(frame, points, ear):
    bbox = _eye_bbox(points)
    width = bbox[2]
    glare = _glare_ratio(frame, bbox)
    score = 1.0
    usable = True
    reason = "OK"
    if width < getattr(config, "EYE_MIN_WIDTH_PX", 8):
        usable = False
        reason = "TOO_SMALL"
        score = 0.0
    elif ear < getattr(config, "EYE_EAR_MIN", 0.05) or ear > getattr(config, "EYE_EAR_MAX", 0.45):
        usable = False
        reason = "EAR_OUT_OF_RANGE"
        score = 0.0
    elif glare >= getattr(config, "EYE_GLARE_RATIO_THRESHOLD", 0.55):
        usable = False
        reason = "GLARE"
        score = max(0.0, 1.0 - glare)
    return {
        "usable": bool(usable),
        "score": float(score),
        "reason": reason,
        "glare_ratio": float(glare),
    }


def _build_eye_quality(frame, left_points, right_points, left_ear, right_ear):
    left = _eye_side_quality(frame, left_points, float(left_ear or 0.0))
    right = _eye_side_quality(frame, right_points, float(right_ear or 0.0))
    left_ok = bool(left["usable"])
    right_ok = bool(right["usable"])

    if left_ok and right_ok:
        asymmetry = abs(float(left_ear or 0.0) - float(right_ear or 0.0))
        if asymmetry > getattr(config, "EYE_ASYMMETRY_THRESHOLD", 0.12):
            if float(left_ear or 0.0) >= float(right_ear or 0.0):
                return {
                    "left": left,
                    "right": right,
                    "selected": "left",
                    "usable": True,
                    "reason": "ASYMMETRIC",
                    "ear_used": float(left_ear or 0.0),
                }
            return {
                "left": left,
                "right": right,
                "selected": "right",
                "usable": True,
                "reason": "ASYMMETRIC",
                "ear_used": float(right_ear or 0.0),
            }
        return {
            "left": left,
            "right": right,
            "selected": "both",
            "usable": True,
            "reason": "OK",
            "ear_used": (float(left_ear or 0.0) + float(right_ear or 0.0)) / 2.0,
        }
    if left_ok:
        return {
            "left": left,
            "right": right,
            "selected": "left",
            "usable": True,
            "reason": "RIGHT_%s" % right["reason"],
            "ear_used": float(left_ear or 0.0),
        }
    if right_ok:
        return {
            "left": left,
            "right": right,
            "selected": "right",
            "usable": True,
            "reason": "LEFT_%s" % left["reason"],
            "ear_used": float(right_ear or 0.0),
        }
    return {
        "left": left,
        "right": right,
        "selected": "none",
        "usable": False,
        "reason": "BOTH_UNRELIABLE",
        "ear_used": 0.0,
    }


def _build_face_quality(face_bbox, frame_width, frame_height, confidence):
    if not face_bbox:
        return {
            "face_height": 0,
            "face_width": 0,
            "face_area_ratio": 0.0,
            "landmark_confidence": float(confidence or 0.0),
            "usable": False,
            "reason": "NO_FACE",
        }
    x, y, width, height = face_bbox
    area = float(max(0, width) * max(0, height))
    frame_area = float(max(1, frame_width) * max(1, frame_height))
    area_ratio = area / frame_area
    usable = True
    reason = "OK"
    if height < getattr(config, "FACE_MIN_HEIGHT_PX", 160):
        usable = False
        reason = "FACE_TOO_SMALL"
    elif confidence < getattr(config, "FACE_MIN_LANDMARK_CONFIDENCE", 0.20):
        usable = False
        reason = "LOW_LANDMARK_CONFIDENCE"
    return {
        "face_height": int(height),
        "face_width": int(width),
        "face_area_ratio": area_ratio,
        "landmark_confidence": float(confidence or 0.0),
        "usable": usable,
        "reason": reason,
    }


class FaceMetrics:
    """Data class holding per-frame analysis results."""
    __slots__ = (
        "face_present", "ear", "mar", "pitch", "confidence",
        "face_bbox", "raw_ear", "raw_mar", "raw_pitch",
        "left_eye_points", "right_eye_points", "mouth_points", "face_quality",
        "left_ear", "right_ear", "raw_left_ear", "raw_right_ear",
        "ear_used", "eye_quality",
    )

    def __init__(self):
        self.face_present = False
        self.ear = 0.0
        self.mar = 0.0
        self.pitch = 0.0
        self.confidence = 0.0
        self.face_bbox = None
        self.raw_ear = 0.0
        self.raw_mar = 0.0
        self.raw_pitch = 0.0
        self.left_eye_points = []
        self.right_eye_points = []
        self.mouth_points = []
        self.face_quality = _build_face_quality(None, 0, 0, 0.0)
        self.left_ear = 0.0
        self.right_ear = 0.0
        self.raw_left_ear = 0.0
        self.raw_right_ear = 0.0
        self.ear_used = 0.0
        self.eye_quality = _empty_eye_quality("NO_FACE")


class FaceAnalyzer:
    """MediaPipe Face Mesh based drowsiness analyzer."""

    def __init__(self):
        if np is None:
            raise ImportError("numpy is not installed")
        if cv2 is None:
            raise ImportError("opencv-python is not installed")
        if mp is None:
            raise ImportError("mediapipe is not installed")

        self._face_mesh = self._create_face_mesh()

        # Smoothed values
        self._ear_smooth = None
        self._mar_smooth = None
        self._pitch_smooth = None

        # PERCLOS tracking
        self._perclos_window = deque(maxlen=max(1, int(config.PERCLOS_WINDOW * config.AI_TARGET_FPS)))

        # Performance
        self._process_time = 0.0

        logger.info("FaceAnalyzer initialized with MediaPipe Face Mesh")

    def _create_face_mesh(self):
        kwargs = {
            "max_num_faces": config.MAX_NUM_FACES,
            "refine_landmarks": True,
            "min_detection_confidence": config.FACE_MESH_MIN_DETECTION_CONFIDENCE,
            "min_tracking_confidence": config.FACE_MESH_MIN_TRACKING_CONFIDENCE,
        }
        try:
            return mp.solutions.face_mesh.FaceMesh(**kwargs)
        except TypeError as exc:
            if "refine_landmarks" not in str(exc):
                raise
            logger.warning("MediaPipe build does not support refine_landmarks; retrying without it")
            kwargs.pop("refine_landmarks", None)
            return mp.solutions.face_mesh.FaceMesh(**kwargs)

    def analyze(self, frame) -> FaceMetrics:
        """Process a single BGR frame and return FaceMetrics."""
        metrics = FaceMetrics()
        if frame is None:
            return metrics

        t0 = time.monotonic()
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            return metrics

        face = results.multi_face_landmarks[0]
        lm = face.landmark

        # ── Confidence check ────────────────────────────────
        # Use detection score approximation from landmark visibility
        vis_sum = sum(lm[i].visibility for i in POSE_POINTS if hasattr(lm[i], 'visibility'))
        metrics.confidence = vis_sum / len(POSE_POINTS) if vis_sum else 0.5

        # ── Convert to pixel coords ────────────────────────
        def px(idx):
            return (lm[idx].x * w, lm[idx].y * h)

        def pxi(idx):
            return (int(lm[idx].x * w), int(lm[idx].y * h))

        # ── EAR (Eye Aspect Ratio) ──────────────────────────
        def ear_single(indices):
            p = [px(i) for i in indices]
            v1 = _dist(p[1], p[5])
            v2 = _dist(p[2], p[4])
            h_dist = _dist(p[0], p[3])
            if h_dist < 1e-6:
                return 0.3
            return (v1 + v2) / (2.0 * h_dist)

        ear_l = ear_single(L_EYE)
        ear_r = ear_single(R_EYE)
        left_eye_points = [pxi(i) for i in L_EYE]
        right_eye_points = [pxi(i) for i in R_EYE]
        eye_quality = _build_eye_quality(frame, left_eye_points, right_eye_points, ear_l, ear_r)
        raw_ear = float(eye_quality.get("ear_used", 0.0) or 0.0)

        # ── MAR (Mouth Aspect Ratio) ────────────────────────
        mp_pts = [px(i) for i in MOUTH_MAR_CORE]
        raw_mar = _mouth_aspect_ratio(mp_pts[0], mp_pts[1], mp_pts[2], mp_pts[3])

        # ── Head Pose (Pitch) ───────────────────────────────
        image_points = np.array([px(i) for i in POSE_POINTS], dtype=np.float64)
        focal_length = w
        center = (w / 2, h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        success, rotation_vec, _ = cv2.solvePnP(
            MODEL_POINTS, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        raw_pitch = 0.0
        if success:
            rmat, _ = cv2.Rodrigues(rotation_vec)
            angles = cv2.decomposeProjectionMatrix(
                np.hstack((rmat, np.zeros((3, 1))))
            )[6]
            raw_pitch = _normalize_pitch_angle(float(angles[0]))

        # ── Smoothing ───────────────────────────────────────
        if eye_quality.get("usable"):
            self._ear_smooth = _ema(self._ear_smooth, raw_ear, config.EAR_SMOOTHING_ALPHA)
        elif self._ear_smooth is None:
            self._ear_smooth = 0.0
        self._mar_smooth = _ema(self._mar_smooth, raw_mar, config.MAR_SMOOTHING_ALPHA)
        self._pitch_smooth = _ema(self._pitch_smooth, raw_pitch, config.PITCH_SMOOTHING_ALPHA)

        # ── PERCLOS ─────────────────────────────────────────
        if eye_quality.get("usable"):
            eye_closed = 1 if self._ear_smooth < config.EAR_THRESHOLD else 0
            self._perclos_window.append(eye_closed)

        # ── Bounding box ────────────────────────────────────
        xs = [l.x for l in lm]
        ys = [l.y for l in lm]
        x_min, x_max = int(min(xs) * w), int(max(xs) * w)
        y_min, y_max = int(min(ys) * h), int(max(ys) * h)
        metrics.face_bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
        metrics.left_eye_points = left_eye_points
        metrics.right_eye_points = right_eye_points
        metrics.mouth_points = [pxi(i) for i in MOUTH_OUTLINE]
        metrics.face_quality = _build_face_quality(metrics.face_bbox, w, h, metrics.confidence)

        # ── Populate metrics ────────────────────────────────
        metrics.face_present = True
        metrics.ear = self._ear_smooth
        metrics.left_ear = ear_l
        metrics.right_ear = ear_r
        metrics.ear_used = self._ear_smooth
        metrics.mar = self._mar_smooth
        metrics.pitch = self._pitch_smooth
        metrics.raw_ear = raw_ear
        metrics.raw_left_ear = ear_l
        metrics.raw_right_ear = ear_r
        metrics.raw_mar = raw_mar
        metrics.raw_pitch = raw_pitch
        metrics.eye_quality = eye_quality

        self._process_time = time.monotonic() - t0
        return metrics

    @property
    def perclos(self) -> float:
        """PERCLOS over sliding window (0.0 ~ 1.0)."""
        if not self._perclos_window:
            return 0.0
        return sum(self._perclos_window) / len(self._perclos_window)

    @property
    def process_time_ms(self) -> float:
        return self._process_time * 1000

    def release(self):
        if self._face_mesh:
            self._face_mesh.close()
            logger.info("FaceAnalyzer released")
