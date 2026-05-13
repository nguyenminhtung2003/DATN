# Demo Release Checklist - Project 9/10 Roadmap Round 1

Date: 2026-05-13

Purpose: provide a repeatable checklist for testing the current DrowsiGuard demo snapshot before commit, push, or live presentation.

## Known Demo Context

- Project root: `D:\DATN-testing1`
- Jetson SSH target used in Round 0/1: `nano@192.168.2.29`
- Jetson runtime path: `/home/nano/Version3`
- Jetson launcher: `/home/nano/start_drowsiguard_full.sh`
- WebQuanLi backend URL used on the LAN during earlier checks: `http://192.168.2.24:8000`
- Jetson WebSocket URL observed in the latest Round 5/7 readiness check: `ws://100.91.225.22:8000/ws/jetson/JETSON-001`
- Jetson local dashboard/health port observed: `http://192.168.2.29:8080`

## Required Runtime Flags

Expected strict identity-gated demo state:

```text
DROWSIGUARD_DEMO_MODE=false
DROWSIGUARD_FEATURE_FACE_VERIFY=true
DROWSIGUARD_FACE_VERIFY_THRESHOLD=0.785
```

Local source default:

```text
FACE_VERIFY_THRESHOLD = 0.785
DEMO_MODE_ALLOW_UNVERIFIED = False
FEATURE_FACE_VERIFY = True
```

## Start Commands

Start WebQuanLi on Windows:

```powershell
cd D:\DATN-testing1
.\start_webquanli.bat
```

Open WebQuanLi from another device on the same network by using the LAN IP, not `127.0.0.1`:

```text
http://192.168.2.24:8000
```

Start Jetson runtime manually over SSH if the desktop launcher is not already running:

```powershell
ssh nano@192.168.2.29 "bash /home/nano/start_drowsiguard_full.sh"
```

If using NoMachine/desktop, launch:

```text
DrowsiGuard-Full.desktop
```

## Stop Commands

Stop Jetson runtime process:

```powershell
ssh nano@192.168.2.29 "pkill -f 'python3 main.py' || true"
```

Check whether Python runtime is active:

```powershell
ssh nano@192.168.2.29 "pgrep -af '[p]ython3 main.py' || true"
```

Stop WebQuanLi by closing the terminal that runs `start_webquanli.bat`, or by stopping the Python/uvicorn process from that terminal.

## Pre-Demo Health Checks

Run local focused identity/demo tests:

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_verify_flow.py tests/test_demo_readiness_script.py tests/test_face_registry_sync.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-demo-release
```

Run local simulation checks:

```powershell
cd D:\DATN-testing1\Version3
python scripts\test_demo_readiness.py --mode identity-sim
python scripts\test_demo_readiness.py --mode simulate
```

Run Jetson hardware readiness:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode hardware"
```

Inspect launcher flags:

```powershell
ssh nano@192.168.2.29 "grep -E 'DROWSIGUARD_DEMO_MODE|DROWSIGUARD_FACE_VERIFY_THRESHOLD|DROWSIGUARD_FEATURE_FACE_VERIFY|Starting python3 main.py|Mode' /home/nano/start_drowsiguard_full.sh"
```

## Identity Verification Manual Tests

Run these with WebQuanLi open, Jetson runtime active, monitor enabled, and RFID reader connected.

1. No face in camera + scan RFID.
   - Expected: session must not start.
   - Expected reason: `NO_FACE_FRAME`.

2. Correct registered driver face + scan RFID.
   - Expected: face verify succeeds.
   - Expected state: `RUNNING`.
   - Expected WebQuanLi event: `session_start` and `verify_snapshot`.

3. Show face, leave camera frame, then scan RFID.
   - Expected: session must not start.
   - Expected reason: `NO_FACE_FRAME`.

4. Wrong face or intentionally bad angle.
   - Expected: session must not start.
   - Expected reason: `MISMATCH` or `LOW_CONFIDENCE`.

## Drowsiness Alert Manual Tests

Run only after identity verification succeeds and the session is in `RUNNING`.

1. Normal face, eyes open.
   - Expected: no immediate alert spam.
   - Expected AI state: normal/awake or collecting enough samples.

2. Close eyes long enough for warning.
   - Expected: warning level increases.
   - Expected event: `alert` with `ear`, `perclos`, `ai_state`, and `level`.

3. Open mouth/yawn pose if feasible.
   - Expected: MAR rises and warning can trigger if duration threshold is met.

4. Look down.
   - Expected: pitch value changes and head-down warning can trigger if held long enough.

5. Return to normal.
   - Expected: alert state recovers instead of staying stuck.

## Release Gate

Do not commit or push the demo snapshot unless all items below are true or explicitly documented as accepted risks:

- Local focused tests pass.
- `identity-sim` passes.
- `simulate` passes.
- Jetson hardware readiness passes.
- `python3 main.py` is confirmed active before RFID testing.
- `DROWSIGUARD_DEMO_MODE=false`.
- `DROWSIGUARD_FEATURE_FACE_VERIFY=true`.
- Correct-face RFID test starts a session.
- No-face RFID test does not start a session.
- Stale/no-current-face RFID test does not start a session.
- At least one drowsiness alert can be demonstrated.

## Rollback Notes

Round 1 local rollback if checklist or ignore rules are wrong:

```powershell
cd D:\DATN-testing1
git restore -- .gitignore
Remove-Item -LiteralPath docs\demo-readiness\2026-05-13-demo-release-checklist.md
```

No Jetson files are modified by Round 1. If Jetson runtime behaves unexpectedly, stop the runtime and restart with the existing launcher:

```powershell
ssh nano@192.168.2.29 "pkill -f 'python3 main.py' || true"
ssh nano@192.168.2.29 "bash /home/nano/start_drowsiguard_full.sh"
```

## Known Open Risks From Round 0

- `python3 main.py` was not detected during Round 0 process verification, even though hardware readiness passed.
- Manual identity tests still need physical RFID/camera execution.
- GPS is currently disabled.
- Speaker output has not been manually heard in this round.
- Jetson launcher flags are strict, and the launcher echo text was corrected in Round 5 to report face verification as enabled.
