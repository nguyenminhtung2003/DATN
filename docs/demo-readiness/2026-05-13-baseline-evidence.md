# Round 0 Baseline Evidence - Project 9/10 Roadmap

Time: 2026-05-13 21:18:16 +07:00

Plan: `docs/superpowers/plans/2026-05-13-project-9-10-roadmap.md`

Scope: freeze and prove the current baseline before any new roadmap changes. This round does not change runtime behavior and does not deploy to Jetson.

## Git State

Current branch:

```text
codex/global-rfid-face-registry
```

Latest commits:

```text
2685198 feat: stabilize demo face verification
31aa739 chore: update demo-ready project snapshot
7ff26ef fix: disable webquanli ota controls
1847f1e fix: make webquanli startup seeding idempotent
16bcf6d Merge branch 'codex/webquanli-history-timezone-retention'
```

Untracked files/directories present before Round 0 edits:

```text
?? .deploy/
?? .pytest_deps/
?? .test_tmp/
?? .tmp/
?? Research-Paper-Writing-Skills/
```

Round 0 intentionally did not revert, delete, stage, or commit these files.

## Local Version3 Focused Tests

Command:

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_verify_flow.py tests/test_reverify_flow.py tests/test_demo_readiness_script.py tests/test_face_registry_sync.py tests/test_face_crop_compat.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round0-version3
```

Result:

```text
27 passed in 3.60s
```

Decision: PASS.

## Demo Readiness Simulation

Identity simulation command:

```powershell
cd D:\DATN-testing1\Version3
python scripts\test_demo_readiness.py --mode identity-sim
```

Important result lines:

```text
[IDENTITY] correct-face-pass: PASS
[IDENTITY] wrong-face-reject: PASS
[IDENTITY] no-face-reject: PASS
[IDENTITY] low-confidence-reject: PASS
[IDENTITY] rfid-session-end: PASS
[IDENTITY] PASS: fixed demo identity checks are ready.
```

Simulation command:

```powershell
cd D:\DATN-testing1\Version3
python scripts\test_demo_readiness.py --mode simulate
```

Important result lines:

```text
[SIM] PASS: reconnect/session/alert flow is ready for demo simulation.
```

Decision: PASS.

## Jetson Read-Only Hardware Check

Command:

```powershell
ssh nano@192.168.2.29 "pgrep -af 'python3 main.py' || true; cd /home/nano/Version3 && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode hardware"
```

Hardware readiness result:

```text
PASS device_id            JETSON-001
PASS websocket_url        ws://192.168.2.24:8000/ws/jetson/JETSON-001
PASS strict_mode          DROWSIGUARD_DEMO_MODE=false
PASS queue_db             /home/nano/Version3/storage/local_events.db
PASS face_registry        /home/nano/Version3/storage/driver_registry.json
PASS camera_dependency    cv2 available
PASS mediapipe_dependency mediapipe available
PASS websocket_dependency vendored websocket client available
PASS rfid_dependency      evdev available
PASS runtime_dir          /home/nano/Version3/storage/runtime
PASS bluetooth_adapter    detected
PASS audio_files          all alert audio files exist
PASS audio_backend        paplay/aplay auto-detect ready
PASS dashboard_port       8080 serving dashboard
[HW] PASS: no blocking failures in quick hardware readiness.
```

GPS note:

```text
GPS feature is disabled; enable DROWSIGUARD_FEATURE_GPS=true after wiring NEO-6M.
```

Additional process verification:

```powershell
ssh nano@192.168.2.29 "pgrep -af '[p]ython3 main.py' || true"
```

Result:

```text
<no output>
```

Broader process check:

```text
24664  5283 Sl+  lxterminal -e /home/nano/start_drowsiguard_full.sh
24667 24664 Ss+  /bin/bash /home/nano/start_drowsiguard_full.sh
```

Interpretation: Jetson hardware readiness is PASS, strict mode is confirmed, and dashboard port 8080 is serving. However, `python3 main.py` was not detected as an active runtime process during this check. Only the launcher shell was visible. This should be treated as a Round 0 finding before live manual testing.

Decision: PARTIAL PASS. Hardware smoke passes, but current runtime process presence is not confirmed.

## Manual Jetson Identity Tests

Not executed by Codex in this round because they require physical camera/RFID interaction.

Required manual checks before claiming full Round 0 pass:

- No face in camera + scan RFID: must reject with `NO_FACE_FRAME`.
- Correct face in camera + scan RFID: must verify and enter `RUNNING`.
- Show face, leave frame, then scan RFID: must reject with `NO_FACE_FRAME`.

Decision: PENDING USER TEST.

## Round 0 Decision

Automated/local baseline: PASS.

Jetson hardware smoke: PASS.

Jetson runtime process: NEEDS ATTENTION, because `python3 main.py` was not detected.

Manual Jetson identity cases: PENDING.

Round 0 score estimate:

- If the user starts/confirms runtime and the three manual identity tests pass: 8.3/10 baseline target is met.
- Until runtime process and manual identity checks are confirmed: keep baseline at 8.2/10.

## Risks Left

- The launcher shell may be open while the Python runtime is not running.
- Generated folders remain untracked and should be handled in Round 1.
- GPS is disabled, which is acceptable only if GPS is not part of the live demo.
- Audio backend is ready, but live speaker output was not manually verified in this round.

## Rollback

Round 0 only created this evidence document. No runtime rollback is needed.

If this evidence is inaccurate, edit or remove only:

```text
docs/demo-readiness/2026-05-13-baseline-evidence.md
```
