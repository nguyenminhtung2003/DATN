# Project 9/10 Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not execute this plan in one pass; stop after each round and wait for user confirmation.

**Goal:** Raise the DATN DrowsiGuard project from the current demo-ready level toward a defensible 9/10 by improving identity verification evidence, demo reliability, runtime hardening, and thesis presentation proof.

**Architecture:** Keep Jetson Nano as the offline runtime owner for RFID, camera, face verification, drowsiness detection, audio, GPS, and WebSocket events. Keep WebQuanLi as the dashboard, driver registry, face image source, and demo evidence surface. Improve quality through measurable gates before adding heavier model dependencies.

**Tech Stack:** Python 3, OpenCV, MediaPipe Face Mesh, existing Jetson `Version3`, FastAPI/SQLite WebQuanLi, WebSocket, pytest, Jetson SSH, manual demo checklist.

---

## Baseline Score And Target

Current estimate before this roadmap:

| Area | Current | Target |
|---|---:|---:|
| Live face verification | 7.4/10 | 8.7/10 |
| Real demo readiness | 8.2/10 | 9.2/10 |
| Jetson-WebQuanLi integration | 8.3/10 | 9.0/10 |
| Drowsiness AI pipeline | 7.8/10 | 8.6/10 |
| Testing, rollback, evidence | 8.0/10 | 9.2/10 |
| Overall | 8.1/10 | 9.0/10 |

The target is not "industrial biometric security". The target is a graduation-thesis demo that is technically honest, stable under live presentation, and backed by tests plus repeatable evidence.

---

## Recommended Strategy

### Recommended Path: Practical 9/10

Complete rounds 0 to 5:

1. Freeze a known-good demo baseline.
2. Prove identity verification with fixed positive/negative/no-face cases.
3. Calibrate face threshold from a small evidence dataset.
4. Add demo-facing observability and clear failure reasons.
5. Harden launch, audio, healthcheck, and rollback.
6. Produce a defense evidence pack.

This is the safest path because it improves the score through reliability, evidence, and presentation quality without risking Jetson performance.

### Optional Technical Path: Embedding Face Recognition

Run Round 6 only after the practical path is stable. Evaluate a lightweight embedding method such as OpenCV SFace/FaceRecognizerSF if model files and Jetson OpenCV support are available. Keep the existing fallback similarity path as the safety net.

This can improve technical credibility, but it can also consume time if Jetson dependencies or model files are not ready.

### Not Recommended Before Demo

Do not replace the whole verification pipeline with a heavy deep-learning stack, do not add WebQuanLi multi-image upload UI before the current demo is stable, and do not refactor unrelated drowsiness logic while identity verification is still being tested.

---

## Execution Rules

After each round, stop and report:

1. Files changed.
2. Commands run.
3. Automated test result.
4. Jetson/manual test result.
5. Pass/fail decision.
6. Risk left.
7. Rollback note.
8. Ask: "Tiep tuc vong tiep theo khong?"

Do not start the next round until the user confirms.

Do not commit or push unless the user explicitly approves that step.

---

## Round 0: Freeze And Prove Current Baseline

**Goal:** Make the current working state measurable before new changes, because a 9/10 project needs a reproducible stable checkpoint.

**Score impact:** 8.1 -> 8.3 if all checks pass and baseline evidence is saved.

**Files to read:**

- `D:/DATN-testing1/Version3/main.py`
- `D:/DATN-testing1/Version3/config.py`
- `D:/DATN-testing1/Version3/camera/face_verifier.py`
- `D:/DATN-testing1/Version3/storage/driver_registry.py`
- `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- `D:/DATN-testing1/WebQuanLi/app/api/vehicles.py`
- `D:/DATN-testing1/docs/superpowers/plans/2026-05-12-demo-readiness-face-verification-stabilization.md`
- `D:/DATN-testing1/docs/superpowers/plans/2026-05-13-jetson-face-reference-finalization.md`

**Files to modify:**

- Create: `D:/DATN-testing1/docs/demo-readiness/2026-05-13-baseline-evidence.md`

**Steps:**

- [ ] Record git state.

```powershell
git status --short
git branch --show-current
git log --oneline -5
```

Expected:

```text
Current branch and dirty files are documented.
No unrelated file is reverted.
```

- [ ] Run local Version3 focused tests.

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_verify_flow.py tests/test_reverify_flow.py tests/test_demo_readiness_script.py tests/test_face_registry_sync.py tests/test_face_crop_compat.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round0-version3
```

Expected:

```text
All focused identity/demo tests pass.
```

- [ ] Run demo readiness simulation.

```powershell
cd D:\DATN-testing1\Version3
python scripts\test_demo_readiness.py --mode identity-sim
python scripts\test_demo_readiness.py --mode simulate
```

Expected:

```text
[IDENTITY] PASS
[SIM] PASS
```

- [ ] Run Jetson read-only checks.

```powershell
ssh nano@192.168.2.29 "pgrep -af 'python3 main.py' || true; cd /home/nano/Version3 && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode hardware"
```

Expected:

```text
DrowsiGuard process is running.
Hardware smoke reports PASS or every warning is documented.
```

- [ ] Create `docs/demo-readiness/2026-05-13-baseline-evidence.md` with command outputs summarized.

**Manual Jetson test:**

- [ ] No face in camera + scan RFID: must reject with `NO_FACE_FRAME`.
- [ ] Correct face in camera + scan RFID: must verify and enter `RUNNING`.
- [ ] Show face, leave frame, then scan RFID: must reject with `NO_FACE_FRAME`.

**Pass criteria:**

- Local tests pass.
- Jetson hardware smoke pass or non-blocking warnings are documented.
- All three manual identity cases pass.

**Fail criteria:**

- No-face case starts session.
- Correct-face case cannot pass under controlled lighting.
- Runtime is not in strict mode.

**Risks:**

- Current worktree is dirty, so baseline must document existing changed files before any new work.
- Audio sink warnings may exist and should be tracked separately from face verification.

**Rollback:**

- No runtime rollback for read-only checks.
- If evidence doc is wrong, edit only that doc.

**Stop checkpoint:** Report baseline score and wait for approval.

---

## Round 1: Demo Release Snapshot And Git Hygiene

**Goal:** Create a clean, reviewable demo snapshot so the project can be pushed or rolled back confidently.

**Score impact:** 8.3 -> 8.45.

**Files to read:**

- `D:/DATN-testing1/.gitignore`
- Output from `git status --short`
- Files changed by previous face-verification rounds

**Files to modify:**

- Modify: `D:/DATN-testing1/.gitignore` only if generated folders are not ignored.
- Create: `D:/DATN-testing1/docs/demo-readiness/2026-05-13-demo-release-checklist.md`

**Generated folders to keep out of commit:**

- `D:/DATN-testing1/.pytest_deps/`
- `D:/DATN-testing1/.test_tmp/`
- `D:/DATN-testing1/.tmp/`
- `D:/DATN-testing1/.deploy/`

**Steps:**

- [ ] Separate intentional source changes from generated files.

```powershell
git status --short
```

Expected:

```text
Runtime/test/docs changes are identifiable.
Generated folders are either ignored or deliberately left untracked.
```

- [ ] If generated folders are not ignored, add these lines to `.gitignore`.

```gitignore
.pytest_deps/
.test_tmp/
.tmp/
.deploy/
```

- [ ] Create `docs/demo-readiness/2026-05-13-demo-release-checklist.md` with:
  - exact Jetson IP used;
  - start command;
  - stop command;
  - face verify threshold;
  - strict mode state;
  - WebQuanLi URL;
  - three identity tests;
  - three drowsiness alert tests;
  - rollback commands.

- [ ] Run focused tests again after ignore/doc changes.

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_verify_flow.py tests/test_demo_readiness_script.py tests/test_face_registry_sync.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round1
```

**Manual Jetson test:**

- [ ] Confirm the checklist commands match the actual launcher:

```powershell
ssh nano@192.168.2.29 "grep -E 'DROWSIGUARD_DEMO_MODE|DROWSIGUARD_FACE_VERIFY_THRESHOLD|DROWSIGUARD_FEATURE_FACE_VERIFY|Starting python3 main.py|Mode' /home/nano/start_drowsiguard_full.sh"
```

**Pass criteria:**

- Source changes are clearly separated from generated artifacts.
- Checklist can be followed by another person.
- Tests pass.

**Fail criteria:**

- Generated folders remain mixed with source changes.
- Checklist contains commands that do not match Jetson.

**Risks:**

- Accidentally staging large/generated artifacts.

**Rollback:**

- Revert only `.gitignore` and checklist edits if they are incorrect.
- Do not revert runtime source changes from earlier rounds unless user requests it.

**Stop checkpoint:** Report whether the repo is ready for a demo commit.

---

## Round 2: Evidence-Based Face Threshold Calibration

**Goal:** Replace threshold guessing with a small local benchmark that shows why the chosen threshold is reasonable.

**Score impact:** 8.45 -> 8.65.

**Files to read:**

- `D:/DATN-testing1/Version3/camera/face_verifier.py`
- `D:/DATN-testing1/Version3/storage/driver_registry.py`
- `D:/DATN-testing1/Version3/tests/test_face_registry_sync.py`

**Files to modify:**

- Create: `D:/DATN-testing1/Version3/scripts/evaluate_face_threshold.py`
- Create: `D:/DATN-testing1/Version3/tests/test_face_threshold_evaluation.py`
- Create: `D:/DATN-testing1/docs/demo-readiness/face-threshold-calibration.md`

**Data layout for evaluation:**

```text
D:/DATN-testing1/.tmp/face_eval/
  positives/
    pos_01.jpg
    pos_02.jpg
    pos_03.jpg
  negatives/
    neg_01.jpg
    neg_02.jpg
  no_face/
    no_face_01.jpg
```

**Implementation approach:**

- Add a script that loads the same `FaceVerifier` preprocessing path used by runtime.
- Compute similarity scores between each probe image and current references.
- Print a table:
  - filename;
  - expected label;
  - best reference;
  - score;
  - decision at threshold `0.785`;
  - recommendation.
- Do not change `FACE_VERIFY_THRESHOLD` until evidence is reviewed.

**Steps:**

- [ ] Add a test that validates threshold evaluation output schema.

Example expected output row:

```json
{
  "file": "pos_01.jpg",
  "expected": "positive",
  "best_reference": "ref_04.jpg",
  "score": 0.884,
  "threshold": 0.785,
  "decision": "MATCH"
}
```

- [ ] Run the failing test.

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_face_threshold_evaluation.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round2-red
```

Expected:

```text
FAIL because evaluate_face_threshold.py does not exist.
```

- [ ] Implement `scripts/evaluate_face_threshold.py`.

Required command:

```powershell
python scripts\evaluate_face_threshold.py --rfid 0199190080 --dataset D:\DATN-testing1\.tmp\face_eval --threshold 0.785 --json-out D:\DATN-testing1\.tmp\face_eval\report.json
```

Expected:

```text
The script writes report.json and prints pass/fail summary.
```

- [ ] Run the green test.

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_face_threshold_evaluation.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round2-green
```

- [ ] Write calibration evidence into `docs/demo-readiness/face-threshold-calibration.md`.

**Manual Jetson test:**

- [ ] Copy 2-3 real positive probes and 1-2 negative probes from Jetson to `.tmp/face_eval`.
- [ ] Run the evaluator on Windows or Jetson.
- [ ] Decide whether to keep `0.785`, raise to `0.80`, or document why not.

**Pass criteria:**

- Positive images score above the selected threshold.
- Negative images score below the selected threshold or are rejected as `LOW_CONFIDENCE/MISMATCH`.
- No-face images do not produce a successful match.

**Fail criteria:**

- Negative images often pass at `0.785`.
- Positive images often fail under normal demo lighting.

**Risks:**

- Too few negative examples can make the threshold look safer than it is.
- IR/purple lighting differences can shift scores.

**Rollback:**

- Do not change threshold in this round unless user approves after evidence.
- Delete only the new evaluator script/test/doc if the approach is rejected.

**Stop checkpoint:** Report score distribution and recommended threshold.

---

## Round 3: Face Verification UX And Failure Reason Clarity

**Goal:** Make demo behavior understandable to the user and the committee: no face, low confidence, wrong identity, and no enrollment should be visibly different.

**Score impact:** 8.65 -> 8.78.

**Files to read:**

- `D:/DATN-testing1/Version3/main.py`
- `D:/DATN-testing1/Version3/alerts/alert_manager.py`
- `D:/DATN-testing1/Version3/speaker.py` or current speaker/audio module path if different
- `D:/DATN-testing1/WebQuanLi/templates/dashboard.html`
- `D:/DATN-testing1/WebQuanLi/tests/test_verify_snapshot_contract.py`

**Files to modify:**

- Modify: `D:/DATN-testing1/Version3/main.py`
- Modify: `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- Modify or create: `D:/DATN-testing1/Version3/tests/test_verify_flow.py`
- Modify: `D:/DATN-testing1/WebQuanLi/templates/dashboard.html`
- Modify or create: `D:/DATN-testing1/WebQuanLi/tests/test_verify_snapshot_contract.py`

**Implementation approach:**

- Keep `NO_FACE_FRAME` mapped to "Vui long nhin vao camera".
- Keep `LOW_CONFIDENCE` mapped to "Khong du tin cay, hay giu mat on dinh".
- Keep `MISMATCH` mapped to "Sai danh tinh tai xe".
- Keep `NO_ENROLLMENT` mapped to "Tai xe chua co anh dang ky".
- Ensure dashboard shows the reason, not a generic failure.

**Automated tests:**

- [ ] `NO_FACE_FRAME` queues `verify_error.reason == NO_FACE_FRAME` and no `session_start`.
- [ ] `LOW_CONFIDENCE` queues `verify_error.reason == LOW_CONFIDENCE` and no `session_start`.
- [ ] `MISMATCH` queues `face_mismatch` and no `session_start`.
- [ ] WebQuanLi renders friendly labels for all four states.

**Commands:**

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_verify_flow.py tests/test_demo_readiness_script.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round3-version3
```

```powershell
cd D:\DATN-testing1\WebQuanLi
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_verify_snapshot_contract.py tests/test_dashboard_realtime_context.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round3-webquanli
```

**Manual Jetson test:**

- [ ] No face: observe camera GUI and WebQuanLi log.
- [ ] Low confidence: partially cover face or use bad angle; observe distinct message.
- [ ] Wrong face: test with another person or printed non-matching face only if user approves.
- [ ] Correct face: verify success.

**Pass criteria:**

- Each failure has a distinct message and event.
- No failure starts a session.
- Correct success still starts session.

**Fail criteria:**

- `LOW_CONFIDENCE` is displayed as "no face".
- Dashboard hides the reason from the demo operator.

**Risks:**

- Audio files for some prompts may not exist; text/dashboard fallback must still work.

**Rollback:**

- Restore previous `main.py` and dashboard template from git or Jetson backup if prompt/status mapping breaks.

**Stop checkpoint:** Report UX evidence.

---

## Round 4: Drowsiness Demo Stability Pack

**Goal:** Make the AI buồn ngủ portion feel stable and explainable, not just identity verification.

**Score impact:** 8.78 -> 8.9.

**Files to read:**

- `D:/DATN-testing1/Version3/camera/face_analyzer.py`
- `D:/DATN-testing1/Version3/ai/drowsiness_classifier.py`
- `D:/DATN-testing1/Version3/ai/session_controller.py`
- `D:/DATN-testing1/Version3/ai/threshold_policy.py`
- `D:/DATN-testing1/Version3/alerts/alert_manager.py`
- `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`

**Files to modify:**

- Modify: `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- Create: `D:/DATN-testing1/Version3/tests/test_drowsiness_demo_script.py`
- Create: `D:/DATN-testing1/docs/demo-readiness/drowsiness-demo-script.md`

**Implementation approach:**

- Do not change classifier thresholds unless evidence shows a problem.
- Add a scripted manual demo path:
  - normal face open-eye baseline;
  - closed eyes warning;
  - yawning warning;
  - head down warning;
  - recovery back to normal.
- Add a simulated test case that confirms alert events contain:
  - `ai_state`;
  - `ai_confidence`;
  - `ear`;
  - `mar`;
  - `perclos`;
  - `level`.

**Automated tests:**

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_drowsiness_demo_script.py tests/test_threshold_policy.py tests/test_calibration.py tests/test_ai_session_controller.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round4
```

**Manual Jetson test:**

- [ ] After identity verify, keep eyes open for calibration.
- [ ] Close eyes long enough to trigger alert level 1 or 2.
- [ ] Yawn or open mouth to trigger MAR signal if feasible.
- [ ] Look down to verify pitch display changes.
- [ ] Return to normal and confirm alert state recovers.

**Pass criteria:**

- Demo script can be followed in under 5 minutes.
- At least one alert triggers reliably.
- Normal face does not immediately spam false alerts after calibration.

**Fail criteria:**

- AI stays `NOT_ENOUGH_SAMPLE` too long for demo.
- Alerts trigger randomly during normal face.
- No clear recovery after normal posture.

**Risks:**

- Glasses, lighting, and camera angle can destabilize EAR.
- Jetson FPS may drop if GUI/camera resolution is too high.

**Rollback:**

- This round should mostly add tests/docs. If threshold changes are later approved, keep the old values documented and revert config/env only.

**Stop checkpoint:** Report whether drowsiness demo can be performed predictably.

---

## Round 5: Runtime Hardening And Operator Checklist

**Goal:** Remove demo-killing operational issues: misleading launcher text, unclear health status, audio sink ambiguity, and no one-command verification.

**Score impact:** 8.9 -> 9.0.

**Files to read:**

- `/home/nano/start_drowsiguard_full.sh`
- `/home/nano/Version3/drowsiguard.env`
- `D:/DATN-testing1/Version3/healthcheck.py`
- `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- `D:/DATN-testing1/docs/demo-readiness/2026-05-13-demo-release-checklist.md`

**Files to modify locally first:**

- Modify: `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- Modify: `D:/DATN-testing1/Version3/healthcheck.py`
- Create: `D:/DATN-testing1/docs/demo-readiness/operator-runbook.md`

**Remote files to modify only after approval:**

- `/home/nano/start_drowsiguard_full.sh`

**Implementation approach:**

- Fix launcher echo text so it says face verify is enabled when `DROWSIGUARD_DEMO_MODE=false`.
- Add a healthcheck section that prints:
  - demo mode;
  - face verify flag;
  - threshold;
  - number of references for demo RFID;
  - camera alive;
  - RFID reader opened;
  - WebSocket URL;
  - dashboard reachability.
- Keep audio warning non-blocking but visible.

**Automated tests:**

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_demo_readiness_script.py tests/test_healthcheck.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round5
```

If `tests/test_healthcheck.py` does not exist, create it with checks for strict mode and face verification fields.

**Manual Jetson test:**

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode hardware"
```

Expected:

```text
DROWSIGUARD_DEMO_MODE=false
face_verify=true
threshold=0.785 or approved calibrated value
dashboard_port PASS
```

**Pass criteria:**

- Launcher text no longer contradicts runtime behavior.
- One command tells the operator if demo is ready.
- Runbook includes start, stop, restart, test, and rollback.

**Fail criteria:**

- Healthcheck reports false PASS when demo mode is enabled.
- Launcher starts a different config than the runbook documents.

**Risks:**

- Editing remote launcher can interrupt the current demo process. Back up before editing.

**Rollback:**

```bash
cp /home/nano/start_drowsiguard_full.sh.bak-9of10 /home/nano/start_drowsiguard_full.sh
```

**Stop checkpoint:** Report operator readiness.

---

## Round 6: Optional Lightweight Embedding Verification Spike

**Goal:** Determine whether a stronger face-recognition method can run on Jetson Nano without breaking demo stability.

**Score impact:** 9.0 -> 9.15 only if it is faster than 300 ms per verify and has better positive/negative separation than fallback similarity.

**Files to read:**

- `D:/DATN-testing1/Version3/camera/face_verifier.py`
- `D:/DATN-testing1/Version3/config.py`
- `D:/DATN-testing1/Version3/requirements.txt`
- Jetson Python/OpenCV capability output

**Files to modify for spike only:**

- Create: `D:/DATN-testing1/Version3/scripts/probe_face_embedding_support.py`
- Create: `D:/DATN-testing1/docs/demo-readiness/face-embedding-spike.md`

**Implementation approach:**

- First run a read-only capability probe:

```powershell
ssh nano@192.168.2.29 "python3 - <<'PY'
import cv2
print('cv2', cv2.__version__)
print('has_face', hasattr(cv2, 'face'))
print('has_dnn', hasattr(cv2, 'dnn'))
print('has_FaceRecognizerSF', hasattr(cv2, 'FaceRecognizerSF_create'))
print('has_FaceDetectorYN', hasattr(cv2, 'FaceDetectorYN_create'))
PY"
```

- If OpenCV SFace APIs are unavailable, stop the round and keep current method.
- If APIs are available and model files are already present locally, test a candidate implementation behind `FACE_VERIFY_METHOD=sface`.
- Never remove the existing fallback similarity path.

**Automated tests:**

- [ ] Test that `FACE_VERIFY_METHOD=auto` still uses existing fallback when SFace is unavailable.
- [ ] Test that missing model files do not crash boot.
- [ ] Test that `FaceVerifier.verify()` still returns only `MATCH`, `MISMATCH`, `LOW_CONFIDENCE`, or `NO_ENROLLMENT`.

**Commands:**

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_face_registry_sync.py tests/test_verify_flow.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round6
```

**Manual Jetson test:**

- [ ] Benchmark one positive and one negative verify case.
- [ ] Compare score separation against Round 2 report.
- [ ] Confirm CPU/FPS remains acceptable.

**Pass criteria:**

- Embedding method improves separation and does not slow RFID verification noticeably.
- Fallback method remains available.

**Fail criteria:**

- Model files are missing.
- OpenCV APIs are unavailable.
- Verify time is too slow for demo.
- Positive cases become less stable.

**Risks:**

- Downloading models during demo preparation is risky.
- Jetson Nano may be too slow without TensorRT optimization.

**Rollback:**

- Keep `FACE_VERIFY_METHOD=auto` or `fallback`.
- Remove only spike files if the method is rejected.

**Stop checkpoint:** Decide whether embedding is worth implementing after demo.

---

## Round 7: Thesis Defense Evidence Pack

**Goal:** Convert the technical improvements into materials that help the committee see the system as complete and defensible.

**Score impact:** 9.0 -> 9.2 presentation value, without necessarily changing runtime.

**Files to read:**

- `D:/DATN-testing1/docs/diagrams/`
- `D:/DATN-testing1/docs/images/`
- `D:/DATN-testing1/docs/render_diagrams.ps1`
- `D:/DATN-testing1/docs/demo-readiness/*.md`
- `D:/DATN-testing1/Version3/docs/jetson_demo_checklist.md`

**Files to modify:**

- Create: `D:/DATN-testing1/docs/demo-readiness/committee-demo-script.md`
- Create: `D:/DATN-testing1/docs/demo-readiness/project-scorecard.md`
- Modify: relevant diagram source files only if they are outdated.

**Evidence pack must include:**

- System overview: Jetson, camera, RFID, WebQuanLi, SQLite, WebSocket.
- Identity workflow: RFID identifies driver, camera verifies live face, only verified sessions start AI.
- Drowsiness workflow: MediaPipe Face Mesh -> EAR/MAR/PERCLOS/pitch -> temporal classifier -> alert.
- Test evidence: identity-sim, simulate, hardware smoke, manual checklist.
- Known limitations: not industrial biometric security, lighting-sensitive, Jetson resource limits.
- Future work: stronger face embedding, liveness detection, better audio routing, larger dataset.

**Commands:**

```powershell
cd D:\DATN-testing1
powershell -ExecutionPolicy Bypass -File docs\render_diagrams.ps1
```

Expected:

```text
Existing diagrams render successfully or failures are listed with exact file names.
```

**Manual review:**

- [ ] Open rendered diagrams.
- [ ] Confirm labels are Vietnamese and report-ready.
- [ ] Confirm the demo script fits within the expected presentation time.

**Pass criteria:**

- The user can present the project without improvising core technical explanation.
- Every claim in the scorecard links to code, test, or manual evidence.

**Fail criteria:**

- Diagrams contradict current runtime behavior.
- Claims overstate the biometric strength of the face verifier.

**Risks:**

- Report materials can become too dense; keep them committee-friendly.

**Rollback:**

- Docs-only rollback by reverting changed files under `docs/`.

**Stop checkpoint:** Report final score estimate and remaining gaps.

---

## Final 9/10 Acceptance Criteria

The project can be claimed as approximately 9/10 only when all required checks below pass:

- [ ] Jetson runs with `DROWSIGUARD_DEMO_MODE=false`.
- [ ] `DROWSIGUARD_FEATURE_FACE_VERIFY=true`.
- [ ] No-face RFID scan does not start session.
- [ ] Correct-face RFID scan starts session.
- [ ] Stale cached face does not start session.
- [ ] Wrong-face or low-confidence case does not start session.
- [ ] Drowsiness alert can be demonstrated after verified session starts.
- [ ] WebQuanLi receives `session_start` and `verify_snapshot` on verified start, `verify_error` on no-face/no-enrollment/low-confidence failure, `face_mismatch` on wrong identity, `alert` during drowsiness warning, and `session_end` on checkout.
- [ ] One-command hardware readiness check passes or documents non-blocking warnings.
- [ ] Rollback commands are written and tested at least once in a non-destructive way.
- [ ] Demo checklist and committee demo script exist.
- [ ] Stable code snapshot is committed and optionally pushed after user approval.

---

## Expected Final Score After Rounds

| Completed rounds | Expected score | Meaning |
|---|---:|---|
| 0-1 | 8.4/10 | Stable enough to test and commit |
| 0-3 | 8.7/10 | Identity demo becomes clear and evidence-backed |
| 0-5 | 9.0/10 | Strong graduation demo readiness |
| 0-7 | 9.1-9.2/10 | Strong demo plus defense-ready evidence |

Round 6 is optional. It can raise technical credibility, but it should not be allowed to destabilize the working demo.
