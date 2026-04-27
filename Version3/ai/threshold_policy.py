"""Canonical threshold payloads for drowsiness decisions."""

from .calibration import CalibrationProfile


class ThresholdPolicy:
    """Read threshold values from a calibration profile without changing them."""

    def __init__(self, ear_closed, mar_yawn, pitch_down):
        self.ear_closed = float(ear_closed)
        self.mar_yawn = float(mar_yawn)
        self.pitch_down = float(pitch_down)

    @classmethod
    def from_profile(cls, profile):
        profile = profile or CalibrationProfile.fallback(reason="FALLBACK")
        return cls(
            ear_closed=profile.ear_closed_threshold,
            mar_yawn=profile.mar_yawn_threshold,
            pitch_down=profile.pitch_down_threshold,
        )

    def to_dict(self):
        return {
            "ear_closed": self.ear_closed,
            "mar_yawn": self.mar_yawn,
            "pitch_down": self.pitch_down,
        }
