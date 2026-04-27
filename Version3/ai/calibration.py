"""Driver-specific calibration for drowsiness thresholds.

The calibration step keeps fixed safety defaults available while adapting EAR,
MAR and pitch thresholds to the current driver/camera placement.
"""
import statistics

import config


FALLBACK_EAR_CLOSED = 0.24
FALLBACK_MAR_YAWN = 0.45
FALLBACK_PITCH_NEUTRAL = 0.0
FALLBACK_PITCH_DOWN = -15.0
MIN_FACE_HEIGHT = 160


def _clamp(value, low, high):
    return max(low, min(high, value))


class CalibrationSample:
    def __init__(
        self,
        face_present,
        ear,
        mar,
        pitch,
        face_bbox,
        timestamp,
        left_ear=None,
        right_ear=None,
        ear_used=None,
        eye_quality=None,
    ):
        self.face_present = bool(face_present)
        self.ear = float(ear or 0.0)
        self.mar = float(mar or 0.0)
        self.pitch = float(pitch or 0.0)
        self.face_bbox = face_bbox
        self.timestamp = float(timestamp or 0.0)
        self.left_ear = self.ear if left_ear is None else float(left_ear or 0.0)
        self.right_ear = self.ear if right_ear is None else float(right_ear or 0.0)
        self.ear_used = self.ear if ear_used is None else float(ear_used or 0.0)
        self.eye_quality = dict(eye_quality or {"usable": True, "selected": "both", "reason": "OK"})

    @property
    def face_height(self):
        if not self.face_bbox or len(self.face_bbox) < 4:
            return 0.0
        return float(self.face_bbox[3] or 0.0)


class CalibrationProfile:
    def __init__(
        self,
        valid=False,
        reason="NOT_ENOUGH_SAMPLES",
        ear_open_median=None,
        mar_closed_median=None,
        pitch_neutral=None,
        ear_closed_threshold=None,
        mar_yawn_threshold=None,
        pitch_down_threshold=None,
        sample_count=0,
        face_height_median=None,
        left_ear_open_median=None,
        right_ear_open_median=None,
        ear_used_open_median=None,
    ):
        self.valid = bool(valid)
        self.reason = reason
        self.ear_open_median = ear_open_median
        self.mar_closed_median = mar_closed_median
        self.pitch_neutral = FALLBACK_PITCH_NEUTRAL if pitch_neutral is None else float(pitch_neutral)
        self.ear_closed_threshold = (
            FALLBACK_EAR_CLOSED if ear_closed_threshold is None else float(ear_closed_threshold)
        )
        self.mar_yawn_threshold = FALLBACK_MAR_YAWN if mar_yawn_threshold is None else float(mar_yawn_threshold)
        self.pitch_down_threshold = (
            FALLBACK_PITCH_DOWN if pitch_down_threshold is None else float(pitch_down_threshold)
        )
        self.sample_count = int(sample_count or 0)
        self.face_height_median = face_height_median
        self.left_ear_open_median = left_ear_open_median
        self.right_ear_open_median = right_ear_open_median
        self.ear_used_open_median = ear_used_open_median

    @classmethod
    def fallback(cls, reason="NOT_ENOUGH_SAMPLES", sample_count=0):
        return cls(
            valid=False,
            reason=reason,
            ear_open_median=None,
            mar_closed_median=None,
            pitch_neutral=FALLBACK_PITCH_NEUTRAL,
            ear_closed_threshold=getattr(config, "EAR_THRESHOLD", FALLBACK_EAR_CLOSED),
            mar_yawn_threshold=getattr(config, "MAR_THRESHOLD", FALLBACK_MAR_YAWN),
            pitch_down_threshold=getattr(config, "PITCH_DELTA_THRESHOLD", FALLBACK_PITCH_DOWN),
            sample_count=sample_count,
            face_height_median=None,
            left_ear_open_median=None,
            right_ear_open_median=None,
            ear_used_open_median=None,
        )

    def to_dict(self, active=False):
        return {
            "active": bool(active),
            "valid": self.valid,
            "reason": self.reason,
            "sample_count": self.sample_count,
            "ear_open_median": self.ear_open_median,
            "mar_closed_median": self.mar_closed_median,
            "pitch_neutral": self.pitch_neutral,
            "ear_closed_threshold": self.ear_closed_threshold,
            "mar_yawn_threshold": self.mar_yawn_threshold,
            "pitch_down_threshold": self.pitch_down_threshold,
            "face_height_median": self.face_height_median,
            "left_ear_open_median": self.left_ear_open_median,
            "right_ear_open_median": self.right_ear_open_median,
            "ear_used_open_median": self.ear_used_open_median,
        }


class DriverCalibrator:
    def __init__(self, duration_sec=None, min_samples=None, min_face_height=None):
        self.duration_sec = float(duration_sec if duration_sec is not None else getattr(config, "CALIBRATION_DURATION", 7.0))
        self.min_samples = int(min_samples if min_samples is not None else getattr(config, "CALIBRATION_MIN_SAMPLES", 30))
        self.min_face_height = int(min_face_height if min_face_height is not None else MIN_FACE_HEIGHT)
        self._samples = []
        self._started_at = None
        self._profile = None

    def add(self, metrics, timestamp):
        if self._started_at is None:
            self._started_at = float(timestamp or 0.0)
        sample = CalibrationSample(
            face_present=getattr(metrics, "face_present", False),
            ear=getattr(metrics, "ear", 0.0),
            mar=getattr(metrics, "mar", 0.0),
            pitch=getattr(metrics, "pitch", 0.0),
            face_bbox=getattr(metrics, "face_bbox", None),
            timestamp=timestamp,
            left_ear=getattr(metrics, "left_ear", getattr(metrics, "ear", 0.0)),
            right_ear=getattr(metrics, "right_ear", getattr(metrics, "ear", 0.0)),
            ear_used=getattr(metrics, "ear_used", getattr(metrics, "ear", 0.0)),
            eye_quality=getattr(metrics, "eye_quality", None),
        )
        if self._is_valid_sample(sample):
            self._samples.append(sample)
            self._profile = None

    @property
    def ready(self):
        return self.profile.valid

    def complete(self, timestamp=None):
        if self.profile.valid:
            return True
        if self.sample_count >= self.min_samples and self.profile.reason != "NOT_ENOUGH_SAMPLES":
            return True
        if self._started_at is None or timestamp is None:
            return False
        return float(timestamp or 0.0) - self._started_at >= self.duration_sec

    @property
    def sample_count(self):
        return len(self._samples)

    @property
    def profile(self):
        if self._profile is None:
            self._profile = self._build_profile()
        return self._profile

    def reset(self):
        self._samples = []
        self._started_at = None
        self._profile = None

    def _is_valid_sample(self, sample):
        if not sample.face_present or not sample.face_bbox:
            return False
        if not bool((sample.eye_quality or {}).get("usable", True)):
            return False
        return True

    def _build_profile(self):
        count = len(self._samples)
        if count < self.min_samples:
            return CalibrationProfile.fallback(reason="NOT_ENOUGH_SAMPLES", sample_count=count)

        ears = [s.ear_used for s in self._samples]
        left_ears = [s.left_ear for s in self._samples]
        right_ears = [s.right_ear for s in self._samples]
        mars = [s.mar for s in self._samples]
        pitches = [s.pitch for s in self._samples]
        heights = [s.face_height for s in self._samples]

        ear_open = float(statistics.median(ears))
        left_ear_open = float(statistics.median(left_ears))
        right_ear_open = float(statistics.median(right_ears))
        mar_closed = float(statistics.median(mars))
        pitch_neutral = float(statistics.median(pitches))
        face_height = float(statistics.median(heights))

        if face_height < self.min_face_height:
            return CalibrationProfile.fallback(reason="FACE_TOO_SMALL", sample_count=count)
        if ear_open < 0.25:
            return CalibrationProfile.fallback(reason="LOW_EAR_BASELINE", sample_count=count)
        if mar_closed > 0.35:
            return CalibrationProfile.fallback(reason="HIGH_MAR_BASELINE", sample_count=count)

        ear_closed = _clamp(min(FALLBACK_EAR_CLOSED, ear_open - 0.02), 0.20, FALLBACK_EAR_CLOSED)
        mar_yawn = _clamp(max(FALLBACK_MAR_YAWN, mar_closed + 0.18), FALLBACK_MAR_YAWN, 0.65)
        pitch_down = pitch_neutral - 15.0

        return CalibrationProfile(
            valid=True,
            reason="OK",
            ear_open_median=ear_open,
            mar_closed_median=mar_closed,
            pitch_neutral=pitch_neutral,
            ear_closed_threshold=ear_closed,
            mar_yawn_threshold=mar_yawn,
            pitch_down_threshold=pitch_down,
            sample_count=count,
            face_height_median=face_height,
            left_ear_open_median=left_ear_open,
            right_ear_open_median=right_ear_open,
            ear_used_open_median=ear_open,
        )
