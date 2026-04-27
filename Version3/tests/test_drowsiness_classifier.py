from ai.calibration import CalibrationProfile
from ai.drowsiness_classifier import DrowsinessClassifier, AIState
from ai.feature_extractor import FeatureExtractor
import config


def profile(ear=0.24, mar=0.45, pitch=-15.0):
    return CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=0.29,
        mar_closed_median=0.12,
        pitch_neutral=pitch + 15.0,
        ear_closed_threshold=ear,
        mar_yawn_threshold=mar,
        pitch_down_threshold=pitch,
        sample_count=40,
        face_height_median=220.0,
    )


def metrics(face_present=True, ear=0.28, mar=0.12, pitch=0.0, usable=True, eye_quality=None, left_ear=None, right_ear=None):
    return {
        "face_present": face_present,
        "ear": ear,
        "ear_used": ear,
        "left_ear": ear if left_ear is None else left_ear,
        "right_ear": ear if right_ear is None else right_ear,
        "mar": mar,
        "pitch": pitch,
        "face_quality": {"usable": usable, "reason": "OK" if usable else "LOW_CONFIDENCE"},
        "eye_quality": eye_quality if eye_quality is not None else {"usable": True, "selected": "both", "reason": "OK"},
    }


def test_classifier_reports_normal_for_stable_open_eyes():
    classifier = DrowsinessClassifier(window_seconds=5, target_fps=10)

    for _ in range(20):
        result = classifier.update({
            "face_present": True,
            "ear": 0.31,
            "mar": 0.25,
            "pitch": 0.0,
            "perclos": 0.02,
        })

    assert result["state"] == AIState.NORMAL
    assert result["confidence"] >= 0.8
    assert "normal" in result["reason"].lower() or "ml" in result["reason"].lower()


def test_classifier_reports_drowsy_for_low_ear_and_high_perclos():
    classifier = DrowsinessClassifier(window_seconds=5, target_fps=10)

    for _ in range(40):
        result = classifier.update({
            "face_present": True,
            "ear": 0.14,
            "mar": 0.25,
            "pitch": -5.0,
            "perclos": 0.48,
        })

    assert result["state"] == AIState.DROWSY
    assert result["confidence"] >= 0.85
    assert "perclos" in result["reason"].lower() or "ml" in result["reason"].lower()


def test_classifier_reports_yawning_when_mar_is_high():
    classifier = DrowsinessClassifier(window_seconds=5, target_fps=10)

    for _ in range(12):
        result = classifier.update({
            "face_present": True,
            "ear": 0.28,
            "mar": 0.78,
            "pitch": -3.0,
            "perclos": 0.08,
        })

    assert result["state"] == AIState.YAWNING
    assert result["confidence"] >= 0.75
    assert "mar" in result["reason"].lower() or "ml" in result["reason"].lower()


def test_classifier_reports_no_face_after_missing_face_window():
    classifier = DrowsinessClassifier(window_seconds=5, target_fps=10)

    for _ in range(15):
        result = classifier.update({
            "face_present": False,
            "ear": 0.0,
            "mar": 0.0,
            "pitch": 0.0,
            "perclos": 1.0,
        })

    assert result["state"] == AIState.NO_FACE
    assert result["confidence"] >= 0.8


def test_open_eyes_are_not_drowsy_after_stale_high_perclos():
    classifier = DrowsinessClassifier(window_seconds=2, target_fps=10)

    for _ in range(20):
        result = classifier.update({
            "face_present": True,
            "ear": 0.27,
            "mar": 0.10,
            "pitch": 0.0,
            "perclos": 0.70,
        })

    assert result["state"] == AIState.NORMAL


def test_feature_extractor_uses_current_eye_closure_not_stale_perclos():
    samples = [
        {"face_present": True, "ear": 0.28, "mar": 0.10, "pitch": 0.0, "perclos": 0.70}
        for _ in range(20)
    ]

    features = FeatureExtractor.extract(samples, config.EAR_THRESHOLD, config.MAR_THRESHOLD, config.PITCH_DELTA_THRESHOLD)

    assert features["low_ear_ratio"] == 0.0
    assert features["perclos"] == 0.0


def test_classifier_reports_yawning_after_two_seconds_of_open_mouth():
    classifier = DrowsinessClassifier(window_seconds=2, target_fps=10)

    for _ in range(20):
        result = classifier.update({
            "face_present": True,
            "ear": 0.29,
            "mar": 0.50,
            "pitch": 0.0,
            "perclos": 0.0,
        })

    assert result["state"] == AIState.YAWNING


def test_open_eyes_stay_normal_with_profile_threshold():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    for _ in range(20):
        result = classifier.update(metrics(ear=0.28, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert result["thresholds"]["ear_closed"] == 0.24


def test_short_low_ear_is_blink_not_alert():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    for _ in range(2):
        result = classifier.update(metrics(ear=0.20, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.BLINK
    assert result["alert_hint"] == 0


def test_eyes_closed_becomes_level1_after_0_8s():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    for _ in range(8):
        result = classifier.update(metrics(ear=0.20, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 1
    assert result["durations"]["eyes_closed_sec"] >= 0.8


def test_yawn_after_one_second_of_high_mar():
    classifier = DrowsinessClassifier(profile=profile(mar=0.45), target_fps=10)

    for _ in range(10):
        result = classifier.update(metrics(ear=0.29, mar=0.55, pitch=0.0))

    assert result["state"] == AIState.YAWNING
    assert result["alert_hint"] == 1
    assert result["durations"]["mouth_open_sec"] >= 1.0


def test_no_face_does_not_raise_perclos_windows():
    classifier = DrowsinessClassifier(profile=profile(), target_fps=10)

    for _ in range(20):
        result = classifier.update(metrics(face_present=False, ear=0.0, mar=0.0, pitch=0.0))

    assert result["state"] == AIState.NO_FACE
    assert result["features"]["perclos_short"] == 0.0
    assert result["features"]["perclos_long"] == 0.0


def test_low_confidence_does_not_alert_before_no_face_timeout():
    classifier = DrowsinessClassifier(profile=profile(), target_fps=10)

    for _ in range(3):
        result = classifier.update(metrics(face_present=True, ear=0.0, mar=0.0, pitch=0.0, usable=False))

    assert result["state"] == AIState.LOW_CONFIDENCE
    assert result["alert_hint"] == 0


def test_unusable_eye_quality_does_not_raise_perclos_or_drowsy_alert():
    classifier = DrowsinessClassifier(profile=profile(), target_fps=10)

    for _ in range(20):
        result = classifier.update(metrics(
            face_present=True,
            ear=0.10,
            mar=0.12,
            pitch=0.0,
            eye_quality={"usable": False, "selected": "none", "reason": "BOTH_UNRELIABLE"},
        ))

    assert result["state"] == AIState.LOW_CONFIDENCE
    assert result["alert_hint"] == 0
    assert result["features"]["perclos_short"] == 0.0
    assert result["features"]["perclos_long"] == 0.0


def test_one_clear_eye_with_glasses_stays_normal_when_eye_used_is_open():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    for _ in range(20):
        result = classifier.update(metrics(
            face_present=True,
            ear=0.29,
            left_ear=0.12,
            right_ear=0.29,
            mar=0.12,
            pitch=0.0,
            eye_quality={
                "usable": True,
                "selected": "right",
                "reason": "LEFT_GLARE",
                "left": {"usable": False, "reason": "GLARE"},
                "right": {"usable": True, "reason": "OK"},
            },
        ))

    assert result["state"] == AIState.NORMAL
    assert result["features"]["ear"] == 0.29
    assert result["features"]["eye_quality"]["selected"] == "right"
