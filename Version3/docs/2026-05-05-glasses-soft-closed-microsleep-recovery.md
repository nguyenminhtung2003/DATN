# Glasses Soft-Closed Calibration And Microsleep Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve drowsiness detection for drivers whose glasses keep EAR in a narrow range, and prevent stale microsleep evidence from keeping the AI state stuck in `DROWSY`.

**Architecture:** Add an optional soft-closed calibration phase that learns each driver's open-eye and nheo/closed-eye EAR medians, including per-eye medians, then derives driver-specific closed thresholds from the measured separation. Keep the old adaptive threshold as fallback when soft-closed samples are missing or unreliable. Separately, change microsleep escalation so it acts as recent risk evidence, not a 60-second unconditional `DROWSY` latch.

**Tech Stack:** Python 3.6-compatible syntax, pytest, existing Version3 calibration/classifier/session-controller/local-monitor architecture.

---

## File Structure

- Modify: `Version3/config.py`
  - Add feature flags and tuning constants for soft-closed calibration and microsleep recovery.
- Modify: `Version3/ai/calibration.py`
  - Extend samples/profile fields for soft-closed medians, per-eye thresholds, phase counts, and reliability reason.
  - Keep existing open-eye calibration behavior as fallback.
- Modify: `Version3/ai/threshold_policy.py`
  - Expose aggregate and per-eye closed thresholds from `CalibrationProfile`.
- Modify: `Version3/ai/drowsiness_classifier.py`
  - Use per-eye learned closed thresholds.
  - Add microsleep recent/recovery gating.
- Modify: `Version3/ai/session_controller.py`
  - Drive open-eye then soft-closed calibration phases based on elapsed calibration time.
  - Expose calibration phase/counts in payloads.
- Modify: `Version3/main.py`
  - Include new calibration fields in logs/runtime payload already passing through `calibration_payload()`.
  - No alert/audio flow change.
- Modify: `Version3/ui/local_monitor.py`
  - Display calibration phase instructions and soft-closed sample counts.
- Modify tests:
  - `Version3/tests/test_calibration.py`
  - `Version3/tests/test_threshold_policy.py`
  - `Version3/tests/test_drowsiness_classifier.py`
  - `Version3/tests/test_ai_session_controller.py`
  - `Version3/tests/test_local_monitor_gui.py`
  - `Version3/tests/test_config_defaults.py`

---

## Behavior Target

For the measured glasses case:

```text
open EAR:        0.29 - 0.31
soft-closed EAR: 0.26 - 0.27
```

The calibrated threshold should be around:

```python
threshold = soft_closed + (open - soft_closed) * 0.40
```

Example:

```text
open = 0.300
soft_closed = 0.265
threshold = 0.265 + 0.035 * 0.40 = 0.279
```

Expected runtime behavior:

- EAR `0.29-0.31` stays `NORMAL`.
- EAR `0.26-0.27` becomes closed evidence after the existing duration debounce.
- One eye closed while the other remains clearly open uses the existing one-eye guard path, not immediate `DROWSY`.
- `microsleep_count >= 3` no longer keeps state `DROWSY` after eyes are open and stable for the configured recovery duration.

---

### Task 1: Add Soft-Closed Calibration Profile Fields

**Files:**
- Modify: `Version3/config.py`
- Modify: `Version3/ai/calibration.py`
- Test: `Version3/tests/test_config_defaults.py`
- Test: `Version3/tests/test_calibration.py`

- [ ] **Step 1: Add failing config defaults test**

Add to `Version3/tests/test_config_defaults.py`:

```python
    def test_soft_closed_calibration_flags_default_to_safe_values(self):
        self.assertTrue(config.SOFT_CLOSED_CALIBRATION)
        self.assertEqual(config.SOFT_CLOSED_OPEN_SECONDS, 3.0)
        self.assertEqual(config.SOFT_CLOSED_SECONDS, 2.0)
        self.assertEqual(config.SOFT_CLOSED_MIN_SAMPLES, 10)
        self.assertEqual(config.SOFT_CLOSED_MIN_SEPARATION, 0.025)
        self.assertEqual(config.SOFT_CLOSED_THRESHOLD_RATIO, 0.40)
        self.assertEqual(config.MICROSLEEP_RECENT_SECONDS, 5.0)
        self.assertEqual(config.MICROSLEEP_RECOVERY_OPEN_SECONDS, 1.5)
```

- [ ] **Step 2: Run config test and verify RED**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_config_defaults.py::ConfigDefaultsTest::test_soft_closed_calibration_flags_default_to_safe_values -q
```

Expected: FAIL with missing attributes such as `config.SOFT_CLOSED_CALIBRATION`.

- [ ] **Step 3: Add config constants**

Add to `Version3/config.py` near existing AI classifier flags:

```python
SOFT_CLOSED_CALIBRATION = env_bool("DROWSIGUARD_SOFT_CLOSED_CALIBRATION", True)
SOFT_CLOSED_OPEN_SECONDS = env_float("DROWSIGUARD_SOFT_CLOSED_OPEN_SECONDS", 3.0)
SOFT_CLOSED_SECONDS = env_float("DROWSIGUARD_SOFT_CLOSED_SECONDS", 2.0)
SOFT_CLOSED_MIN_SAMPLES = env_int("DROWSIGUARD_SOFT_CLOSED_MIN_SAMPLES", 10)
SOFT_CLOSED_MIN_SEPARATION = env_float("DROWSIGUARD_SOFT_CLOSED_MIN_SEPARATION", 0.025)
SOFT_CLOSED_THRESHOLD_RATIO = env_float("DROWSIGUARD_SOFT_CLOSED_THRESHOLD_RATIO", 0.40)
MICROSLEEP_RECENT_SECONDS = env_float("DROWSIGUARD_MICROSLEEP_RECENT_SECONDS", 5.0)
MICROSLEEP_RECOVERY_OPEN_SECONDS = env_float("DROWSIGUARD_MICROSLEEP_RECOVERY_OPEN_SECONDS", 1.5)
```

- [ ] **Step 4: Run config test and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_config_defaults.py::ConfigDefaultsTest::test_soft_closed_calibration_flags_default_to_safe_values -q
```

Expected: PASS.

- [ ] **Step 5: Add failing calibration test for aggregate soft-closed threshold**

Add to `Version3/tests/test_calibration.py`:

```python
def test_calibration_uses_soft_closed_samples_for_narrow_glasses_range():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)
    for i in range(30):
        calibrator.add(sample(ear=0.30, left_ear=0.31, right_ear=0.29), i * 0.1, phase="open")
    for i in range(12):
        calibrator.add(sample(ear=0.265, left_ear=0.270, right_ear=0.260), 3.0 + i * 0.1, phase="soft_closed")

    profile = calibrator.profile

    assert profile.valid is True
    assert profile.reason == "OK"
    assert round(profile.ear_open_median, 3) == 0.300
    assert round(profile.ear_soft_closed_median, 3) == 0.265
    assert round(profile.ear_soft_closed_separation, 3) == 0.035
    assert profile.soft_closed_valid is True
    assert profile.soft_closed_reason == "OK"
    assert round(profile.ear_closed_threshold, 3) == 0.279
    assert round(profile.ear_adaptive_closed_threshold, 3) == 0.279
    assert profile.open_sample_count == 30
    assert profile.soft_closed_sample_count == 12
```

- [ ] **Step 6: Add failing calibration test for unreliable separation fallback**

Add to `Version3/tests/test_calibration.py`:

```python
def test_calibration_falls_back_when_soft_closed_separation_is_too_small():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)
    for i in range(30):
        calibrator.add(sample(ear=0.300, left_ear=0.305, right_ear=0.295), i * 0.1, phase="open")
    for i in range(12):
        calibrator.add(sample(ear=0.286, left_ear=0.290, right_ear=0.282), 3.0 + i * 0.1, phase="soft_closed")

    profile = calibrator.profile

    assert profile.valid is True
    assert profile.soft_closed_valid is False
    assert profile.soft_closed_reason == "SOFT_CLOSED_SEPARATION_TOO_SMALL"
    assert round(profile.ear_soft_closed_separation, 3) == 0.014
    assert round(profile.ear_closed_threshold, 3) == 0.255
```

The fallback expected value `0.255` comes from old adaptive behavior for open EAR `0.300`: `0.300 - EAR_OPEN_DELTA(0.045)`.

- [ ] **Step 7: Add failing calibration test for per-eye soft-closed thresholds**

Add to `Version3/tests/test_calibration.py`:

```python
def test_calibration_stores_per_eye_soft_closed_thresholds():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)
    for i in range(30):
        calibrator.add(sample(ear=0.300, left_ear=0.330, right_ear=0.290), i * 0.1, phase="open")
    for i in range(12):
        calibrator.add(sample(ear=0.265, left_ear=0.285, right_ear=0.255), 3.0 + i * 0.1, phase="soft_closed")

    profile = calibrator.profile

    assert round(profile.left_ear_soft_closed_median, 3) == 0.285
    assert round(profile.right_ear_soft_closed_median, 3) == 0.255
    assert round(profile.left_ear_closed_threshold, 3) == 0.303
    assert round(profile.right_ear_closed_threshold, 3) == 0.269
```

The per-eye thresholds use `soft + (open - soft) * 0.40`.

- [ ] **Step 8: Run calibration tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_calibration.py::test_calibration_uses_soft_closed_samples_for_narrow_glasses_range tests\test_calibration.py::test_calibration_falls_back_when_soft_closed_separation_is_too_small tests\test_calibration.py::test_calibration_stores_per_eye_soft_closed_thresholds -q
```

Expected: FAIL because `DriverCalibrator.add()` does not accept `phase` and profile fields do not exist.

- [ ] **Step 9: Extend calibration sample/profile data model**

In `Version3/ai/calibration.py`, update `CalibrationSample.__init__`:

```python
        phase="open",
```

and set:

```python
        self.phase = phase if phase in ("open", "soft_closed") else "open"
```

Extend `CalibrationProfile.__init__` parameters:

```python
        ear_soft_closed_median=None,
        left_ear_soft_closed_median=None,
        right_ear_soft_closed_median=None,
        ear_soft_closed_separation=None,
        left_ear_closed_threshold=None,
        right_ear_closed_threshold=None,
        soft_closed_valid=False,
        soft_closed_reason="NOT_COLLECTED",
        open_sample_count=None,
        soft_closed_sample_count=0,
```

Set instance fields:

```python
        self.ear_soft_closed_median = ear_soft_closed_median
        self.left_ear_soft_closed_median = left_ear_soft_closed_median
        self.right_ear_soft_closed_median = right_ear_soft_closed_median
        self.ear_soft_closed_separation = ear_soft_closed_separation
        self.left_ear_closed_threshold = left_ear_closed_threshold
        self.right_ear_closed_threshold = right_ear_closed_threshold
        self.soft_closed_valid = bool(soft_closed_valid)
        self.soft_closed_reason = soft_closed_reason
        self.open_sample_count = int(sample_count if open_sample_count is None else open_sample_count)
        self.soft_closed_sample_count = int(soft_closed_sample_count or 0)
```

Add the same fields to `fallback()` with safe defaults:

```python
            ear_soft_closed_median=None,
            left_ear_soft_closed_median=None,
            right_ear_soft_closed_median=None,
            ear_soft_closed_separation=None,
            left_ear_closed_threshold=None,
            right_ear_closed_threshold=None,
            soft_closed_valid=False,
            soft_closed_reason=reason,
            open_sample_count=sample_count,
            soft_closed_sample_count=0,
```

Add to `to_dict()`:

```python
            "ear_soft_closed_median": self.ear_soft_closed_median,
            "left_ear_soft_closed_median": self.left_ear_soft_closed_median,
            "right_ear_soft_closed_median": self.right_ear_soft_closed_median,
            "ear_soft_closed_separation": self.ear_soft_closed_separation,
            "left_ear_closed_threshold": self.left_ear_closed_threshold,
            "right_ear_closed_threshold": self.right_ear_closed_threshold,
            "soft_closed_valid": self.soft_closed_valid,
            "soft_closed_reason": self.soft_closed_reason,
            "open_sample_count": self.open_sample_count,
            "soft_closed_sample_count": self.soft_closed_sample_count,
```

- [ ] **Step 10: Add threshold helper**

Add near `_clamp()` in `Version3/ai/calibration.py`:

```python
def _soft_closed_threshold(open_value, closed_value, ratio=None, min_separation=None):
    if open_value is None or closed_value is None:
        return None, None, False, "NOT_COLLECTED"
    open_value = float(open_value)
    closed_value = float(closed_value)
    separation = open_value - closed_value
    min_separation = float(
        min_separation if min_separation is not None else getattr(config, "SOFT_CLOSED_MIN_SEPARATION", 0.025)
    )
    if separation < min_separation:
        return None, separation, False, "SOFT_CLOSED_SEPARATION_TOO_SMALL"
    ratio = float(ratio if ratio is not None else getattr(config, "SOFT_CLOSED_THRESHOLD_RATIO", 0.40))
    return closed_value + separation * ratio, separation, True, "OK"
```

- [ ] **Step 11: Split calibrator samples by phase**

Change `DriverCalibrator.__init__`:

```python
        self._open_samples = []
        self._soft_closed_samples = []
```

Keep `self._samples = []` for compatibility if desired, but make it point to open samples:

```python
        self._samples = self._open_samples
```

Update `add()` signature:

```python
    def add(self, metrics, timestamp, phase="open"):
```

Pass `phase=phase` into `CalibrationSample`.

When valid:

```python
            if sample.phase == "soft_closed":
                self._soft_closed_samples.append(sample)
            else:
                self._open_samples.append(sample)
            self._samples = self._open_samples
            self._profile = None
```

Update `sample_count`:

```python
        return len(self._open_samples)
```

Update `reset()`:

```python
        self._open_samples = []
        self._soft_closed_samples = []
        self._samples = self._open_samples
```

- [ ] **Step 12: Build profile with soft-closed thresholds**

In `_build_profile()`, treat open samples as the canonical baseline:

```python
        count = len(self._open_samples)
        if count < self.min_samples:
            return CalibrationProfile.fallback(reason="NOT_ENOUGH_SAMPLES", sample_count=count)

        open_samples = self._open_samples
        soft_samples = self._soft_closed_samples
```

Use `open_samples` for existing medians.

After computing old fallback `ear_closed`, compute soft-closed values:

```python
        soft_closed_valid = False
        soft_closed_reason = "NOT_COLLECTED"
        ear_soft_closed = None
        left_ear_soft_closed = None
        right_ear_soft_closed = None
        ear_soft_closed_separation = None
        left_ear_closed_threshold = None
        right_ear_closed_threshold = None

        if bool(getattr(config, "SOFT_CLOSED_CALIBRATION", True)) and len(soft_samples) >= int(getattr(config, "SOFT_CLOSED_MIN_SAMPLES", 10)):
            ear_soft_closed = float(statistics.median([s.ear_used for s in soft_samples]))
            left_ear_soft_closed = float(statistics.median([s.left_ear for s in soft_samples]))
            right_ear_soft_closed = float(statistics.median([s.right_ear for s in soft_samples]))
            soft_threshold, separation, soft_closed_valid, soft_closed_reason = _soft_closed_threshold(ear_open, ear_soft_closed)
            ear_soft_closed_separation = separation
            if soft_closed_valid:
                ear_closed = soft_threshold
                left_threshold, _, left_valid, _ = _soft_closed_threshold(left_ear_open, left_ear_soft_closed)
                right_threshold, _, right_valid, _ = _soft_closed_threshold(right_ear_open, right_ear_soft_closed)
                left_ear_closed_threshold = left_threshold if left_valid else None
                right_ear_closed_threshold = right_threshold if right_valid else None
                ear_drop_closed = min(float(ear_drop_closed), 0.08)
```

Pass all new fields into `CalibrationProfile(...)`:

```python
            ear_soft_closed_median=ear_soft_closed,
            left_ear_soft_closed_median=left_ear_soft_closed,
            right_ear_soft_closed_median=right_ear_soft_closed,
            ear_soft_closed_separation=ear_soft_closed_separation,
            left_ear_closed_threshold=left_ear_closed_threshold,
            right_ear_closed_threshold=right_ear_closed_threshold,
            soft_closed_valid=soft_closed_valid,
            soft_closed_reason=soft_closed_reason,
            open_sample_count=count,
            soft_closed_sample_count=len(soft_samples),
```

- [ ] **Step 13: Run calibration and config tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_config_defaults.py tests\test_calibration.py -q
```

Expected: PASS.

---

### Task 2: Expose Soft-Closed Thresholds To The Classifier

**Files:**
- Modify: `Version3/ai/threshold_policy.py`
- Modify: `Version3/ai/drowsiness_classifier.py`
- Test: `Version3/tests/test_threshold_policy.py`
- Test: `Version3/tests/test_drowsiness_classifier.py`

- [ ] **Step 1: Add failing threshold policy test**

Add to `Version3/tests/test_threshold_policy.py`:

```python
def test_threshold_policy_exposes_soft_closed_per_eye_thresholds():
    profile = CalibrationProfile(
        valid=True,
        ear_open_median=0.30,
        left_ear_open_median=0.33,
        right_ear_open_median=0.29,
        ear_closed_threshold=0.279,
        left_ear_closed_threshold=0.303,
        right_ear_closed_threshold=0.269,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
    )

    thresholds = ThresholdPolicy.from_profile(profile).to_dict()

    assert thresholds["ear_closed"] == 0.279
    assert thresholds["left_ear_closed"] == 0.303
    assert thresholds["right_ear_closed"] == 0.269
```

- [ ] **Step 2: Run threshold policy test and verify RED**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_threshold_policy.py::test_threshold_policy_exposes_soft_closed_per_eye_thresholds -q
```

Expected: FAIL because `left_ear_closed` and `right_ear_closed` are missing.

- [ ] **Step 3: Extend ThresholdPolicy**

In `Version3/ai/threshold_policy.py`, extend `__init__`:

```python
        left_ear_closed=None,
        right_ear_closed=None,
```

Set fields:

```python
        self.left_ear_closed = None if left_ear_closed is None else float(left_ear_closed)
        self.right_ear_closed = None if right_ear_closed is None else float(right_ear_closed)
```

In `from_profile()` pass:

```python
            left_ear_closed=getattr(profile, "left_ear_closed_threshold", None),
            right_ear_closed=getattr(profile, "right_ear_closed_threshold", None),
```

In `to_dict()` add:

```python
            "left_ear_closed": self.left_ear_closed,
            "right_ear_closed": self.right_ear_closed,
```

- [ ] **Step 4: Run threshold policy test and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_threshold_policy.py::test_threshold_policy_exposes_soft_closed_per_eye_thresholds -q
```

Expected: PASS.

- [ ] **Step 5: Add failing classifier test for glasses narrow EAR range**

Add to `Version3/tests/test_drowsiness_classifier.py`:

```python
def test_soft_closed_profile_catches_glasses_narrow_ear_range():
    classifier = DrowsinessClassifier(target_fps=10)
    profile = CalibrationProfile(
        valid=True,
        ear_open_median=0.300,
        left_ear_open_median=0.310,
        right_ear_open_median=0.290,
        ear_closed_threshold=0.279,
        left_ear_closed_threshold=0.294,
        right_ear_closed_threshold=0.276,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
    )
    classifier.set_profile(profile)

    result = None
    for i in range(10):
        result = classifier.update(sample_payload(
            ear=0.270,
            left_ear=0.285,
            right_ear=0.265,
            raw_ear=0.270,
            raw_left_ear=0.285,
            raw_right_ear=0.265,
            timestamp=i * 0.1,
        ))

    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 1
    assert result["features"]["closed"] is True
```

Use the existing helper in `test_drowsiness_classifier.py`; if it is named differently, add keyword fields to that helper rather than creating mocks.

- [ ] **Step 6: Add failing classifier test for open eyes staying normal**

Add:

```python
def test_soft_closed_profile_keeps_glasses_open_eyes_normal():
    classifier = DrowsinessClassifier(target_fps=10)
    profile = CalibrationProfile(
        valid=True,
        ear_open_median=0.300,
        left_ear_open_median=0.310,
        right_ear_open_median=0.290,
        ear_closed_threshold=0.279,
        left_ear_closed_threshold=0.294,
        right_ear_closed_threshold=0.276,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
    )
    classifier.set_profile(profile)

    result = None
    for i in range(20):
        result = classifier.update(sample_payload(
            ear=0.292,
            left_ear=0.305,
            right_ear=0.286,
            raw_ear=0.292,
            raw_left_ear=0.305,
            raw_right_ear=0.286,
            timestamp=i * 0.1,
        ))

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert result["features"]["closed"] is False
```

- [ ] **Step 7: Add failing classifier test for one-eye guard with learned per-eye thresholds**

Add:

```python
def test_soft_closed_per_eye_thresholds_still_use_one_eye_guard():
    classifier = DrowsinessClassifier(target_fps=10)
    profile = CalibrationProfile(
        valid=True,
        ear_open_median=0.300,
        left_ear_open_median=0.330,
        right_ear_open_median=0.290,
        ear_closed_threshold=0.279,
        left_ear_closed_threshold=0.303,
        right_ear_closed_threshold=0.269,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
    )
    classifier.set_profile(profile)

    result = classifier.update(sample_payload(
        ear=0.295,
        left_ear=0.295,
        right_ear=0.292,
        raw_ear=0.295,
        raw_left_ear=0.295,
        raw_right_ear=0.292,
        eye_quality={"usable": True, "selected": "both", "reason": "OK"},
        timestamp=0.0,
    ))

    assert result["features"]["one_eye_guard_active"] is True
    assert result["features"]["closed"] is False
    assert result["alert_hint"] == 0
```

- [ ] **Step 8: Run classifier tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_drowsiness_classifier.py::test_soft_closed_profile_catches_glasses_narrow_ear_range tests\test_drowsiness_classifier.py::test_soft_closed_profile_keeps_glasses_open_eyes_normal tests\test_drowsiness_classifier.py::test_soft_closed_per_eye_thresholds_still_use_one_eye_guard -q
```

Expected: at least the per-eye threshold behavior fails because classifier ignores `left_ear_closed`/`right_ear_closed`.

- [ ] **Step 9: Use per-eye learned closed thresholds in classifier**

In `_eye_closed_decision()` in `Version3/ai/drowsiness_classifier.py`, after `ear_closed`:

```python
        left_ear_closed_threshold = thresholds.get("left_ear_closed")
        right_ear_closed_threshold = thresholds.get("right_ear_closed")
        left_threshold = float(left_ear_closed_threshold if left_ear_closed_threshold is not None else ear_closed)
        right_threshold = float(right_ear_closed_threshold if right_ear_closed_threshold is not None else ear_closed)
```

Replace:

```python
        left_closed = left_ear <= ear_closed or left_drop >= drop_threshold
        right_closed = right_ear <= ear_closed or right_drop >= drop_threshold
```

with:

```python
        left_closed = left_ear <= left_threshold or left_drop >= drop_threshold
        right_closed = right_ear <= right_threshold or right_drop >= drop_threshold
```

Extend returned features:

```python
            "left_ear_closed_threshold": float(left_threshold),
            "right_ear_closed_threshold": float(right_threshold),
```

- [ ] **Step 10: Run threshold/classifier tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_threshold_policy.py tests\test_drowsiness_classifier.py -q
```

Expected: PASS.

---

### Task 3: Drive Open/Soft-Closed Calibration Phases At Runtime

**Files:**
- Modify: `Version3/ai/session_controller.py`
- Modify: `Version3/ui/local_monitor.py`
- Test: `Version3/tests/test_ai_session_controller.py`
- Test: `Version3/tests/test_local_monitor_gui.py`

- [ ] **Step 1: Add failing session-controller test for phase routing**

Add to `Version3/tests/test_ai_session_controller.py`:

```python
def test_session_controller_collects_open_then_soft_closed_calibration_samples(monkeypatch):
    monkeypatch.setattr("config.SOFT_CLOSED_CALIBRATION", True, raising=False)
    monkeypatch.setattr("config.SOFT_CLOSED_OPEN_SECONDS", 3.0, raising=False)
    monkeypatch.setattr("config.SOFT_CLOSED_SECONDS", 2.0, raising=False)
    monkeypatch.setattr("config.SOFT_CLOSED_MIN_SAMPLES", 10, raising=False)

    controller = AiSessionController(target_fps=10)
    controller.reset_session()

    for i in range(30):
        controller.update_calibration_from_metrics(metrics(ear=0.300, left_ear=0.310, right_ear=0.290), now=i * 0.1)
    for i in range(12):
        controller.update_calibration_from_metrics(metrics(ear=0.265, left_ear=0.270, right_ear=0.260), now=3.1 + i * 0.1)

    profile = controller.profile

    assert controller.calibration_applied is True
    assert profile.soft_closed_valid is True
    assert round(profile.ear_closed_threshold, 3) == 0.279
```

If the existing test helper is not named `metrics`, add optional `left_ear` and `right_ear` fields to the helper rather than mocking the calibrator.

- [ ] **Step 2: Add failing calibration payload test**

Add to `Version3/tests/test_ai_session_controller.py`:

```python
def test_session_controller_calibration_payload_reports_soft_closed_phase(monkeypatch):
    monkeypatch.setattr("config.SOFT_CLOSED_CALIBRATION", True, raising=False)
    monkeypatch.setattr("config.SOFT_CLOSED_OPEN_SECONDS", 3.0, raising=False)

    controller = AiSessionController(target_fps=10)
    controller.reset_session()
    controller.update_calibration_from_metrics(metrics(ear=0.300), now=0.0)

    payload = controller.calibration_payload(session_active=True)
    assert payload["phase"] == "open"
    assert payload["open_sample_count"] >= 1
    assert payload["soft_closed_sample_count"] == 0

    controller.update_calibration_from_metrics(metrics(ear=0.265), now=3.2)
    payload = controller.calibration_payload(session_active=True)
    assert payload["phase"] == "soft_closed"
```

- [ ] **Step 3: Run session-controller tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_ai_session_controller.py::test_session_controller_collects_open_then_soft_closed_calibration_samples tests\test_ai_session_controller.py::test_session_controller_calibration_payload_reports_soft_closed_phase -q
```

Expected: FAIL because all samples are currently routed as open samples and payload lacks `phase`.

- [ ] **Step 4: Add phase calculation to AiSessionController**

In `Version3/ai/session_controller.py`, add fields in `__init__`:

```python
        self._calibration_started_at = None
        self._calibration_phase = "open"
```

Reset them in `reset_session()`:

```python
        self._calibration_started_at = None
        self._calibration_phase = "open"
```

Add method:

```python
    def _phase_for_calibration_time(self, timestamp):
        if not bool(getattr(config, "SOFT_CLOSED_CALIBRATION", True)):
            return "open"
        if self._calibration_started_at is None:
            self._calibration_started_at = float(timestamp or 0.0)
        elapsed = float(timestamp or 0.0) - float(self._calibration_started_at)
        if elapsed < float(getattr(config, "SOFT_CLOSED_OPEN_SECONDS", 3.0)):
            return "open"
        return "soft_closed"
```

Add `import config` at top of file.

In `update_calibration_from_metrics()`:

```python
            phase = self._phase_for_calibration_time(timestamp)
            self._calibration_phase = phase
            self.calibrator.add(metrics, timestamp, phase=phase)
```

- [ ] **Step 5: Avoid applying calibration before soft-closed window completes**

In `update_calibration_from_metrics()`, replace the apply condition with:

```python
        soft_closed_enabled = bool(getattr(config, "SOFT_CLOSED_CALIBRATION", True))
        soft_window_elapsed = True
        if soft_closed_enabled and self._calibration_started_at is not None:
            required = float(getattr(config, "SOFT_CLOSED_OPEN_SECONDS", 3.0)) + float(getattr(config, "SOFT_CLOSED_SECONDS", 2.0))
            soft_window_elapsed = (timestamp - self._calibration_started_at) >= required
        if profile.valid and (not soft_closed_enabled or soft_window_elapsed):
            should_apply = True
        else:
            should_apply = self.calibrator.complete(timestamp)
        if should_apply:
            ...
```

This prevents a valid open-only profile from applying before the user has had a chance to nheo/close eyes.

- [ ] **Step 6: Expose phase in calibration payload**

In `calibration_payload()`, after building `payload`:

```python
            payload["phase"] = self._calibration_phase
```

For applied profiles, also include:

```python
        payload = profile.to_dict(active=False)
        payload["phase"] = "applied"
        return payload
```

- [ ] **Step 7: Update local monitor test for calibration phase text**

Add to `Version3/tests/test_local_monitor_gui.py`:

```python
def test_local_monitor_state_reads_soft_closed_calibration_fields():
    from ui.local_monitor import LocalMonitorState

    state = LocalMonitorState.from_payload({
        "calibration": {
            "active": True,
            "valid": False,
            "reason": "COLLECTING",
            "phase": "soft_closed",
            "sample_count": 30,
            "open_sample_count": 30,
            "soft_closed_sample_count": 8,
            "soft_closed_valid": False,
            "soft_closed_reason": "NOT_COLLECTED",
        }
    })

    assert state.calibration_phase == "soft_closed"
    assert state.calibration_open_sample_count == 30
    assert state.calibration_soft_closed_sample_count == 8
```

- [ ] **Step 8: Run local monitor test and verify RED**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_local_monitor_gui.py::test_local_monitor_state_reads_soft_closed_calibration_fields -q
```

Expected: FAIL because state fields do not exist.

- [ ] **Step 9: Add local monitor fields**

In `Version3/ui/local_monitor.py`, add slots/defaults:

```python
        "calibration_phase",
        "calibration_open_sample_count",
        "calibration_soft_closed_sample_count",
        "calibration_soft_closed_valid",
        "calibration_soft_closed_reason",
```

Defaults:

```python
        "calibration_phase": "",
        "calibration_open_sample_count": 0,
        "calibration_soft_closed_sample_count": 0,
        "calibration_soft_closed_valid": False,
        "calibration_soft_closed_reason": "",
```

In `from_payload()`:

```python
            calibration_phase=calibration.get("phase") or "",
            calibration_open_sample_count=int(calibration.get("open_sample_count") or calibration.get("sample_count") or 0),
            calibration_soft_closed_sample_count=int(calibration.get("soft_closed_sample_count") or 0),
            calibration_soft_closed_valid=bool(calibration.get("soft_closed_valid")),
            calibration_soft_closed_reason=calibration.get("soft_closed_reason") or "",
```

In overlay rendering, add a line near existing calibration text:

```python
        "Cal phase %s | open %s | soft %s" % (
            state.calibration_phase or "-",
            state.calibration_open_sample_count,
            state.calibration_soft_closed_sample_count,
        ),
```

- [ ] **Step 10: Run session/local monitor tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_ai_session_controller.py tests\test_local_monitor_gui.py -q
```

Expected: PASS.

---

### Task 4: Make Microsleep Evidence Recover Instead Of Latching DROWSY

**Files:**
- Modify: `Version3/ai/drowsiness_classifier.py`
- Test: `Version3/tests/test_drowsiness_classifier.py`

- [ ] **Step 1: Add failing test for stable-open recovery after microsleep escalation**

Add to `Version3/tests/test_drowsiness_classifier.py`:

```python
def test_microsleep_escalation_recovers_after_stable_open_eyes(monkeypatch):
    monkeypatch.setattr("config.MICROSLEEP_RECENT_SECONDS", 5.0, raising=False)
    monkeypatch.setattr("config.MICROSLEEP_RECOVERY_OPEN_SECONDS", 1.5, raising=False)

    classifier = DrowsinessClassifier(target_fps=10)
    classifier.set_profile(CalibrationProfile(
        valid=True,
        ear_open_median=0.300,
        ear_closed_threshold=0.279,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
    ))

    t = 0.0
    result = None
    for _ in range(3):
        for _ in range(5):
            result = classifier.update(sample_payload(ear=0.260, raw_ear=0.260, timestamp=t))
            t += 0.1
        for _ in range(4):
            result = classifier.update(sample_payload(ear=0.300, raw_ear=0.300, timestamp=t))
            t += 0.1

    assert result["features"]["microsleep_count"] >= 3
    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 2

    for _ in range(20):
        result = classifier.update(sample_payload(ear=0.300, raw_ear=0.300, timestamp=t))
        t += 0.1

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert result["features"]["microsleep_count"] >= 3
    assert result["features"]["microsleep_influence_active"] is False
```

- [ ] **Step 2: Add failing test for stale microsleep count not causing DROWSY**

Add:

```python
def test_stale_microsleep_count_does_not_force_drowsy(monkeypatch):
    monkeypatch.setattr("config.MICROSLEEP_RECENT_SECONDS", 5.0, raising=False)

    classifier = DrowsinessClassifier(target_fps=10)
    classifier.set_profile(CalibrationProfile(
        valid=True,
        ear_open_median=0.300,
        ear_closed_threshold=0.279,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
    ))

    t = 0.0
    for _ in range(3):
        for _ in range(5):
            classifier.update(sample_payload(ear=0.260, raw_ear=0.260, timestamp=t))
            t += 0.1
        for _ in range(4):
            classifier.update(sample_payload(ear=0.300, raw_ear=0.300, timestamp=t))
            t += 0.1

    t += 10.0
    result = classifier.update(sample_payload(ear=0.300, raw_ear=0.300, timestamp=t))

    assert result["features"]["microsleep_count"] >= 3
    assert result["features"]["last_microsleep_age_sec"] > 5.0
    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
```

- [ ] **Step 3: Run microsleep tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_drowsiness_classifier.py::test_microsleep_escalation_recovers_after_stable_open_eyes tests\test_drowsiness_classifier.py::test_stale_microsleep_count_does_not_force_drowsy -q
```

Expected: FAIL because current logic returns `DROWSY` whenever `microsleep_count >= 3`.

- [ ] **Step 4: Track last microsleep time**

In `DrowsinessClassifier.__init__`:

```python
        self._last_microsleep_at = None
```

In `reset_state()`:

```python
        self._last_microsleep_at = None
```

In `_update_microsleep()`, when appending a microsleep:

```python
                self._microsleep_events.append(float(now))
                self._last_microsleep_at = float(now)
```

When detection disabled:

```python
            self._last_microsleep_at = None
```

- [ ] **Step 5: Add microsleep influence helper**

Add method to `DrowsinessClassifier`:

```python
    def _microsleep_influence_active(self, now, eyes_open_sec, perclos_long):
        if not getattr(config, "MICROSLEEP_DETECTION", True):
            return False, None
        if len(self._microsleep_events) < 3 or self._last_microsleep_at is None:
            return False, None
        age = max(0.0, float(now) - float(self._last_microsleep_at))
        recent_limit = float(getattr(config, "MICROSLEEP_RECENT_SECONDS", 5.0))
        recovery_open = float(getattr(config, "MICROSLEEP_RECOVERY_OPEN_SECONDS", 1.5))
        if eyes_open_sec >= recovery_open:
            return False, age
        if age <= recent_limit:
            return True, age
        if perclos_long >= 0.20:
            return True, age
        return False, age
```

- [ ] **Step 6: Gate microsleep DROWSY escalation**

In `_classify_sample()`, replace:

```python
        if getattr(config, "MICROSLEEP_DETECTION", True) and microsleep_count >= 3:
            return AIState.DROWSY, 0.90, "Repeated microsleep episodes in 60s", 2
```

with:

```python
        microsleep_active, _ = self._microsleep_influence_active(now, eyes_open_sec, perclos_long)
        if microsleep_active:
            return AIState.DROWSY, 0.90, "Recent repeated microsleep episodes", 2
```

- [ ] **Step 7: Expose microsleep age/influence in features**

In `_features()`, before `features.update(...)`:

```python
        now = self._current_sample_time
        eyes_open_sec = self._current_duration(self._eyes_open_started_at, self._eyes_open_frames)
        perclos_long = self._perclos_ratio("long")
        microsleep_active, microsleep_age = self._microsleep_influence_active(now, eyes_open_sec, perclos_long)
```

Then update feature fields:

```python
            "microsleep_count": len(self._microsleep_events),
            "last_microsleep_age_sec": None if microsleep_age is None else round(float(microsleep_age), 3),
            "microsleep_influence_active": bool(microsleep_active),
```

- [ ] **Step 8: Run microsleep tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_drowsiness_classifier.py::test_microsleep_escalation_recovers_after_stable_open_eyes tests\test_drowsiness_classifier.py::test_stale_microsleep_count_does_not_force_drowsy -q
```

Expected: PASS.

- [ ] **Step 9: Run full classifier tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_drowsiness_classifier.py -q
```

Expected: PASS.

---

### Task 5: Document And Verify The Combined Behavior

**Files:**
- Modify: `Version3/CHANGELOG.md`
- Modify: `Version3/docs/BASELINE_METRICS_2026-05.md`
- Test: full Version3 test suite

- [ ] **Step 1: Update changelog**

Add under `Version3/CHANGELOG.md` `Unreleased`:

```markdown
### Added
- Soft-closed calibration for glasses/narrow-EAR drivers, including per-eye closed thresholds.

### Changed
- Microsleep evidence now recovers after stable open eyes instead of holding `DROWSY` unconditionally for the full 60-second window.
```

- [ ] **Step 2: Update baseline metrics doc with manual test case**

In `Version3/docs/BASELINE_METRICS_2026-05.md`, add a row under Required Benchmark Clips:

```markdown
| Glasses narrow EAR | 3 min | Open EAR around 0.29-0.31, nheo/closed EAR around 0.26-0.27 | `glasses_narrow_ear_*.mp4` |
```

Add metric row:

```markdown
| Glasses narrow-EAR closed detection | TBD | TBD | percent of nheo/closed windows detected without normal-open false positives |
```

- [ ] **Step 3: Run targeted behavior tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests\test_calibration.py tests\test_threshold_policy.py tests\test_ai_session_controller.py tests\test_drowsiness_classifier.py tests\test_local_monitor_gui.py tests\test_config_defaults.py -q
```

Expected: PASS.

- [ ] **Step 4: Run full Version3 suite**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests -q --basetemp D:\DATN-testing1\.tmp\pytest-soft-closed-final
```

Expected: PASS. Previous baseline before this plan was `234 passed, 4 deselected`.

- [ ] **Step 5: Manual Jetson validation command**

After code is reviewed and approved for deployment, run on Jetson:

```bash
cd /home/nano/Version3
python3 -m py_compile ai/calibration.py ai/threshold_policy.py ai/drowsiness_classifier.py ai/session_controller.py ui/local_monitor.py main.py
```

Expected: command exits `0`.

- [ ] **Step 6: Manual Jetson test scenario**

Use the Desktop launcher and observe local monitor:

```text
1. Start DrowsiGuard Full.
2. During calibration phase "open", look straight with eyes open.
3. During calibration phase "soft_closed", nheo/close eyes as in the glasses test.
4. Confirm threshold appears around 0.275-0.282 for open 0.29-0.31 and closed 0.26-0.27.
5. Open eyes at 0.29-0.31: AI should be NORMAL.
6. Nheo/closed at 0.26-0.27 for >=0.8s: AI should become DROWSY with alert_hint 1.
7. Re-open eyes for >=1.5s after microsleep events: AI should return NORMAL and alert_hint 0.
```

Expected: no `DROWSY` latch after stable open eyes.

---

## Self-Review Checklist

- [ ] Soft-closed calibration has tests for valid narrow-EAR glasses case.
- [ ] Soft-closed calibration has fallback test for unreliable separation.
- [ ] Per-eye thresholds are exposed and consumed.
- [ ] Runtime calibration has an open phase and a soft-closed phase.
- [ ] Local monitor shows enough information for the driver to follow calibration.
- [ ] Microsleep recovery has tests for stable-open recovery and stale-count behavior.
- [ ] No code changes happen until this plan is explicitly approved.

---

## Execution Options

Plan complete and saved to `Version3/docs/superpowers/plans/2026-05-05-glasses-soft-closed-microsleep-recovery.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch one task at a time, review between tasks, faster but requires explicit permission to use subagents.
2. **Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, with checkpoints after the calibration section and microsleep section.

Implementation must wait for user approval before any code changes.
