from alerts.alert_manager import AlertLevel, AlertManager
from ai.drowsiness_classifier import AIState


class Metrics:
    face_present = True
    ear = 0.31
    mar = 0.24
    pitch = 0.0


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

    def play_alert(self, level):
        self.last_level = level
        return True

    def stop(self):
        self.last_level = 0


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
