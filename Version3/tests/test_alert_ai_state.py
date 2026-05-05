from alerts.alert_manager import AlertLevel, AlertManager
from ai.drowsiness_classifier import AIState


class Metrics:
    def __init__(self, face_present=True, ear=0.31, mar=0.24, pitch=0.0):
        self.face_present = face_present
        self.ear = ear
        self.mar = mar
        self.pitch = pitch


def test_alert_manager_escalates_from_ai_drowsy_state():
    manager = AlertManager()

    manager.update(
        Metrics(),
        perclos=0.05,
        ai_result={"state": AIState.DROWSY, "confidence": 0.9, "reason": "classifier"},
    )

    assert manager.current_level == AlertLevel.LEVEL_2


class FakeSpeaker:
    def __init__(self):
        self.last_level = None
        self.stopped = False

    def play_alert(self, level):
        self.last_level = level
        self.stopped = False
        return True

    def stop(self):
        self.last_level = 0
        self.stopped = True


class FailingSpeaker(FakeSpeaker):
    def play_alert(self, level):
        self.last_level = level
        return False


def test_alert_hint_1_plays_speaker_level_1():
    speaker = FakeSpeaker()
    manager = AlertManager(speaker=speaker)

    manager.update(Metrics(), perclos=0.0, ai_result={"state": "DROWSY", "alert_hint": 1})

    assert manager.current_level == AlertLevel.LEVEL_1
    assert speaker.last_level == 1


def test_alert_hint_2_plays_speaker_level_2():
    speaker = FakeSpeaker()
    manager = AlertManager(speaker=speaker)

    manager.update(Metrics(), perclos=0.0, ai_result={"state": "DROWSY", "alert_hint": 2})

    assert manager.current_level == AlertLevel.LEVEL_2
    assert speaker.last_level == 2


def test_alert_hint_3_plays_speaker_level_3():
    speaker = FakeSpeaker()
    manager = AlertManager(speaker=speaker)

    manager.update(Metrics(), perclos=0.0, ai_result={"state": "DROWSY", "alert_hint": 3})

    assert manager.current_level == AlertLevel.LEVEL_3
    assert speaker.last_level == 3


def test_speaker_failure_does_not_crash_alert_manager():
    speaker = FailingSpeaker()
    manager = AlertManager(speaker=speaker)

    manager.update(Metrics(), perclos=0.0, ai_result={"state": "DROWSY", "alert_hint": 2})

    assert manager.current_level == AlertLevel.LEVEL_2
    assert speaker.last_level == 2


def test_alert_manager_stops_outputs_when_ai_recovers_to_normal():
    speaker = FakeSpeaker()
    manager = AlertManager(speaker=speaker)

    manager.update(Metrics(ear=0.20, mar=0.12), perclos=0.50, ai_result={
        "state": "DROWSY",
        "confidence": 0.90,
        "reason": "test drowsy",
        "alert_hint": 2,
    })

    assert manager.current_level == AlertLevel.LEVEL_2
    assert speaker.last_level == 2

    manager.update(Metrics(ear=0.30, mar=0.12), perclos=0.40, ai_result={
        "state": "NORMAL",
        "confidence": 0.92,
        "reason": "stable open eyes",
        "alert_hint": 0,
    })

    assert manager.current_level == AlertLevel.NONE
    assert speaker.stopped is True


def test_alert_manager_does_not_stop_outputs_on_low_confidence_hint_zero():
    speaker = FakeSpeaker()
    manager = AlertManager(speaker=speaker)

    manager.update(Metrics(ear=0.20), perclos=0.50, ai_result={
        "state": "DROWSY",
        "confidence": 0.90,
        "reason": "test drowsy",
        "alert_hint": 2,
    })

    manager.update(Metrics(ear=0.0), perclos=0.40, ai_result={
        "state": "LOW_CONFIDENCE",
        "confidence": 0.45,
        "reason": "BOTH_EYES_UNRELIABLE",
        "alert_hint": 0,
    })

    assert manager.current_level == AlertLevel.LEVEL_2
    assert speaker.stopped is False


def test_alert_manager_does_not_stop_outputs_on_no_face_hint_zero():
    speaker = FakeSpeaker()
    manager = AlertManager(speaker=speaker)

    manager.update(Metrics(ear=0.20), perclos=0.50, ai_result={
        "state": "DROWSY",
        "confidence": 0.90,
        "reason": "test drowsy",
        "alert_hint": 2,
    })

    manager.update(Metrics(face_present=False, ear=0.0), perclos=0.40, ai_result={
        "state": "NO_FACE",
        "confidence": 0.85,
        "reason": "No usable face",
        "alert_hint": 0,
    })

    assert manager.current_level == AlertLevel.LEVEL_2
    assert speaker.stopped is False
