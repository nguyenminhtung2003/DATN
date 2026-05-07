# Version3 WebQuanLi Hardware Contract Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Version3 and WebQuanLi exchange hardware/monitoring state reliably so WebQuanLi does not show all hardware as failed while Jetson Nano is actually connected.

**Architecture:** Fix the producer contract first: `Version3` must expose a `HardwareMonitor.status()` method because `AsyncStatusAdapter` calls `status()`, not `snapshot()`. Add a WebQuanLi defensive guard so empty hardware payloads cannot overwrite the last known hardware state as all-false. Keep the dashboard connection badge from accidentally sending `disconnect_monitoring` during normal operation.

**Tech Stack:** Python 3.6-compatible Version3 runtime, FastAPI/WebQuanLi, Pydantic v1/v2 compatibility layer, pytest/unittest, Jetson Nano A02 deployment over SSH/SCP.

---

## Current Confirmed Root Cause

`Version3/main.py` creates:

```python
self.hw_status = AsyncStatusAdapter(self.hw_monitor, default_status={}, interval_sec=...)
```

`AsyncStatusAdapter._read_status()` only reads:

```python
status_method = getattr(self._reader, "status", None)
if callable(status_method):
    ...
if callable(self._reader):
    ...
return {}
```

But the currently tested worktree `Version3/sensors/hardware_monitor.py` only exposes:

```python
def snapshot(self) -> dict:
    ...
```

Therefore the periodic hardware payload becomes `{}`. WebQuanLi parses missing hardware fields as false defaults, so the dashboard shows Power/RFID/GPS/Camera/Speaker as failed.

The `disconnect_monitoring` log is a separate cross-control issue: the online dashboard badge currently exposes `data-next-monitoring-state="disconnect"`, so clicking it can turn monitoring off.

---

## Execution Target

Use the existing tested worktree:

```powershell
D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention
```

Do not use mixed code from root `D:\DATN-testing1\Version3` and worktree `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi` during verification. The final deploy to Nano must copy Version3 and WebQuanLi from the same worktree revision.

---

## Files Allowed

- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\sensors\hardware_monitor.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\tests\test_alert_output_adapters.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\tests\test_main_local_gui.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\app\schemas.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\app\api\control.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\templates\dashboard.html`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_api_validation_contract.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_dashboard_realtime_context.py`

## Files Forbidden

- Do not modify EAR/drowsiness algorithm files:
  - `Version3\ai\*.py`
  - `Version3\camera\face_analyzer.py`
  - `Version3\ui\local_monitor.py`
- Do not modify database schema/migrations unless a test proves the current schema cannot store the corrected payload.
- Do not modify visual styling/CSS except text/title attributes directly tied to the connection badge behavior.
- Do not deploy to Jetson Nano until local targeted tests pass and the user approves the deploy checkpoint.
- Do not commit, stage, or push unless the user explicitly asks.

---

## Task 1: Fix Version3 Hardware Producer Contract

**Files:**
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\sensors\hardware_monitor.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\tests\test_alert_output_adapters.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\tests\test_main_local_gui.py`

- [ ] **Step 1: Add failing test for `HardwareMonitor.status()`**

Add this test to `Version3\tests\test_alert_output_adapters.py` inside `AlertOutputAdapterTest`:

```python
    def test_hardware_monitor_status_matches_snapshot_payload(self):
        monitor = HardwareMonitor()

        snapshot = monitor.snapshot()
        status = monitor.status(force_refresh=True)

        self.assertEqual(status, snapshot)
        for key in (
            "power",
            "camera",
            "rfid",
            "gps",
            "speaker",
            "cellular",
            "camera_ok",
            "rfid_reader_ok",
            "gps_uart_ok",
            "gps_fix_ok",
            "speaker_output_ok",
            "websocket_ok",
            "details",
        ):
            self.assertIn(key, status)
```

- [ ] **Step 2: Add failing test for `AsyncStatusAdapter(HardwareMonitor)`**

Add this test to `Version3\tests\test_main_local_gui.py` inside `MainLocalGUITest`:

```python
    def test_async_status_adapter_reads_hardware_monitor_status_contract(self):
        from sensors.hardware_monitor import HardwareMonitor

        adapter = AsyncStatusAdapter(HardwareMonitor(), default_status={}, interval_sec=0.0)

        status = adapter.status(force_refresh=True)

        self.assertIn("power", status)
        self.assertIn("camera_ok", status)
        self.assertIn("rfid_reader_ok", status)
        self.assertIn("gps_uart_ok", status)
        self.assertIn("speaker_output_ok", status)
        self.assertIn("websocket_ok", status)
```

- [ ] **Step 3: Run the failing Version3 tests**

Run from:

```powershell
cd D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention
python -m pytest Version3\tests\test_alert_output_adapters.py::AlertOutputAdapterTest::test_hardware_monitor_status_matches_snapshot_payload Version3\tests\test_main_local_gui.py::MainLocalGUITest::test_async_status_adapter_reads_hardware_monitor_status_contract -q
```

Expected before implementation:

```text
FAILED ... AttributeError: 'HardwareMonitor' object has no attribute 'status'
```

- [ ] **Step 4: Implement minimal compatibility method**

Add this method immediately after `snapshot()` in `Version3\sensors\hardware_monitor.py`:

```python
    def status(self, force_refresh=False) -> dict:
        """Return hardware status for AsyncStatusAdapter compatibility."""
        return self.snapshot()
```

`force_refresh` is accepted for compatibility with `AsyncStatusAdapter`; `HardwareMonitor.snapshot()` already reads live values.

- [ ] **Step 5: Run Version3 targeted tests**

Run:

```powershell
python -m pytest Version3\tests\test_alert_output_adapters.py Version3\tests\test_main_local_gui.py Version3\tests\test_webquanli_contract.py -q
```

Expected:

```text
passed
```

---

## Task 2: Prevent WebQuanLi From Turning Empty Hardware Payloads Into All-Red UI

**Files:**
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\app\schemas.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_api_validation_contract.py`

- [ ] **Step 1: Add failing schema guard test**

Add this test to `WebQuanLi\tests\test_api_validation_contract.py`:

```python
    def test_hardware_ws_schema_rejects_payload_without_status_fields(self):
        from pydantic import ValidationError
        from app.schemas import HardwareData

        with self.assertRaises(ValidationError):
            HardwareData(queue_pending=1)
```

- [ ] **Step 2: Run failing WebQuanLi schema test**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_hardware_ws_schema_rejects_payload_without_status_fields -q
```

Expected before implementation:

```text
FAILED ... ValidationError not raised
```

- [ ] **Step 3: Add explicit hardware status-key guard**

Add this constant near the top of `WebQuanLi\app\schemas.py`, after the regex constants:

```python
HARDWARE_STATUS_KEYS = {
    "power",
    "cellular",
    "gps",
    "camera",
    "rfid",
    "speaker",
    "camera_ok",
    "rfid_reader_ok",
    "gps_uart_ok",
    "gps_fix_ok",
    "bluetooth_adapter_ok",
    "bluetooth_speaker_connected",
    "speaker_output_ok",
    "websocket_ok",
}
```

Add this validator inside `class HardwareData(BaseModel):` before `_coalesce()`:

```python
    @model_validator(mode="before")
    def require_status_fields(cls, values):
        if not isinstance(values, dict):
            return values
        if not any(key in values for key in HARDWARE_STATUS_KEYS):
            raise ValueError("hardware payload missing device status fields")
        return values
```

This keeps valid legacy payloads working because legacy keys like `camera`, `rfid`, `gps`, `speaker`, and `cellular` are still accepted.

- [ ] **Step 4: Run WebQuanLi schema tests**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_api_validation_contract.py -q
```

Expected:

```text
passed
```

---

## Task 3: Stop Dashboard Badge From Accidentally Sending `disconnect_monitoring`

**Files:**
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\templates\dashboard.html`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\app\api\control.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_dashboard_realtime_context.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_api_validation_contract.py`

- [ ] **Step 1: Update dashboard expectations first**

In `WebQuanLi\tests\test_dashboard_realtime_context.py`, change the online dashboard expectation from:

```python
self.assertIn('data-next-monitoring-state="disconnect"', response.text)
```

to:

```python
self.assertIn('data-next-monitoring-state="connect"', response.text)
```

Keep the offline expectation as:

```python
self.assertIn('data-next-monitoring-state="connect"', response.text)
```

- [ ] **Step 2: Update JSON response expectation**

In `WebQuanLi\tests\test_api_validation_contract.py`, inside `test_monitoring_endpoint_returns_json_for_connection_badge`, change:

```python
self.assertEqual(response.json()["next_state"], "disconnect")
```

to:

```python
self.assertEqual(response.json()["next_state"], "connect")
```

Keep `test_monitoring_endpoint_sends_connect_and_disconnect_commands` unchanged so explicit API disconnect remains supported.

- [ ] **Step 3: Run failing dashboard/control tests**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_monitoring_endpoint_returns_json_for_connection_badge -q
```

Expected before implementation:

```text
FAILED ... data-next-monitoring-state="connect" not found
FAILED ... 'disconnect' != 'connect'
```

- [ ] **Step 4: Make connection badge always request connect/reconnect**

In `WebQuanLi\templates\dashboard.html`, change the connection badge attributes to keep the next action as connect:

```html
data-next-monitoring-state="connect"
aria-label="{{ 'Ket noi voi Jetson. Bam de bat/dong bo giam sat.' if connection_status == 'online' else 'Mat ket noi voi Jetson. Bam de gui lenh ket noi giam sat.' }}"
title="{{ 'Bam de bat/dong bo giam sat' if connection_status == 'online' else 'Bam de gui lenh ket noi giam sat' }}"
```

Do not change the visible connection status text.

- [ ] **Step 5: Keep JSON badge state on connect**

In `WebQuanLi\app\api\control.py`, change `_monitoring_payload()` for sent commands from:

```python
"next_state": "disconnect" if state == "connect" else "connect",
```

to:

```python
"next_state": "connect",
```

This only changes the dashboard JSON badge behavior. The endpoint still accepts `state=disconnect` for explicit admin/API actions.

- [ ] **Step 6: Run WebQuanLi targeted tests**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py -q
```

Expected:

```text
passed
```

---

## Task 4: Local Full Verification Checkpoint

**Files:**
- No new implementation files.

- [ ] **Step 1: Run cross-project targeted suite**

Run from:

```powershell
cd D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention
python -m pytest Version3\tests\test_alert_output_adapters.py Version3\tests\test_main_local_gui.py Version3\tests\test_webquanli_contract.py WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Check no unrelated files were touched**

Run:

```powershell
git status --short
```

Expected:

```text
Only files listed in Files Allowed are changed for this plan, plus pre-existing dirty files already known before execution.
```

- [ ] **Step 3: Stop and report before Nano deploy**

Report:

```text
Local checkpoint complete.
Do not deploy yet.
Need user approval to copy files to Jetson Nano A02.
```

---

## Task 5: Nano Deployment After User Approval Only

**Files copied to Nano after approval:**
- `Version3\sensors\hardware_monitor.py` -> `/home/nano/Version3/sensors/hardware_monitor.py`
- `Version3\tests\test_alert_output_adapters.py` -> `/home/nano/Version3/tests/test_alert_output_adapters.py`
- `Version3\tests\test_main_local_gui.py` -> `/home/nano/Version3/tests/test_main_local_gui.py`
- `WebQuanLi\app\schemas.py` -> `/home/nano/WebQuanLi/app/schemas.py`
- `WebQuanLi\app\api\control.py` -> `/home/nano/WebQuanLi/app/api/control.py`
- `WebQuanLi\templates\dashboard.html` -> `/home/nano/WebQuanLi/templates/dashboard.html`
- `WebQuanLi\tests\test_api_validation_contract.py` -> `/home/nano/WebQuanLi/tests/test_api_validation_contract.py`
- `WebQuanLi\tests\test_dashboard_realtime_context.py` -> `/home/nano/WebQuanLi/tests/test_dashboard_realtime_context.py`

- [ ] **Step 1: Back up current Nano files**

Run only after approval:

```powershell
ssh nano@192.168.2.17 "mkdir -p /home/nano/backup_2026_05_06_hardware_contract && cp /home/nano/Version3/sensors/hardware_monitor.py /home/nano/backup_2026_05_06_hardware_contract/hardware_monitor.py && cp /home/nano/WebQuanLi/app/schemas.py /home/nano/backup_2026_05_06_hardware_contract/schemas.py && cp /home/nano/WebQuanLi/app/api/control.py /home/nano/backup_2026_05_06_hardware_contract/control.py && cp /home/nano/WebQuanLi/templates/dashboard.html /home/nano/backup_2026_05_06_hardware_contract/dashboard.html"
```

- [ ] **Step 2: Copy approved files**

Run:

```powershell
scp Version3\sensors\hardware_monitor.py nano@192.168.2.17:/home/nano/Version3/sensors/hardware_monitor.py
scp Version3\tests\test_alert_output_adapters.py Version3\tests\test_main_local_gui.py nano@192.168.2.17:/home/nano/Version3/tests/
scp WebQuanLi\app\schemas.py nano@192.168.2.17:/home/nano/WebQuanLi/app/schemas.py
scp WebQuanLi\app\api\control.py nano@192.168.2.17:/home/nano/WebQuanLi/app/api/control.py
scp WebQuanLi\templates\dashboard.html nano@192.168.2.17:/home/nano/WebQuanLi/templates/dashboard.html
scp WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py nano@192.168.2.17:/home/nano/WebQuanLi/tests/
```

- [ ] **Step 3: Compile on Nano**

Run:

```powershell
ssh nano@192.168.2.17 "cd /home/nano/Version3 && python3 -m py_compile sensors/hardware_monitor.py main.py"
ssh nano@192.168.2.17 "cd /home/nano/WebQuanLi && python3 -m py_compile app/schemas.py app/api/control.py"
```

Expected:

```text
No output and exit code 0
```

- [ ] **Step 4: Run Nano targeted tests**

Run:

```powershell
ssh nano@192.168.2.17 "cd /home/nano/Version3 && python3 -m pytest tests/test_alert_output_adapters.py tests/test_main_local_gui.py tests/test_webquanli_contract.py -q"
ssh nano@192.168.2.17 "cd /home/nano/WebQuanLi && python3 -m pytest tests/test_api_validation_contract.py tests/test_dashboard_realtime_context.py -q"
```

Expected:

```text
passed
```

- [ ] **Step 5: Runtime verification on Nano**

Start WebQuanLi and DrowsiGuard normally, then run:

```powershell
ssh nano@192.168.2.17 "python3 - <<'PY'
import json
path = '/home/nano/Version3/storage/runtime/status.json'
with open(path, 'r') as f:
    data = json.load(f)
hardware = data.get('hardware', {})
for key in ('power', 'camera', 'rfid', 'gps', 'speaker', 'camera_ok', 'rfid_reader_ok', 'gps_uart_ok', 'speaker_output_ok', 'websocket_ok'):
    print(key, hardware.get(key, '<missing>'))
PY"
```

Expected:

```text
No core key prints <missing>.
Camera should be true when camera is running.
RFID/GPS/Speaker should reflect actual hardware state instead of defaulting false because the payload was empty.
```

---

## Success Criteria

- `Version3` periodic hardware payload is not `{}`.
- WebQuanLi rejects hardware payloads that contain no device status fields.
- WebQuanLi dashboard no longer sends `disconnect_monitoring` from the online connection badge.
- Local targeted tests pass.
- Nano targeted tests pass after explicit deploy approval.
- WebQuanLi hardware badges reflect the latest Jetson hardware state instead of all red defaults.

---

## Rollback Note

If local tests fail, revert only the files listed in **Files Allowed**.

If Nano runtime gets worse after deployment, restore:

```powershell
ssh nano@192.168.2.17 "cp /home/nano/backup_2026_05_06_hardware_contract/hardware_monitor.py /home/nano/Version3/sensors/hardware_monitor.py && cp /home/nano/backup_2026_05_06_hardware_contract/schemas.py /home/nano/WebQuanLi/app/schemas.py && cp /home/nano/backup_2026_05_06_hardware_contract/control.py /home/nano/WebQuanLi/app/api/control.py && cp /home/nano/backup_2026_05_06_hardware_contract/dashboard.html /home/nano/WebQuanLi/templates/dashboard.html"
```

Then restart WebQuanLi and DrowsiGuard.

