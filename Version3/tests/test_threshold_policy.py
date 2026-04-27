from ai.calibration import CalibrationProfile
from ai.threshold_policy import ThresholdPolicy


def test_threshold_policy_uses_profile_thresholds():
    profile = CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=0.29,
        mar_closed_median=0.12,
        pitch_neutral=0.0,
        ear_closed_threshold=0.24,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
        sample_count=40,
    )

    thresholds = ThresholdPolicy.from_profile(profile).to_dict()

    assert thresholds == {
        "ear_closed": 0.24,
        "mar_yawn": 0.45,
        "pitch_down": -15.0,
    }


def test_threshold_policy_uses_fallback_profile_when_missing():
    thresholds = ThresholdPolicy.from_profile(None).to_dict()

    assert thresholds["ear_closed"] == CalibrationProfile.fallback().ear_closed_threshold
    assert thresholds["mar_yawn"] == CalibrationProfile.fallback().mar_yawn_threshold
    assert thresholds["pitch_down"] == CalibrationProfile.fallback().pitch_down_threshold
