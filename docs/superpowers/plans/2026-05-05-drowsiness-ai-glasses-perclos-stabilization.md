# Drowsiness AI Glasses And PERCLOS Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for token-efficient inline execution. Execute adjacent RED/GREEN tasks as green vertical slices: add failing tests, verify RED, implement, verify GREEN, then commit once. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DrowsiGuard classify drowsiness more reliably for both non-glasses and prescription-glasses drivers, while preventing stale PERCLOS history from keeping the system in DROWSY when the current eyes are clearly open.

**Architecture:** Keep the rule-based state machine, but make eye-closure decisions come from a single helper that combines absolute EAR, calibrated open-eye baseline, EAR drop ratio, and per-eye quality. Add an open-eye recovery gate so long-window PERCLOS cannot trigger level-2 DROWSY after the driver has reopened eyes steadily. Keep WebSocket payload compatibility by only adding optional fields to existing `thresholds`, `features`, and `calibration` dictionaries.

**Tech Stack:** Python 3, pytest, MediaPipe Face Mesh metrics, OpenCV-derived EAR/MAR/head pose, existing `Version3` AI/session/alert modules.

---

## Current Code Findings

- `Version3/ai/drowsiness_classifier.py` currently marks DROWSY when `perclos_long >= 0.35` even if the latest EAR is open.
- `Version3/ai/calibration.py` currently caps `ear_closed_threshold` at `0.24`, so glasses cases like `open=0.32`, `closed=0.27` are under-detected.
- `Version3/alerts/alert_manager.py` receives `alert_hint` from the AI classifier and can keep the previous alert level until `ALERT_COOLDOWN` expires.
- `Version3/ui/local_monitor.py` already displays thresholds, PERCLOS short/long, eye quality, and calibration, so the overlay can show new optional fields without changing the dashboard contract.

## Execution Workflow

Use green commits only. Do not commit RED-only test changes. Run the RED checks as local verification inside each slice, then implement and commit after the focused tests pass.

- Slice 1: Task 1 + Task 2, then commit `fix: gate stale perclos with open-eye recovery`.
- Slice 2: Task 3 + Task 4, then commit `feat: add adaptive ear baseline thresholds`.
- Slice 3: Task 5 + Task 6, then commit `feat: classify eye closure from adaptive ear drop`.
- Slice 4: Task 7 + Task 8, then commit `fix: stop alerts when ai returns to normal`.
- Slice 5: Task 9, then commit `feat: show adaptive ear recovery telemetry`.
- Slice 6: Task 10 verification and Jetson deployment only after local tests pass.

## File Structure

- Modify: `Version3/ai/calibration.py`
  - Add adaptive EAR fields to `CalibrationProfile`.
  - Compute glasses-friendly threshold from open-eye baseline.
- Modify: `Version3/ai/threshold_policy.py`
  - Export canonical threshold payload including `ear_open`, `ear_drop_closed`, and `ear_delta`.
- Modify: `Version3/ai/drowsiness_classifier.py`
  - Add open-eye recovery gate for stale PERCLOS.
  - Add adaptive/drop-based closed-eye decision.
  - Add per-eye guard for glasses glare/asymmetry.
- Modify: `Version3/alerts/alert_manager.py`
  - Allow safe immediate de-escalation only when AI explicitly returns `state="NORMAL"` with `alert_hint=0`.
- Modify: `Version3/ui/local_monitor.py`
  - Display baseline, drop score, open-stable seconds, and PERCLOS gate status.
- Modify: `Version3/scripts/local_ai_monitor.py`
  - Keep standalone local AI monitor overlay consistent with the integrated GUI.
- Modify tests:
  - `Version3/tests/test_drowsiness_classifier.py`
  - `Version3/tests/test_calibration.py`
  - `Version3/tests/test_threshold_policy.py`
  - `Version3/tests/test_alert_ai_state.py`
  - `Version3/tests/test_local_monitor_gui.py`
  - `Version3/tests/test_local_ai_monitor_script.py`

---

### Task 1: Add RED Tests For Stale PERCLOS Recovery

**Files:**
- Modify: `Version3/tests/test_drowsiness_classifier.py`

- [ ] **Step 1: Add failing classifier tests**

Append these tests to `Version3/tests/test_drowsiness_classifier.py`:

```python
def test_stale_long_perclos_does_not_keep_drowsy_after_stable_open_eyes():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    for _ in range(12):
        result = classifier.update(metrics(ear=0.20, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.DROWSY
    assert result["features"]["perclos_long"] >= 0.35

    for _ in range(12):
        result = classifier.update(metrics(ear=0.29, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert result["features"]["eyes_open_sec"] >= 1.0
    assert result["features"]["perclos_long"] >= 0.35


def test_recent_closed_eyes_can_still_use_long_perclos_for_fatigue():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    for _ in range(7):
        for _ in range(3):
            result = classifier.update(metrics(ear=0.20, mar=0.12, pitch=0.0))
        result = classifier.update(metrics(ear=0.29, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 2
    assert result["durations"]["eyes_closed_sec"] == 0.0
    assert result["features"]["perclos_long"] >= 0.35
    assert result["features"]["perclos_gate_active"] is True
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py::test_stale_long_perclos_does_not_keep_drowsy_after_stable_open_eyes Version3\tests\test_drowsiness_classifier.py::test_recent_closed_eyes_can_still_use_long_perclos_for_fatigue -q
```

Expected:

```text
FAILED ... KeyError: 'eyes_open_sec'
```

or:

```text
FAILED ... assert 'DROWSY' == 'NORMAL'
```

- [ ] **Step 3: Keep RED tests uncommitted for Slice 1**

Do not commit here. Continue directly to Task 2, then commit the complete green Slice 1 after `Version3\tests\test_drowsiness_classifier.py` passes.


---

### Task 2: Implement PERCLOS Open-Eye Recovery Gate

**Files:**
- Modify: `Version3/ai/drowsiness_classifier.py`
- Test: `Version3/tests/test_drowsiness_classifier.py`

- [ ] **Step 1: Add open-eye frame state**

In `DrowsinessClassifier.__init__`, after `_eyes_closed_frames`:

```python
self._eyes_open_frames = 0
```

In `reset_state`, after resetting `_eyes_closed_frames`:

```python
self._eyes_open_frames = 0
```

- [ ] **Step 2: Update usable-eye frame counters**

In `_classify_sample`, replace:

```python
self._eyes_closed_frames = self._eyes_closed_frames + 1 if ear_low else 0
```

with:

```python
if ear_low:
    self._eyes_closed_frames += 1
    self._eyes_open_frames = 0
else:
    self._eyes_closed_frames = 0
    self._eyes_open_frames += 1
```

In the `if not sample["usable"]:` block, also reset open frames:

```python
self._eyes_open_frames = 0
```

- [ ] **Step 3: Gate stale long PERCLOS with stable open eyes**

After:

```python
perclos_long = self._ratio(self._perclos_long)
```

add:

```python
eyes_open_sec = self._duration(self._eyes_open_frames)
perclos_gate_active = eyes_open_sec < 1.0
```

Replace:

```python
if perclos_long >= 0.35 and len(self._perclos_long) >= max(5, int(2.0 * self._target_fps)):
    return AIState.DROWSY, 0.90, "Long PERCLOS %.2f indicates fatigue" % perclos_long, 2
```

with:

```python
if (
    perclos_gate_active
    and perclos_long >= 0.35
    and len(self._perclos_long) >= max(5, int(2.0 * self._target_fps))
):
    return AIState.DROWSY, 0.90, "Long PERCLOS %.2f indicates fatigue" % perclos_long, 2
```

- [ ] **Step 4: Expose recovery features**

In `_durations`, add:

```python
"eyes_open_sec": self._duration(self._eyes_open_frames),
```

In `_features`, add:

```python
"eyes_open_sec": self._duration(self._eyes_open_frames),
"perclos_gate_active": self._duration(self._eyes_open_frames) < 1.0,
```

- [ ] **Step 5: Run classifier tests and verify GREEN**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add Version3\ai\drowsiness_classifier.py Version3\tests\test_drowsiness_classifier.py
git commit -m "fix: gate stale perclos with open-eye recovery"
```

---

### Task 3: Add RED Tests For Adaptive EAR Baseline

**Files:**
- Modify: `Version3/tests/test_calibration.py`
- Modify: `Version3/tests/test_threshold_policy.py`

- [ ] **Step 1: Add calibration tests for glasses and non-glasses profiles**

Append to `Version3/tests/test_calibration.py`:

```python
def test_calibration_keeps_non_glasses_threshold_at_safety_default():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(ear=0.27, left_ear=0.28, right_ear=0.26), i * 0.1)

    profile = calibrator.profile

    assert profile.valid is True
    assert round(profile.ear_open_median, 3) == 0.270
    assert round(profile.ear_closed_threshold, 3) == 0.240
    assert round(profile.ear_adaptive_closed_threshold, 3) == 0.240
    assert round(profile.ear_drop_closed_threshold, 3) == 0.130


def test_calibration_raises_threshold_for_prescription_glasses_baseline():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(ear=0.32, left_ear=0.33, right_ear=0.31), i * 0.1)

    profile = calibrator.profile

    assert profile.valid is True
    assert round(profile.ear_open_median, 3) == 0.320
    assert round(profile.ear_closed_threshold, 3) == 0.275
    assert round(profile.ear_adaptive_closed_threshold, 3) == 0.275
    assert round(profile.ear_drop_closed_threshold, 3) == 0.130
```

- [ ] **Step 2: Add threshold policy test for new optional fields**

Update `Version3/tests/test_threshold_policy.py::test_threshold_policy_uses_profile_thresholds` expected dictionary to:

```python
assert thresholds == {
    "ear_closed": 0.24,
    "ear_open": 0.29,
    "ear_delta": 0.045,
    "ear_drop_closed": 0.13,
    "mar_yawn": 0.45,
    "pitch_down": -15.0,
}
```

Update `test_threshold_policy_uses_fallback_profile_when_missing` with:

```python
assert thresholds["ear_open"] is None
assert thresholds["ear_delta"] == 0.045
assert thresholds["ear_drop_closed"] == 0.13
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m pytest Version3\tests\test_calibration.py Version3\tests\test_threshold_policy.py -q
```

Expected:

```text
FAILED ... AttributeError: 'CalibrationProfile' object has no attribute 'ear_adaptive_closed_threshold'
```

- [ ] **Step 4: Keep RED tests uncommitted for Slice 2**

Do not commit here. Continue directly to Task 4, then commit the complete green Slice 2 after calibration and threshold policy tests pass.


---

### Task 4: Implement Adaptive EAR Profile And Threshold Policy

**Files:**
- Modify: `Version3/config.py`
- Modify: `Version3/ai/calibration.py`
- Modify: `Version3/ai/threshold_policy.py`
- Test: `Version3/tests/test_calibration.py`
- Test: `Version3/tests/test_threshold_policy.py`

- [ ] **Step 1: Add configuration constants**

In `Version3/config.py`, near the existing EAR settings, add:

```python
EAR_OPEN_DELTA = env_float("DROWSIGUARD_EAR_OPEN_DELTA", 0.045)
EAR_DROP_CLOSED_THRESHOLD = env_float("DROWSIGUARD_EAR_DROP_CLOSED_THRESHOLD", 0.13)
EAR_ADAPTIVE_MIN = env_float("DROWSIGUARD_EAR_ADAPTIVE_MIN", 0.20)
EAR_ADAPTIVE_MAX = env_float("DROWSIGUARD_EAR_ADAPTIVE_MAX", 0.30)
```

- [ ] **Step 2: Extend `CalibrationProfile`**

In `Version3/ai/calibration.py`, add parameters to `CalibrationProfile.__init__`:

```python
ear_adaptive_closed_threshold=None,
ear_drop_closed_threshold=None,
ear_open_delta=None,
```

After `self.ear_closed_threshold = ...`, add:

```python
self.ear_adaptive_closed_threshold = (
    self.ear_closed_threshold
    if ear_adaptive_closed_threshold is None
    else float(ear_adaptive_closed_threshold)
)
self.ear_drop_closed_threshold = (
    float(getattr(config, "EAR_DROP_CLOSED_THRESHOLD", 0.13))
    if ear_drop_closed_threshold is None
    else float(ear_drop_closed_threshold)
)
self.ear_open_delta = (
    float(getattr(config, "EAR_OPEN_DELTA", 0.045))
    if ear_open_delta is None
    else float(ear_open_delta)
)
```

In `fallback`, pass:

```python
ear_adaptive_closed_threshold=getattr(config, "EAR_THRESHOLD", FALLBACK_EAR_CLOSED),
ear_drop_closed_threshold=getattr(config, "EAR_DROP_CLOSED_THRESHOLD", 0.13),
ear_open_delta=getattr(config, "EAR_OPEN_DELTA", 0.045),
```

In `to_dict`, add:

```python
"ear_adaptive_closed_threshold": self.ear_adaptive_closed_threshold,
"ear_drop_closed_threshold": self.ear_drop_closed_threshold,
"ear_open_delta": self.ear_open_delta,
```

- [ ] **Step 3: Replace capped EAR calibration formula**

In `_build_profile`, replace:

```python
ear_closed = _clamp(min(FALLBACK_EAR_CLOSED, ear_open - 0.02), 0.20, FALLBACK_EAR_CLOSED)
```

with:

```python
ear_delta = float(getattr(config, "EAR_OPEN_DELTA", 0.045))
ear_closed = _clamp(
    max(FALLBACK_EAR_CLOSED, ear_open - ear_delta),
    float(getattr(config, "EAR_ADAPTIVE_MIN", 0.20)),
    float(getattr(config, "EAR_ADAPTIVE_MAX", 0.30)),
)
```

When returning `CalibrationProfile`, pass:

```python
ear_adaptive_closed_threshold=ear_closed,
ear_drop_closed_threshold=getattr(config, "EAR_DROP_CLOSED_THRESHOLD", 0.13),
ear_open_delta=ear_delta,
```

- [ ] **Step 4: Extend `ThresholdPolicy`**

Replace `ThresholdPolicy.__init__` in `Version3/ai/threshold_policy.py` with:

```python
def __init__(self, ear_closed, mar_yawn, pitch_down, ear_open=None, ear_delta=0.045, ear_drop_closed=0.13):
    self.ear_closed = float(ear_closed)
    self.mar_yawn = float(mar_yawn)
    self.pitch_down = float(pitch_down)
    self.ear_open = None if ear_open is None else float(ear_open)
    self.ear_delta = float(ear_delta)
    self.ear_drop_closed = float(ear_drop_closed)
```

Replace `from_profile` with:

```python
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
```

Replace `to_dict` with:

```python
def to_dict(self):
    return {
        "ear_closed": self.ear_closed,
        "ear_open": self.ear_open,
        "ear_delta": self.ear_delta,
        "ear_drop_closed": self.ear_drop_closed,
        "mar_yawn": self.mar_yawn,
        "pitch_down": self.pitch_down,
    }
```

- [ ] **Step 5: Run calibration and threshold tests**

Run:

```powershell
python -m pytest Version3\tests\test_calibration.py Version3\tests\test_threshold_policy.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add Version3\config.py Version3\ai\calibration.py Version3\ai\threshold_policy.py Version3\tests\test_calibration.py Version3\tests\test_threshold_policy.py
git commit -m "feat: add adaptive ear baseline thresholds"
```

---

### Task 5: Add RED Tests For Glasses Closed-Eye Detection

**Files:**
- Modify: `Version3/tests/test_drowsiness_classifier.py`

- [ ] **Step 1: Add helper profile for glasses**

In `Version3/tests/test_drowsiness_classifier.py`, update helper `profile` signature to:

```python
def profile(ear=0.24, mar=0.45, pitch=-15.0, ear_open=0.29, ear_drop=0.13):
    return CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=ear_open,
        mar_closed_median=0.12,
        pitch_neutral=pitch + 15.0,
        ear_closed_threshold=ear,
        ear_adaptive_closed_threshold=ear,
        ear_drop_closed_threshold=ear_drop,
        ear_open_delta=0.045,
        mar_yawn_threshold=mar,
        pitch_down_threshold=pitch,
        sample_count=40,
        face_height_median=220.0,
    )
```

- [ ] **Step 2: Add adaptive classifier tests**

Append:

```python
def test_glasses_closed_eyes_detected_by_drop_from_baseline():
    classifier = DrowsinessClassifier(profile=profile(ear=0.275, ear_open=0.32), target_fps=10)

    for _ in range(8):
        result = classifier.update(metrics(ear=0.27, left_ear=0.27, right_ear=0.27, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 1
    assert round(result["features"]["ear_drop_score"], 3) >= 0.13
    assert result["features"]["closed_by_drop"] is True


def test_glasses_open_eyes_stay_normal_near_baseline():
    classifier = DrowsinessClassifier(profile=profile(ear=0.275, ear_open=0.32), target_fps=10)

    for _ in range(20):
        result = classifier.update(metrics(ear=0.30, left_ear=0.30, right_ear=0.30, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert round(result["features"]["ear_drop_score"], 3) < 0.13


def test_non_glasses_closed_eyes_still_detected_at_default_threshold():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24, ear_open=0.27), target_fps=10)

    for _ in range(8):
        result = classifier.update(metrics(ear=0.24, left_ear=0.24, right_ear=0.24, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 1
    assert result["features"]["closed_by_threshold"] is True
```

- [ ] **Step 3: Add one-eye glare guard test**

Append:

```python
def test_one_low_eye_does_not_close_when_other_eye_is_clearly_open():
    classifier = DrowsinessClassifier(profile=profile(ear=0.275, ear_open=0.32), target_fps=10)

    for _ in range(20):
        result = classifier.update(metrics(
            face_present=True,
            ear=0.275,
            left_ear=0.32,
            right_ear=0.23,
            mar=0.12,
            pitch=0.0,
            eye_quality={"usable": True, "selected": "both", "reason": "OK"},
        ))

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert result["features"]["one_eye_guard_active"] is True
```

- [ ] **Step 4: Run tests and verify RED**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py -q
```

Expected:

```text
FAILED ... KeyError: 'ear_drop_score'
```

or:

```text
FAILED ... assert 'NORMAL' == 'DROWSY'
```

- [ ] **Step 5: Keep RED tests uncommitted for Slice 3**

Do not commit here. Continue directly to Task 6, then commit the complete green Slice 3 after `Version3\tests\test_drowsiness_classifier.py` passes.


---

### Task 6: Implement Adaptive Closed-Eye Decision In Classifier

**Files:**
- Modify: `Version3/ai/drowsiness_classifier.py`
- Test: `Version3/tests/test_drowsiness_classifier.py`

- [ ] **Step 1: Add helper method for EAR drop**

In `DrowsinessClassifier`, before `_classify_sample`, add:

```python
@staticmethod
def _ear_drop_score(ear_open, ear_current):
    if ear_open is None or float(ear_open or 0.0) <= 0.0:
        return 0.0
    return max(0.0, (float(ear_open) - float(ear_current or 0.0)) / float(ear_open))

@staticmethod
def _default_eye_decision():
    return {
        "closed": False,
        "closed_by_threshold": False,
        "closed_by_drop": False,
        "ear_drop_score": 0.0,
        "left_ear_drop_score": 0.0,
        "right_ear_drop_score": 0.0,
        "one_eye_guard_active": False,
    }
```

- [ ] **Step 2: Add helper method for closed-eye decision**

Add:

```python
def _eye_closed_decision(self, sample, thresholds):
    ear = float(sample["ear"] or 0.0)
    left_ear = float(sample["left_ear"] or ear)
    right_ear = float(sample["right_ear"] or ear)
    ear_open = thresholds.get("ear_open")
    ear_closed = float(thresholds["ear_closed"])
    drop_threshold = float(thresholds.get("ear_drop_closed", 0.13))

    used_drop = self._ear_drop_score(ear_open, ear)
    left_drop = self._ear_drop_score(ear_open, left_ear)
    right_drop = self._ear_drop_score(ear_open, right_ear)

    used_closed_by_threshold = ear <= ear_closed
    used_closed_by_drop = used_drop >= drop_threshold
    left_closed = left_ear <= ear_closed or left_drop >= drop_threshold
    right_closed = right_ear <= ear_closed or right_drop >= drop_threshold

    selected = (sample.get("eye_quality") or {}).get("selected", "both")
    one_eye_guard_active = False
    if selected == "both" and left_closed != right_closed:
        one_eye_guard_active = True
        closed = False
    elif selected == "left":
        closed = left_closed
    elif selected == "right":
        closed = right_closed
    else:
        closed = used_closed_by_threshold or used_closed_by_drop

    return {
        "closed": bool(closed),
        "closed_by_threshold": bool(used_closed_by_threshold),
        "closed_by_drop": bool(used_closed_by_drop),
        "ear_drop_score": float(used_drop),
        "left_ear_drop_score": float(left_drop),
        "right_ear_drop_score": float(right_drop),
        "one_eye_guard_active": bool(one_eye_guard_active),
    }
```

- [ ] **Step 3: Use helper in `_classify_sample`**

Replace:

```python
ear_low = sample["usable"] and sample["ear"] < thresholds["ear_closed"]
```

with:

```python
if sample["usable"]:
    eye_decision = self._eye_closed_decision(sample, thresholds)
else:
    eye_decision = self._default_eye_decision()
ear_low = sample["usable"] and eye_decision["closed"]
self._last_eye_decision = eye_decision
```

In `__init__`, initialize:

```python
self._last_eye_decision = self._default_eye_decision()
```

In `reset_state`, reset `_last_eye_decision`:

```python
self._last_eye_decision = self._default_eye_decision()
```

In the `if not sample["usable"]:` block, before returning `LOW_CONFIDENCE` or `NO_FACE`, keep the telemetry neutral:

```python
self._last_eye_decision = self._default_eye_decision()
```

- [ ] **Step 4: Expose decision fields in features**

In `_features`, add:

```python
features.update(self._last_eye_decision)
features.update({
    "ear_open_baseline": self._thresholds().get("ear_open"),
})
```

- [ ] **Step 5: Run classifier tests**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add Version3\ai\drowsiness_classifier.py Version3\tests\test_drowsiness_classifier.py
git commit -m "feat: classify eye closure from adaptive ear drop"
```

---

### Task 7: Add RED Tests For Alert De-Escalation After AI Recovery

**Files:**
- Modify: `Version3/tests/test_alert_ai_state.py`

- [ ] **Step 1: Add alert manager recovery tests**

If the existing `Metrics` helper does not accept constructor arguments, replace it with:

```python
class Metrics:
    def __init__(self, face_present=True, ear=0.31, mar=0.24, pitch=0.0):
        self.face_present = face_present
        self.ear = ear
        self.mar = mar
        self.pitch = pitch
```

Append to `Version3/tests/test_alert_ai_state.py`:

```python
def test_alert_manager_stops_outputs_when_ai_recovers_to_normal():
    speaker = FakeSpeaker()
    manager = AlertManager(speaker=speaker)
    metrics = Metrics(ear=0.20, mar=0.12, pitch=0.0, face_present=True)

    manager.update(metrics, perclos=0.50, ai_result={
        "state": "DROWSY",
        "confidence": 0.90,
        "reason": "test drowsy",
        "alert_hint": 2,
    })

    assert manager.current_level == AlertLevel.LEVEL_2
    assert speaker.last_level == 2

    metrics = Metrics(ear=0.30, mar=0.12, pitch=0.0, face_present=True)
    manager.update(metrics, perclos=0.40, ai_result={
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
```

If `FakeSpeaker` does not expose `stopped`, update it in the same file:

```python
class FakeSpeaker:
    def __init__(self):
        self.last_level = None
        self.stopped = False

    def play_alert(self, level):
        self.last_level = level
        self.stopped = False
        return True

    def stop(self):
        self.stopped = True
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest Version3\tests\test_alert_ai_state.py::test_alert_manager_stops_outputs_when_ai_recovers_to_normal Version3\tests\test_alert_ai_state.py::test_alert_manager_does_not_stop_outputs_on_low_confidence_hint_zero Version3\tests\test_alert_ai_state.py::test_alert_manager_does_not_stop_outputs_on_no_face_hint_zero -q
```

Expected:

```text
FAILED ... assert 2 == 0
```

- [ ] **Step 3: Keep RED tests uncommitted for Slice 4**

Do not commit here. Continue directly to Task 8, then commit the complete green Slice 4 after `Version3\tests\test_alert_ai_state.py` passes.


---

### Task 8: Implement Immediate De-Escalation For Explicit AI Normal

**Files:**
- Modify: `Version3/alerts/alert_manager.py`
- Test: `Version3/tests/test_alert_ai_state.py`

- [ ] **Step 1: Allow explicit AI hint to de-escalate without cooldown**

In `AlertManager.update`, replace:

```python
if new_level != self._current_level:
    if (now - self._last_alert_time) >= config.ALERT_COOLDOWN or new_level > self._current_level:
```

with:

```python
if new_level != self._current_level:
    explicit_ai_deescalation = (
        ai_state == "NORMAL"
        and hinted_level == AlertLevel.NONE
        and new_level < self._current_level
    )
    if explicit_ai_deescalation or (now - self._last_alert_time) >= config.ALERT_COOLDOWN or new_level > self._current_level:
```

- [ ] **Step 2: Run alert tests**

Run:

```powershell
python -m pytest Version3\tests\test_alert_ai_state.py -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Commit**

Run:

```powershell
git add Version3\alerts\alert_manager.py Version3\tests\test_alert_ai_state.py
git commit -m "fix: stop alerts when ai returns to normal"
```

---

### Task 9: Update Local GUI Telemetry For Baseline And Recovery

**Files:**
- Modify: `Version3/ui/local_monitor.py`
- Modify: `Version3/scripts/local_ai_monitor.py`
- Modify: `Version3/tests/test_local_monitor_gui.py`
- Modify: `Version3/tests/test_local_ai_monitor_script.py`

- [ ] **Step 1: Add local monitor tests**

In `Version3/tests/test_local_ai_monitor_script.py`, add a case that calls `build_overlay_lines` with:

```python
ai_result = {
    "state": "NORMAL",
    "confidence": 0.92,
    "reason": "stable open eyes",
    "alert_hint": 0,
    "thresholds": {
        "ear_closed": 0.275,
        "ear_open": 0.32,
        "ear_drop_closed": 0.13,
        "mar_yawn": 0.45,
        "pitch_down": -15.0,
    },
    "features": {
        "ear_drop_score": 0.156,
        "eyes_open_sec": 1.2,
        "perclos_gate_active": False,
        "one_eye_guard_active": True,
        "perclos_short": 0.0,
        "perclos_long": 0.42,
    },
}
```

Assert:

```python
assert any("Adaptive base 0.320" in line for line in lines)
assert any("drop 0.156/0.130" in line for line in lines)
assert any("open 1.2s" in line for line in lines)
assert any("PERCLOS gate OFF" in line for line in lines)
assert any("one-eye guard ON" in line for line in lines)
```

In `Version3/tests/test_local_monitor_gui.py`, update `test_state_extracts_thresholds_calibration_and_landmarks` so the payload includes the new optional threshold and feature fields:

```python
"thresholds": {
    "ear_closed": 0.275,
    "ear_open": 0.32,
    "ear_drop_closed": 0.13,
    "mar_yawn": 0.45,
    "pitch_down": -15.0,
},
"features": {
    "ear_drop_score": 0.156,
    "eyes_open_sec": 1.2,
    "perclos_gate_active": False,
    "one_eye_guard_active": True,
    "perclos_short": 0.1,
    "perclos_long": 0.2,
},
```

Then assert:

```python
self.assertEqual(state.ear_open_baseline, 0.32)
self.assertEqual(state.ear_drop_score, 0.156)
self.assertEqual(state.ear_drop_threshold, 0.13)
self.assertEqual(state.eyes_open_sec, 1.2)
self.assertFalse(state.perclos_gate_active)
self.assertTrue(state.one_eye_guard_active)
```

- [ ] **Step 2: Run GUI tests and verify RED**

Run:

```powershell
python -m pytest Version3\tests\test_local_ai_monitor_script.py Version3\tests\test_local_monitor_gui.py -q
```

Expected:

```text
FAILED ... AttributeError
```

or:

```text
FAILED ... assert False
```

- [ ] **Step 3: Implement integrated GUI fields**

In `Version3/ui/local_monitor.py`, extend `LocalMonitorState.FIELDS` with:

```python
"ear_open_baseline",
"ear_drop_score",
"ear_drop_threshold",
"eyes_open_sec",
"perclos_gate_active",
"one_eye_guard_active",
```

Add defaults in `LocalMonitorState.DEFAULTS`:

```python
"ear_open_baseline": 0.0,
"ear_drop_score": 0.0,
"ear_drop_threshold": 0.13,
"eyes_open_sec": 0.0,
"perclos_gate_active": False,
"one_eye_guard_active": False,
```

In `LocalMonitorState.from_runtime_payload`, read:

```python
ear_open_baseline=_float(thresholds.get("ear_open"), 0.0),
ear_drop_score=_float(features.get("ear_drop_score"), 0.0),
ear_drop_threshold=_float(thresholds.get("ear_drop_closed"), 0.13),
eyes_open_sec=_float(features.get("eyes_open_sec"), 0.0),
perclos_gate_active=bool(features.get("perclos_gate_active")),
one_eye_guard_active=bool(features.get("one_eye_guard_active")),
```

In `build_panel_lines`, insert this line immediately after the existing `"Pitch %.1f / %.1f | PERCLOS %.3f / %.3f"` line:

```python
"Adaptive base %.3f | threshold %.3f | drop %.3f/%.3f | open %.1fs" % (
    state.ear_open_baseline,
    state.ear_threshold,
    state.ear_drop_score,
    state.ear_drop_threshold,
    state.eyes_open_sec,
)
```

Insert one more line immediately after that adaptive line:

```python
"PERCLOS gate %s | one-eye guard %s" % (
    "ON" if state.perclos_gate_active else "OFF",
    "ON" if state.one_eye_guard_active else "OFF",
)
```

- [ ] **Step 4: Implement standalone monitor text fields**

In `Version3/scripts/local_ai_monitor.py`, update `build_overlay_lines` so it appends:

```python
"Adaptive base %.3f | threshold %.3f | drop %.3f/%.3f | open %.1fs" % (
    float(thresholds.get("ear_open") or 0.0),
    float(thresholds.get("ear_closed", config.EAR_THRESHOLD) or config.EAR_THRESHOLD),
    float(features.get("ear_drop_score") or 0.0),
    float(thresholds.get("ear_drop_closed") or 0.13),
    float(features.get("eyes_open_sec") or 0.0),
)
```

and:

```python
"PERCLOS gate %s | one-eye guard %s" % (
    "ON" if features.get("perclos_gate_active") else "OFF",
    "ON" if features.get("one_eye_guard_active") else "OFF",
)
```

- [ ] **Step 5: Run GUI tests**

Run:

```powershell
python -m pytest Version3\tests\test_local_ai_monitor_script.py Version3\tests\test_local_monitor_gui.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add Version3\ui\local_monitor.py Version3\scripts\local_ai_monitor.py Version3\tests\test_local_monitor_gui.py Version3\tests\test_local_ai_monitor_script.py
git commit -m "feat: show adaptive ear recovery telemetry"
```

---

### Task 10: Full Verification And Jetson Deployment

**Files:**
- Verify local project files.
- Deploy only after local tests pass.

- [ ] **Step 1: Run focused Version3 tests**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py Version3\tests\test_calibration.py Version3\tests\test_threshold_policy.py Version3\tests\test_alert_ai_state.py Version3\tests\test_local_monitor_gui.py Version3\tests\test_local_ai_monitor_script.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run broader Version3 tests if runtime dependencies are available**

Run:

```powershell
python -m pytest Version3\tests -q
```

Expected:

```text
passed
```

If optional hardware-only tests fail because Windows lacks Jetson devices, record the exact failing test names and continue only if the focused tests in Step 1 pass.

- [ ] **Step 3: Deploy runtime files to Jetson**

Run these exact subdirectory-aware commands so each file lands in the correct package directory:

```powershell
scp Version3\config.py nano@192.168.2.17:/home/nano/Version3/config.py
scp Version3\ai\calibration.py Version3\ai\threshold_policy.py Version3\ai\drowsiness_classifier.py nano@192.168.2.17:/home/nano/Version3/ai/
scp Version3\alerts\alert_manager.py nano@192.168.2.17:/home/nano/Version3/alerts/
scp Version3\ui\local_monitor.py nano@192.168.2.17:/home/nano/Version3/ui/
scp Version3\scripts\local_ai_monitor.py nano@192.168.2.17:/home/nano/Version3/scripts/
```

- [ ] **Step 4: Restart Jetson runtime**

On Jetson via NoMachine:

```bash
/home/nano/start_drowsiguard_full.sh
```

or double-click **DrowsiGuard Full**.

- [ ] **Step 5: Manual validation without glasses**

Expected observations:

```text
Mắt mở EAR khoảng 0.26-0.30 -> AI NORMAL
Nhắm mắt 0.8s -> DROWSY level 1
Nhắm mắt 1.8s -> DROWSY level 2
Nhắm mắt 3.0s -> DROWSY level 3
Mở mắt lại ổn định khoảng 1s -> AI NORMAL, alert về NONE
```

- [ ] **Step 6: Manual validation with prescription glasses**

Expected observations:

```text
Mắt mở EAR khoảng 0.30-0.33 -> AI NORMAL
Nhắm mắt EAR khoảng 0.26-0.28 -> DROWSY after duration threshold
Nếu một mắt bị phản chiếu IR nhưng mắt còn lại mở rõ -> AI NORMAL hoặc LOW_CONFIDENCE, không DROWSY
Overlay hiển thị ear_open_baseline, drop score, PERCLOS gate, one-eye guard
```

- [ ] **Step 7: Commit final verification note**

Run:

```powershell
git status --short
git add docs/superpowers/plans/2026-05-05-drowsiness-ai-glasses-perclos-stabilization.md
git commit -m "docs: plan drowsiness ai glasses stabilization"
```

Do not commit generated runtime logs, database files, or camera snapshots.

---

## Self-Review

- **Spec coverage:** The plan covers stale PERCLOS false positives, adaptive EAR baseline for glasses, non-glasses default behavior, one-eye glasses/IR noise, alert de-escalation, GUI telemetry, local tests, and Jetson deployment.
- **Placeholder scan:** The plan contains concrete file paths, commands, expected failures, implementation snippets, and validation criteria.
- **Commit workflow:** RED checks are verification checkpoints only; commits happen after each vertical slice is GREEN.
- **Type consistency:** New fields are consistently named `ear_open`, `ear_delta`, `ear_drop_closed`, `ear_drop_score`, `eyes_open_sec`, `perclos_gate_active`, and `one_eye_guard_active` across threshold policy, classifier features, and GUI display.
