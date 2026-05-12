# Fleet Add Vehicle And Soft Delete Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin UI button to create vehicles from the fleet page and an admin delete button that removes drivers from the visible driver list without breaking historical data.

**Architecture:** Reuse the existing FastAPI vehicle/driver API and the existing `/fleet` template. Driver deletion will be a soft delete (`Driver.is_active = False`) so old sessions, alerts, RFID records, and report data remain intact. After a driver is deactivated, WebQuanLi must trigger driver-registry sync to online Jetson devices so the deleted driver is removed from the Jetson face registry on the next sync.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Jinja2 templates, plain JavaScript `fetch`, pytest/unittest with `httpx.ASGITransport`.

---

## Scope

### In Scope

- Add `DELETE /api/drivers/{driver_id}`.
- Soft delete drivers by setting `is_active = False`.
- Hide inactive drivers from `/fleet`.
- Add a `+ Thêm xe` admin button and inline vehicle form on `/fleet`.
- Add a delete icon/button per driver row for admins.
- Trigger registry sync after driver soft delete.
- Add tests for API behavior and fleet UI behavior.

### Out Of Scope

- Hard deleting drivers from the database.
- Deleting old `driver_sessions`, `system_alerts`, or face image files from disk.
- Changing Jetson `Version3` face-verification algorithm.
- Changing database schema.
- Staging, committing, or deploying unless the user explicitly asks.

### Files Allowed To Modify

- `WebQuanLi/app/api/vehicles.py`
- `WebQuanLi/app/api/pages.py`
- `WebQuanLi/templates/fleet.html`
- `WebQuanLi/tests/test_driver_registry_sync.py`
- `WebQuanLi/tests/test_fleet_management.py` if creating a focused fleet UI test is cleaner than extending an existing file.
- `WebQuanLi/tests/test_api_validation_contract.py` only if the delete endpoint test is placed with existing API contract tests.

### Files Forbidden To Modify

- `Version3/**`
- Jetson runtime files under `/home/nano/**`
- Existing database files such as `WebQuanLi/data/*.db`
- Static face images unless a test creates temporary files under a test temp directory.

---

## Current Code Facts

- Vehicle creation API already exists: `POST /api/vehicles` in `WebQuanLi/app/api/vehicles.py`.
- Driver creation/update/upload-face APIs already exist: `POST /api/drivers`, `PUT /api/drivers/{driver_id}`, `POST /api/drivers/{driver_id}/face`.
- There is no `DELETE /api/drivers/{driver_id}` endpoint yet.
- `/fleet` currently renders vehicles and drivers from `WebQuanLi/app/api/pages.py`.
- `Driver.is_active` already exists in `WebQuanLi/app/models.py`.
- Driver registry manifest already filters active drivers with face images, so soft-deleted drivers will disappear from manifest once `is_active = False`.

---

## Task 1: Add Failing API Test For Soft Delete Driver

**Files:**
- Modify: `WebQuanLi/tests/test_driver_registry_sync.py`

- [ ] **Step 1: Add a seeded active driver with face image for delete testing**

In `DriverRegistrySyncTest._seed`, add a driver that has `face_image_path` and return its id:

```python
delete_target = Driver(
    name="Delete Target Driver",
    rfid_tag="RFID-DELETE",
    vehicle_id=vehicle.id,
    face_image_path="/static/faces/driver_delete.jpg",
)
```

Add it to `db.add_all([...])` and return:

```python
"delete_target_id": delete_target.id,
```

- [ ] **Step 2: Add failing delete endpoint test**

Add this test to `DriverRegistrySyncTest`:

```python
def test_soft_delete_driver_removes_from_registry_and_syncs_online_devices(self):
    with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
        "app.ws.jetson_handler.manager.active",
        {
            "jetson-nano-001": object(),
            "jetson-other-002": object(),
        },
        clear=True,
    ):
        delete_response = asyncio.run(
            self._request("DELETE", f"/api/drivers/{self.ids['delete_target_id']}")
        )
        registry_response = asyncio.run(
            self._request("GET", "/api/jetson/jetson-nano-001/driver-registry")
        )

    self.assertEqual(delete_response.status_code, 200)
    self.assertEqual(delete_response.json()["status"], "deleted")

    payload = registry_response.json()
    rfids = {driver["rfid_tag"] for driver in payload["drivers"]}
    self.assertNotIn("RFID-DELETE", rfids)

    self.assertEqual(send_command.await_count, 2)
    sent_by_device = {call.args[0]: call.args[1] for call in send_command.await_args_list}
    self.assertEqual(set(sent_by_device), {"jetson-nano-001", "jetson-other-002"})
    for device_id, command in sent_by_device.items():
        self.assertEqual(command["action"], "sync_driver_registry")
        self.assertTrue(command["manifest_url"].endswith(f"/api/jetson/{device_id}/driver-registry"))
```

- [ ] **Step 3: Run the focused test and verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_driver_registry_sync.py::DriverRegistrySyncTest::test_soft_delete_driver_removes_from_registry_and_syncs_online_devices -q
```

Expected before implementation:

```text
FAILED
```

Expected reason:

```text
405 Method Not Allowed
```

or:

```text
404 Not Found
```

---

## Task 2: Implement Soft Delete Driver Endpoint

**Files:**
- Modify: `WebQuanLi/app/api/vehicles.py`

- [ ] **Step 1: Add a reusable driver lookup helper**

Place this helper near `_get_vehicle_or_404`:

```python
async def _get_driver_or_404(db: AsyncSession, driver_id: int) -> Driver:
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Tai xe khong tim thay")
    return driver
```

- [ ] **Step 2: Add helper to sync all online active vehicle registries**

Place this helper near `_dispatch_driver_registry_sync_for_driver`:

```python
async def _dispatch_driver_registry_sync_to_online_vehicles(request: Request, db: AsyncSession) -> int:
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.is_active.is_(True),
            Vehicle.device_id.is_not(None),
        ).order_by(Vehicle.id)
    )
    vehicles = result.scalars().all()

    sent_count = 0
    for vehicle in vehicles:
        if await _dispatch_driver_registry_sync(request, vehicle):
            sent_count += 1
    return sent_count
```

Reason: registry manifest is global by active driver, so deleting one driver must notify all currently online Jetson devices, not just one assigned vehicle.

- [ ] **Step 3: Reuse `_get_driver_or_404` in existing endpoints**

In `update_driver`, replace the local query block:

```python
result = await db.execute(select(Driver).where(Driver.id == driver_id))
driver = result.scalar_one_or_none()
if not driver:
    raise HTTPException(status_code=404, detail="Tai xe khong tim thay")
```

with:

```python
driver = await _get_driver_or_404(db, driver_id)
```

In `upload_face_image`, replace the same local query block with:

```python
driver = await _get_driver_or_404(db, driver_id)
```

- [ ] **Step 4: Add `DELETE /api/drivers/{driver_id}`**

Add this endpoint after `update_driver` and before `upload_face_image`:

```python
@router.delete("/drivers/{driver_id}")
async def delete_driver(
    driver_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    driver = await _get_driver_or_404(db, driver_id)
    driver.is_active = False
    await db.commit()

    sent_count = await _dispatch_driver_registry_sync_to_online_vehicles(request, db)
    return {
        "status": "deleted",
        "driver_id": driver_id,
        "sync_sent": sent_count,
    }
```

- [ ] **Step 5: Run the focused delete test**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_driver_registry_sync.py::DriverRegistrySyncTest::test_soft_delete_driver_removes_from_registry_and_syncs_online_devices -q
```

Expected:

```text
1 passed
```

---

## Task 3: Add Failing Fleet UI Tests

**Files:**
- Create: `WebQuanLi/tests/test_fleet_management.py`

- [ ] **Step 1: Create test file with isolated DB setup**

Create `WebQuanLi/tests/test_fleet_management.py`:

```python
import asyncio
import sys
import uuid
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Driver, User, Vehicle


class FleetManagementTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"fleet_management_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        admin = User(username="admin", role="admin")
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: admin
        app.dependency_overrides[check_admin] = lambda: admin
        asyncio.run(self._seed())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(
                plate_number="59A-12345",
                name="Xe Demo 01",
                device_id="JETSON-001",
                manager_phone="0901234567",
            )
            active_driver = Driver(name="Active Driver", rfid_tag="RFID-A", is_active=True)
            inactive_driver = Driver(name="Inactive Driver", rfid_tag="RFID-I", is_active=False)
            db.add_all([vehicle, active_driver, inactive_driver])
            await db.commit()

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_fleet_page_has_add_vehicle_and_delete_driver_controls_for_admin(self):
        response = asyncio.run(self._request("GET", "/fleet"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('id="btn-add-vehicle"', html)
        self.assertIn('id="add-vehicle-form"', html)
        self.assertIn("fetch('/api/vehicles'", html)
        self.assertIn("btn-delete-driver", html)
        self.assertIn("fetch(`/api/drivers/${driverId}`", html)

    def test_fleet_page_hides_inactive_drivers(self):
        response = asyncio.run(self._request("GET", "/fleet"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Active Driver", html)
        self.assertNotIn("Inactive Driver", html)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_fleet_management.py -q
```

Expected before implementation:

```text
2 failed
```

Expected reasons:

- missing `btn-add-vehicle`
- inactive driver is still rendered

---

## Task 4: Filter Inactive Drivers From `/fleet`

**Files:**
- Modify: `WebQuanLi/app/api/pages.py`

- [ ] **Step 1: Update fleet driver query**

Find:

```python
drivers_result = await db.execute(select(Driver).order_by(Driver.id))
```

Replace with:

```python
drivers_result = await db.execute(
    select(Driver).where(Driver.is_active.is_(True)).order_by(Driver.id)
)
```

- [ ] **Step 2: Run the inactive-driver fleet test**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_fleet_management.py::FleetManagementTest::test_fleet_page_hides_inactive_drivers -q
```

Expected:

```text
1 passed
```

---

## Task 5: Add Vehicle Form And Driver Delete Button To Fleet Page

**Files:**
- Modify: `WebQuanLi/templates/fleet.html`

- [ ] **Step 1: Add vehicle form above the vehicle table**

Inside the vehicle `<section class="panel">`, directly below the vehicle title, add:

```html
{% if user.role == 'admin' %}
<div class="add-driver-section" id="add-vehicle-section" style="display:none;">
    <h4>➕ Thêm xe mới</h4>
    <form id="add-vehicle-form" class="filter-form">
        <div class="filter-grid">
            <div class="form-group">
                <label>Biển số</label>
                <input type="text" name="plate_number" required placeholder="59A-12345">
            </div>
            <div class="form-group">
                <label>Tên xe</label>
                <input type="text" name="name" required placeholder="Xe Demo 02">
            </div>
            <div class="form-group">
                <label>Device ID</label>
                <input type="text" name="device_id" placeholder="JETSON-002">
            </div>
            <div class="form-group">
                <label>SĐT quản lý</label>
                <input type="text" name="manager_phone" placeholder="0901234567">
            </div>
            <div class="form-group form-group-btn">
                <button type="submit" class="btn btn-primary">💾 Lưu</button>
                <button type="button" class="btn btn-secondary"
                    onclick="document.getElementById('add-vehicle-section').style.display='none'">Hủy</button>
            </div>
        </div>
    </form>
</div>

<button class="btn btn-primary" onclick="document.getElementById('add-vehicle-section').style.display='block'"
    id="btn-add-vehicle" style="margin-bottom: 16px;">
    ➕ Thêm xe
</button>
{% endif %}
```

Keep the styling consistent with the existing `add-driver-section` instead of introducing a new CSS system.

- [ ] **Step 2: Add delete button next to edit/upload face**

In the driver action cell, after the upload face input, add:

```html
<button class="btn-icon btn-delete-driver" data-id="{{ d.id }}" data-name="{{ d.name }}"
    title="Xóa tài xế">🗑️</button>
```

- [ ] **Step 3: Add JavaScript handler for vehicle creation**

At the top of the existing `<script>` block, before the `// Add new driver` handler, add:

```javascript
// Add new vehicle
document.getElementById('add-vehicle-form')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const formData = new FormData(this);
    const data = Object.fromEntries(formData.entries());
    data.device_id = data.device_id || null;
    data.manager_phone = data.manager_phone || null;

    const resp = await fetch('/api/vehicles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });

    if (resp.ok) {
        location.reload();
    } else {
        const err = await resp.json();
        alert('Lỗi: ' + (err.detail || 'Không thể thêm xe'));
    }
});
```

- [ ] **Step 4: Add JavaScript handler for soft deleting driver**

After the edit-driver setup block or before `uploadFace`, add:

```javascript
// Soft delete driver
document.querySelectorAll('.btn-delete-driver').forEach(function (btn) {
    btn.addEventListener('click', async function () {
        const driverId = this.dataset.id;
        const driverName = this.dataset.name || 'tài xế này';
        if (!confirm(`Bạn có chắc muốn xóa ${driverName} khỏi danh sách tài xế?`)) {
            return;
        }

        const resp = await fetch(`/api/drivers/${driverId}`, {
            method: 'DELETE',
        });

        if (resp.ok) {
            location.reload();
        } else {
            const err = await resp.json();
            alert('Lỗi: ' + (err.detail || 'Không thể xóa tài xế'));
        }
    });
});
```

- [ ] **Step 5: Run the fleet UI controls test**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_fleet_management.py::FleetManagementTest::test_fleet_page_has_add_vehicle_and_delete_driver_controls_for_admin -q
```

Expected:

```text
1 passed
```

---

## Task 6: Run Focused Regression Tests

**Files:**
- No code changes.

- [ ] **Step 1: Run fleet and registry tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_fleet_management.py WebQuanLi/tests/test_driver_registry_sync.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: Run API contract tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_api_validation_contract.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 3: Run WebQuanLi/Jetson contract tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_webquanli_contract.py -q
```

Expected:

```text
all tests passed
```

---

## Task 7: Manual Browser Verification

**Files:**
- No code changes.

- [ ] **Step 1: Start WebQuanLi**

Run:

```powershell
cmd /c D:\DATN-testing1\start_webquanli.bat
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 2: Open fleet page**

Open:

```text
http://127.0.0.1:8000/fleet
```

Expected:

- Vehicle panel shows `+ Thêm xe`.
- Driver panel still shows `+ Thêm tài xế`.
- Each driver row has edit, upload-face, and delete buttons.

- [ ] **Step 3: Create a test vehicle**

Use the `+ Thêm xe` form with:

```text
Biển số: 59A-99999
Tên xe: Xe Test Them Moi
Device ID: JETSON-TEST
SĐT quản lý: 0909999999
```

Expected:

- Page reloads.
- New vehicle appears in "Danh sách xe".

- [ ] **Step 4: Delete a test driver**

Click the delete button on a non-essential test driver.

Expected:

- Confirmation appears.
- After confirmation, page reloads.
- Driver no longer appears in "Danh sách tài xế".
- Existing history/statistics pages still load because the driver record was not hard deleted.

---

## Rollback

If anything behaves incorrectly:

```powershell
git diff -- WebQuanLi/app/api/vehicles.py WebQuanLi/app/api/pages.py WebQuanLi/templates/fleet.html WebQuanLi/tests/test_driver_registry_sync.py WebQuanLi/tests/test_fleet_management.py
```

Then revert only the files touched by this plan after confirming with the user. Do not run `git reset --hard`.

---

## Expected Final Result

- Admin can add a vehicle directly from `/fleet`.
- Admin can remove a driver from the visible fleet list.
- Removed drivers are soft-deleted with `is_active = False`.
- Removed drivers disappear from `/fleet` and from driver-registry manifests.
- Jetson online devices receive `sync_driver_registry` command after a driver is removed.
- No historical alert/session data is deleted.
