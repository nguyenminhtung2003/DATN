# Demo Readiness Face Verification Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan is intentionally checkpointed: after every round, stop, report evidence, and wait for the user to approve the next round.

**Goal:** Raise live face verification and demo readiness toward 8.5/10 by stabilizing same-driver verification, separating misleading failure reasons, and adding a fixed demo smoke-test routine.

**Architecture:** Keep the solution practical for the thesis demo. Jetson remains the owner of local face verification, `DriverRegistry` remains the owner of local `RFID -> face reference files`, and WebQuanLi continues to provide the active-driver registry. The first version uses 3-5 local references per RFID and best-score matching, not a new deep-learning face-recognition model.

**Tech Stack:** Python 3, existing OpenCV/fallback similarity path, existing `Version3` registry and verify flow, pytest, Jetson SSH/manual runtime checks.

---

## Non-Negotiable Execution Rule

Do **not** execute this plan in one pass.

Each round must end with:

1. Files changed.
2. Commands run.
3. Automated test result.
4. Jetson/manual test result if that round includes Jetson work.
5. Pass/fail decision.
6. Known risk left.
7. Rollback note.
8. Explicit question: "Tiếp tục vòng tiếp theo không?"

Do not start the next round until the user confirms.

---

## Current Code Facts Read Before Planning

- `Version3/storage/driver_registry.py`
  - Current local cache stores one primary face file per RFID at `storage/driver_faces/<rfid>/reference.jpg`.
  - `DriverRegistry.reference_path(rfid_uid)` returns only `reference.jpg`.
  - `DriverRegistry.has_enrollment(rfid_uid)` only checks `reference.jpg`.
  - `sync_from_manifest()` downloads one `face_image_url` per driver and writes it to `reference.jpg`.

- `Version3/camera/face_verifier.py`
  - `FaceVerifier.verify(face_frame, rfid_uid)` currently loads only `registry.reference_path(rfid_uid)`.
  - It compares the live face crop against that single reference.
  - Fallback score rules:
    - `score >= FACE_VERIFY_THRESHOLD` => `MATCH`
    - `score <= FACE_VERIFY_THRESHOLD - 0.18` => `MISMATCH`
    - otherwise => `LOW_CONFIDENCE`
  - Current local default threshold is `FACE_VERIFY_THRESHOLD = 0.785`.

- `Version3/main.py`
  - RFID flow is `IDLE -> VERIFYING_DRIVER -> _verify_driver(uid)`.
  - No face crop returns `NO_FACE_FRAME`.
  - Verifier result `LOW_CONFIDENCE` is preserved as a verify error reason.
  - `_prompt_for_verify_failure()` maps both `NO_FACE_FRAME` and `LOW_CONFIDENCE` to `no_face`, which is misleading for the demo.

- `Version3/tests/test_face_registry_sync.py`
  - Existing tests cover single-reference enrollment, single-reference match, mismatch/low-confidence behavior, and WebQuanLi manifest sync.

- `Version3/tests/test_verify_flow.py`
  - Existing tests cover verify success, mismatch, no face, no enrollment, prompts, and strict demo-mode behavior.
  - Existing low-confidence test currently expects a no-face-style failure when no face frame is available; it does not protect the case "face exists but score is low".

- `Version3/scripts/test_demo_readiness.py`
  - Existing script has `--mode simulate` and `--mode hardware`.
  - It checks basic session/alert flow and hardware visibility.
  - It does not yet run a fixed identity-verification checklist: correct face pass, wrong face reject, no face reject.

- `WebQuanLi/templates/dashboard.html`
  - Dashboard receives `verify_error` and `verify_snapshot` events.
  - It displays raw verify error reasons in the alert log.
  - It maps only `VERIFIED`, `DEMO_VERIFIED`, and `MISMATCH` to friendly labels.

---

## Scope

### In Scope

- Add local multi-reference support on Jetson using `reference.jpg` plus sorted `ref_*.jpg`.
- Compare live face crop against all valid references and accept the best score.
- Separate `LOW_CONFIDENCE` from `NO_FACE_FRAME` in runtime prompt/status/message behavior.
- Add automated tests for multi-reference matching and failure reason separation.
- Add a fixed demo-readiness smoke checklist for host simulation and Jetson manual execution.
- Define Jetson manual verification commands and pass/fail evidence.

### Out Of Scope

- FaceNet, ArcFace, SFace, TensorRT, or any new heavy face-recognition model.
- WebQuanLi database migration for multiple face images per driver.
- WebQuanLi UI for uploading multiple face images in this pass.
- Changing drowsiness classifier thresholds, calibration, GPS, RFID reader, or alert policy.
- Blind Jetson deployment before local tests pass and the user approves the deployment round.

---

## Round 0: Baseline And Safety Snapshot

**Goal:** Capture the current local and Jetson/demo state before changing anything, so every later round has a known rollback point.

**Files to read:**

- `D:/DATN-testing1/Version3/config.py`
- `D:/DATN-testing1/Version3/camera/face_verifier.py`
- `D:/DATN-testing1/Version3/storage/driver_registry.py`
- `D:/DATN-testing1/Version3/main.py`
- `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- `D:/DATN-testing1/WebQuanLi/app/api/vehicles.py`
- `D:/DATN-testing1/WebQuanLi/templates/dashboard.html`
- `D:/DATN-testing1/docs/session-summary-2026-05-12.md`

**Files to modify:** none.

**Implementation steps:**

- [ ] Run local git snapshot:

```powershell
git status --short
git branch --show-current
git log --oneline -5
```

- [ ] Run focused local tests:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_face_registry_sync.py tests/test_verify_flow.py tests/test_main_plan_completion.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round0-version3
```

Run from:

```text
D:\DATN-testing1\Version3
```

- [ ] Run WebQuanLi contract tests that protect registry/dashboard behavior:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_driver_registry_sync.py tests/test_dashboard_realtime_context.py tests/test_api_validation_contract.py tests/test_ws_session_flow.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round0-webquanli
```

Run from:

```text
D:\DATN-testing1\WebQuanLi
```

**Manual Jetson test:**

- [ ] Only if SSH is reachable, run read-only checks:

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 nano@192.168.2.29 "hostname; pgrep -af 'python3 .*main.py' || true; cd /home/nano/Version3 && grep -E 'DROWSIGUARD_DEMO_MODE|FACE_VERIFY_THRESHOLD|WEBSOCKET|CAMERA_WIDTH|CAMERA_HEIGHT' drowsiguard.env /home/nano/start_drowsiguard_full.sh 2>/dev/null || true"
```

- [ ] Tail identity logs if runtime exists:

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 nano@192.168.2.29 "cd /home/nano/Version3 && tail -120 logs/drowsiguard.log | grep -E 'RFID|VERIFY|NO_FACE|NO_ENROLLMENT|LOW_CONFIDENCE|MISMATCH|VERIFIED|Fallback score' || true"
```

**Pass criteria:**

- Local focused tests either pass or failures are documented as existing baseline failures.
- No runtime files are modified.
- Current threshold/demo-mode/launcher state is recorded.

**Fail criteria:**

- Tests cannot run because dependencies or import paths are broken.
- Git state is unclear enough that implementation would risk overwriting unrelated user work.
- Jetson is unreachable and the user expects live deployment in the next round.

**Risks:**

- Jetson IP may have changed.
- Worktree is dirty; unrelated changes must not be reverted.

**Rollback:**

- No rollback needed because this round is read-only.

**Stop checkpoint:**

Stop and report baseline evidence. Wait for user approval before Round 1.

---

## Round 1: Local Multi-Reference Registry Support

**Goal:** Teach the Jetson local registry to know about `reference.jpg` plus optional `ref_*.jpg` files without changing verifier decision logic yet.

**Files to read:**

- `D:/DATN-testing1/Version3/storage/driver_registry.py`
- `D:/DATN-testing1/Version3/tests/test_face_registry_sync.py`

**Files to modify:**

- `D:/DATN-testing1/Version3/storage/driver_registry.py`
- `D:/DATN-testing1/Version3/tests/test_face_registry_sync.py`

**Implementation approach:**

- Preserve existing `reference_path(rfid_uid)` and `has_enrollment(rfid_uid)` behavior.
- Add `reference_paths(rfid_uid)`:
  - returns `reference.jpg` first if it exists;
  - then returns sorted `ref_*.jpg` paths that exist;
  - ignores non-files and unrelated names.
- Add `reference_slot_path(rfid_uid, slot)`:
  - validates slot is from `1` to `5`;
  - returns `ref_01.jpg` to `ref_05.jpg`.
- Add `copy_extra_reference_file(rfid_uid, source_path, slot)`:
  - creates the RFID directory;
  - copies the source into the selected `ref_NN.jpg`;
  - does not edit WebQuanLi DB;
  - does not replace `reference.jpg`.
- Update `_remove_stale_entries()` behavior only if needed so active RFID directories keep both `reference.jpg` and `ref_*.jpg`.

**Automated tests:**

- [ ] Add a failing test:

```text
FaceRegistrySyncTest.test_reference_paths_include_primary_and_sorted_extra_references
```

Expected assertion:

```text
reference_paths("UID-001") returns:
1. .../UID-001/reference.jpg
2. .../UID-001/ref_01.jpg
3. .../UID-001/ref_02.jpg
```

- [ ] Add a failing test:

```text
FaceRegistrySyncTest.test_copy_extra_reference_file_writes_numbered_slot_without_replacing_primary
```

Expected assertion:

```text
reference.jpg still exists and ref_02.jpg contains the copied extra reference.
```

- [ ] Run focused tests:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_face_registry_sync.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round1
```

Run from:

```text
D:\DATN-testing1\Version3
```

**Manual Jetson test:** none in this round. This round is local-only.

**Pass criteria:**

- Existing single-reference tests still pass.
- New registry tests pass.
- No verifier behavior has changed yet.

**Fail criteria:**

- `reference.jpg` backward compatibility breaks.
- Manifest sync no longer creates `reference.jpg`.

**Risks:**

- Accidentally deleting extra `ref_*.jpg` during WebQuanLi sync would make Jetson demo unstable.
- Slot validation that is too strict could block emergency manual references.

**Rollback:**

- Revert only:
  - `Version3/storage/driver_registry.py`
  - `Version3/tests/test_face_registry_sync.py`
- Existing `reference.jpg` behavior remains the rollback baseline.

**Stop checkpoint:**

Stop and report registry diff and test output. Wait for user approval before Round 2.

---

## Round 2: Best-Score Multi-Reference Face Verification

**Goal:** Make `FaceVerifier` compare the live face crop against all local references for that RFID and decide from the best score.

**Files to read:**

- `D:/DATN-testing1/Version3/camera/face_verifier.py`
- `D:/DATN-testing1/Version3/storage/driver_registry.py`
- `D:/DATN-testing1/Version3/tests/test_face_registry_sync.py`

**Files to modify:**

- `D:/DATN-testing1/Version3/camera/face_verifier.py`
- `D:/DATN-testing1/Version3/tests/test_face_registry_sync.py`

**Implementation approach:**

- Keep `VerifyResult` names unchanged.
- In `FaceVerifier.verify(face_frame, rfid_uid)`:
  - call `registry.reference_paths(rfid_uid)`;
  - load and normalize each readable image;
  - skip unreadable or empty references;
  - compare the probe against each valid reference;
  - choose the highest score;
  - log RFID, number of valid references, best reference filename, best score, and threshold;
  - return `MATCH`, `MISMATCH`, or `LOW_CONFIDENCE` using the same threshold bands as before.
- If `reference_paths()` returns no existing files, return `NO_ENROLLMENT`.
- If paths exist but none can be decoded, return `NO_ENROLLMENT`.
- Do not lower `FACE_VERIFY_THRESHOLD` in this round.
- Do not add WebQuanLi schema or upload UI.

**Automated tests:**

- [ ] Add a failing test:

```text
FaceRegistrySyncTest.test_verify_uses_best_extra_reference_when_primary_scores_too_low
```

Test shape:

```text
reference.jpg is intentionally less similar to the probe.
ref_01.jpg is similar enough to pass.
verify(probe, "UID-001") returns MATCH.
```

- [ ] Add a failing test:

```text
FaceRegistrySyncTest.test_verify_returns_no_enrollment_when_all_reference_files_are_unreadable
```

Expected:

```text
VerifyResult.BLOCKED
```

- [ ] Run focused tests:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_face_registry_sync.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round2
```

- [ ] Run verify-flow tests to catch integration regressions:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_verify_flow.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round2-verify
```

Run both from:

```text
D:\DATN-testing1\Version3
```

**Manual Jetson test:** none in this round unless the user explicitly approves deployment after local pass.

**Pass criteria:**

- Same-reference match still passes.
- Clearly different face still rejects or stays low confidence.
- Probe can match via `ref_*.jpg` even when `reference.jpg` alone would be too weak.
- Logs include enough score detail to debug live demo.

**Fail criteria:**

- Any single-reference behavior regresses.
- Unreadable extra references crash verification.
- Score logging is missing or too vague for live debugging.

**Risks:**

- More references can increase false accept risk if references are poor quality.
- Best-score matching can hide bad primary reference quality; that is acceptable for demo but must be explained honestly.

**Rollback:**

- Revert only:
  - `Version3/camera/face_verifier.py`
  - `Version3/tests/test_face_registry_sync.py`
- Keep Round 1 registry helpers only if they are already accepted and tests pass.

**Stop checkpoint:**

Stop and report best-score tests and any score samples. Wait for user approval before Round 3.

---

## Round 3: Separate LOW_CONFIDENCE From NO_FACE

**Goal:** Stop telling the user "không phát hiện khuôn mặt" when the real result is "có mặt nhưng điểm xác thực chưa đủ tin cậy".

**Files to read:**

- `D:/DATN-testing1/Version3/main.py`
- `D:/DATN-testing1/Version3/config.py`
- `D:/DATN-testing1/Version3/tests/test_verify_flow.py`
- `D:/DATN-testing1/WebQuanLi/templates/dashboard.html`
- `D:/DATN-testing1/WebQuanLi/tests/test_dashboard_realtime_context.py`

**Files to modify:**

- `D:/DATN-testing1/Version3/main.py`
- `D:/DATN-testing1/Version3/tests/test_verify_flow.py`
- Optional, only if needed for dashboard clarity:
  - `D:/DATN-testing1/WebQuanLi/templates/dashboard.html`
  - `D:/DATN-testing1/WebQuanLi/tests/test_dashboard_realtime_context.py`

**Implementation approach:**

- Keep `NO_FACE_FRAME` meaning:
  - camera/frame acquisition did not produce a usable face crop.
  - prompt remains `no_face`.
- Keep `LOW_CONFIDENCE` meaning:
  - face crop exists;
  - verification ran;
  - score was not high enough for `MATCH` and not low enough for `MISMATCH`.
- Change `_prompt_for_verify_failure(reason)`:
  - `NO_FACE_FRAME` => `no_face`
  - `LOW_CONFIDENCE` => `failed_identity`
  - `UNKNOWN_ERROR` => no prompt or `failed_identity`, choose one and document it in the implementation report.
- Ensure `_reject_verification(uid, "LOW_CONFIDENCE", ...)` still sends `verify_error` with reason `LOW_CONFIDENCE`.
- Optional dashboard label improvement:
  - render `LOW_CONFIDENCE` as `Độ tin cậy khuôn mặt thấp`;
  - render `NO_FACE_FRAME` as `Không phát hiện khuôn mặt`;
  - do not change backend contract names.

**Automated tests:**

- [ ] Add or update test:

```text
VerifyFlowTest.test_low_confidence_with_face_plays_failed_identity_prompt_and_reports_low_confidence
```

Test shape:

```text
frame_buffer.get_good_face_frame returns a non-empty frame.
verifier.extract_face returns that frame.
verifier.verify returns VerifyResult.LOW_CONFIDENCE.
Expected:
  - app state returns IDLE.
  - verify_error reason is LOW_CONFIDENCE.
  - speaker.play_prompt called with "failed_identity".
  - face_mismatch is not queued.
```

- [ ] Keep no-face test:

```text
VerifyFlowTest.test_no_face_plays_no_face_prompt
```

Expected:

```text
verify_error reason is NO_FACE_FRAME and prompt is no_face.
```

- [ ] If dashboard labels are changed, add/update a dashboard test asserting:

```text
LOW_CONFIDENCE label text is present in dashboard JavaScript mapping.
NO_FACE_FRAME label text is distinct from LOW_CONFIDENCE.
```

- [ ] Run Version3 verify-flow tests:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_verify_flow.py tests/test_main_plan_completion.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round3-version3
```

Run from:

```text
D:\DATN-testing1\Version3
```

- [ ] If dashboard changed, run WebQuanLi dashboard tests:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_dashboard_realtime_context.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round3-webquanli
```

Run from:

```text
D:\DATN-testing1\WebQuanLi
```

**Manual Jetson test:**

- [ ] After deployment approval only, trigger a low-confidence scenario:
  - scan the correct RFID;
  - use a face angle/lighting that produces low similarity but still visible face;
  - verify log contains `LOW_CONFIDENCE`;
  - verify audio/UI does not say "không phát hiện khuôn mặt".

**Pass criteria:**

- `NO_FACE_FRAME` and `LOW_CONFIDENCE` are visibly distinct in tests.
- No successful session starts on `LOW_CONFIDENCE` while strict demo mode is enabled.
- No `face_mismatch` event is emitted for `LOW_CONFIDENCE`.

**Fail criteria:**

- `LOW_CONFIDENCE` still plays `no_face`.
- `NO_FACE_FRAME` behavior changes unexpectedly.
- Dashboard or audio claims the wrong reason.

**Risks:**

- Using `failed_identity` for `LOW_CONFIDENCE` may sound too harsh; if the user wants softer audio, add a later prompt file such as `verify_low_confidence.wav`.
- WebQuanLi label change could be blocked by existing mojibake/encoding in `dashboard.html`; keep changes minimal.

**Rollback:**

- Revert only:
  - `Version3/main.py`
  - `Version3/tests/test_verify_flow.py`
  - optional dashboard files if changed

**Stop checkpoint:**

Stop and report reason/prompt tests. Wait for user approval before Round 4.

---

## Round 4: Fixed Demo Readiness Test Suite

**Goal:** Add a repeatable checklist that proves the exact demo flows before facing the committee.

**Files to read:**

- `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- `D:/DATN-testing1/Version3/tests/test_verify_flow.py`
- `D:/DATN-testing1/Version3/tests/test_reverify_flow.py`
- `D:/DATN-testing1/Version3/tests/test_webquanli_contract.py`
- `D:/DATN-testing1/WebQuanLi/tests/test_ws_session_flow.py`

**Files to modify:**

- `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- Optional:
  - `D:/DATN-testing1/Version3/tests/test_demo_readiness_script.py`
  - `D:/DATN-testing1/docs/demo-readiness-checklist.md`

**Implementation approach:**

- Extend `scripts/test_demo_readiness.py` with a new mode:

```text
python3 scripts/test_demo_readiness.py --mode identity-sim
```

- `identity-sim` should use mocks and no hardware to prove:
  1. Correct RFID + correct face => `verify_snapshot: VERIFIED`, `session_start`.
  2. Correct RFID + wrong face => `face_mismatch`, no `session_start`.
  3. Correct RFID + no face => `verify_error: NO_FACE_FRAME`, no `session_start`.
  4. Correct RFID + low-confidence visible face => `verify_error: LOW_CONFIDENCE`, no `session_start`.
  5. Running session + RFID scan again => `session_end`.
- Keep existing `--mode simulate` and `--mode hardware`.
- Add clear exit code behavior:
  - `0` only if all checks pass;
  - `1` if any required demo event is missing.
- Print a short checklist summary that the user can screenshot or paste into report notes.
- Optionally add `docs/demo-readiness-checklist.md` with the manual sequence and expected UI/log evidence.

**Automated tests:**

- [ ] Add script-level tests if practical:

```text
Version3/tests/test_demo_readiness_script.py
```

Expected:

```text
identity-sim returns 0 and prints all required scenario labels.
```

- [ ] Run script directly:

```powershell
python scripts/test_demo_readiness.py --mode identity-sim
```

Run from:

```text
D:\DATN-testing1\Version3
```

- [ ] Run focused Version3 tests:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_verify_flow.py tests/test_reverify_flow.py tests/test_webquanli_contract.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round4-version3
```

- [ ] Run WebQuanLi session contract test:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_ws_session_flow.py tests/test_dashboard_realtime_context.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-round4-webquanli
```

Run from:

```text
D:\DATN-testing1\WebQuanLi
```

**Manual Jetson test:**

- [ ] After deployment approval only, run:

```bash
cd /home/nano/Version3
python3 scripts/test_demo_readiness.py --mode hardware
```

- [ ] Then run the human demo checklist:
  1. Start WebQuanLi.
  2. Start Jetson runtime.
  3. Confirm dashboard shows Jetson online.
  4. Sync driver registry.
  5. Correct RFID + correct face: session starts.
  6. End session by scanning RFID again.
  7. Correct RFID + wrong face: mismatch/reject.
  8. Correct RFID + no face: no-face reject.
  9. Correct RFID + intentionally poor angle: low-confidence reject, not no-face.
  10. Trigger drowsiness posture/closed eyes: dashboard alert appears.

**Pass criteria:**

- Host `identity-sim` passes.
- Jetson `hardware` mode passes if hardware is available.
- Manual checklist can be repeated twice without changing code or threshold.
- Log evidence includes `VERIFIED`, `MISMATCH`, `NO_FACE_FRAME`, and `LOW_CONFIDENCE` in the expected cases.

**Fail criteria:**

- Any identity scenario starts a session when it should reject.
- Any expected session start does not occur.
- Manual checklist requires changing threshold between attempts.

**Risks:**

- Host simulation can pass while camera lighting on Jetson still causes low score.
- Manual wrong-face testing requires a second person or a known wrong face in front of camera.

**Rollback:**

- Revert only:
  - `Version3/scripts/test_demo_readiness.py`
  - optional new test/doc files
- Runtime behavior from Rounds 1-3 remains unchanged unless explicitly reverted.

**Stop checkpoint:**

Stop and report script output, test results, and whether the manual checklist is ready for Jetson. Wait for user approval before Round 5.

---

## Round 5: Jetson Deployment, Evidence, And Demo Freeze

**Goal:** Deploy only the approved demo-readiness changes to Jetson, prove the exact live demo flows, then freeze the demo state.

**Files to read locally before copy:**

- `D:/DATN-testing1/Version3/storage/driver_registry.py`
- `D:/DATN-testing1/Version3/camera/face_verifier.py`
- `D:/DATN-testing1/Version3/main.py`
- `D:/DATN-testing1/Version3/scripts/test_demo_readiness.py`
- any optional helper/doc files accepted in earlier rounds

**Files to modify locally:** none unless previous rounds are incomplete.

**Remote Jetson files to copy only after approval:**

- `/home/nano/Version3/storage/driver_registry.py`
- `/home/nano/Version3/camera/face_verifier.py`
- `/home/nano/Version3/main.py`
- `/home/nano/Version3/scripts/test_demo_readiness.py`
- optional helper script if created

**Implementation approach:**

- Confirm SSH target first. Prefer `nano@192.168.2.29` if reachable; fall back only after the user confirms the current IP.
- Backup each remote file before overwrite:

```bash
cp /home/nano/Version3/main.py /home/nano/Version3/main.py.bak-demo-readiness-20260512
cp /home/nano/Version3/camera/face_verifier.py /home/nano/Version3/camera/face_verifier.py.bak-demo-readiness-20260512
cp /home/nano/Version3/storage/driver_registry.py /home/nano/Version3/storage/driver_registry.py.bak-demo-readiness-20260512
cp /home/nano/Version3/scripts/test_demo_readiness.py /home/nano/Version3/scripts/test_demo_readiness.py.bak-demo-readiness-20260512
```

- Copy approved files via `scp`.
- Compile on Jetson:

```bash
cd /home/nano/Version3
python3 -m py_compile storage/driver_registry.py camera/face_verifier.py main.py scripts/test_demo_readiness.py
```

- Add 3-5 good local references for each demo RFID:

```text
/home/nano/Version3/storage/driver_faces/<RFID>/reference.jpg
/home/nano/Version3/storage/driver_faces/<RFID>/ref_01.jpg
/home/nano/Version3/storage/driver_faces/<RFID>/ref_02.jpg
/home/nano/Version3/storage/driver_faces/<RFID>/ref_03.jpg
```

- Use reference images captured by the Jetson camera under demo lighting.
- Restart the same runtime path used in the actual demo.

**Automated tests on Jetson:**

- [ ] Compile:

```bash
cd /home/nano/Version3
python3 -m py_compile storage/driver_registry.py camera/face_verifier.py main.py scripts/test_demo_readiness.py
```

- [ ] Hardware readiness:

```bash
cd /home/nano/Version3
python3 scripts/test_demo_readiness.py --mode hardware
```

- [ ] Optional focused pytest if available on Jetson:

```bash
cd /home/nano/Version3
python3 -m pytest tests/test_face_registry_sync.py tests/test_verify_flow.py -q
```

**Manual Jetson test:**

- [ ] Correct RFID + correct face:
  - Expected log: `best_score >= threshold`, `VERIFIED`, `session_start`.
  - Expected UI: driver verified and session running.

- [ ] Correct RFID + wrong face:
  - Expected log: `MISMATCH` or `LOW_CONFIDENCE`, no `session_start`.
  - Expected UI: reject/mismatch visible.

- [ ] Correct RFID + no face:
  - Expected log: `NO_FACE_FRAME`.
  - Expected UI/audio: no-face only.

- [ ] Correct RFID + visible but poor confidence:
  - Expected log: `LOW_CONFIDENCE`.
  - Expected UI/audio: low confidence or failed identity, not no-face.

- [ ] Session end:
  - Start a verified session, scan RFID again.
  - Expected log/event: `session_end`.

- [ ] Drowsiness alert:
  - During verified session, simulate eyes closed/head down/yawn as appropriate.
  - Expected dashboard alert appears and speaker/buzzer behavior is acceptable.

**Pass criteria:**

- All approved files compile on Jetson.
- Runtime restarts.
- Correct driver passes twice in a row without changing threshold.
- Wrong/no-face/low-confidence cases reject without starting AI session.
- Dashboard receives session and verify events.
- The final threshold and reference count are recorded.

**Fail criteria:**

- Jetson cannot start runtime after copy.
- Correct driver cannot pass after 3-5 references.
- Wrong face starts session.
- Demo requires lowering threshold below the agreed safe value without cross-test.

**Risks:**

- Camera lighting or face angle still produces scores below threshold.
- Extra references captured under poor lighting can increase false accepts or make results inconsistent.
- Jetson Python/OpenCV behavior can differ from Windows host tests.

**Rollback:**

- Stop runtime.
- Restore backups:

```bash
cp /home/nano/Version3/main.py.bak-demo-readiness-20260512 /home/nano/Version3/main.py
cp /home/nano/Version3/camera/face_verifier.py.bak-demo-readiness-20260512 /home/nano/Version3/camera/face_verifier.py
cp /home/nano/Version3/storage/driver_registry.py.bak-demo-readiness-20260512 /home/nano/Version3/storage/driver_registry.py
cp /home/nano/Version3/scripts/test_demo_readiness.py.bak-demo-readiness-20260512 /home/nano/Version3/scripts/test_demo_readiness.py
```

- Restart the previous launcher.
- Keep reference images unchanged unless they are proven bad.

**Stop checkpoint:**

Stop and report final Jetson evidence. Ask the user whether to freeze the demo state or continue polishing.

---

## Final Demo Freeze Checklist

Only use this after Rounds 1-5 pass.

- [ ] Record current branch and git status.
- [ ] Record final `FACE_VERIFY_THRESHOLD`.
- [ ] Record the active Jetson IP.
- [ ] Record WebQuanLi URL.
- [ ] Record demo RFID values and driver names.
- [ ] Record reference image count per demo RFID.
- [ ] Save last successful log excerpt containing `VERIFIED`, `MISMATCH`, `NO_FACE_FRAME`, `LOW_CONFIDENCE`, and `session_end`.
- [ ] Do not change threshold, camera resolution, registry files, or launcher before the defense unless a new full checklist run passes.

---

## Suggested Execution Order

1. Round 0: baseline and safety snapshot.
2. Round 1: registry support for extra references.
3. Round 2: verifier best-score matching.
4. Round 3: distinct low-confidence failure behavior.
5. Round 4: repeatable demo-readiness tests.
6. Round 5: Jetson deployment and live proof.

This order avoids a risky all-in-one deployment. It also allows the user to stop after any round if the demo is already stable enough.
