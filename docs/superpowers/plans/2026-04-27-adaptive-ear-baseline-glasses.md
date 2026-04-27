# Adaptive EAR Baseline For Glasses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect closed eyes for drivers wearing prescription glasses by comparing live EAR against the driver's calibrated open-eye baseline instead of relying only on the fixed `0.24` EAR threshold.

**Architecture:** Keep the existing `FaceAnalyzer` left/right EAR and `eye_quality` work. Add adaptive baseline math to `CalibrationProfile` and `ThresholdPolicy`, then make `DrowsinessClassifier` call that policy for each frame. Publish the new decision diagnostics through the existing AI payload so local GUI and WebQuanLi remain backward compatible.

**Tech Stack:** Python 3.6 compatible code, pytest, MediaPipe/OpenCV metrics already present in `Version3`, existing WebSocket payloads, no new runtime dependency.

---

## Current Code Context

- `Version3/camera/face_analyzer.py` already provides `left_ear`, `right_ear`, `ear_used`, and `eye_quality`.
- `Version3/ai/calibration.py` already stores `ear_open_median`, `left_ear_open_median`, `right_ear_open_median`, and `ear_used_open_median`.
- `Version3/ai/threshold_policy.py` currently only returns fixed profile thresholds and does not decide adaptive eye closure.
- `Version3/ai/drowsiness_classifier.py` currently uses `sample["ear"] < thresholds["ear_closed"]`, so `ear=0.27` with glasses remains `NORMAL` when threshold is `0.24`.
- `Version3/main.py` already includes `left_ear`, `right_ear`, `ear_used`, and `eye_quality` in runtime/local monitor payload.

## File Structure

- Modify: `D:\DATN-testing1\Version3\config.py`
  - Add adaptive EAR tunables with safe defaults.
- Modify: `D:\DATN-testing1\Version3\ai\calibration.py`
  - Store adaptive threshold and drop threshold in `CalibrationProfile` and `to_dict()`.
  - Compute adaptive closed threshold from open-eye baseline.
- Modify: `D:\DATN-testing1\Version3\ai\threshold_policy.py`
  - Own all adaptive threshold math and per-frame eye closure decision.
  - Select baseline by `eye_quality.selected`.
- Modify: `D:\DATN-testing1\Version3\ai\drowsiness_classifier.py`
  - Replace direct fixed threshold comparison with `ThresholdPolicy.eye_decision()`.
  - Include adaptive diagnostics in result features.
- Modify: `D:\DATN-testing1\Version3\main.py`
  - Publish classifier adaptive PERCLOS and adaptive threshold diagnostics in AI payload.
- Modify: `D:\DATN-testing1\Version3\ui\local_monitor.py`
  - Display adaptive threshold and drop score for Jetson local testing.
- Modify: `D:\DATN-testing1\Version3\scripts\local_ai_monitor.py`
  - Display adaptive threshold and drop score in the standalone AI monitor overlay.
- Modify: `D:\DATN-testing1\Version3\docs\protocol.md`
  - Document new optional AI fields.
- Test: `D:\DATN-testing1\Version3\tests\test_threshold_policy.py`
- Test: `D:\DATN-testing1\Version3\tests\test_calibration.py`
- Test: `D:\DATN-testing1\Version3\tests\test_drowsiness_classifier.py`
- Test: `D:\DATN-testing1\Version3\tests\test_main_local_gui.py`
- Test: `D:\DATN-testing1\Version3\tests\test_local_monitor_gui.py`
- Test: `D:\DATN-testing1\Version3\tests\test_local_ai_monitor_script.py`

---

## Task 0: Safety Baseline

**Files:**
- Read only: `D:\DATN-testing1`

- [ ] **Step 1: Confirm clean workspace**

Run:

```powershell
git status --short
```

Expected: no output. If there is output, inspect it and do not overwrite user changes.

- [ ] **Step 2: Create implementation branch**

Run:

```powershell
git switch -c codex/adaptive-ear-baseline-glasses
```

Expected: branch created from current `main`.

- [ ] **Step 3: Run current focused tests before changing behavior**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_threshold_policy.py tests/test_calibration.py tests/test_drowsiness_classifier.py tests/test_main_local_gui.py tests/test_local_monitor_gui.py tests/test_local_ai_monitor_script.py -q
```

Expected: pass before starting adaptive EAR work.

---

## Task 1: Add Adaptive EAR Data To Calibration And Threshold Policy

**Files:**
- Modify: `D:\DATN-testing1\Version3\config.py`
- Modify: `D:\DATN-testing1\Version3\ai\calibration.py`
- Modify: `D:\DATN-testing1\Version3\ai\threshold_policy.py`
- Test: `D:\DATN-testing1\Version3\tests\test_threshold_policy.py`
- Test: `D:\DATN-testing1\Version3\tests\test_calibration.py`

- [ ] **Step 1: Write failing threshold policy tests**

Append these tests to `Version3\tests\test_threshold_policy.py`:

```python
def test_threshold_policy_raises_closed_threshold_for_glasses_baseline():
    profile = CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=0.32,
        mar_closed_median=0.12,
        pitch_neutral=0.0,
        ear_closed_threshold=0.275,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
        sample_count=40,
        left_ear_open_median=0.31,
        right_ear_open_median=0.33,
        ear_used_open_median=0.32,
    )

    thresholds = ThresholdPolicy.from_profile(profile).to_dict()

    assert thresholds["ear_closed"] == 0.275
    assert thresholds["ear_adaptive_closed"] == 0.275
    assert thresholds["ear_open_baseline"] == 0.32
    assert thresholds["ear_drop_closed"] == 0.13


def test_threshold_policy_closes_glasses_eye_by_adaptive_drop():
    profile = CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=0.32,
        mar_closed_median=0.12,
        pitch_neutral=0.0,
        ear_closed_threshold=0.275,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
        sample_count=40,
        ear_used_open_median=0.32,
    )
    policy = ThresholdPolicy.from_profile(profile)

    decision = policy.eye_decision({
        "usable": True,
        "ear": 0.27,
        "left_ear": 0.27,
        "right_ear": 0.27,
        "eye_quality": {"usable": True, "selected": "both", "reason": "OK"},
    })

    assert decision["closed"] is True
    assert decision["baseline"] == 0.32
    assert decision["threshold"] == 0.275
    assert round(decision["drop_score"], 3) == 0.156
    assert decision["reason"] in ("ADAPTIVE_EAR", "EAR_DROP")


def test_threshold_policy_keeps_glasses_eye_open_when_drop_is_small():
    profile = CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=0.32,
        mar_closed_median=0.12,
        pitch_neutral=0.0,
        ear_closed_threshold=0.275,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
        sample_count=40,
        ear_used_open_median=0.32,
    )
    policy = ThresholdPolicy.from_profile(profile)

    decision = policy.eye_decision({
        "usable": True,
        "ear": 0.30,
        "left_ear": 0.30,
        "right_ear": 0.30,
        "eye_quality": {"usable": True, "selected": "both", "reason": "OK"},
    })

    assert decision["closed"] is False
    assert round(decision["drop_score"], 3) == 0.063
    assert decision["reason"] == "OPEN"


def test_threshold_policy_uses_selected_eye_baseline():
    profile = CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=0.31,
        mar_closed_median=0.12,
        pitch_neutral=0.0,
        ear_closed_threshold=0.275,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
        sample_count=40,
        left_ear_open_median=0.28,
        right_ear_open_median=0.33,
        ear_used_open_median=0.31,
    )
    policy = ThresholdPolicy.from_profile(profile)

    decision = policy.eye_decision({
        "usable": True,
        "ear": 0.30,
        "left_ear": 0.28,
        "right_ear": 0.27,
        "eye_quality": {"usable": True, "selected": "right", "reason": "LEFT_GLARE"},
    })

    assert decision["closed"] is True
    assert decision["baseline"] == 0.33
    assert decision["ear"] == 0.27
    assert round(decision["drop_score"], 3) == 0.182
```

- [ ] **Step 2: Write failing calibration tests**

Append these tests to `Version3\tests\test_calibration.py`:

```python
def test_calibration_computes_adaptive_threshold_for_glasses_baseline():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(ear=0.32, left_ear=0.31, right_ear=0.33), i * 0.1)

    profile = calibrator.profile

    assert profile.valid is True
    assert round(profile.ear_open_median, 3) == 0.32
    assert round(profile.ear_closed_threshold, 3) == 0.275
    assert round(profile.ear_adaptive_closed_threshold, 3) == 0.275
    assert profile.ear_drop_closed_threshold == 0.13
    assert profile.to_dict()["ear_adaptive_closed_threshold"] == profile.ear_adaptive_closed_threshold
    assert profile.to_dict()["ear_drop_closed_threshold"] == 0.13


def test_calibration_keeps_no_glasses_threshold_at_safe_fallback_floor():
    calibrator = DriverCalibrator(duration_sec=5, min_samples=30)

    for i in range(35):
        calibrator.add(sample(ear=0.27, left_ear=0.27, right_ear=0.27), i * 0.1)

    profile = calibrator.profile

    assert profile.valid is True
    assert round(profile.ear_closed_threshold, 3) == 0.24
    assert round(profile.ear_adaptive_closed_threshold, 3) == 0.24
```

- [ ] **Step 3: Run tests to verify they fail for the current code**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_threshold_policy.py tests/test_calibration.py -q
```

Expected: fail because `ear_adaptive_closed_threshold`, `ear_drop_closed_threshold`, and `ThresholdPolicy.eye_decision()` do not exist yet.

- [ ] **Step 4: Add adaptive config constants**

In `Version3\config.py`, directly under the existing fallback thresholds, add:

```python
EAR_ADAPTIVE_BASE_DELTA = env_float("DROWSIGUARD_EAR_ADAPTIVE_BASE_DELTA", 0.045)
EAR_ADAPTIVE_MIN = env_float("DROWSIGUARD_EAR_ADAPTIVE_MIN", 0.20)
EAR_ADAPTIVE_MAX = env_float("DROWSIGUARD_EAR_ADAPTIVE_MAX", 0.30)
EAR_DROP_CLOSED_THRESHOLD = env_float("DROWSIGUARD_EAR_DROP_CLOSED_THRESHOLD", 0.13)
```

- [ ] **Step 5: Extend `CalibrationProfile`**

In `Version3\ai\calibration.py`, add parameters to `CalibrationProfile.__init__`:

```python
        ear_adaptive_closed_threshold=None,
        ear_drop_closed_threshold=None,
```

Set these attributes after `self.ear_closed_threshold`:

```python
        self.ear_adaptive_closed_threshold = (
            self.ear_closed_threshold
            if ear_adaptive_closed_threshold is None
            else float(ear_adaptive_closed_threshold)
        )
        self.ear_drop_closed_threshold = (
            getattr(config, "EAR_DROP_CLOSED_THRESHOLD", 0.13)
            if ear_drop_closed_threshold is None
            else float(ear_drop_closed_threshold)
        )
```

Add these keys to `CalibrationProfile.to_dict()`:

```python
            "ear_adaptive_closed_threshold": self.ear_adaptive_closed_threshold,
            "ear_drop_closed_threshold": self.ear_drop_closed_threshold,
```

In `CalibrationProfile.fallback()`, pass:

```python
            ear_adaptive_closed_threshold=getattr(config, "EAR_THRESHOLD", FALLBACK_EAR_CLOSED),
            ear_drop_closed_threshold=getattr(config, "EAR_DROP_CLOSED_THRESHOLD", 0.13),
```

- [ ] **Step 6: Compute adaptive threshold in calibration**

In `Version3\ai\calibration.py`, add this helper near `_clamp`:

```python
def _adaptive_ear_threshold(open_baseline):
    if open_baseline is None:
        return getattr(config, "EAR_THRESHOLD", FALLBACK_EAR_CLOSED)
    return _clamp(
        max(
            getattr(config, "EAR_THRESHOLD", FALLBACK_EAR_CLOSED),
            float(open_baseline) - getattr(config, "EAR_ADAPTIVE_BASE_DELTA", 0.045),
        ),
        getattr(config, "EAR_ADAPTIVE_MIN", 0.20),
        getattr(config, "EAR_ADAPTIVE_MAX", 0.30),
    )
```

In `DriverCalibrator._build_profile()`, replace:

```python
        ear_closed = _clamp(min(FALLBACK_EAR_CLOSED, ear_open - 0.02), 0.20, FALLBACK_EAR_CLOSED)
```

with:

```python
        ear_closed = _adaptive_ear_threshold(ear_open)
```

In the returned `CalibrationProfile`, pass:

```python
            ear_adaptive_closed_threshold=ear_closed,
            ear_drop_closed_threshold=getattr(config, "EAR_DROP_CLOSED_THRESHOLD", 0.13),
```

- [ ] **Step 7: Replace `ThresholdPolicy` with adaptive decision policy**

Replace the contents of `Version3\ai\threshold_policy.py` with:

```python
"""Canonical threshold payloads and adaptive eye-closure decisions."""

import config
from .calibration import CalibrationProfile


def _clamp(value, low, high):
    return max(low, min(high, value))


class ThresholdPolicy:
    """Read threshold values from calibration and decide eye closure per frame."""

    def __init__(
        self,
        ear_closed,
        mar_yawn,
        pitch_down,
        ear_open_baseline=None,
        left_ear_open_baseline=None,
        right_ear_open_baseline=None,
        ear_adaptive_closed=None,
        ear_drop_closed=None,
    ):
        self.ear_closed = float(ear_closed)
        self.mar_yawn = float(mar_yawn)
        self.pitch_down = float(pitch_down)
        self.ear_open_baseline = _optional_float(ear_open_baseline)
        self.left_ear_open_baseline = _optional_float(left_ear_open_baseline)
        self.right_ear_open_baseline = _optional_float(right_ear_open_baseline)
        self.ear_adaptive_closed = float(
            ear_adaptive_closed if ear_adaptive_closed is not None else ear_closed
        )
        self.ear_drop_closed = float(
            ear_drop_closed
            if ear_drop_closed is not None
            else getattr(config, "EAR_DROP_CLOSED_THRESHOLD", 0.13)
        )

    @classmethod
    def from_profile(cls, profile):
        profile = profile or CalibrationProfile.fallback(reason="FALLBACK")
        baseline = (
            profile.ear_used_open_median
            if profile.ear_used_open_median is not None
            else profile.ear_open_median
        )
        return cls(
            ear_closed=profile.ear_closed_threshold,
            mar_yawn=profile.mar_yawn_threshold,
            pitch_down=profile.pitch_down_threshold,
            ear_open_baseline=baseline,
            left_ear_open_baseline=profile.left_ear_open_median,
            right_ear_open_baseline=profile.right_ear_open_median,
            ear_adaptive_closed=getattr(profile, "ear_adaptive_closed_threshold", profile.ear_closed_threshold),
            ear_drop_closed=getattr(profile, "ear_drop_closed_threshold", None),
        )

    def to_dict(self):
        return {
            "ear_closed": self.ear_closed,
            "ear_adaptive_closed": self.ear_adaptive_closed,
            "ear_drop_closed": self.ear_drop_closed,
            "ear_open_baseline": self.ear_open_baseline,
            "left_ear_open_baseline": self.left_ear_open_baseline,
            "right_ear_open_baseline": self.right_ear_open_baseline,
            "mar_yawn": self.mar_yawn,
            "pitch_down": self.pitch_down,
        }

    def eye_decision(self, sample):
        sample = sample or {}
        eye_quality = sample.get("eye_quality") or {}
        if not bool(sample.get("usable", True)) or not bool(eye_quality.get("usable", True)):
            return self._decision(False, 0.0, None, self.ear_adaptive_closed, 0.0, "UNUSABLE_EYE")

        selected = eye_quality.get("selected") or "both"
        ear = self._selected_ear(sample, selected)
        baseline = self._selected_baseline(selected)
        threshold = self._threshold_for_baseline(baseline)
        drop_score = self._drop_score(baseline, ear)

        closed_by_threshold = ear <= threshold
        closed_by_drop = drop_score >= self.ear_drop_closed
        if closed_by_threshold:
            reason = "ADAPTIVE_EAR"
        elif closed_by_drop:
            reason = "EAR_DROP"
        else:
            reason = "OPEN"

        return self._decision(
            bool(closed_by_threshold or closed_by_drop),
            ear,
            baseline,
            threshold,
            drop_score,
            reason,
        )

    def _selected_ear(self, sample, selected):
        if selected == "left":
            return float(sample.get("left_ear", sample.get("ear", 0.0)) or 0.0)
        if selected == "right":
            return float(sample.get("right_ear", sample.get("ear", 0.0)) or 0.0)
        return float(sample.get("ear", 0.0) or 0.0)

    def _selected_baseline(self, selected):
        if selected == "left" and self.left_ear_open_baseline is not None:
            return self.left_ear_open_baseline
        if selected == "right" and self.right_ear_open_baseline is not None:
            return self.right_ear_open_baseline
        return self.ear_open_baseline

    def _threshold_for_baseline(self, baseline):
        if baseline is None:
            return self.ear_closed
        return _clamp(
            max(
                getattr(config, "EAR_THRESHOLD", 0.24),
                float(baseline) - getattr(config, "EAR_ADAPTIVE_BASE_DELTA", 0.045),
            ),
            getattr(config, "EAR_ADAPTIVE_MIN", 0.20),
            getattr(config, "EAR_ADAPTIVE_MAX", 0.30),
        )

    def _drop_score(self, baseline, ear):
        if baseline is None or float(baseline) <= 0.0:
            return 0.0
        return max(0.0, (float(baseline) - float(ear)) / float(baseline))

    @staticmethod
    def _decision(closed, ear, baseline, threshold, drop_score, reason):
        return {
            "closed": bool(closed),
            "ear": round(float(ear or 0.0), 6),
            "baseline": None if baseline is None else round(float(baseline), 6),
            "threshold": round(float(threshold or 0.0), 6),
            "drop_score": round(float(drop_score or 0.0), 6),
            "reason": reason,
        }


def _optional_float(value):
    if value is None:
        return None
    return float(value)
```

- [ ] **Step 8: Run threshold and calibration tests**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_threshold_policy.py tests/test_calibration.py -q
```

Expected: pass.

- [ ] **Step 9: Commit Task 1**

Run:

```powershell
git add Version3/config.py Version3/ai/calibration.py Version3/ai/threshold_policy.py Version3/tests/test_threshold_policy.py Version3/tests/test_calibration.py
git commit -m "feat: add adaptive EAR threshold policy"
```

---

## Task 2: Use Adaptive Policy In DrowsinessClassifier

**Files:**
- Modify: `D:\DATN-testing1\Version3\ai\drowsiness_classifier.py`
- Test: `D:\DATN-testing1\Version3\tests\test_drowsiness_classifier.py`

- [ ] **Step 1: Write failing classifier tests**

In `Version3\tests\test_drowsiness_classifier.py`, replace the `profile()` helper with:

```python
def profile(ear=0.24, mar=0.45, pitch=-15.0, open_ear=0.29, left_open=None, right_open=None):
    return CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=open_ear,
        mar_closed_median=0.12,
        pitch_neutral=pitch + 15.0,
        ear_closed_threshold=ear,
        mar_yawn_threshold=mar,
        pitch_down_threshold=pitch,
        sample_count=40,
        face_height_median=220.0,
        left_ear_open_median=open_ear if left_open is None else left_open,
        right_ear_open_median=open_ear if right_open is None else right_open,
        ear_used_open_median=open_ear,
        ear_adaptive_closed_threshold=ear,
        ear_drop_closed_threshold=0.13,
    )
```

Append these tests:

```python
def test_glasses_closed_ear_above_hard_threshold_becomes_drowsy():
    classifier = DrowsinessClassifier(
        profile=profile(ear=0.275, open_ear=0.32),
        target_fps=10,
    )

    for _ in range(8):
        result = classifier.update(metrics(ear=0.27, left_ear=0.27, right_ear=0.27))

    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 1
    assert result["features"]["ear_closed"] is True
    assert result["features"]["ear_closed_reason"] in ("ADAPTIVE_EAR", "EAR_DROP")
    assert round(result["features"]["ear_drop_score"], 3) == 0.156
    assert result["features"]["ear_open_baseline"] == 0.32


def test_glasses_open_eye_with_small_drop_stays_normal():
    classifier = DrowsinessClassifier(
        profile=profile(ear=0.275, open_ear=0.32),
        target_fps=10,
    )

    for _ in range(20):
        result = classifier.update(metrics(ear=0.30, left_ear=0.30, right_ear=0.30))

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert result["features"]["ear_closed"] is False
    assert round(result["features"]["ear_drop_score"], 3) == 0.063


def test_selected_right_eye_uses_right_eye_baseline_for_glasses():
    classifier = DrowsinessClassifier(
        profile=profile(ear=0.285, open_ear=0.30, left_open=0.27, right_open=0.33),
        target_fps=10,
    )
    eye_quality = {
        "usable": True,
        "selected": "right",
        "reason": "LEFT_GLARE",
        "left": {"usable": False, "reason": "GLARE"},
        "right": {"usable": True, "reason": "OK"},
    }

    for _ in range(8):
        result = classifier.update(metrics(
            ear=0.30,
            left_ear=0.27,
            right_ear=0.27,
            eye_quality=eye_quality,
        ))

    assert result["state"] == AIState.DROWSY
    assert result["features"]["ear_open_baseline"] == 0.33
    assert result["features"]["ear_used"] == 0.27


def test_unusable_eye_quality_still_blocks_adaptive_drowsy():
    classifier = DrowsinessClassifier(
        profile=profile(ear=0.275, open_ear=0.32),
        target_fps=10,
    )

    for _ in range(20):
        result = classifier.update(metrics(
            ear=0.20,
            left_ear=0.20,
            right_ear=0.20,
            eye_quality={"usable": False, "selected": "none", "reason": "BOTH_UNRELIABLE"},
        ))

    assert result["state"] == AIState.LOW_CONFIDENCE
    assert result["alert_hint"] == 0
    assert result["features"]["perclos_short"] == 0.0
    assert result["features"]["perclos_long"] == 0.0
```

- [ ] **Step 2: Run classifier tests to verify failure**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_drowsiness_classifier.py -q
```

Expected: fail because classifier still uses direct `sample["ear"] < thresholds["ear_closed"]` and does not publish adaptive feature fields.

- [ ] **Step 3: Update classifier to use `ThresholdPolicy.eye_decision()`**

In `Version3\ai\drowsiness_classifier.py`, replace this block in `_classify_sample()`:

```python
        thresholds = self._thresholds()
        ear_low = sample["usable"] and sample["ear"] < thresholds["ear_closed"]
        mouth_open = sample["usable"] and sample["mar"] > thresholds["mar_yawn"]
        head_down = sample["usable"] and sample["pitch"] <= thresholds["pitch_down"]
```

with:

```python
        policy = self._policy()
        thresholds = policy.to_dict()
        eye_decision = policy.eye_decision(sample)
        sample["eye_decision"] = eye_decision
        sample["ear"] = eye_decision["ear"]
        ear_low = sample["usable"] and eye_decision["closed"]
        mouth_open = sample["usable"] and sample["mar"] > thresholds["mar_yawn"]
        head_down = sample["usable"] and sample["pitch"] <= thresholds["pitch_down"]
```

Replace the `EYES_CLOSED` reason block:

```python
            return AIState.EYES_CLOSED, 0.72, "EAR %.3f below %.3f" % (
                sample["ear"],
                thresholds["ear_closed"],
            ), 0
```

with:

```python
            return AIState.EYES_CLOSED, 0.72, "EAR %.3f closed by %s threshold %.3f drop %.3f" % (
                sample["ear"],
                eye_decision["reason"],
                eye_decision["threshold"],
                eye_decision["drop_score"],
            ), 0
```

Add this method above `_thresholds()`:

```python
    def _policy(self):
        profile = self._profile or CalibrationProfile.fallback(reason="FALLBACK")
        return ThresholdPolicy.from_profile(profile)
```

Replace `_thresholds()` body with:

```python
    def _thresholds(self):
        return self._policy().to_dict()
```

- [ ] **Step 4: Publish adaptive features from classifier**

In `Version3\ai\drowsiness_classifier.py`, update `_features()` by assigning the policy once:

```python
        policy = self._policy()
        thresholds = policy.to_dict()
        features = FeatureExtractor.extract(
            self._samples,
            thresholds["ear_closed"],
            thresholds["mar_yawn"],
            thresholds["pitch_down"],
            target_fps=self._target_fps,
        ) or {}
        eye_decision = sample.get("eye_decision") or policy.eye_decision(sample)
```

Then include these keys in `features.update({ ... })`:

```python
            "ear_closed": bool(eye_decision["closed"]),
            "ear_closed_reason": eye_decision["reason"],
            "ear_open_baseline": eye_decision["baseline"],
            "ear_adaptive_threshold": eye_decision["threshold"],
            "ear_drop_score": eye_decision["drop_score"],
```

- [ ] **Step 5: Run classifier tests**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_drowsiness_classifier.py -q
```

Expected: pass.

- [ ] **Step 6: Run threshold, calibration, and classifier tests together**

Run:

```powershell
python -m pytest tests/test_threshold_policy.py tests/test_calibration.py tests/test_drowsiness_classifier.py -q
```

Expected: pass.

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add Version3/ai/drowsiness_classifier.py Version3/tests/test_drowsiness_classifier.py
git commit -m "feat: classify eye closure from adaptive EAR baseline"
```

---

## Task 3: Publish Adaptive Diagnostics To Runtime And Local GUI

**Files:**
- Modify: `D:\DATN-testing1\Version3\main.py`
- Modify: `D:\DATN-testing1\Version3\ui\local_monitor.py`
- Modify: `D:\DATN-testing1\Version3\scripts\local_ai_monitor.py`
- Test: `D:\DATN-testing1\Version3\tests\test_main_local_gui.py`
- Test: `D:\DATN-testing1\Version3\tests\test_local_monitor_gui.py`
- Test: `D:\DATN-testing1\Version3\tests\test_local_ai_monitor_script.py`

- [ ] **Step 1: Write failing runtime payload test**

Append this test to `Version3\tests\test_main_local_gui.py`:

```python
    @patch("main.LocalQueue")
    def test_runtime_payload_prefers_classifier_adaptive_perclos_and_thresholds(self, _mock_local_queue_class):
        app = DrowsiGuard()
        app._last_metrics = Mock(
            face_present=True,
            ear=0.27,
            left_ear=0.27,
            right_ear=0.27,
            ear_used=0.27,
            mar=0.12,
            pitch=0.0,
            face_quality={"usable": True},
            eye_quality={"usable": True, "selected": "both", "reason": "OK"},
            left_eye_points=[],
            right_eye_points=[],
            mouth_points=[],
            face_bbox=None,
        )
        app._last_ai_result = {
            "state": "DROWSY",
            "confidence": 0.88,
            "reason": "adaptive",
            "alert_hint": 1,
            "thresholds": {
                "ear_closed": 0.275,
                "ear_adaptive_closed": 0.275,
                "ear_drop_closed": 0.13,
                "ear_open_baseline": 0.32,
                "mar_yawn": 0.45,
                "pitch_down": -15.0,
            },
            "features": {
                "perclos_short": 1.0,
                "perclos_long": 1.0,
                "ear_open_baseline": 0.32,
                "ear_adaptive_threshold": 0.275,
                "ear_drop_score": 0.156,
                "ear_closed": True,
                "ear_closed_reason": "EAR_DROP",
            },
        }

        payload = app._build_local_monitor_payload()

        self.assertEqual(payload["ai"]["perclos"], 1.0)
        self.assertEqual(payload["ai"]["features"]["ear_open_baseline"], 0.32)
        self.assertEqual(payload["ai"]["features"]["ear_adaptive_threshold"], 0.275)
        self.assertEqual(payload["ai"]["features"]["ear_drop_score"], 0.156)
        self.assertEqual(payload["ai"]["thresholds"]["ear_adaptive_closed"], 0.275)
```

- [ ] **Step 2: Write failing local monitor parser test**

Append this test to `Version3\tests\test_local_monitor_gui.py`:

```python
def test_local_monitor_state_parses_adaptive_ear_fields():
    state = LocalMonitorState.from_runtime_payload({
        "ai": {
            "ear": 0.27,
            "left_ear": 0.27,
            "right_ear": 0.27,
            "ear_used": 0.27,
            "perclos": 1.0,
            "thresholds": {
                "ear_closed": 0.275,
                "ear_adaptive_closed": 0.275,
                "ear_drop_closed": 0.13,
                "ear_open_baseline": 0.32,
            },
            "features": {
                "perclos_short": 1.0,
                "perclos_long": 1.0,
                "ear_open_baseline": 0.32,
                "ear_adaptive_threshold": 0.275,
                "ear_drop_score": 0.156,
                "ear_closed": True,
                "ear_closed_reason": "EAR_DROP",
            },
        }
    })

    assert state.ear_threshold == 0.275
    assert state.ear_open_baseline == 0.32
    assert state.ear_adaptive_threshold == 0.275
    assert state.ear_drop_score == 0.156
    assert state.ear_closed is True
    assert state.ear_closed_reason == "EAR_DROP"
```

- [ ] **Step 3: Write failing standalone monitor overlay test**

Append this test to `Version3\tests\test_local_ai_monitor_script.py`:

```python
def test_overlay_lines_include_adaptive_ear_diagnostics():
    metrics = DummyMetrics()
    metrics.ear = 0.27
    metrics.left_ear = 0.27
    metrics.right_ear = 0.27
    metrics.ear_used = 0.27
    ai_result = {
        "state": "DROWSY",
        "confidence": 0.88,
        "reason": "adaptive",
        "thresholds": {
            "ear_closed": 0.275,
            "ear_adaptive_closed": 0.275,
            "ear_drop_closed": 0.13,
            "ear_open_baseline": 0.32,
            "mar_yawn": 0.45,
            "pitch_down": -15.0,
        },
        "features": {
            "ear_open_baseline": 0.32,
            "ear_adaptive_threshold": 0.275,
            "ear_drop_score": 0.156,
            "ear_closed": True,
            "ear_closed_reason": "EAR_DROP",
        },
    }

    lines = build_overlay_lines(metrics, 1.0, ai_result, 12.0, 12.0, 10)

    joined = "\n".join(lines)
    assert "Base 0.320" in joined
    assert "Adapt 0.275" in joined
    assert "Drop 0.156" in joined
    assert "EAR_DROP" in joined
```

- [ ] **Step 4: Run GUI/payload tests to verify failure**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_main_local_gui.py tests/test_local_monitor_gui.py tests/test_local_ai_monitor_script.py -q
```

Expected: fail because adaptive fields are not yet parsed or displayed.

- [ ] **Step 5: Use classifier PERCLOS in `main.py` payload**

In `Version3\main.py`, add this helper method near `_publish_runtime_status()`:

```python
    def _ai_perclos_payload(self, ai_result):
        features = (ai_result or {}).get("features", {}) or {}
        if "perclos_long" in features:
            return round(float(features.get("perclos_long") or 0.0), 3)
        return round(float(self.face_analyzer.perclos if self.face_analyzer else 0.0), 3)
```

In both AI payload builders in `main.py`, replace:

```python
                "perclos": round(float(self.face_analyzer.perclos if self.face_analyzer else 0.0), 3),
```

with:

```python
                "perclos": self._ai_perclos_payload(ai_result),
```

- [ ] **Step 6: Add adaptive fields to `LocalMonitorState`**

In `Version3\ui\local_monitor.py`, add these names to `LocalMonitorState.FIELDS` after `ear_threshold`:

```python
        "ear_open_baseline",
        "ear_adaptive_threshold",
        "ear_drop_score",
        "ear_closed",
        "ear_closed_reason",
```

Add these defaults to `LocalMonitorState.DEFAULTS` after `ear_threshold`:

```python
        "ear_open_baseline": None,
        "ear_adaptive_threshold": DEFAULT_EAR_THRESHOLD,
        "ear_drop_score": 0.0,
        "ear_closed": False,
        "ear_closed_reason": "",
```

In `LocalMonitorState.from_runtime_payload()`, add these constructor arguments after `ear_threshold`:

```python
            ear_open_baseline=_optional_float(features.get("ear_open_baseline"), _optional_float(thresholds.get("ear_open_baseline"))),
            ear_adaptive_threshold=_float(features.get("ear_adaptive_threshold"), _float(thresholds.get("ear_adaptive_closed"), DEFAULT_EAR_THRESHOLD)),
            ear_drop_score=_float(features.get("ear_drop_score")),
            ear_closed=bool(features.get("ear_closed")),
            ear_closed_reason=features.get("ear_closed_reason") or "",
```

Update `build_panel_lines()` by adding this line immediately after the `EAR` line:

```python
        "Adaptive base %s | threshold %.3f | drop %.3f | %s" % (
            _fmt(state.ear_open_baseline),
            state.ear_adaptive_threshold,
            state.ear_drop_score,
            state.ear_closed_reason or ("CLOSED" if state.ear_closed else "OPEN"),
        ),
```

- [ ] **Step 7: Add adaptive fields to standalone AI monitor overlay**

In `Version3\scripts\local_ai_monitor.py`, inside `build_overlay_lines()`, after `features = ...`, add:

```python
    ear_open_baseline = features.get("ear_open_baseline", thresholds.get("ear_open_baseline"))
    ear_adaptive_threshold = features.get("ear_adaptive_threshold", thresholds.get("ear_adaptive_closed", thresholds.get("ear_closed", config.EAR_THRESHOLD)))
    ear_drop_score = float(features.get("ear_drop_score", 0.0) or 0.0)
    ear_closed_reason = features.get("ear_closed_reason", "OPEN")
```

Add this output line immediately after the `L/R/USED` line:

```python
        "Base %.3f | Adapt %.3f | Drop %.3f | %s" % (
            float(ear_open_baseline or 0.0),
            float(ear_adaptive_threshold or config.EAR_THRESHOLD),
            ear_drop_score,
            ear_closed_reason,
        ),
```

- [ ] **Step 8: Run GUI/payload tests**

Run:

```powershell
python -m pytest tests/test_main_local_gui.py tests/test_local_monitor_gui.py tests/test_local_ai_monitor_script.py -q
```

Expected: pass.

- [ ] **Step 9: Commit Task 3**

Run:

```powershell
git add Version3/main.py Version3/ui/local_monitor.py Version3/scripts/local_ai_monitor.py Version3/tests/test_main_local_gui.py Version3/tests/test_local_monitor_gui.py Version3/tests/test_local_ai_monitor_script.py
git commit -m "feat: expose adaptive EAR diagnostics"
```

---

## Task 4: Contract And Documentation

**Files:**
- Modify: `D:\DATN-testing1\Version3\docs\protocol.md`
- Modify: `D:\DATN-testing1\Version3\tests\fixtures\websocket_payloads.py`
- Test: `D:\DATN-testing1\Version3\tests\test_webquanli_contract.py`
- Test: `D:\DATN-testing1\WebQuanLi\tests\test_websocket_contract_fixtures.py`

- [ ] **Step 1: Add optional adaptive AI fields to fixture**

In `Version3\tests\fixtures\websocket_payloads.py`, update `alert_payload()` to include:

```python
        "ear_open_baseline": 0.32,
        "ear_adaptive_threshold": 0.275,
        "ear_drop_score": 0.156,
        "ear_closed_reason": "EAR_DROP",
```

- [ ] **Step 2: Run WebQuanLi contract tests to confirm compatibility**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_webquanli_contract.py -q
```

Run in `D:\DATN-testing1\WebQuanLi`:

```powershell
python -m pytest tests/test_websocket_contract_fixtures.py -q
```

Expected: both pass. WebQuanLi should ignore the extra optional alert fields if it does not display them yet.

- [ ] **Step 3: Document adaptive EAR payload**

In `Version3\docs\protocol.md`, add this subsection under AI/runtime payload documentation:

```markdown
### Adaptive EAR diagnostics

Version3 may include these optional AI fields for glasses-aware eye closure:

- `ai.thresholds.ear_open_baseline`: calibrated open-eye EAR baseline for the selected eye mode.
- `ai.thresholds.ear_adaptive_closed`: adaptive closed-eye threshold after clamping.
- `ai.thresholds.ear_drop_closed`: required proportional drop from baseline.
- `ai.features.ear_open_baseline`: baseline used for the current frame.
- `ai.features.ear_adaptive_threshold`: threshold used for the current frame.
- `ai.features.ear_drop_score`: `(baseline - current_ear) / baseline`.
- `ai.features.ear_closed`: final frame-level closed-eye decision.
- `ai.features.ear_closed_reason`: `ADAPTIVE_EAR`, `EAR_DROP`, `OPEN`, or `UNUSABLE_EYE`.

Legacy fields remain valid. `ear`, `left_ear`, `right_ear`, `ear_used`, and `eye_quality` keep their existing meaning.
```

- [ ] **Step 4: Commit Task 4**

Run:

```powershell
git add Version3/docs/protocol.md Version3/tests/fixtures/websocket_payloads.py
git commit -m "docs: document adaptive EAR diagnostics"
```

---

## Task 5: Final Local Verification

**Files:**
- Read only: `D:\DATN-testing1`

- [ ] **Step 1: Run Version3 focused suite**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -m pytest tests/test_threshold_policy.py tests/test_calibration.py tests/test_drowsiness_classifier.py tests/test_ai_session_controller.py tests/test_main_local_gui.py tests/test_local_monitor_gui.py tests/test_local_ai_monitor_script.py tests/test_webquanli_contract.py -q
```

Expected: pass.

- [ ] **Step 2: Run WebQuanLi contract suite**

Run in `D:\DATN-testing1\WebQuanLi`:

```powershell
python -m pytest tests/test_websocket_contract_fixtures.py tests/test_ws_session_flow.py tests/test_api_validation_contract.py -q
```

Expected: pass.

- [ ] **Step 3: Compile runtime files**

Run in `D:\DATN-testing1`:

```powershell
python -m py_compile Version3\main.py Version3\ai\calibration.py Version3\ai\drowsiness_classifier.py Version3\ai\threshold_policy.py Version3\ai\session_controller.py Version3\camera\face_analyzer.py Version3\alerts\alert_manager.py Version3\ui\local_monitor.py Version3\scripts\local_ai_monitor.py
```

Expected: exit code `0`.

- [ ] **Step 4: Manual non-deploy sanity simulation**

Run in `D:\DATN-testing1\Version3`:

```powershell
python -c "from ai.drowsiness_classifier import DrowsinessClassifier; from ai.calibration import CalibrationProfile; p=CalibrationProfile(valid=True, reason='OK', ear_open_median=0.32, mar_closed_median=0.12, pitch_neutral=0.0, ear_closed_threshold=0.275, mar_yawn_threshold=0.45, pitch_down_threshold=-15.0, sample_count=40, ear_used_open_median=0.32, ear_adaptive_closed_threshold=0.275, ear_drop_closed_threshold=0.13); c=DrowsinessClassifier(profile=p, target_fps=10); m={'face_present': True, 'face_quality': {'usable': True}, 'eye_quality': {'usable': True, 'selected': 'both', 'reason': 'OK'}, 'ear_used': 0.27, 'left_ear': 0.27, 'right_ear': 0.27, 'mar': 0.12, 'pitch': 0.0}; r=None; [c.update(m) for _ in range(8)]; print(c.last_result['state'], c.last_result['alert_hint'], c.last_result['features']['ear_drop_score'])"
```

Expected output starts with:

```text
DROWSY 1
```

- [ ] **Step 5: Commit verification notes if any docs changed**

If no files changed during verification, do not commit. If documentation was adjusted, run:

```powershell
git add Version3/docs/protocol.md
git commit -m "docs: clarify adaptive EAR validation"
```

---

## Task 6: Jetson Deployment Checkpoint

**Files:**
- Deploy candidates only after user approval:
  - `D:\DATN-testing1\Version3\config.py`
  - `D:\DATN-testing1\Version3\main.py`
  - `D:\DATN-testing1\Version3\ai\calibration.py`
  - `D:\DATN-testing1\Version3\ai\drowsiness_classifier.py`
  - `D:\DATN-testing1\Version3\ai\threshold_policy.py`
  - `D:\DATN-testing1\Version3\ui\local_monitor.py`
  - `D:\DATN-testing1\Version3\scripts\local_ai_monitor.py`

- [ ] **Step 1: Ask user before deploy**

Stop and ask:

```text
Local tests passed. Do you want me to deploy the adaptive EAR runtime files to Jetson now?
```

- [ ] **Step 2: Backup remote files before copying**

Run only after user approves deployment:

```powershell
ssh nano@192.168.2.17 'cd /home/nano/Version3 && ts=$(date +%Y%m%d-%H%M%S) && backup_dir=storage/deploy_backups/$ts && mkdir -p "$backup_dir" && cp config.py main.py "$backup_dir"/ && mkdir -p "$backup_dir/ai" "$backup_dir/ui" "$backup_dir/scripts" && cp ai/calibration.py ai/drowsiness_classifier.py ai/threshold_policy.py "$backup_dir/ai"/ && cp ui/local_monitor.py "$backup_dir/ui"/ && cp scripts/local_ai_monitor.py "$backup_dir/scripts"/ && echo "$backup_dir"'
```

Expected: prints backup path such as `/home/nano/Version3/storage/deploy_backups/20260427-203000`.

- [ ] **Step 3: Copy runtime files**

Run from `D:\DATN-testing1\Version3`:

```powershell
scp config.py main.py nano@192.168.2.17:/home/nano/Version3/
scp ai\calibration.py ai\drowsiness_classifier.py ai\threshold_policy.py nano@192.168.2.17:/home/nano/Version3/ai/
scp ui\local_monitor.py nano@192.168.2.17:/home/nano/Version3/ui/
scp scripts\local_ai_monitor.py nano@192.168.2.17:/home/nano/Version3/scripts/
```

Expected: all `scp` commands exit `0`.

- [ ] **Step 4: Compile on Jetson**

Run:

```powershell
ssh nano@192.168.2.17 'cd /home/nano/Version3 && python3 -m py_compile config.py main.py ai/calibration.py ai/drowsiness_classifier.py ai/threshold_policy.py ui/local_monitor.py scripts/local_ai_monitor.py && echo JETSON_ADAPTIVE_EAR_COMPILE_OK'
```

Expected:

```text
JETSON_ADAPTIVE_EAR_COMPILE_OK
```

- [ ] **Step 5: Restart services and verify**

Run:

```powershell
ssh nano@192.168.2.17 'printf "nano\n" | sudo -S systemctl restart drowsiguard.service drowsiguard-dashboard.service && sleep 5 && printf "DROWSIGUARD=" && systemctl is-active drowsiguard.service && printf "DASHBOARD=" && systemctl is-active drowsiguard-dashboard.service'
```

Expected:

```text
DROWSIGUARD=active
DASHBOARD=active
```

- [ ] **Step 6: Manual Jetson validation**

Use the Jetson camera and record these observations:

```text
No glasses:
- open eyes normal
- short blink reports BLINK only
- closed eyes 1s reports DROWSY level 1
- closed eyes 2s reports DROWSY level 2
- closed eyes 3s reports DROWSY level 3

Prescription glasses:
- open eyes around 0.30-0.33 remain NORMAL
- closed eyes around 0.26-0.28 become EYES_CLOSED/DROWSY after enough time
- mild glare on one eye selects the other usable eye
- both eyes unreliable becomes LOW_CONFIDENCE, not false DROWSY
```

---

## Self-Review

- Spec coverage: adaptive baseline, side-aware baseline, fixed fallback, `eye_quality` gate, dashboard diagnostics, WebSocket compatibility, local tests, and Jetson deployment checkpoint are covered.
- Placeholder scan: no deferred implementation markers and no unnamed tests.
- Type consistency: plan uses existing names `CalibrationProfile`, `ThresholdPolicy`, `DrowsinessClassifier`, `eye_quality`, `ear_used`, `left_ear`, `right_ear`, `perclos_short`, and `perclos_long`.
- Risk note: this plan intentionally does not change RFID, GPS, Bluetooth, speaker, face verification, or WebQuanLi control flow.
