from ai.calibration import CalibrationProfile, DriverCalibrator


class SampleMetrics:
    def __init__(
        self,
        face_present=True,
        ear=0.29,
        mar=0.12,
        pitch=-2.0,
        face_bbox=(100, 80, 220, 230),
        left_ear=0.30,
        right_ear=0.28,
        eye_quality=None,
    ):
        self.face_present = face_present
        self.ear = ear
        self.mar = mar
        self.pitch = pitch
        self.face_bbox = face_bbox
        self.left_ear = left_ear
        self.right_ear = right_ear
        self.ear_used = ear
        self.eye_quality = eye_quality if eye_quality is not None else {"usable": True, "selected": "both", "reason": "OK"}


def sample(
    face_present=True,
    ear=0.29,
    mar=0.12,
    pitch=-2.0,
    face_bbox=(100, 80, 220, 230),
    left_ear=0.30,
    right_ear=0.28,
    eye_quality=None,
):
    return SampleMetrics(
        face_present=face_present,
        ear=ear,
        mar=mar,
        pitch=pitch,
        face_bbox=face_bbox,
        left_ear=left_ear,
        right_ear=right_ear,
        eye_quality=eye_quality,
    )


def test_calibration_profile_valid_for_open_eyes():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(), i * 0.1)

    assert calibrator.ready is True
    profile = calibrator.profile
    assert profile.valid is True
    assert profile.reason == "OK"
    assert 0.20 <= profile.ear_closed_threshold <= 0.24
    assert profile.mar_yawn_threshold >= 0.45
    assert profile.pitch_down_threshold == profile.pitch_neutral - 15.0
    assert round(profile.left_ear_open_median, 2) == 0.30
    assert round(profile.right_ear_open_median, 2) == 0.28
    assert round(profile.ear_used_open_median, 2) == 0.29


def test_calibration_rejects_low_open_eye_baseline():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(ear=0.21), i * 0.1)

    profile = calibrator.profile
    assert profile.valid is False
    assert profile.reason == "LOW_EAR_BASELINE"
    assert profile.ear_closed_threshold == CalibrationProfile.fallback().ear_closed_threshold


def test_calibration_rejects_small_face():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(face_bbox=(100, 80, 100, 90)), i * 0.1)

    profile = calibrator.profile
    assert profile.valid is False
    assert profile.reason == "FACE_TOO_SMALL"


def test_calibration_ignores_missing_face_samples():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(20):
        calibrator.add(sample(face_present=False, face_bbox=None), i * 0.1)
    for i in range(20, 55):
        calibrator.add(sample(ear=0.30, mar=0.10, pitch=1.0), i * 0.1)

    profile = calibrator.profile
    assert profile.valid is True
    assert profile.sample_count == 35
    assert round(profile.ear_open_median, 2) == 0.30


def test_calibration_ignores_unusable_eye_samples():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(15):
        calibrator.add(sample(eye_quality={"usable": False, "selected": "none", "reason": "BOTH_UNRELIABLE"}), i * 0.1)
    for i in range(15, 50):
        calibrator.add(sample(ear=0.31, left_ear=0.32, right_ear=0.30), i * 0.1)

    profile = calibrator.profile
    assert profile.valid is True
    assert profile.sample_count == 35
    assert round(profile.ear_used_open_median, 2) == 0.31


def test_calibration_rejects_when_not_enough_usable_eye_samples():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(eye_quality={"usable": False, "selected": "none", "reason": "BOTH_UNRELIABLE"}), i * 0.1)

    profile = calibrator.profile
    assert profile.valid is False
    assert profile.reason == "NOT_ENOUGH_SAMPLES"
    assert profile.sample_count == 0
