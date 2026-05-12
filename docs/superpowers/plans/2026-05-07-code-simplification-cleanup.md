# Code Simplification Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean small, reviewable code complexity in WebQuanLi and Version3 while preserving the stable demo build and deploying the cleaned Jetson runtime separately as `/home/nano/V3Cleanup`.

**Architecture:** Execute cleanup in an isolated branch or worktree, not directly on the stable `main` checkout. Keep behavior-preserving changes small: remove unreachable code, remove stale UI-only OTA residue, add a separate WebQuanLi cleanup launcher, and deploy Version3 cleanup to a separate Nano directory with a separate desktop launcher. Do not split `Version3/main.py`, remove AI logic, or deploy over `/home/nano/Version3` in this pass.

**Tech Stack:** Python 3, FastAPI, Jinja/HTMX, pytest, PowerShell, Windows batch launcher, Jetson Nano Ubuntu/Python 3.6, SSH/SCP.

---

## Current Code Review Findings

### Finding 1: Stable GitHub baseline exists

- `main` is synced with `origin/main` at commit `7ff26ef fix: disable webquanli ota controls`.
- The current stable demo code is already pushed.
- The root workspace still has unrelated untracked files and directories. Cleanup work must use explicit file staging and must not use broad `git add .`.

### Finding 2: WebQuanLi OTA endpoint is disabled, but UI script still has stale OTA UI handling

- `WebQuanLi/app/api/control.py` now returns `410` for `POST /api/vehicles/{vehicle_id}/update`.
- `WebQuanLi/templates/partials/admin_controls.html` no longer renders the upload form.
- `WebQuanLi/templates/dashboard.html` still has an `ota_status` event handler that looks for `#upload-status`, but that element is no longer rendered.
- `WebQuanLi/jetson_simulator.py` still announces `Test/OTA` and still simulates `update_software`, even though WebQuanLi no longer sends that command from the UI.

### Finding 3: Version3 has small dead-code cleanup candidates

- `Version3/sensors/rfid_reader.py` has an unreachable log and return after `return path` in `_find_device()`.
- `Version3/sensors/hardware_monitor.py` defines `_check_rfid()` and `_check_gps()`, but `snapshot()` now uses `_read_rfid_status()` and `_read_gps_status()` instead. `rg` shows no call sites for `_check_rfid()` or `_check_gps()`.
- Existing tests already cover the current RFID `fn` fallback and hardware monitor payload behavior:
  - `Version3/tests/test_rfid_hid_fallback.py`
  - `Version3/tests/test_alert_output_adapters.py`
  - `Version3/tests/test_webquanli_contract.py`

### Finding 4: Large files exist but are not safe first-pass cleanup targets

- `Version3/main.py` is about 58 KB.
- `Version3/ui/local_monitor.py` and `Version3/scripts/local_ai_monitor.py` share monitor layout/canvas concepts.
- `WebQuanLi/templates/dashboard.html` is large and contains substantial inline JavaScript.
- These are valid later refactor targets, but first-pass cleanup should avoid changing these broad runtime flows except for stale OTA UI residue.

---

## Hard Boundaries

### Files and paths allowed in this cleanup pass

- `D:\DATN-testing1\start_webquanli_cleanup.bat`
- `D:\DATN-testing1\WebQuanLi\templates\dashboard.html`
- `D:\DATN-testing1\WebQuanLi\tests\test_dashboard_realtime_context.py`
- `D:\DATN-testing1\WebQuanLi\jetson_simulator.py`
- `D:\DATN-testing1\Version3\sensors\rfid_reader.py`
- `D:\DATN-testing1\Version3\sensors\hardware_monitor.py`
- `D:\DATN-testing1\Version3\tests\test_rfid_hid_fallback.py`
- `D:\DATN-testing1\Version3\tests\test_alert_output_adapters.py`
- Deployment archive under `D:\DATN-testing1\.deploy\`

### Files and paths forbidden in this cleanup pass

- `D:\DATN-testing1\start_webquanli.bat`
- `D:\DATN-testing1\start_jetson_ai_main.bat`
- `D:\DATN-testing1\Version3\main.py`
- `D:\DATN-testing1\Version3\ai\**`
- `D:\DATN-testing1\Version3\camera\**`
- `D:\DATN-testing1\Version3\network\ota_handler.py`
- `D:\DATN-testing1\WebQuanLi\app\models.py`
- `D:\DATN-testing1\WebQuanLi\app\schemas.py`
- `D:\DATN-testing1\WebQuanLi\app\ws\jetson_handler.py`
- `/home/nano/Version3`
- `/home/nano/Desktop/DrowsiGuard-Full.desktop`
- Any existing stash, backup branch, generated database, or unrelated untracked file.

### Deployment rule

- Local cleanup proof must happen before Nano deployment.
- Nano deployment must copy Version3 cleanup to `/home/nano/V3Cleanup`.
- Nano launcher must be separate: `/home/nano/Desktop/DrowsiGuard-V3Cleanup.desktop`.
- Do not overwrite `/home/nano/Desktop/DrowsiGuard-Full.desktop` unless the user explicitly asks for that exact overwrite in a separate approval.

---

## Task 0: Create Isolated Cleanup Workspace And Baseline

**Files:**
- No source edits.

- [ ] **Step 1: Confirm current repo state**

Run:

```powershell
git status --short --branch
git log --oneline --decorate -3
```

Expected:

```text
main is synced with origin/main.
Untracked files may exist and must remain untouched.
```

- [ ] **Step 2: Create cleanup worktree**

Run from `D:\DATN-testing1`:

```powershell
git worktree add .worktrees\code-simplification-cleanup -b codex/code-simplification-cleanup main
```

Expected:

```text
Preparing worktree (new branch 'codex/code-simplification-cleanup')
HEAD is now at 7ff26ef fix: disable webquanli ota controls
```

- [ ] **Step 3: Enter cleanup worktree**

Run:

```powershell
Set-Location D:\DATN-testing1\.worktrees\code-simplification-cleanup
```

Expected:

```text
Current directory is D:\DATN-testing1\.worktrees\code-simplification-cleanup
```

- [ ] **Step 4: Run baseline tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi;D:\DATN-testing1\.worktrees\code-simplification-cleanup\Version3'
python -m pytest WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py Version3\tests\test_rfid_hid_fallback.py Version3\tests\test_alert_output_adapters.py Version3\tests\test_webquanli_contract.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 5: Run WebQuanLi import check**

Run:

```powershell
D:\DATN-testing1\.worktrees\code-simplification-cleanup\start_webquanli.bat --check
```

Expected:

```text
Check OK: WebQuanLi imports successfully.
```

---

## Task 1: Add Separate WebQuanLi Cleanup Launcher

**Files:**
- Create: `D:\DATN-testing1\.worktrees\code-simplification-cleanup\start_webquanli_cleanup.bat`

- [ ] **Step 1: Create cleanup launcher**

Create `start_webquanli_cleanup.bat` with this exact content:

```bat
@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "PROJECT_DIR=%ROOT_DIR%WebQuanLi"
set "LOCAL_DEPS_DIR=%ROOT_DIR%.pytest_deps"
set "SHARED_DEPS_DIR=D:\DATN-testing1\.pytest_deps"
set "HOST=0.0.0.0"
set "PORT=8010"
set "CHECK_ONLY=0"

if /I "%~1"=="--check" set "CHECK_ONLY=1"

echo ========================================
echo DrowsiGuard - Start WebQuanLi Cleanup
echo ========================================
echo.

if not exist "%PROJECT_DIR%\app\main.py" (
    echo ERROR: Cannot find WebQuanLi app at:
    echo %PROJECT_DIR%
    echo.
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"
) else if exist "D:\DATN-testing1\.venv\Scripts\python.exe" (
    set "PYTHON=D:\DATN-testing1\.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if exist "%LOCAL_DEPS_DIR%" (
    set "PYTHONPATH=%LOCAL_DEPS_DIR%;%PROJECT_DIR%;%PYTHONPATH%"
) else if exist "%SHARED_DEPS_DIR%" (
    set "PYTHONPATH=%SHARED_DEPS_DIR%;%PROJECT_DIR%;%PYTHONPATH%"
)

if not defined SECRET_KEY set "SECRET_KEY=drowsiguard-local-dev-secret"
if not defined ADMIN_USERNAME set "ADMIN_USERNAME=minhtung2003"
if not defined ADMIN_PASSWORD set "ADMIN_PASSWORD=minhtung2003"

echo Project : %PROJECT_DIR%
echo Source  : cleanup worktree WebQuanLi
echo URL     : http://127.0.0.1:%PORT%
echo Python  : %PYTHON%
if exist "%LOCAL_DEPS_DIR%" echo Deps    : %LOCAL_DEPS_DIR%
if not exist "%LOCAL_DEPS_DIR%" if exist "%SHARED_DEPS_DIR%" echo Deps    : %SHARED_DEPS_DIR%
echo.

"%PYTHON%" -c "import uvicorn; import app.main" >nul 2>nul
if errorlevel 1 (
    echo ERROR: WebQuanLi cleanup cannot import required Python modules.
    echo Checked project:
    echo     %PROJECT_DIR%
    echo.
    pause
    exit /b 1
)

if "%CHECK_ONLY%"=="1" (
    echo Check OK: WebQuanLi cleanup imports successfully.
    exit /b 0
)

start "" "http://127.0.0.1:%PORT%"

echo Starting WebQuanLi cleanup on port %PORT%...
echo Keep this window open while testing.
echo Press Ctrl+C to stop the server.
echo.

"%PYTHON%" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload

echo.
echo WebQuanLi cleanup server stopped.
pause
```

- [ ] **Step 2: Verify cleanup launcher imports WebQuanLi**

Run:

```powershell
D:\DATN-testing1\.worktrees\code-simplification-cleanup\start_webquanli_cleanup.bat --check
```

Expected:

```text
Check OK: WebQuanLi cleanup imports successfully.
```

- [ ] **Step 3: Verify stable launcher was not modified**

Run from `D:\DATN-testing1\.worktrees\code-simplification-cleanup`:

```powershell
git diff -- start_webquanli.bat
```

Expected:

```text
No diff output.
```

- [ ] **Step 4: Commit launcher slice**

Run:

```powershell
git add start_webquanli_cleanup.bat
git commit -m "chore: add webquanli cleanup launcher"
```

Expected:

```text
Commit created with only start_webquanli_cleanup.bat.
```

---

## Task 2: Remove Stale WebQuanLi OTA UI Residue

**Files:**
- Modify: `D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi\tests\test_dashboard_realtime_context.py`
- Modify: `D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi\templates\dashboard.html`
- Modify: `D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi\jetson_simulator.py`

- [ ] **Step 1: Tighten dashboard test for removed OTA UI script**

In `WebQuanLi\tests\test_dashboard_realtime_context.py`, extend `test_dashboard_hides_ota_upload_controls()` to this:

```python
    def test_dashboard_hides_ota_upload_controls(self):
        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/api/vehicles/1/update", response.text)
        self.assertNotIn('id="ota-file-input"', response.text)
        self.assertNotIn('id="btn-upload"', response.text)
        self.assertNotIn('id="upload-status"', response.text)
        self.assertNotIn("handleRealtimeEvent('ota_status'", response.text)
        self.assertNotIn("addEventListener('ota_status'", response.text)
        self.assertIn('id="btn-test-1"', response.text)
        self.assertIn('id="btn-test-2"', response.text)
        self.assertIn('id="btn-test-3"', response.text)
```

- [ ] **Step 2: Run the dashboard test and verify it fails before cleanup**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi'
python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py::DashboardRealtimeContextTest::test_dashboard_hides_ota_upload_controls -q
```

Expected:

```text
FAILED because dashboard.html still contains ota_status listener or handler.
```

- [ ] **Step 3: Remove OTA status UI branch from dashboard script**

In `WebQuanLi\templates\dashboard.html`, remove this block:

```javascript
        if (type === 'ota_status') {
            markLastSeenNow();
            const el = document.getElementById('upload-status');
            if (el) {
                el.innerHTML = data.status === 'APPLIED'
                    ? '<div class="alert-success">✅ Cập nhật thành công: ' + data.filename + '</div>'
                    : '<div class="alert-danger">❌ Cập nhật thất bại: ' + (data.error || data.filename) + '</div>';
            }
        }
```

Also remove this listener line:

```javascript
        dashboardEventSource.addEventListener('ota_status', (event) => handleRealtimeEvent('ota_status', parseRealtimePayload(event)));
```

Do not change the WebSocket backend schema in this task. Keeping `ota_status` schema parsing on the backend is a safer compatibility boundary.

- [ ] **Step 4: Simplify simulator command text and remove OTA simulation branch**

In `WebQuanLi\jetson_simulator.py`, replace:

```python
            print("\n[*] Đang lắng nghe Lệnh điều khiển (Test/OTA) từ Web Admin trong 30 giây...")
```

with:

```python
            print("\n[*] Dang lang nghe lenh test canh bao tu Web Admin trong 30 giay...")
```

Then remove this branch:

```python
                    elif cmd.get("action") == "update_software":
                        print("         (Bắt đầu tải bản cập nhật OTA từ web)")
                        await ws.send(json.dumps({
                            "type": "ota_status",
                            "data": {"status": "downloading", "progress": 50}
                        }))
                        await asyncio.sleep(1)
                        await ws.send(json.dumps({
                            "type": "ota_status",
                            "data": {"status": "success", "progress": 100}
                        }))
```

Leave the `test_alert` branch unchanged.

- [ ] **Step 5: Verify dashboard and simulator cleanup**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi'
python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py::DashboardRealtimeContextTest::test_dashboard_hides_ota_upload_controls -q
python -m py_compile WebQuanLi\jetson_simulator.py
```

Expected:

```text
1 passed
py_compile exits 0
```

- [ ] **Step 6: Run WebQuanLi focused regression**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi'
python -m pytest WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py -q
D:\DATN-testing1\.worktrees\code-simplification-cleanup\start_webquanli_cleanup.bat --check
```

Expected:

```text
All selected tests pass.
Check OK: WebQuanLi cleanup imports successfully.
```

- [ ] **Step 7: Commit WebQuanLi cleanup slice**

Run:

```powershell
git add WebQuanLi\templates\dashboard.html WebQuanLi\tests\test_dashboard_realtime_context.py WebQuanLi\jetson_simulator.py
git commit -m "refactor: remove stale webquanli ota ui residue"
```

Expected:

```text
Commit created with only WebQuanLi dashboard test, dashboard template, and simulator changes.
```

---

## Task 3: Remove Version3 RFID And HardwareMonitor Dead Code

**Files:**
- Modify: `D:\DATN-testing1\.worktrees\code-simplification-cleanup\Version3\sensors\rfid_reader.py`
- Modify: `D:\DATN-testing1\.worktrees\code-simplification-cleanup\Version3\sensors\hardware_monitor.py`

- [ ] **Step 1: Verify existing RFID fallback test covers the active path**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.worktrees\code-simplification-cleanup\Version3'
python -m pytest Version3\tests\test_rfid_hid_fallback.py::test_evdev_auto_detect_supports_input_device_fn_attribute -q
```

Expected:

```text
1 passed
```

- [ ] **Step 2: Remove unreachable code in RFID device detection**

In `Version3\sensors\rfid_reader.py`, replace:

```python
                path = input_device_path(dev)
                self._last_device_path = path
                logger.info(f"Found RFID device: {path} ({dev.name})")
                return path
                logger.info(f"Found RFID device: {dev.path} — {dev.name}")
                return dev.path
```

with:

```python
                path = input_device_path(dev)
                self._last_device_path = path
                logger.info(f"Found RFID device: {path} ({dev.name})")
                return path
```

- [ ] **Step 3: Verify RFID behavior still passes**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.worktrees\code-simplification-cleanup\Version3'
python -m pytest Version3\tests\test_rfid_hid_fallback.py -q
```

Expected:

```text
All tests in test_rfid_hid_fallback.py pass.
```

- [ ] **Step 4: Verify `_check_rfid` and `_check_gps` have no call sites**

Run:

```powershell
rg -n "def _check_rfid|def _check_gps|_check_rfid\(|_check_gps\(" Version3 WebQuanLi -S
```

Expected before edit:

```text
Only the two definitions in Version3\sensors\hardware_monitor.py are returned.
```

- [ ] **Step 5: Remove unused helpers from HardwareMonitor**

In `Version3\sensors\hardware_monitor.py`, remove:

```python
    def _check_rfid(self) -> bool:
        if self._rfid is None:
            return False
        try:
            return bool(self._rfid.is_alive)
        except Exception:
            return False

    def _check_gps(self) -> bool:
        if not config.HAS_GPS or self._gps is None:
            return False
        try:
            return bool(self._gps.is_alive)
        except Exception:
            return False
```

Do not change `_read_rfid_status()` or `_read_gps_status()`.

- [ ] **Step 6: Verify unused helper names are gone**

Run:

```powershell
rg -n "def _check_rfid|def _check_gps|_check_rfid\(|_check_gps\(" Version3 WebQuanLi -S
```

Expected after edit:

```text
No output.
```

- [ ] **Step 7: Run Version3 focused regression**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.worktrees\code-simplification-cleanup\Version3;D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi'
python -m pytest Version3\tests\test_rfid_hid_fallback.py Version3\tests\test_alert_output_adapters.py Version3\tests\test_webquanli_contract.py Version3\tests\test_main_local_gui.py -q
```

Expected:

```text
All selected Version3 tests pass.
```

- [ ] **Step 8: Commit Version3 cleanup slice**

Run:

```powershell
git add Version3\sensors\rfid_reader.py Version3\sensors\hardware_monitor.py
git commit -m "refactor: remove version3 hardware dead code"
```

Expected:

```text
Commit created with only rfid_reader.py and hardware_monitor.py changes.
```

---

## Task 4: Final Local Verification Before Nano Deployment

**Files:**
- No additional source edits.

- [ ] **Step 1: Run combined targeted tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\.worktrees\code-simplification-cleanup\WebQuanLi;D:\DATN-testing1\.worktrees\code-simplification-cleanup\Version3'
python -m pytest WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py Version3\tests\test_rfid_hid_fallback.py Version3\tests\test_alert_output_adapters.py Version3\tests\test_webquanli_contract.py Version3\tests\test_main_local_gui.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 2: Verify both launchers**

Run:

```powershell
D:\DATN-testing1\.worktrees\code-simplification-cleanup\start_webquanli.bat --check
D:\DATN-testing1\.worktrees\code-simplification-cleanup\start_webquanli_cleanup.bat --check
```

Expected:

```text
Both checks print Check OK.
```

- [ ] **Step 3: Verify diff does not touch forbidden files**

Run:

```powershell
git diff --name-only main...HEAD
```

Expected:

```text
start_webquanli_cleanup.bat
WebQuanLi/templates/dashboard.html
WebQuanLi/tests/test_dashboard_realtime_context.py
WebQuanLi/jetson_simulator.py
Version3/sensors/rfid_reader.py
Version3/sensors/hardware_monitor.py
```

If any forbidden file appears, stop and review before continuing.

---

## Task 5: Deploy Version3 Cleanup Separately To Jetson Nano

**Files and remote paths:**
- Local archive: `D:\DATN-testing1\.deploy\v3cleanup-code-simplification.tar.gz`
- Local desktop launcher staging file: `D:\DATN-testing1\.deploy\DrowsiGuard-V3Cleanup.desktop`
- Remote target directory: `/home/nano/V3Cleanup`
- Remote launcher: `/home/nano/Desktop/DrowsiGuard-V3Cleanup.desktop`

> **Important:** All steps in Task 5 must run in the **same PowerShell session** so that `$env:NANO_HOST` set in Step 1 persists for the later `ssh`/`scp` calls. If you open a new terminal mid-task, re-run Step 1 first.

- [ ] **Step 1: Set Jetson host variable and verify SSH connectivity**

Default Jetson IP is `192.168.2.17`. If the Jetson is on a different network (e.g. phone hotspot), set `$env:NANO_HOST` to the current Jetson IP before running the SSH check.

Run:

```powershell
if (-not $env:NANO_HOST) { $env:NANO_HOST = '192.168.2.17' }
Write-Host "NANO_HOST = $env:NANO_HOST"
ssh -o BatchMode=yes -o ConnectTimeout=8 "nano@$env:NANO_HOST" "echo SSH_OK && hostname"
```

Expected:

```text
NANO_HOST = <current Jetson IP>
SSH_OK
<Jetson hostname>
```

- [ ] **Step 2: Create a Version3-only cleanup archive from the cleanup branch**

Run from `D:\DATN-testing1\.worktrees\code-simplification-cleanup`:

```powershell
New-Item -ItemType Directory -Force -Path D:\DATN-testing1\.deploy | Out-Null
git archive --format=tar --prefix=V3Cleanup/ HEAD:Version3 | gzip > D:\DATN-testing1\.deploy\v3cleanup-code-simplification.tar.gz
Get-Item D:\DATN-testing1\.deploy\v3cleanup-code-simplification.tar.gz
```

Expected:

```text
Archive exists and has non-zero size.
```

- [ ] **Step 3: Copy archive to Jetson**

Run:

```powershell
scp D:\DATN-testing1\.deploy\v3cleanup-code-simplification.tar.gz "nano@${env:NANO_HOST}:/home/nano/v3cleanup-code-simplification.tar.gz"
```

Expected:

```text
SCP exits 0.
```

- [ ] **Step 4: Install archive into `/home/nano/V3Cleanup` without touching `/home/nano/Version3`**

Run:

```powershell
ssh "nano@$env:NANO_HOST" "bash -lc 'set -e; mkdir -p /home/nano/.codex_backups; if [ -d /home/nano/V3Cleanup ]; then mv /home/nano/V3Cleanup /home/nano/.codex_backups/V3Cleanup-before-`$(date +%Y%m%d-%H%M%S); fi; mkdir -p /home/nano/V3Cleanup; tar -xzf /home/nano/v3cleanup-code-simplification.tar.gz --strip-components=1 -C /home/nano/V3Cleanup; test -f /home/nano/V3Cleanup/main.py; test -d /home/nano/Version3; echo V3CLEANUP_DEPLOYED'"
```

Note: the backtick before `$(date ...)` escapes the `$` so PowerShell does not try to expand it; the `$(...)` is then evaluated by remote bash.

Expected:

```text
V3CLEANUP_DEPLOYED
```

- [ ] **Step 5: Create separate V3Cleanup desktop launcher**

Write the launcher file locally first (LF line endings, no BOM), then `scp` it to the Jetson Desktop, then `chmod +x` remotely. This avoids fragile heredoc-through-SSH quoting on PowerShell.

Run:

```powershell
$desktopLocal = 'D:\DATN-testing1\.deploy\DrowsiGuard-V3Cleanup.desktop'
$desktopBody = @(
    '[Desktop Entry]',
    'Type=Application',
    'Name=DrowsiGuard V3Cleanup',
    'Comment=Run cleaned DrowsiGuard Version3 from /home/nano/V3Cleanup',
    "Exec=bash -lc 'cd /home/nano/V3Cleanup && export DISPLAY=:0 && export XAUTHORITY=/home/nano/.Xauthority && python3 main.py'",
    'Terminal=true',
    'Icon=utilities-terminal',
    'Categories=Utility;'
) -join "`n"
[System.IO.File]::WriteAllText($desktopLocal, $desktopBody + "`n", (New-Object System.Text.UTF8Encoding $false))
Get-Item $desktopLocal

scp $desktopLocal "nano@${env:NANO_HOST}:/home/nano/Desktop/DrowsiGuard-V3Cleanup.desktop"
ssh "nano@$env:NANO_HOST" "bash -lc 'chmod +x /home/nano/Desktop/DrowsiGuard-V3Cleanup.desktop && grep -n V3Cleanup /home/nano/Desktop/DrowsiGuard-V3Cleanup.desktop'"
```

Expected:

```text
Local staging file exists.
SCP exits 0.
Grep prints lines containing V3Cleanup, including the Exec= line referencing /home/nano/V3Cleanup.
```

- [ ] **Step 6: Verify remote compile without starting full runtime**

Run:

```powershell
ssh "nano@$env:NANO_HOST" "bash -lc 'cd /home/nano/V3Cleanup && python3 -m py_compile main.py sensors/rfid_reader.py sensors/hardware_monitor.py && echo V3CLEANUP_PY_COMPILE_OK'"
```

Expected:

```text
V3CLEANUP_PY_COMPILE_OK
```

- [ ] **Step 7: Verify stable runtime directory and launcher were not overwritten**

Run:

```powershell
ssh "nano@$env:NANO_HOST" "bash -lc 'test -d /home/nano/Version3 && test -f /home/nano/Desktop/DrowsiGuard-Full.desktop && grep -n Version3 /home/nano/Desktop/DrowsiGuard-Full.desktop || true; echo STABLE_PATHS_CHECKED'"
```

Expected:

```text
STABLE_PATHS_CHECKED
```

The stable `/home/nano/Version3` directory must still exist.

---

## Task 6: Final Review And Publish Choice

**Files:**
- No additional source edits.

- [ ] **Step 1: Review final diff**

Run from `D:\DATN-testing1\.worktrees\code-simplification-cleanup`:

```powershell
git status --short --branch
git log --oneline --decorate -5
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Expected:

```text
Only cleanup branch commits and allowed files are shown.
```

- [ ] **Step 2: Decide integration path**

After the user reviews the result, choose one:

```text
Option A: Push cleanup branch only, leave main unchanged.
Option B: Merge cleanup branch to main and push main.
Option C: Keep cleanup branch local for more testing.
```

Do not merge or push `main` until the user explicitly chooses Option B.

---

## Out Of Scope For This First Cleanup Pass

- Splitting `Version3/main.py`.
- Refactoring AI threshold logic or drowsiness classification.
- Removing `WebQuanLi/app/models.py::OtaAuditLog`.
- Removing `WebQuanLi/app/schemas.py::OTAStatusData`.
- Removing `Version3/network/ota_handler.py`.
- Removing `update_software` support from Version3 command handling.
- Rewriting `WebQuanLi/templates/dashboard.html` into separate JavaScript modules.
- Cleaning unrelated untracked files or generated directories in the root workspace.

These may be useful later, but they need separate plans because they either affect public contracts, database shape, or runtime behavior.

## Completion Criteria

- Cleanup branch exists separately from stable `main`.
- `start_webquanli_cleanup.bat --check` passes.
- WebQuanLi dashboard has no OTA upload form and no stale `ota_status` UI handler.
- Version3 RFID and hardware monitor dead code is removed.
- Targeted WebQuanLi and Version3 tests pass locally.
- `/home/nano/V3Cleanup` exists and compiles on Jetson.
- `/home/nano/Version3` still exists and was not overwritten.
- `/home/nano/Desktop/DrowsiGuard-V3Cleanup.desktop` launches `/home/nano/V3Cleanup`.
- No broad `git add .` was used.
- No unrelated untracked files were staged, deleted, or committed.

## Rollback Notes

- Local cleanup branch can be abandoned without affecting `main`.
- If `/home/nano/V3Cleanup` behaves badly, do not modify `/home/nano/Version3`; simply stop using the V3Cleanup desktop launcher.
- Previous `/home/nano/V3Cleanup` copies are moved under `/home/nano/.codex_backups/` before replacement.
- Delete `/home/nano/Desktop/DrowsiGuard-V3Cleanup.desktop` only if the user asks to remove the cleanup launcher.
