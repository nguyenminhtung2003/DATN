"""AI session orchestration for calibration and classifier state."""

import time

from .calibration import CalibrationProfile, DriverCalibrator
from .drowsiness_classifier import AIState, DrowsinessClassifier
from .threshold_policy import ThresholdPolicy


class AiSessionController:
    """Owns per-session calibration state and classifier updates."""

    def __init__(self, target_fps=None, classifier=None, calibrator=None, create_classifier=True):
        if classifier is None and create_classifier:
            classifier = DrowsinessClassifier(target_fps=target_fps)
        self.classifier = classifier
        self.calibrator = calibrator or DriverCalibrator()
        self._calibration_profile = CalibrationProfile.fallback(reason="NOT_STARTED")
        self._calibration_applied = False
        self._last_applied_profile = None
        self._last_result = self._build_unknown_result("No samples yet")

    @property
    def last_result(self):
        return dict(self._last_result)

    @property
    def profile(self):
        return self._calibration_profile

    @property
    def calibration_applied(self):
        return bool(self._calibration_applied)

    def reset_session(self):
        self.calibrator = DriverCalibrator()
        self._calibration_profile = CalibrationProfile.fallback(reason="COLLECTING")
        self._calibration_applied = False
        self._last_applied_profile = None
        if self.classifier and hasattr(self.classifier, "reset_state"):
            self.classifier.reset_state()
        if self.classifier and hasattr(self.classifier, "set_profile"):
            self.classifier.set_profile(self._calibration_profile)
        self._last_result = self._build_unknown_result("Calibration collecting")
        return self.last_result

    def update(self, metrics, perclos=0.0, now=None):
        self.update_calibration_from_metrics(metrics, now=now)
        if not self.classifier:
            return self.last_result
        result = self.classifier.update(self._metrics_payload(metrics, perclos))
        self._last_result = result
        return result

    def update_calibration_from_metrics(self, metrics, now=None):
        if not self.calibrator or self._calibration_applied:
            return
        timestamp = time.time() if now is None else now
        if metrics is not None:
            self.calibrator.add(metrics, timestamp)
        profile = self.calibrator.profile
        if profile.valid or self.calibrator.complete(timestamp):
            self._calibration_profile = profile
            self._calibration_applied = True
            self._last_applied_profile = profile
            if self.classifier and hasattr(self.classifier, "set_profile"):
                self.classifier.set_profile(profile)

    def consume_applied_profile(self):
        profile = self._last_applied_profile
        self._last_applied_profile = None
        return profile

    def thresholds_payload(self):
        return ThresholdPolicy.from_profile(self._calibration_profile).to_dict()

    def calibration_payload(self, session_active=False):
        if self.calibrator and not self._calibration_applied:
            profile = self.calibrator.profile
            payload = profile.to_dict(active=bool(session_active))
            if session_active and payload["reason"] == "NOT_ENOUGH_SAMPLES":
                payload["reason"] = "COLLECTING"
            return payload
        profile = self._calibration_profile or CalibrationProfile.fallback(reason="NOT_STARTED")
        return profile.to_dict(active=False)

    def _build_unknown_result(self, reason):
        return {
            "state": AIState.UNKNOWN,
            "confidence": 0.0,
            "reason": reason,
            "alert_hint": 0,
            "thresholds": self.thresholds_payload(),
            "features": {},
        }

    @staticmethod
    def _metrics_payload(metrics, perclos):
        return {
            "face_present": getattr(metrics, "face_present", False),
            "ear": getattr(metrics, "ear", 0.0),
            "left_ear": getattr(metrics, "left_ear", getattr(metrics, "ear", 0.0)),
            "right_ear": getattr(metrics, "right_ear", getattr(metrics, "ear", 0.0)),
            "ear_used": getattr(metrics, "ear_used", getattr(metrics, "ear", 0.0)),
            "mar": getattr(metrics, "mar", 0.0),
            "pitch": getattr(metrics, "pitch", 0.0),
            "perclos": perclos,
            "face_bbox": getattr(metrics, "face_bbox", None),
            "face_quality": getattr(metrics, "face_quality", {}),
            "eye_quality": getattr(metrics, "eye_quality", {}),
        }
