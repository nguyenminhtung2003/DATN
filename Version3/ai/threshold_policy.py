"""Canonical threshold payloads for drowsiness decisions."""

from .calibration import CalibrationProfile


class ThresholdPolicy:
    """Read threshold values from a calibration profile without changing them."""

    def __init__(self, ear_closed, mar_yawn, pitch_down, ear_open=None, ear_delta=0.045, ear_drop_closed=0.13):
        self.ear_closed = float(ear_closed)
        self.mar_yawn = float(mar_yawn)
        self.pitch_down = float(pitch_down)
        self.ear_open = None if ear_open is None else float(ear_open)
        self.ear_delta = float(ear_delta)
        self.ear_drop_closed = float(ear_drop_closed)

    @classmethod
    def from_profile(cls, profile):
        profile = profile or CalibrationProfile.fallback(reason="FALLBACK")
        return cls(
            ear_closed=getattr(profile, "ear_adaptive_closed_threshold", profile.ear_closed_threshold),
            mar_yawn=profile.mar_yawn_threshold,
            pitch_down=profile.pitch_down_threshold,
            ear_open=profile.ear_open_median,
            ear_delta=getattr(profile, "ear_open_delta", 0.045),
            ear_drop_closed=getattr(profile, "ear_drop_closed_threshold", 0.13),
        )

    def to_dict(self):
        return {
            "ear_closed": self.ear_closed,
            "ear_open": self.ear_open,
            "ear_delta": self.ear_delta,
            "ear_drop_closed": self.ear_drop_closed,
            "mar_yawn": self.mar_yawn,
            "pitch_down": self.pitch_down,
        }
