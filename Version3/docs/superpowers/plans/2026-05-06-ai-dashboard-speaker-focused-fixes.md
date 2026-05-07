# AI Dashboard Speaker Focused Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three confirmed issues in isolated loops: rapid-blink false DROWSY alerts, dashboard alert-log overgrowth, and unclear/non-working dashboard speaker-test buttons.

**Architecture:** Execute one issue per loop with a separate failing test, minimal implementation, targeted verification, user report, and commit. Version3 classifier changes stay inside the classifier/test boundary. WebQuanLi dashboard changes stay inside dashboard query/template/test files. Speaker-test changes stay inside the WebQuanLi control endpoint/admin controls/API tests and do not touch Version3 speaker playback code.

**Tech Stack:** Python, pytest/unittest, Version3 rule-based drowsiness classifier, FastAPI/WebQuanLi, Jinja templates, HTMX, SQLite test databases.

---

## Execution Target

Use this worktree only:

```powershell
D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention
```

Do not mix files from:

```powershell
D:\DATN-testing1\Version3
D:\DATN-testing1\WebQuanLi
```

The local browser target for manual checks is:

```text
http://127.0.0.1:8000/
```

---

## Root Causes Confirmed Before This Plan

### Issue 1: Rapid blink/noise can become false DROWSY

`Version3\ai\drowsiness_classifier.py` currently uses:

```python
if perclos_long >= 0.35 and len(self._perclos_long) >= max(5, int(2.0 * self._target_fps)):
    return AIState.DROWSY, 0.90, "Long PERCLOS %.2f indicates fatigue" % perclos_long, 2
```

This bypasses `config.PERCLOS_THRESHOLD` which defaults to `0.55`, and it allows the long-PERCLOS branch after only about 2 seconds of samples. The user's runtime evidence shows `Long PERCLOS 0.36 indicates fatigue`, matching this branch.

### Issue 2: Dashboard alert log shows too many rows

`WebQuanLi\app\api\dashboard.py` initially loads 20 alerts:

```python
select(SystemAlert).order_by(SystemAlert.timestamp.desc()).limit(20)
```

`WebQuanLi\templates\dashboard.html` then inserts realtime rows with `tbody.insertBefore(...)` and increments the count, but does not remove older rows.

### Issue 3: Dashboard speaker-test buttons appear to do nothing

`WebQuanLi\templates\partials\admin_controls.html` relies on HTMX `hx-post` buttons.

`WebQuanLi\app\api\control.py` only sends a test-alert command when the vehicle WebSocket is active:

```python
if vehicle.device_id and vehicle.device_id in manager.active:
    await manager.send_command(vehicle.device_id, {
        "action": "test_alert",
        "level": level,
        "state": state,
    })
```

If Jetson is offline, the endpoint still returns a new button without a clear delivery failure message. The user sees no sound and no obvious reason.

---

## Global Rules

- Do not edit code before the relevant task's failing test is added and run.
- Do not use `git add .`.
- Do not stage unrelated dirty files.
- Do not commit until that issue's targeted tests pass.
- After each issue commit, report:
  - files changed,
  - test commands and results,
  - commit hash,
  - remaining known risk.
- Do not start the next issue until the previous issue has passed tests and has its own commit.
- Do not deploy to Jetson in this plan. Jetson runtime checks are manual confirmation after local behavior is correct.

---

## Files Allowed

### Issue 1 Only

- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\ai\drowsiness_classifier.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3\tests\test_drowsiness_classifier.py`

### Issue 2 Only

- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\app\api\dashboard.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\templates\dashboard.html`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_dashboard_realtime_context.py`

### Issue 3 Only

- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\app\api\control.py`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\templates\partials\admin_controls.html`
- Modify: `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_api_validation_contract.py`

---

## Files Forbidden

- Do not modify `Version3\camera\face_analyzer.py`.
- Do not modify `Version3\alerts\alert_manager.py`.
- Do not modify `Version3\alerts\speaker.py`.
- Do not modify `Version3\main.py`.
- Do not modify `Version3\ai\threshold_policy.py`.
- Do not modify `Version3\ai\calibration.py`.
- Do not modify WebQuanLi database models or migrations.
- Do not modify WebQuanLi CSS unless a test proves the HTML-only speaker-test status cannot render.
- Do not modify WAV/audio assets.
- Do not modify startup scripts.

---

## Preflight

- [ ] **Step 1: Confirm worktree and dirty files**

Run:

```powershell
git status --short
```

Expected:

```text
The command prints current dirty files. Treat files outside this plan as user/pre-existing changes and do not stage them.
```

- [ ] **Step 2: Confirm test import path works**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py::test_short_low_ear_is_blink_not_alert -q
```

Expected:

```text
1 passed
```

If this fails because dependencies are missing, stop and report the dependency/import failure before editing.

---

## Issue 1 Loop: Reduce False DROWSY From Rapid Blinks

### Task 1.1: Add Rapid-Blink Regression Tests

**Files:**
- Modify: `Version3\tests\test_drowsiness_classifier.py`

- [ ] **Step 1: Add these tests after `test_eyes_closed_becomes_level1_after_0_8s`**

```python
def test_rapid_blink_burst_does_not_trigger_long_perclos_drowsy():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    # 40% closed samples over 3 seconds, but each closure is only 0.4s.
    # This reproduces fast-blink/noise accumulation without sustained eye closure.
    blink_burst = [0.20, 0.20, 0.20, 0.20, 0.29, 0.29, 0.29, 0.29, 0.29, 0.29]
    result = None
    for _ in range(3):
        for ear in blink_burst:
            result = classifier.update(metrics(ear=ear, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.NORMAL
    assert result["alert_hint"] == 0
    assert "Long PERCLOS" not in result["reason"]


def test_sustained_high_perclos_after_window_still_triggers_drowsy():
    classifier = DrowsinessClassifier(profile=profile(ear=0.24), target_fps=10)

    # 60% closed samples over 8 seconds, but no single closure reaches 0.8s.
    # This preserves the intended long-PERCLOS fatigue behavior.
    high_perclos_pattern = [0.20, 0.20, 0.20, 0.20, 0.20, 0.20, 0.29, 0.29, 0.29, 0.29]
    result = None
    for _ in range(8):
        for ear in high_perclos_pattern:
            result = classifier.update(metrics(ear=ear, mar=0.12, pitch=0.0))

    assert result["state"] == AIState.DROWSY
    assert result["alert_hint"] == 2
    assert "Long PERCLOS" in result["reason"]
```

- [ ] **Step 2: Run the new focused tests and confirm the first test fails**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py::test_rapid_blink_burst_does_not_trigger_long_perclos_drowsy Version3\tests\test_drowsiness_classifier.py::test_sustained_high_perclos_after_window_still_triggers_drowsy -q
```

Expected:

```text
test_rapid_blink_burst_does_not_trigger_long_perclos_drowsy fails because current code returns AIState.DROWSY from Long PERCLOS.
test_sustained_high_perclos_after_window_still_triggers_drowsy passes or fails only if the current hard-coded threshold produces an earlier incompatible reason.
```

### Task 1.2: Use Existing PERCLOS Threshold And Window

**Files:**
- Modify: `Version3\ai\drowsiness_classifier.py`

- [ ] **Step 1: Replace the hard-coded long-PERCLOS branch**

Find:

```python
if perclos_long >= 0.35 and len(self._perclos_long) >= max(5, int(2.0 * self._target_fps)):
    return AIState.DROWSY, 0.90, "Long PERCLOS %.2f indicates fatigue" % perclos_long, 2
```

Replace with:

```python
perclos_alert_threshold = float(getattr(config, "PERCLOS_THRESHOLD", 0.55))
perclos_window_sec = float(getattr(config, "PERCLOS_WINDOW", 8.0) or 8.0)
min_perclos_samples = max(5, int(perclos_window_sec * self._target_fps))
if perclos_long >= perclos_alert_threshold and len(self._perclos_long) >= min_perclos_samples:
    return AIState.DROWSY, 0.90, "Long PERCLOS %.2f indicates fatigue" % perclos_long, 2
```

Rationale:

```text
This removes the local 0.35 threshold that contradicts config.PERCLOS_THRESHOLD=0.55.
It also prevents the branch named "Long PERCLOS" from firing after only about 2 seconds.
```

- [ ] **Step 2: Run focused classifier tests**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py::test_rapid_blink_burst_does_not_trigger_long_perclos_drowsy Version3\tests\test_drowsiness_classifier.py::test_sustained_high_perclos_after_window_still_triggers_drowsy -q
```

Expected:

```text
2 passed
```

- [ ] **Step 3: Run full classifier and alert-manager targeted tests**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py Version3\tests\test_alert_ai_state.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 4: Commit Issue 1 only**

Run:

```powershell
git add Version3\ai\drowsiness_classifier.py Version3\tests\test_drowsiness_classifier.py
git commit -m "fix: reduce false drowsy alerts from rapid blinks"
git rev-parse --short HEAD
```

Expected:

```text
A new commit hash is printed. No WebQuanLi files are included in this commit.
```

- [ ] **Step 5: Report Issue 1**

Report:

```text
Issue 1 fixed.
Changed files:
- Version3\ai\drowsiness_classifier.py
- Version3\tests\test_drowsiness_classifier.py
Tests:
- python -m pytest Version3\tests\test_drowsiness_classifier.py Version3\tests\test_alert_ai_state.py -q
Commit:
- <hash> fix: reduce false drowsy alerts from rapid blinks
```

---

## Issue 2 Loop: Show Only 10 Latest Dashboard Alerts

### Task 2.1: Add Dashboard Alert-Log Cap Tests

**Files:**
- Modify: `WebQuanLi\tests\test_dashboard_realtime_context.py`

- [ ] **Step 1: Add this test method inside `DashboardRealtimeContextTest`**

```python
    def test_dashboard_alert_log_is_capped_to_ten_latest_alerts(self):
        async def seed_many_alerts():
            async with self.session_factory() as db:
                vehicle_result = await db.execute(select(Vehicle).where(Vehicle.device_id == self.device_id))
                vehicle = vehicle_result.scalar_one()
                for index in range(12):
                    db.add(SystemAlert(
                        vehicle_id=vehicle.id,
                        alert_type=AlertType.DROWSINESS,
                        alert_level=AlertLevel.LEVEL_1,
                        ear_value=0.20,
                        mar_value=0.10,
                        message=f"alert cap {index:02d}",
                        timestamp=datetime(2026, 5, 6, 12, index, 0, tzinfo=timezone.utc),
                    ))
                await db.commit()

        asyncio.run(seed_many_alerts())

        response = asyncio.run(self._request("GET", "/"))
        alert_section = response.text.split('id="alert-section"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(alert_section.count('class="alert-row'), 10)
        self.assertIn("alert cap 11", alert_section)
        self.assertIn("alert cap 02", alert_section)
        self.assertNotIn("alert cap 01", alert_section)
        self.assertNotIn("alert cap 00", alert_section)
        self.assertIn('id="alert-count">10', alert_section.replace("\n", ""))
```

- [ ] **Step 2: Add this test method inside `DashboardRealtimeContextTest`**

```python
    def test_dashboard_realtime_alert_insert_trims_rows_to_ten(self):
        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("const ALERT_LOG_LIMIT = 10;", response.text)
        self.assertIn("function trimAlertRows()", response.text)
        self.assertIn("rows.slice(ALERT_LOG_LIMIT).forEach(row => row.remove());", response.text)
        self.assertIn("refreshAlertCount();", response.text)
```

- [ ] **Step 3: Run the new focused tests and confirm they fail**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py::DashboardRealtimeContextTest::test_dashboard_alert_log_is_capped_to_ten_latest_alerts WebQuanLi\tests\test_dashboard_realtime_context.py::DashboardRealtimeContextTest::test_dashboard_realtime_alert_insert_trims_rows_to_ten -q
```

Expected:

```text
Both tests fail because the backend currently loads 20 alerts and the template has no trimAlertRows helper.
```

### Task 2.2: Cap Initial Query At 10

**Files:**
- Modify: `WebQuanLi\app\api\dashboard.py`

- [ ] **Step 1: Replace the alert query limit**

Find:

```python
select(SystemAlert).order_by(SystemAlert.timestamp.desc()).limit(20)
```

Replace with:

```python
select(SystemAlert).order_by(SystemAlert.timestamp.desc()).limit(10)
```

- [ ] **Step 2: Run the initial-render cap test**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py::DashboardRealtimeContextTest::test_dashboard_alert_log_is_capped_to_ten_latest_alerts -q
```

Expected:

```text
1 passed
```

### Task 2.3: Trim Realtime Alert Rows To 10

**Files:**
- Modify: `WebQuanLi\templates\dashboard.html`

- [ ] **Step 1: Add the alert-log limit helper before `function addAlertRow(data)`**

Add this block above the comment `// Alert row`:

```javascript
    const ALERT_LOG_LIMIT = 10;

    function refreshAlertCount() {
        const tbody = document.getElementById('alert-log-body');
        const count = document.getElementById('alert-count');
        if (!tbody || !count) return;
        count.textContent = String(tbody.querySelectorAll('tr.alert-row').length);
    }

    function trimAlertRows() {
        const tbody = document.getElementById('alert-log-body');
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll('tr.alert-row'));
        rows.slice(ALERT_LOG_LIMIT).forEach(row => row.remove());
        refreshAlertCount();
    }

    function prependAlertRow(row) {
        const tbody = document.getElementById('alert-log-body');
        if (!tbody) return;
        const emptyRow = tbody.querySelector('td[colspan="6"]');
        if (emptyRow && emptyRow.parentElement) {
            emptyRow.parentElement.remove();
        }
        tbody.insertBefore(row, tbody.firstChild);
        trimAlertRows();
    }
```

- [ ] **Step 2: Update `addAlertRow(data)`**

Find:

```javascript
        tbody.insertBefore(row, tbody.firstChild);
        // Update count
        const count = document.getElementById('alert-count');
        count.textContent = parseInt(count.textContent) + 1;
        // Flash animation
        setTimeout(() => row.classList.remove('alert-new'), 2000);
```

Replace with:

```javascript
        prependAlertRow(row);
        setTimeout(() => row.classList.remove('alert-new'), 2000);
```

- [ ] **Step 3: Update `addMismatchAlert(data)`**

Find:

```javascript
        tbody.insertBefore(row, tbody.firstChild);
        // Trigger red flash on entire page
        document.body.classList.add('mismatch-flash');
```

Replace with:

```javascript
        prependAlertRow(row);
        document.body.classList.add('mismatch-flash');
```

- [ ] **Step 4: Update `addVerifyErrorAlert(data)`**

Find:

```javascript
        tbody.insertBefore(row, tbody.firstChild);

        // Update count
        const count = document.getElementById('alert-count');
        count.textContent = parseInt(count.textContent) + 1;
        // Flash animation
        setTimeout(() => row.classList.remove('alert-new'), 2000);
```

Replace with:

```javascript
        prependAlertRow(row);
        setTimeout(() => row.classList.remove('alert-new'), 2000);
```

- [ ] **Step 5: Run dashboard tests**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py -q
```

Expected:

```text
All dashboard realtime-context tests pass.
```

- [ ] **Step 6: Manual local browser check**

Run:

```powershell
D:\DATN-testing1\start_webquanli.bat
```

Open:

```text
http://127.0.0.1:8000/
```

Expected:

```text
The "Nhat Ky Canh Bao" table shows no more than 10 alert rows after page load.
When new realtime alert rows arrive, older rows are removed so the table remains at 10 rows.
```

- [ ] **Step 7: Commit Issue 2 only**

Run:

```powershell
git add WebQuanLi\app\api\dashboard.py WebQuanLi\templates\dashboard.html WebQuanLi\tests\test_dashboard_realtime_context.py
git commit -m "fix: cap dashboard alert log to latest ten"
git rev-parse --short HEAD
```

Expected:

```text
A new commit hash is printed. No Version3 classifier files are included in this commit.
```

- [ ] **Step 8: Report Issue 2**

Report:

```text
Issue 2 fixed.
Changed files:
- WebQuanLi\app\api\dashboard.py
- WebQuanLi\templates\dashboard.html
- WebQuanLi\tests\test_dashboard_realtime_context.py
Tests:
- python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py -q
Commit:
- <hash> fix: cap dashboard alert log to latest ten
```

---

## Issue 3 Loop: Make Speaker-Test Button Delivery State Clear

### Task 3.1: Add Speaker-Test Endpoint Contract Tests

**Files:**
- Modify: `WebQuanLi\tests\test_api_validation_contract.py`

- [ ] **Step 1: Replace `test_test_alert_rejects_invalid_level_or_state_and_accepts_valid_form` with this version**

```python
    def test_test_alert_rejects_invalid_level_or_state_and_renders_control(self):
        async def run():
            invalid_level = await self._request("POST", "/api/vehicles/1/test", data={"level": "999", "state": "on"})
            invalid_state = await self._request("POST", "/api/vehicles/1/test", data={"level": "1", "state": "start"})
            valid = await self._request("POST", "/api/vehicles/1/test", data={"level": "1", "state": "on"})
            return invalid_level, invalid_state, valid

        invalid_level, invalid_state, valid = asyncio.run(run())

        self.assertEqual(invalid_level.status_code, 400)
        self.assertEqual(invalid_state.status_code, 400)
        self.assertEqual(valid.status_code, 200)
        self.assertIn('id="speaker-test-level-1"', valid.text)
        self.assertIn("hx-post", valid.text)
```

- [ ] **Step 2: Add this offline HTML test inside `ApiValidationContractTest`**

```python
    def test_test_alert_html_reports_offline_when_websocket_missing(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {},
                clear=True,
            ):
                response = await self._request(
                    "POST",
                    "/api/vehicles/1/test",
                    data={"level": "2", "state": "on"},
                )
            return response, send_command

        response, send_command = asyncio.run(run())

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-speaker-test-sent="false"', response.text)
        self.assertIn("Jetson dang offline, chua gui duoc lenh test loa", response.text)
        send_command.assert_not_awaited()
```

- [ ] **Step 3: Add this offline JSON test inside `ApiValidationContractTest`**

```python
    def test_test_alert_json_reports_offline_when_websocket_missing(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {},
                clear=True,
            ):
                response = await self._request(
                    "POST",
                    "/api/vehicles/1/test",
                    data={"level": "2", "state": "on"},
                    headers={"Accept": "application/json"},
                )
            return response, send_command

        response, send_command = asyncio.run(run())

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()["sent"])
        self.assertEqual(response.json()["connection_status"], "offline")
        self.assertEqual(response.json()["message"], "Jetson dang offline, chua gui duoc lenh test loa")
        send_command.assert_not_awaited()
```

- [ ] **Step 4: Add this online command test inside `ApiValidationContractTest`**

```python
    def test_test_alert_sends_command_when_websocket_active(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {"jetson-nano-001": object()},
                clear=True,
            ):
                response = await self._request(
                    "POST",
                    "/api/vehicles/1/test",
                    data={"level": "3", "state": "on"},
                )
            return response, send_command

        response, send_command = asyncio.run(run())

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-speaker-test-sent="true"', response.text)
        self.assertIn("Da gui lenh test loa muc 3", response.text)
        send_command.assert_awaited_once()
        device_id, command = send_command.await_args.args
        self.assertEqual(device_id, "jetson-nano-001")
        self.assertEqual(command, {"action": "test_alert", "level": 3, "state": "on"})
```

- [ ] **Step 5: Run the new focused tests and confirm they fail**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_rejects_invalid_level_or_state_and_renders_control WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_html_reports_offline_when_websocket_missing WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_json_reports_offline_when_websocket_missing WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_sends_command_when_websocket_active -q
```

Expected:

```text
The new tests fail because the current endpoint does not render speaker-test delivery state, does not return JSON offline state for test alerts, and the admin controls do not use per-level targets.
```

### Task 3.2: Render Per-Level Speaker Test Controls

**Files:**
- Modify: `WebQuanLi\app\api\control.py`
- Modify: `WebQuanLi\templates\partials\admin_controls.html`

- [ ] **Step 1: Add helper functions in `control.py` below `_monitoring_payload`**

```python
def _test_alert_payload(device_id: str | None, level: int, state: str, message: str, sent: bool) -> dict:
    return {
        "level": level,
        "state": state,
        "next_state": "off" if state == "on" else "on",
        "connection_status": "online" if sent else "offline",
        "device_id": device_id,
        "message": message,
        "sent": bool(sent),
    }


def _test_alert_button_html(vehicle_id: int, level: int, state: str, message: str | None = None, sent: bool | None = None) -> str:
    next_state = "off" if state == "on" else "on"
    level_labels = {1: "info", 2: "warning", 3: "danger"}
    level_names = {1: "Muc 1", 2: "Muc 2", 3: "Muc 3"}
    btn_class = level_labels.get(level, "info")
    active_class = f"btn btn-{btn_class} active" if state == "on" else f"btn btn-outline-{btn_class}"
    label = f"Tat {level_names[level]}" if state == "on" else f"Bat {level_names[level]}"
    status = ""
    sent_attr = "" if sent is None else f' data-speaker-test-sent="{str(bool(sent)).lower()}"'
    if message:
        status_class = "alert-success" if sent else "alert-warning"
        status = f'<div class="{status_class}" id="speaker-test-status-{level}">{message}</div>'
    return (
        f'<div id="speaker-test-level-{level}" class="speaker-test-control"{sent_attr}>'
        f'<button hx-post="/api/vehicles/{vehicle_id}/test" '
        f'hx-vals=\'{{"level": {level}, "state": "{next_state}"}}\' '
        f'hx-target="#speaker-test-level-{level}" hx-swap="outerHTML" '
        f'class="{active_class}">{label}</button>'
        f'{status}'
        f'</div>'
    )
```

- [ ] **Step 2: Replace the body of `test_alert()` after vehicle lookup**

Find the code from:

```python
if vehicle.device_id and vehicle.device_id in manager.active:
    await manager.send_command(vehicle.device_id, {
        "action": "test_alert",
        "level": level,
        "state": state,
    })

new_state = "off" if state == "on" else "on"
level_labels = {1: "info", 2: "warning", 3: "danger"}
level_names = {1: "Muc 1", 2: "Muc 2", 3: "Muc 3"}
btn_class = level_labels.get(level, "info")

if state == "on":
    return HTMLResponse(
        f'<button hx-post="/api/vehicles/{vehicle_id}/test" '
        f'hx-vals=\'{{"level": {level}, "state": "{new_state}"}}\' '
        f'hx-swap="outerHTML" '
        f'class="btn btn-{btn_class} active">Tat {level_names[level]}</button>'
    )

return HTMLResponse(
    f'<button hx-post="/api/vehicles/{vehicle_id}/test" '
    f'hx-vals=\'{{"level": {level}, "state": "{new_state}"}}\' '
    f'hx-swap="outerHTML" '
    f'class="btn btn-outline-{btn_class}">Bat {level_names[level]}</button>'
)
```

Replace with:

```python
if not vehicle.device_id or vehicle.device_id not in manager.active:
    message = "Jetson dang offline, chua gui duoc lenh test loa"
    if _wants_json(request):
        return JSONResponse(
            _test_alert_payload(vehicle.device_id, level, state, message, sent=False),
            status_code=409,
        )
    return HTMLResponse(
        _test_alert_button_html(vehicle.id, level, "off", message=message, sent=False)
    )

await manager.send_command(vehicle.device_id, {
    "action": "test_alert",
    "level": level,
    "state": state,
})
message = f"Da gui lenh test loa muc {level}" if state == "on" else f"Da gui lenh tat test loa muc {level}"
if _wants_json(request):
    return JSONResponse(_test_alert_payload(vehicle.device_id, level, state, message, sent=True))
return HTMLResponse(_test_alert_button_html(vehicle.id, level, state, message=message, sent=True))
```

- [ ] **Step 3: Replace the speaker-test button block in `admin_controls.html`**

Find the three direct `<button hx-post=...>` controls inside:

```html
<div class="test-buttons">
    ...
</div>
```

Replace that entire inner block with:

```html
    <div class="test-buttons">
        <div id="speaker-test-level-1" class="speaker-test-control">
            <button hx-post="/api/vehicles/{{ vehicle.id if vehicle else 1 }}/test"
                    hx-vals='{"level": 1, "state": "on"}'
                    hx-target="#speaker-test-level-1"
                    hx-swap="outerHTML"
                    class="btn btn-outline-info"
                    id="btn-test-1">
                Bat Muc 1
            </button>
        </div>
        <div id="speaker-test-level-2" class="speaker-test-control">
            <button hx-post="/api/vehicles/{{ vehicle.id if vehicle else 1 }}/test"
                    hx-vals='{"level": 2, "state": "on"}'
                    hx-target="#speaker-test-level-2"
                    hx-swap="outerHTML"
                    class="btn btn-outline-warning"
                    id="btn-test-2">
                Bat Muc 2
            </button>
        </div>
        <div id="speaker-test-level-3" class="speaker-test-control">
            <button hx-post="/api/vehicles/{{ vehicle.id if vehicle else 1 }}/test"
                    hx-vals='{"level": 3, "state": "on"}'
                    hx-target="#speaker-test-level-3"
                    hx-swap="outerHTML"
                    class="btn btn-outline-danger"
                    id="btn-test-3">
                Bat Muc 3
            </button>
        </div>
    </div>
```

- [ ] **Step 4: Run focused speaker-test tests**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_rejects_invalid_level_or_state_and_renders_control WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_html_reports_offline_when_websocket_missing WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_json_reports_offline_when_websocket_missing WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_test_alert_sends_command_when_websocket_active -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Run full API validation contract tests**

Run:

```powershell
python -m pytest WebQuanLi\tests\test_api_validation_contract.py -q
```

Expected:

```text
All API validation contract tests pass.
```

- [ ] **Step 6: Manual local browser check**

Run:

```powershell
D:\DATN-testing1\start_webquanli.bat
```

Open:

```text
http://127.0.0.1:8000/
```

Expected when Jetson is offline:

```text
Clicking Bat Muc 1/2/3 shows "Jetson dang offline, chua gui duoc lenh test loa".
No UI state should imply the speaker test was delivered.
```

Expected when Jetson is online:

```text
Clicking Bat Muc 1/2/3 sends {"action": "test_alert", "level": <level>, "state": "on"} to Jetson.
The button changes to Tat Muc <level> and shows "Da gui lenh test loa muc <level>".
The Jetson Version3 runtime receives the command and calls alert_manager._activate_outputs(level).
```

- [ ] **Step 7: Commit Issue 3 only**

Run:

```powershell
git add WebQuanLi\app\api\control.py WebQuanLi\templates\partials\admin_controls.html WebQuanLi\tests\test_api_validation_contract.py
git commit -m "fix: report dashboard speaker test delivery state"
git rev-parse --short HEAD
```

Expected:

```text
A new commit hash is printed. No Version3 audio/speaker files are included in this commit.
```

- [ ] **Step 8: Report Issue 3**

Report:

```text
Issue 3 fixed.
Changed files:
- WebQuanLi\app\api\control.py
- WebQuanLi\templates\partials\admin_controls.html
- WebQuanLi\tests\test_api_validation_contract.py
Tests:
- python -m pytest WebQuanLi\tests\test_api_validation_contract.py -q
Commit:
- <hash> fix: report dashboard speaker test delivery state
```

---

## Final Verification After All Three Commits

- [ ] **Step 1: Run combined targeted tests**

Run:

```powershell
python -m pytest Version3\tests\test_drowsiness_classifier.py Version3\tests\test_alert_ai_state.py WebQuanLi\tests\test_dashboard_realtime_context.py WebQuanLi\tests\test_api_validation_contract.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 2: Run WebQuanLi import check**

Run:

```powershell
D:\DATN-testing1\start_webquanli.bat --check
```

Expected:

```text
Check OK: WebQuanLi imports successfully.
```

- [ ] **Step 3: Start WebQuanLi and check dashboard**

Run:

```powershell
D:\DATN-testing1\start_webquanli.bat
```

Open:

```text
http://127.0.0.1:8000/
```

Expected:

```text
Dashboard returns 200.
Nhat Ky Canh Bao shows at most 10 rows.
Speaker-test buttons show offline delivery failure when Jetson is disconnected.
Speaker-test buttons deliver test_alert commands when Jetson is connected.
```

- [ ] **Step 4: Confirm commit separation**

Run:

```powershell
git log --oneline -3
git show --name-only --oneline HEAD~2..HEAD
```

Expected:

```text
There are three separate commits:
1. fix: reduce false drowsy alerts from rapid blinks
2. fix: cap dashboard alert log to latest ten
3. fix: report dashboard speaker test delivery state
Each commit contains only files from its issue scope.
```

---

## Rollback Notes

Rollback Issue 1 only:

```powershell
git revert <issue-1-commit>
```

Rollback Issue 2 only:

```powershell
git revert <issue-2-commit>
```

Rollback Issue 3 only:

```powershell
git revert <issue-3-commit>
```

Rollback all three in reverse order:

```powershell
git revert <issue-3-commit>
git revert <issue-2-commit>
git revert <issue-1-commit>
```

---

## Completion Report Template

Use this exact structure after all loops pass:

```text
Completed all three focused fix loops.

Commits:
- <hash1> fix: reduce false drowsy alerts from rapid blinks
- <hash2> fix: cap dashboard alert log to latest ten
- <hash3> fix: report dashboard speaker test delivery state

Verification:
- python -m pytest Version3\tests\test_drowsiness_classifier.py Version3\tests\test_alert_ai_state.py WebQuanLi\tests\test_dashboard_realtime_context.py WebQuanLi\tests\test_api_validation_contract.py -q
- D:\DATN-testing1\start_webquanli.bat --check
- Manual browser check at http://127.0.0.1:8000/

Not changed:
- Version3\camera\face_analyzer.py
- Version3\alerts\alert_manager.py
- Version3\alerts\speaker.py
- Version3\main.py
- WebQuanLi database schema
- WAV/audio assets
```

---

## Self-Review

Spec coverage:

```text
Issue 1 maps to Issue 1 Loop.
Issue 2 maps to Issue 2 Loop.
Issue 3 maps to Issue 3 Loop.
The user's required sequence is encoded: test, report, commit, then next issue.
```

Placeholder scan:

```text
No unresolved placeholder markers or broad deferred-fix instructions. Each code edit has exact target files and replacement snippets.
```

Type and name consistency:

```text
Test function names match the commands.
Helper names are defined before use.
Paths are rooted in the active worktree.
```
