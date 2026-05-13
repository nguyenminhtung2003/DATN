# Drowsiness Demo Script

Date: 2026-05-13

Round: Project 9/10 Roadmap - Round 4

Purpose: make the drowsiness AI portion predictable and explainable during a live graduation demo.

## What This Round Adds

New automated demo smoke mode:

```powershell
cd D:\DATN-testing1\Version3
python scripts\test_demo_readiness.py --mode drowsiness-demo
```

The mode checks that alert events sent by the Jetson runtime contain the fields WebQuanLi needs:

- `level`
- `ear`
- `mar`
- `perclos`
- `ai_state`
- `ai_confidence`

It simulates five demo states:

1. `normal-baseline`
2. `closed-eyes-warning`
3. `yawn-warning`
4. `head-down-warning`
5. `recovery-normal`

## Live Demo Preconditions

Before starting this script:

- WebQuanLi is running and reachable from Jetson.
- Jetson runtime is running.
- `DROWSIGUARD_DEMO_MODE=false`.
- `DROWSIGUARD_FEATURE_FACE_VERIFY=true`.
- RFID identity verification succeeds for the real driver.
- Camera angle shows the full face clearly.
- Lighting is stable enough that both eyes are visible.

## Manual Demo Flow Under 5 Minutes

### 1. Verified Session Start

Action:

- Scan RFID.
- Look directly at the camera.

Expected:

- Face verification succeeds.
- WebQuanLi receives `session_start` and `verify_snapshot`.
- Jetson state enters `RUNNING`.

Fail condition:

- Session starts without face verification.
- Session cannot start with correct face under normal lighting.

### 2. Normal Baseline

Action:

- Keep eyes open.
- Face forward.
- Avoid yawning and head-down pose for a few seconds.

Expected:

- AI state becomes normal or collecting stable samples.
- No immediate alert spam.
- EAR should remain around the open-eye range for the current driver.

Fail condition:

- Warning triggers immediately while posture is normal.
- AI stays stuck in low confidence due to bad eye visibility.

### 3. Closed Eyes Warning

Action:

- Close both eyes steadily long enough to trigger warning.
- Start with about 1-2 seconds. Extend slightly if needed.

Expected:

- EAR drops.
- AI state becomes `EYES_CLOSED` or `DROWSY`.
- WebQuanLi receives an `alert` event with `ear`, `perclos`, `ai_state`, `ai_confidence`, and `level`.

Fail condition:

- No alert after a clearly closed-eye hold.
- Alert fires only after an impractically long time.

### 4. Yawn / Mouth Open Warning

Action:

- Open mouth clearly as if yawning for about 1-2 seconds.

Expected:

- MAR rises.
- AI state can become `YAWNING`.
- Alert level may rise depending on duration and current cooldown.

Fail condition:

- MAR does not visibly change.
- Camera angle hides the mouth.

### 5. Head Down Warning

Action:

- Look down and hold the pose briefly.

Expected:

- Pitch value changes downward.
- AI state can become `HEAD_DOWN`.
- Alert event can be sent if the pose is held long enough.

Fail condition:

- Pitch stays nearly unchanged despite clear head-down pose.
- Face leaves the frame and becomes `NO_FACE` instead of head-down.

### 6. Recovery

Action:

- Return to normal posture.
- Open eyes.
- Face forward.

Expected:

- AI state returns to normal after cooldown/recovery.
- Alert level should not stay stuck.

Fail condition:

- Warning remains stuck after normal posture.
- Repeated false alerts continue during normal posture.

## Automated Evidence

Round 4 RED:

```text
test_demo_readiness.py: error: argument --mode: invalid choice: 'drowsiness-demo'
```

Round 4 GREEN:

```text
1 passed in 0.46s
```

Expected output from the new mode includes:

```text
[DROWSINESS] normal-baseline: PASS
[DROWSINESS] closed-eyes-warning: PASS
[DROWSINESS] yawn-warning: PASS
[DROWSINESS] head-down-warning: PASS
[DROWSINESS] recovery-normal: PASS
[DROWSINESS] PASS: drowsiness demo alert payloads are ready.
```

## Notes For Presentation

Explain the AI honestly:

- MediaPipe Face Mesh detects facial landmarks.
- OpenCV/geometry extracts EAR, MAR, pitch, and PERCLOS.
- The classifier is a rule-based temporal CV pipeline.
- It does not need internet and runs locally on Jetson Nano.
- It is sensitive to lighting, camera angle, glasses glare, and face distance.

## Current Limitation

This round does not change thresholds and does not prove live camera stability by itself. It proves the event contract and gives a repeatable manual demo script. Live Jetson validation is still required.
