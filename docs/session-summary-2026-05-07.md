# Session Summary - 2026-05-07

## Workspace

- Root repo: `D:\DATN-testing1`
- Main branch: `main`
- Worktree branch used earlier: `codex/webquanli-history-timezone-retention`
- Worktree path: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention`
- User rule from `AGENTS.md`: do not edit/fix code without explicit approval; plans must be written as `.md`.

## Launcher Paths

### WebQuanLi on Windows

`C:\Users\Tung\Desktop\start_webquanli.bat.lnk` points to:

```text
D:\DATN-testing1\start_webquanli.bat
```

`start_webquanli.bat` was changed to run root WebQuanLi directly:

```text
D:\DATN-testing1\WebQuanLi
```

It no longer prefers:

```text
D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi
```

Default login configured in `start_webquanli.bat`:

```text
username: minhtung2003
password: minhtung2003
```

### Version3 on Jetson Nano

Jetson desktop launcher:

```text
/home/nano/Desktop/DrowsiGuard-Full.desktop
```

calls:

```text
/home/nano/start_drowsiguard_full.sh
```

That script runs:

```text
cd /home/nano/Version3
python3 main.py
```

Runtime path on Jetson is `/home/nano/Version3`, not a `.worktrees` path. Several checked files in `/home/nano/Version3` matched the worktree by SHA256 hash.

## Git State

Current `main` is ahead of `origin/main` by 5 commits.

Recent commits on `main`:

```text
1847f1e fix: make webquanli startup seeding idempotent
16bcf6d Merge branch 'codex/webquanli-history-timezone-retention'
694b0f5 chore: promote tested worktree runtime state
5fa8314 fix: cap dashboard alert log to latest ten
caa228a fix: reduce false drowsy alerts from rapid blinks
```

Backup branch created before merge:

```text
backup/main-before-worktree-merge-20260507
```

Root tracked dirty files were stashed before merge:

```text
stash@{0}: On main: backup root tracked dirty before worktree merge 2026-05-07
```

Current `git status` still shows untracked files/directories, including `.deploy`, `.pytest_deps`, `.tmp`, some docs, and `start_jetson_ai_main.bat`. These were not cleaned or staged.

## Worktree Promotion

The worktree branch was committed and merged into `main`.

Worktree commit:

```text
694b0f5 chore: promote tested worktree runtime state
```

Merge commit:

```text
16bcf6d Merge branch 'codex/webquanli-history-timezone-retention'
```

Conflicts occurred in:

```text
Version3/ai/drowsiness_classifier.py
Version3/main.py
Version3/tests/test_bluetooth_audio.py
Version3/tests/test_config_defaults.py
Version3/tests/test_verify_flow.py
```

Conflict resolution note:

- In `drowsiness_classifier.py`, kept `perclos_gate_active` behavior from `main` and combined it with `PERCLOS_THRESHOLD` / `PERCLOS_WINDOW` from Issue 1 fix.

## Fixes Completed

### Version3 Issue 1: Rapid Blink False DROWSY

Changed long-PERCLOS logic to use:

```text
config.PERCLOS_THRESHOLD
config.PERCLOS_WINDOW
```

and kept the stale-PERCLOS gate from `main`.

The fix was deployed to Jetson:

```text
D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\ai\drowsiness_classifier.py
-> /home/nano/Version3/ai/drowsiness_classifier.py
```

Jetson verification:

- SHA256 matched worktree after deploy.
- `python3 -m py_compile ai/drowsiness_classifier.py` passed.
- Direct Python smoke test passed:

```text
SMOKE_OK rapid_blink=NORMAL sustained=DROWSY reason=Long PERCLOS 0.60 indicates fatigue
```

Jetson pytest could not run because Python 3.6 pytest/attrs environment failed with:

```text
TypeError: attrib() got an unexpected keyword argument 'convert'
```

### WebQuanLi Issue 2: Dashboard Alert Log Limit

Dashboard alert log was capped to 10 latest alerts.

Relevant behavior:

- initial dashboard query uses `limit(10)`
- realtime alert rows are trimmed to 10

Commit:

```text
5fa8314 fix: cap dashboard alert log to latest ten
```

### WebQuanLi Issue 3: Speaker Test Buttons

Speaker test buttons were made clearer in worktree and then promoted with commit `694b0f5`.

Behavior:

- If Jetson is offline, endpoint returns a visible offline message.
- If Jetson is online, sends `test_alert` command.

### WebQuanLi Startup DB Seed Error

Observed error:

```text
sqlite3.IntegrityError: UNIQUE constraint failed: vehicles.device_id
```

Root cause:

- `start_webquanli.bat` switched to root `WebQuanLi`.
- Root DB already had vehicle `device_id='JETSON-001'`.
- `ADMIN_USERNAME` was changed to `admin`, but root DB had `minhtung2003`.
- `init_db()` tried to create missing user `admin` and also inserted demo vehicle again.

Fix:

- `WebQuanLi/app/database.py` now seeds admin user and demo vehicle independently.
- Demo vehicle is only inserted if neither `plate_number='59A-12345'` nor `device_id='JETSON-001'` exists.
- Added test: `WebQuanLi/tests/test_database_init.py`.
- Updated DB root user `minhtung2003` password hash so password `minhtung2003` works.

Commit:

```text
1847f1e fix: make webquanli startup seeding idempotent
```

## Verification Run

After merge into `main`:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\Version3'
python -m pytest Version3\tests\test_drowsiness_classifier.py Version3\tests\test_bluetooth_audio.py Version3\tests\test_config_defaults.py Version3\tests\test_verify_flow.py -q
```

Result:

```text
52 passed
```

WebQuanLi targeted verification:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\WebQuanLi'
$env:SECRET_KEY='drowsiguard-local-dev-secret'
$env:ADMIN_USERNAME='minhtung2003'
$env:ADMIN_PASSWORD='minhtung2003'
python -m pytest WebQuanLi\tests\test_database_init.py WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py -q
```

Result:

```text
27 passed
```

Launcher check:

```powershell
D:\DATN-testing1\start_webquanli.bat --check
```

Result:

```text
Project : D:\DATN-testing1\WebQuanLi
Source  : root WebQuanLi
Check OK: WebQuanLi imports successfully.
```

Direct root DB startup check from `D:\DATN-testing1\WebQuanLi`:

```powershell
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db()); print('INIT_DB_OK')"
```

Result:

```text
INIT_DB_OK
```

## Clarifications From Discussion

### Camera IMX219-77IR

- Camera is still RGB/BGR color, not only IR.
- It is an IR/NoIR-style camera, so daylight image can be purple/pink due to infrared contamination and lack of normal IR-CUT filtering.
- GUI purple image is from camera/Jetson ISP output, not from `main.py` or GUI drawing.
- Do not blindly convert whole frame to grayscale; current MediaPipe path expects BGR -> RGB. Face verifier already converts face crop to grayscale internally.

### RFID Behavior

If state is `RUNNING` and the RFID is scanned again, current design ends the session:

```text
RUNNING -> IDLE
```

This is expected behavior unless the RFID reader is accidentally re-reading the card left near the reader.

### `Flushed 1 offline events to backend`

This line is not an error by itself.

Reason it repeats:

- `main.py` pushes `hardware` status every `HW_REPORT_INTERVAL = 5.0`.
- `WSClient` flushes queued event(s) to WebQuanLi and logs it.

It is noisy but acceptable if WebQuanLi is receiving data and there are no accompanying logs such as:

```text
WSClient error
WSClient disconnected
flush error
connection refused
```

## Suggested Next Session Starting Points

1. Open this file first.
2. Check current root status:

```powershell
cd D:\DATN-testing1
git status --short --branch
git log --oneline -8
```

3. If testing WebQuanLi, run:

```powershell
D:\DATN-testing1\start_webquanli.bat
```

Login:

```text
minhtung2003 / minhtung2003
```

4. If deploying Version3 again, treat root `D:\DATN-testing1\Version3` as the promoted source, not the old worktree.
5. Do not drop `stash@{0}` or delete backup branch until the user confirms the promoted root is stable.
