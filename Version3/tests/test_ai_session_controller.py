from ai.drowsiness_classifier import AIState
from ai.session_controller import AiSessionController


def sample_metrics(ear=0.29, mar=0.12, pitch=0.0):
    class Metrics:
        face_present = True
        face_bbox = (100, 80, 220, 230)
        left_ear = ear
        right_ear = ear
        ear_used = ear
        face_quality = {"usable": True, "reason": "OK"}
        eye_quality = {"usable": True, "selected": "both", "reason": "OK"}

    metrics = Metrics()
    metrics.ear = ear
    metrics.mar = mar
    metrics.pitch = pitch
    return metrics


def test_ai_session_controller_reset_starts_collecting():
    controller = AiSessionController(target_fps=10)

    controller.reset_session()

    assert controller.last_result["state"] == AIState.UNKNOWN
    assert controller.calibration_payload()["reason"] in ("COLLECTING", "NOT_ENOUGH_SAMPLES")


def test_ai_session_controller_update_returns_classifier_result():
    controller = AiSessionController(target_fps=10)

    result = controller.update(sample_metrics(), perclos=0.0)

    assert "state" in result
    assert "thresholds" in result
