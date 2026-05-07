# Disable WebQuanLi OTA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable WebQuanLi OTA update from the demo surface while keeping a clear tombstone endpoint that explains updates must be done through NoMachine/SSH.

**Architecture:** Keep the existing control API route so old clients receive a deterministic disabled response instead of a missing-route error. Remove the dashboard upload form so the feature cannot be triggered accidentally during demo. Keep Jetson-side OTA code untouched in this plan because the user only approved WebQuanLi OTA handling.

**Tech Stack:** FastAPI, HTMX/Jinja templates, httpx ASGI tests, SQLAlchemy async SQLite tests.

---

## Current Code Reality

- WebQuanLi currently exposes OTA upload at `D:\DATN-testing1\WebQuanLi\app\api\control.py` route `POST /api/vehicles/{vehicle_id}/update`.
- The route currently accepts `.py` and `.zip`, writes the file to `settings.UPLOAD_DIR`, sends `update_software` over WebSocket if Jetson is online, and writes `OtaAuditLog`.
- The dashboard renders an OTA upload form in `D:\DATN-testing1\WebQuanLi\templates\partials\admin_controls.html`.
- Existing tests in `D:\DATN-testing1\WebQuanLi\tests\test_api_validation_contract.py` expect OTA upload to work and send checksum, so those tests must be changed to expect OTA disabled.
- Dashboard JavaScript listens for `ota_status`, but the handler already checks whether `#upload-status` exists before updating the DOM. This plan does not require changing dashboard JavaScript.

## Files Allowed

- `D:\DATN-testing1\WebQuanLi\app\api\control.py`
- `D:\DATN-testing1\WebQuanLi\templates\partials\admin_controls.html`
- `D:\DATN-testing1\WebQuanLi\tests\test_api_validation_contract.py`
- `D:\DATN-testing1\WebQuanLi\tests\test_dashboard_realtime_context.py`

## Files Forbidden

- `D:\DATN-testing1\Version3\**`
- `D:\DATN-testing1\WebQuanLi\app\models.py`
- `D:\DATN-testing1\WebQuanLi\app\schemas.py`
- `D:\DATN-testing1\WebQuanLi\app\ws\jetson_handler.py`
- `D:\DATN-testing1\WebQuanLi\app\database.py`
- Any deployment archive, stash, backup branch, generated database, or `.tmp` file.

## Acceptance Criteria

- Dashboard no longer renders the OTA file input, OTA upload button, or `/update` upload form.
- `POST /api/vehicles/{vehicle_id}/update` returns HTTP `410 Gone` with a clear message.
- Disabled OTA endpoint does not read upload content, does not create upload files, does not send WebSocket command, and does not create `OtaAuditLog`.
- Existing speaker test controls and monitoring controls still render and work.
- Targeted WebQuanLi tests pass.

---

### Task 1: Change API Contract Tests To Expect Disabled OTA

**Files:**
- Modify: `D:\DATN-testing1\WebQuanLi\tests\test_api_validation_contract.py`

- [ ] **Step 1: Replace the two current OTA upload tests**

In `D:\DATN-testing1\WebQuanLi\tests\test_api_validation_contract.py`, replace these two methods:

```python
    def test_ota_upload_rejects_path_traversal_filename(self):
        async def run():
            return await self._request(
                "POST",
                "/api/vehicles/1/update",
                files={"file": ("../evil.py", b"print('boom')", "text/x-python")},
            )

        response = asyncio.run(run())

        self.assertEqual(response.status_code, 400)
        self.assertIn("filename", response.json()["detail"].lower())

    def test_ota_upload_records_audit_log_and_sends_checksum(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {"jetson-nano-001": object()},
                clear=True,
            ):
                response = await self._request(
                    "POST",
                    "/api/vehicles/1/update",
                    files={"file": ("main.py", b"print('safe update')\n", "text/x-python")},
                )

            async with self.session_factory() as db:
                from sqlalchemy import select

                result = await db.execute(select(OtaAuditLog))
                audit_rows = result.scalars().all()
            return response, send_command, audit_rows

        response, send_command, audit_rows = asyncio.run(run())

        self.assertEqual(response.status_code, 200)
        send_command.assert_awaited_once()
        _, command = send_command.await_args.args
        self.assertEqual(command["action"], "update_software")
        self.assertEqual(command["filename"], "main.py")
        self.assertRegex(command["checksum"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(audit_rows), 1)
        self.assertEqual(audit_rows[0].filename, "main.py")
        self.assertEqual(audit_rows[0].status, "sent")
```

with this single disabled-contract test:

```python
    def test_ota_update_endpoint_is_disabled(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {"jetson-nano-001": object()},
                clear=True,
            ):
                response = await self._request(
                    "POST",
                    "/api/vehicles/1/update",
                    files={"file": ("main.py", b"print('safe update')\n", "text/x-python")},
                )

            async with self.session_factory() as db:
                from sqlalchemy import select

                result = await db.execute(select(OtaAuditLog))
                audit_rows = result.scalars().all()
            upload_file = settings.UPLOAD_DIR / "main.py"
            return response, send_command, audit_rows, upload_file.exists()

        response, send_command, audit_rows, upload_exists = asyncio.run(run())

        self.assertEqual(response.status_code, 410)
        self.assertIn("OTA da bi vo hieu hoa", response.json()["detail"])
        send_command.assert_not_awaited()
        self.assertEqual(audit_rows, [])
        self.assertFalse(upload_exists)
```

- [ ] **Step 2: Run the disabled endpoint test and verify it fails before implementation**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\WebQuanLi'; python -m pytest WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_ota_update_endpoint_is_disabled -q
```

Expected before implementation:

```text
FAILED
E       AssertionError: 200 != 410
```

If the exact failure message differs but the response is not `410`, the failing-test checkpoint is valid.

---

### Task 2: Disable The WebQuanLi OTA Endpoint

**Files:**
- Modify: `D:\DATN-testing1\WebQuanLi\app\api\control.py`

- [ ] **Step 1: Remove OTA-only imports**

At the top of `control.py`, replace:

```python
import hashlib
import io
import re
import zipfile

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
```

with:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
```

- [ ] **Step 2: Remove unused settings and OtaAuditLog imports**

Replace:

```python
from app.config import settings
from app.core.event_bus import event_bus
from app.database import get_db
from app.models import AlertLevel, AlertType, OtaAuditLog, SystemAlert, User, Vehicle
```

with:

```python
from app.core.event_bus import event_bus
from app.database import get_db
from app.models import AlertLevel, AlertType, SystemAlert, User, Vehicle
```

- [ ] **Step 3: Replace OTA helper constants and functions with one disabled message**

Remove this block:

```python
SAFE_UPDATE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ALLOWED_UPDATE_SUFFIXES = {".py", ".zip"}


def _sanitize_update_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not SAFE_UPDATE_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_UPDATE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Chi cho phep file .py hoac .zip")
    return filename


def _validate_update_package(filename: str, content: bytes):
    if filename.endswith(".py"):
        return
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if "manifest.json" not in archive.namelist():
                raise HTTPException(status_code=400, detail="Package OTA phai co manifest.json")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Package OTA khong phai zip hop le")
```

and add this constant below `router = APIRouter(prefix="/api", tags=["control"])`:

```python
OTA_DISABLED_MESSAGE = "OTA da bi vo hieu hoa. Cap nhat Jetson qua NoMachine/SSH."
```

- [ ] **Step 4: Replace the upload route body with the tombstone endpoint**

Replace the whole `upload_ota_code()` route:

```python
@router.post("/vehicles/{vehicle_id}/update")
async def upload_ota_code(
    vehicle_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    filename = _sanitize_update_filename(file.filename)

    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Xe khong tim thay")

    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    _validate_update_package(filename, content)
    checksum = hashlib.sha256(content).hexdigest()
    filepath = settings.UPLOAD_DIR / filename

    async with aiofiles.open(str(filepath), "wb") as f:
        await f.write(content)

    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/static/updates/{filename}"

    status = "stored_offline"
    if vehicle.device_id and vehicle.device_id in manager.active:
        await manager.send_command(vehicle.device_id, {
            "action": "update_software",
            "download_url": download_url,
            "filename": filename,
            "checksum": checksum,
        })
        status = "sent"

    db.add(OtaAuditLog(
        vehicle_id=vehicle.id,
        username=user.username,
        filename=filename,
        checksum=checksum,
        status=status,
        message=f"OTA file saved to {filepath.name}",
    ))
    await db.commit()

    if status == "sent":
        return HTMLResponse(
            f'<div class="alert-success" id="upload-status">'
            f'File <strong>{filename}</strong> da gui den Jetson. Dang cap nhat...</div>'
        )

    return HTMLResponse(
        '<div class="alert-warning" id="upload-status">'
        'File da luu nhung Jetson dang offline. Se cap nhat khi ket noi lai.</div>'
    )
```

with:

```python
@router.post("/vehicles/{vehicle_id}/update")
async def upload_ota_code(
    vehicle_id: int,
    user: User = Depends(check_admin),
):
    raise HTTPException(status_code=410, detail=OTA_DISABLED_MESSAGE)
```

This keeps admin authentication on the route and returns a stable disabled response for any old form, old client, or manual request.

- [ ] **Step 5: Run the disabled endpoint test and verify it passes**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\WebQuanLi'; python -m pytest WebQuanLi\tests\test_api_validation_contract.py::ApiValidationContractTest::test_ota_update_endpoint_is_disabled -q
```

Expected:

```text
1 passed
```

---

### Task 3: Hide OTA Controls From The Dashboard

**Files:**
- Modify: `D:\DATN-testing1\WebQuanLi\tests\test_dashboard_realtime_context.py`
- Modify: `D:\DATN-testing1\WebQuanLi\templates\partials\admin_controls.html`

- [ ] **Step 1: Add a dashboard test for hidden OTA UI**

In `D:\DATN-testing1\WebQuanLi\tests\test_dashboard_realtime_context.py`, add this method inside `DashboardRealtimeContextTest` after `test_dashboard_renders_cached_queue_gps_and_last_seen`:

```python
    def test_dashboard_hides_ota_upload_controls(self):
        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/api/vehicles/1/update", response.text)
        self.assertNotIn('id="ota-file-input"', response.text)
        self.assertNotIn('id="btn-upload"', response.text)
        self.assertNotIn('id="upload-status"', response.text)
        self.assertIn('id="btn-test-1"', response.text)
        self.assertIn('id="btn-test-2"', response.text)
        self.assertIn('id="btn-test-3"', response.text)
```

- [ ] **Step 2: Run the dashboard UI test and verify it fails before template change**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\WebQuanLi'; python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py::DashboardRealtimeContextTest::test_dashboard_hides_ota_upload_controls -q
```

Expected before template change:

```text
FAILED
E       AssertionError: '/api/vehicles/1/update' unexpectedly found
```

If the exact string includes a different vehicle id, the failure is still valid when an OTA update form is present.

- [ ] **Step 3: Remove the OTA upload section from admin controls**

In `D:\DATN-testing1\WebQuanLi\templates\partials\admin_controls.html`, remove this whole block:

```html
<!-- Upload Code OTA -->
<div class="admin-section">
    <h4>ðŸ“¦ Cáº­p nháº­t pháº§n má»m Jetson (.py)</h4>
    <form hx-post="/api/vehicles/{{ vehicle.id if vehicle else 1 }}/update"
          hx-encoding="multipart/form-data"
          hx-target="#upload-status"
          class="upload-form">
        <input type="file" name="file" accept=".py" required id="ota-file-input">
        <button type="submit" class="btn btn-warning" id="btn-upload">
            â¬†ï¸ Ghi Ä‘Ã¨ & Khá»Ÿi Ä‘á»™ng láº¡i
        </button>
    </form>
    <div id="upload-status"></div>
</div>
```

Leave the speaker test section unchanged.

- [ ] **Step 4: Run the dashboard UI test and verify it passes**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\WebQuanLi'; python -m pytest WebQuanLi\tests\test_dashboard_realtime_context.py::DashboardRealtimeContextTest::test_dashboard_hides_ota_upload_controls -q
```

Expected:

```text
1 passed
```

---

### Task 4: Run Focused Regression Tests

**Files:**
- No additional file edits.

- [ ] **Step 1: Run API and dashboard tests affected by the change**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps;D:\DATN-testing1\WebQuanLi'; python -m pytest WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run the WebQuanLi startup check**

Run:

```powershell
D:\DATN-testing1\start_webquanli.bat --check
```

Expected:

```text
Check OK
```

- [ ] **Step 3: Check tracked diff is limited to intended files**

Run:

```powershell
git diff -- WebQuanLi\app\api\control.py WebQuanLi\templates\partials\admin_controls.html WebQuanLi\tests\test_api_validation_contract.py WebQuanLi\tests\test_dashboard_realtime_context.py
```

Expected:

```text
Only the tombstone endpoint, removed OTA UI block, and updated tests are shown.
```

Run:

```powershell
git status --short
```

Expected:

```text
The four intended files may be modified. Existing unrelated untracked files may still appear and must not be staged or deleted by this plan.
```

---

### Task 5: Optional Documentation Alignment For Defense Materials

**Files:**
- Optional modify: `D:\DATN-testing1\docs\giao-trinh-bao-ve\C1_Ly_Thuyet_Nen_Tang.md`
- Optional modify: `D:\DATN-testing1\docs\giao-trinh-bao-ve\C2_Giai_Thich_Code_Quan_Trong.md`
- Optional modify: `D:\DATN-testing1\WebQuanLi\Hướng dẫn.md`
- Optional modify: `D:\DATN-testing1\WebQuanLi\Giao_Trinh_Bao_Ve_Do_An.md`
- Optional modify: `D:\DATN-testing1\WebQuanLi\GIAO_AN_2_WEBQUANLI_BAO_VE.md`
- Optional modify: `D:\DATN-testing1\WebQuanLi\Giai_Thich_Ky_Thuat.md`

- [ ] **Step 1: Search for remaining user-facing OTA claims**

Run:

```powershell
rg -n "OTA|update_software|upload update|Cập nhật từ xa|cap nhat phan mem|cập nhật phần mềm" docs WebQuanLi -S
```

Expected:

```text
The command lists defense and guide sections that still describe OTA as active.
```

- [ ] **Step 2: Decide documentation scope before editing docs**

If the user wants the demo code only, do not edit docs in this task. If the user wants defense material to match the disabled feature, update the listed docs to state:

```text
Trong phien ban demo/final hien tai, OTA tren WebQuanLi da duoc vo hieu hoa vi khong phu hop voi mo hinh van hanh thuc te. Cap nhat Jetson duoc thuc hien truc tiep qua NoMachine/SSH de kiem soat rui ro va tranh upload code tu dashboard.
```

- [ ] **Step 3: Verify no docs claim active OTA after documentation edit**

Run:

```powershell
rg -n "OTA|update_software|upload update|Cập nhật từ xa|cap nhat phan mem|cập nhật phần mềm" docs WebQuanLi -S
```

Expected:

```text
Any remaining OTA references describe it as disabled, historical, or not part of the demo operation.
```

---

## Rollback Notes

- To restore the old UI, recover the removed upload block in `D:\DATN-testing1\WebQuanLi\templates\partials\admin_controls.html`.
- To restore the old endpoint, recover the original helper imports, `_sanitize_update_filename()`, `_validate_update_package()`, and upload route body in `D:\DATN-testing1\WebQuanLi\app\api\control.py`.
- Do not touch `D:\DATN-testing1\Version3\network\ota_handler.py` during rollback unless the user separately approves Jetson-side OTA changes.

## Execution Gate

- Do not edit runtime code until the user explicitly approves execution of this plan.
- Do not run `git add`, `git commit`, or delete generated files unless the user explicitly asks for those actions in the execution turn.
- If the workspace has unrelated dirty or untracked files, leave them alone.

## Completion Criteria

- `POST /api/vehicles/{vehicle_id}/update` returns `410`.
- Dashboard has no OTA upload controls.
- No `update_software` command is sent by WebQuanLi OTA path.
- No upload file is written by the disabled endpoint.
- No `OtaAuditLog` row is created by the disabled endpoint.
- Focused API/dashboard tests pass.
- `start_webquanli.bat --check` passes.
