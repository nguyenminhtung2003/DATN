import types

import camera.face_analyzer as face_analyzer


def test_face_analyzer_retries_without_refine_landmarks_for_old_mediapipe(monkeypatch):
    calls = []

    class FakeFaceMesh:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            if "refine_landmarks" in kwargs:
                raise TypeError("__init__() got an unexpected keyword argument 'refine_landmarks'")

        def close(self):
            pass

    fake_mp = types.SimpleNamespace(
        solutions=types.SimpleNamespace(
            face_mesh=types.SimpleNamespace(FaceMesh=FakeFaceMesh)
        )
    )
    monkeypatch.setattr(face_analyzer, "np", object())
    monkeypatch.setattr(face_analyzer, "cv2", object())
    monkeypatch.setattr(face_analyzer, "mp", fake_mp)

    analyzer = face_analyzer.FaceAnalyzer()
    analyzer.release()

    assert calls[0]["refine_landmarks"] is True
    assert "refine_landmarks" not in calls[1]


def test_face_analyzer_uses_configured_detection_confidence(monkeypatch):
    calls = []

    class FakeFaceMesh:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def close(self):
            pass

    fake_mp = types.SimpleNamespace(
        solutions=types.SimpleNamespace(
            face_mesh=types.SimpleNamespace(FaceMesh=FakeFaceMesh)
        )
    )
    monkeypatch.setattr(face_analyzer, "np", object())
    monkeypatch.setattr(face_analyzer, "cv2", object())
    monkeypatch.setattr(face_analyzer, "mp", fake_mp)
    monkeypatch.setattr(face_analyzer.config, "FACE_MESH_MIN_DETECTION_CONFIDENCE", 0.2, raising=False)
    monkeypatch.setattr(face_analyzer.config, "FACE_MESH_MIN_TRACKING_CONFIDENCE", 0.25, raising=False)

    analyzer = face_analyzer.FaceAnalyzer()
    analyzer.release()

    assert calls[0]["min_detection_confidence"] == 0.2
    assert calls[0]["min_tracking_confidence"] == 0.25


def test_face_analyzer_does_not_count_missing_face_as_closed_eyes(monkeypatch):
    class FakeResults:
        multi_face_landmarks = None

    class FakeFaceMesh:
        def __init__(self, **kwargs):
            pass

        def process(self, frame):
            return FakeResults()

        def close(self):
            pass

    fake_mp = types.SimpleNamespace(
        solutions=types.SimpleNamespace(
            face_mesh=types.SimpleNamespace(FaceMesh=FakeFaceMesh)
        )
    )
    fake_cv2 = types.SimpleNamespace(cvtColor=lambda frame, code: frame, COLOR_BGR2RGB=1)
    monkeypatch.setattr(face_analyzer, "np", object())
    monkeypatch.setattr(face_analyzer, "cv2", fake_cv2)
    monkeypatch.setattr(face_analyzer, "mp", fake_mp)

    analyzer = face_analyzer.FaceAnalyzer()

    class Frame:
        shape = (360, 640, 3)

    for _ in range(20):
        metrics = analyzer.analyze(Frame())

    assert metrics.face_present is False
    assert analyzer.perclos == 0.0
    analyzer.release()


def test_pitch_angle_is_folded_into_front_facing_range():
    assert round(face_analyzer._normalize_pitch_angle(168.9), 1) == -11.1
    assert round(face_analyzer._normalize_pitch_angle(-170.0), 1) == 10.0
    assert round(face_analyzer._normalize_pitch_angle(-20.0), 1) == -20.0
    assert round(face_analyzer._normalize_pitch_angle(15.0), 1) == 15.0


def test_mouth_aspect_ratio_uses_vertical_over_horizontal_scale():
    closed = face_analyzer._mouth_aspect_ratio(
        left_corner=(0, 0),
        right_corner=(100, 0),
        upper_lip=(50, -5),
        lower_lip=(50, 5),
    )
    open_mouth = face_analyzer._mouth_aspect_ratio(
        left_corner=(0, 0),
        right_corner=(100, 0),
        upper_lip=(50, -30),
        lower_lip=(50, 30),
    )

    assert round(closed, 3) == 0.1
    assert round(open_mouth, 3) == 0.6


def test_face_metrics_exposes_eye_and_mouth_points():
    metrics = face_analyzer.FaceMetrics()

    assert metrics.left_eye_points == []
    assert metrics.right_eye_points == []
    assert metrics.mouth_points == []
    assert metrics.face_quality["usable"] is False
    assert metrics.face_quality["reason"] == "NO_FACE"
    assert metrics.left_ear == 0.0
    assert metrics.right_ear == 0.0
    assert metrics.ear_used == 0.0
    assert metrics.eye_quality["usable"] is False
    assert metrics.eye_quality["selected"] == "none"


def test_eye_quality_uses_both_clear_eyes():
    np = face_analyzer.np
    if np is None:
        return
    frame = np.zeros((60, 100, 3), dtype=np.uint8)
    left_points = [(10, 30), (14, 24), (22, 24), (30, 30), (22, 36), (14, 36)]
    right_points = [(60, 30), (64, 24), (72, 24), (80, 30), (72, 36), (64, 36)]

    quality = face_analyzer._build_eye_quality(frame, left_points, right_points, 0.30, 0.28)

    assert quality["usable"] is True
    assert quality["selected"] == "both"
    assert round(quality["ear_used"], 3) == 0.29


def test_eye_quality_selects_clear_eye_when_other_eye_has_glare():
    np = face_analyzer.np
    if np is None:
        return
    frame = np.zeros((60, 100, 3), dtype=np.uint8)
    frame[20:40, 5:35] = 255
    left_points = [(10, 30), (14, 24), (22, 24), (30, 30), (22, 36), (14, 36)]
    right_points = [(60, 30), (64, 24), (72, 24), (80, 30), (72, 36), (64, 36)]

    quality = face_analyzer._build_eye_quality(frame, left_points, right_points, 0.30, 0.28)

    assert quality["usable"] is True
    assert quality["left"]["usable"] is False
    assert quality["right"]["usable"] is True
    assert quality["selected"] == "right"
    assert quality["ear_used"] == 0.28


def test_eye_quality_rejects_both_unreliable_eyes():
    np = face_analyzer.np
    if np is None:
        return
    frame = np.zeros((60, 100, 3), dtype=np.uint8)
    frame[:, :] = 255
    left_points = [(10, 30), (14, 24), (22, 24), (30, 30), (22, 36), (14, 36)]
    right_points = [(60, 30), (64, 24), (72, 24), (80, 30), (72, 36), (64, 36)]

    quality = face_analyzer._build_eye_quality(frame, left_points, right_points, 0.30, 0.28)

    assert quality["usable"] is False
    assert quality["selected"] == "none"
    assert quality["reason"] == "BOTH_UNRELIABLE"


def test_face_quality_rejects_small_face():
    quality = face_analyzer._build_face_quality((10, 10, 80, 90), frame_width=640, frame_height=360, confidence=0.8)

    assert quality["usable"] is False
    assert quality["reason"] == "FACE_TOO_SMALL"
