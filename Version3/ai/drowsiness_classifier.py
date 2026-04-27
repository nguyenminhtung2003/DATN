"""State-machine drowsiness classifier for Jetson Nano.

The classifier is intentionally rule-based and temporal. MediaPipe supplies
frame-level metrics; this module turns them into driver states and alert hints.
"""
import time
from collections import deque

import config
from .calibration import CalibrationProfile
from .feature_extractor import FeatureExtractor
from .threshold_policy import ThresholdPolicy
from utils.logger import get_logger

logger = get_logger("ai.classifier")


class AIState:
    UNKNOWN = "UNKNOWN"
    NORMAL = "NORMAL"
    BLINK = "BLINK"
    EYES_CLOSED = "EYES_CLOSED"
    DROWSY = "DROWSY"
    YAWNING = "YAWNING"
    HEAD_DOWN = "HEAD_DOWN"
    NO_FACE = "NO_FACE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class DrowsinessClassifier:
    def __init__(self, window_seconds=None, target_fps=None, profile=None):
        self._target_fps = float(target_fps or getattr(config, "AI_TARGET_FPS", 10.0) or 10.0)
        window_seconds = float(window_seconds or getattr(config, "AI_CLASSIFIER_WINDOW_SECONDS", 2.0) or 2.0)
        maxlen = max(5, int(window_seconds * self._target_fps))
        self._samples = deque(maxlen=maxlen)
        self._perclos_short = deque(maxlen=max(1, int(2.0 * self._target_fps)))
        self._perclos_long = deque(maxlen=max(1, int(30.0 * self._target_fps)))
        self._profile = profile or CalibrationProfile.fallback(reason="FALLBACK")
        self._eyes_closed_frames = 0
        self._mouth_open_frames = 0
        self._head_down_frames = 0
        self._no_face_frames = 0
        self._yawn_times = deque()
        self._last_result = self._result(AIState.UNKNOWN, 0.0, "No samples yet", alert_hint=0)

    def set_profile(self, profile):
        self._profile = profile or CalibrationProfile.fallback(reason="FALLBACK")
        self.reset_state()

    def reset_state(self):
        self._samples.clear()
        self._perclos_short.clear()
        self._perclos_long.clear()
        self._last_result = self._result(AIState.UNKNOWN, 0.0, "No samples yet", alert_hint=0)
        self._eyes_closed_frames = 0
        self._mouth_open_frames = 0
        self._head_down_frames = 0
        self._no_face_frames = 0
        self._yawn_times.clear()

    def update(self, metrics):
        start_time = time.time()
        sample = self._coerce_sample(metrics)
        self._samples.append(sample)

        state, confidence, reason, alert_hint = self._classify_sample(sample, start_time)
        features = self._features(sample)
        result = self._result(
            state,
            confidence,
            reason,
            features=features,
            latency_ms=(time.time() - start_time) * 1000.0,
            alert_hint=alert_hint,
        )
        self._last_result = result
        if state != AIState.UNKNOWN:
            logger.debug(
                "AI Decision: %s | Conf: %.2f | Alert: %s | Reason: %s",
                state,
                confidence,
                alert_hint,
                reason,
            )
        return result

    @property
    def last_result(self):
        return dict(self._last_result)

    def _coerce_sample(self, metrics):
        metrics = metrics or {}
        face_quality = metrics.get("face_quality") or {}
        eye_quality = metrics.get("eye_quality") or {"usable": True, "selected": "both", "reason": "OK"}
        usable = bool(face_quality.get("usable", True))
        eye_usable = bool(eye_quality.get("usable", True))
        face_present = bool(metrics.get("face_present", False))
        return {
            "face_present": face_present,
            "usable": bool(face_present and usable and eye_usable),
            "face_quality": face_quality,
            "eye_quality": eye_quality,
            "face_confidence": float(metrics.get("face_confidence", face_quality.get("landmark_confidence", 1.0)) or 0.0),
            "ear": float(metrics.get("ear_used", metrics.get("ear", 0.0)) or 0.0),
            "left_ear": float(metrics.get("left_ear", metrics.get("ear", 0.0)) or 0.0),
            "right_ear": float(metrics.get("right_ear", metrics.get("ear", 0.0)) or 0.0),
            "mar": float(metrics.get("mar", 0.0) or 0.0),
            "pitch": float(metrics.get("pitch", 0.0) or 0.0),
        }

    def _classify_sample(self, sample, now):
        thresholds = self._thresholds()
        ear_low = sample["usable"] and sample["ear"] < thresholds["ear_closed"]
        mouth_open = sample["usable"] and sample["mar"] > thresholds["mar_yawn"]
        head_down = sample["usable"] and sample["pitch"] <= thresholds["pitch_down"]

        if not sample["face_present"]:
            self._no_face_frames += 1
        else:
            self._no_face_frames = 0

        if not sample["usable"]:
            self._eyes_closed_frames = 0
            self._mouth_open_frames = 0
            self._head_down_frames = 0
            no_face_sec = self._duration(self._no_face_frames)
            if not sample["face_present"] and no_face_sec >= 0.7:
                alert_hint = 1 if no_face_sec >= 1.5 else 0
                return AIState.NO_FACE, 0.85, "No usable face for %.1fs" % no_face_sec, alert_hint
            reason = sample["face_quality"].get("reason", "Low face quality")
            if sample["face_present"] and not sample["eye_quality"].get("usable", True):
                reason = sample["eye_quality"].get("reason", "BOTH_EYES_UNRELIABLE")
            return AIState.LOW_CONFIDENCE, 0.45, reason, 0

        closed_bit = 1 if ear_low else 0
        self._perclos_short.append(closed_bit)
        self._perclos_long.append(closed_bit)

        self._eyes_closed_frames = self._eyes_closed_frames + 1 if ear_low else 0
        self._mouth_open_frames = self._mouth_open_frames + 1 if mouth_open else 0
        self._head_down_frames = self._head_down_frames + 1 if head_down else 0

        eyes_closed_sec = self._duration(self._eyes_closed_frames)
        mouth_open_sec = self._duration(self._mouth_open_frames)
        head_down_sec = self._duration(self._head_down_frames)
        perclos_long = self._ratio(self._perclos_long)

        if mouth_open_sec >= 1.0:
            if not self._yawn_times or now - self._yawn_times[-1] > 2.0:
                self._yawn_times.append(now)
            while self._yawn_times and now - self._yawn_times[0] > getattr(config, "YAWN_COUNT_WINDOW", 60.0):
                self._yawn_times.popleft()
            alert_hint = 2 if len(self._yawn_times) >= getattr(config, "YAWN_COUNT_THRESHOLD", 2) else 1
            return AIState.YAWNING, 0.86, "MAR %.2f above %.2f for %.1fs" % (
                sample["mar"],
                thresholds["mar_yawn"],
                mouth_open_sec,
            ), alert_hint

        if eyes_closed_sec >= 3.0:
            return AIState.DROWSY, 0.98, "Eyes closed for %.1fs; PERCLOS %.2f" % (
                eyes_closed_sec,
                perclos_long,
            ), 3
        if eyes_closed_sec >= 1.8:
            return AIState.DROWSY, 0.94, "Eyes closed for %.1fs; PERCLOS %.2f" % (
                eyes_closed_sec,
                perclos_long,
            ), 2
        if eyes_closed_sec >= 0.8:
            return AIState.DROWSY, 0.88, "Eyes closed for %.1fs; PERCLOS %.2f" % (
                eyes_closed_sec,
                perclos_long,
            ), 1
        if eyes_closed_sec >= 0.35:
            return AIState.EYES_CLOSED, 0.72, "EAR %.3f below %.3f" % (
                sample["ear"],
                thresholds["ear_closed"],
            ), 0
        if eyes_closed_sec > 0.0:
            return AIState.BLINK, 0.62, "Short eye closure %.1fs" % eyes_closed_sec, 0

        if head_down_sec >= 2.5:
            return AIState.HEAD_DOWN, 0.90, "Head down for %.1fs" % head_down_sec, 2
        if head_down_sec >= 1.0:
            return AIState.HEAD_DOWN, 0.82, "Head down for %.1fs" % head_down_sec, 1

        if perclos_long >= 0.35 and len(self._perclos_long) >= max(5, int(2.0 * self._target_fps)):
            return AIState.DROWSY, 0.90, "Long PERCLOS %.2f indicates fatigue" % perclos_long, 2

        return AIState.NORMAL, 0.92, "Normal face posture and blink metrics", 0

    def _features(self, sample):
        features = FeatureExtractor.extract(
            self._samples,
            self._thresholds()["ear_closed"],
            self._thresholds()["mar_yawn"],
            self._thresholds()["pitch_down"],
            target_fps=self._target_fps,
        ) or {}
        features.update({
            "perclos_short": self._ratio(self._perclos_short),
            "perclos_long": self._ratio(self._perclos_long),
            "ear": sample["ear"],
            "left_ear": sample["left_ear"],
            "right_ear": sample["right_ear"],
            "ear_used": sample["ear"],
            "eye_quality": sample["eye_quality"],
            "mar": sample["mar"],
            "pitch": sample["pitch"],
        })
        return features

    def _thresholds(self):
        profile = self._profile or CalibrationProfile.fallback(reason="FALLBACK")
        return ThresholdPolicy.from_profile(profile).to_dict()

    def _durations(self):
        return {
            "eyes_closed_sec": self._duration(self._eyes_closed_frames),
            "mouth_open_sec": self._duration(self._mouth_open_frames),
            "head_down_sec": self._duration(self._head_down_frames),
            "no_face_sec": self._duration(self._no_face_frames),
        }

    def _duration(self, frames):
        return float(frames or 0) / self._target_fps if self._target_fps > 0 else 0.0

    @staticmethod
    def _ratio(values):
        if not values:
            return 0.0
        return float(sum(values)) / float(len(values))

    def _result(self, state, confidence, reason, features=None, latency_ms=0.0, alert_hint=0):
        return {
            "state": state,
            "confidence": round(float(confidence), 3),
            "reason": reason,
            "alert_hint": int(alert_hint or 0),
            "durations": self._durations(),
            "thresholds": self._thresholds(),
            "features": features or {},
            "latency_ms": round(float(latency_ms or 0.0), 2),
        }
