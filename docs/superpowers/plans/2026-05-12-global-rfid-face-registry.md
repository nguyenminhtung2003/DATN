# Global RFID Face Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Jetson verify driver identity by RFID against the central WebQuanLi driver list, without requiring the driver to be assigned to a specific vehicle.

**Architecture:** Keep FaceVerifier on Jetson unchanged. Change only WebQuanLi registry sync semantics so each active Jetson can receive all active drivers that have a face image. When a face image is uploaded for an unassigned driver, dispatch registry sync to all active online vehicles so the Jetson cache can refresh.

**Tech Stack:** FastAPI, SQLAlchemy async, SQLite, existing WebQuanLi driver registry API, existing Jetson `sync_driver_registry` command.

---

## Current Problem

The current demo data has:

```text
Nguyen Minh Tung
RFID: 0199190080
face_image_path: /static/faces/driver_2.jpg
vehicle_id: null

Le Duy Tung
RFID: 0198883744
face_image_path: null
vehicle_id: null
```

Jetson scans RFID `0199190080`, but reports `NO_ENROLLMENT` because `/api/jetson/JETSON-001/driver-registry` currently filters drivers by:

```python
Driver.vehicle_id == vehicle.id
Driver.is_active.is_(True)
Driver.face_image_path.is_not(None)
```

That means a valid system driver with a valid RFID and uploaded face image is excluded if `vehicle_id` is not set.

## Desired Behavior

The registry should be system-wide for identity verification:

- If a driver is active and has a face image, include the driver in the registry manifest.
- If a driver is active but has no face image, exclude the driver until an image is uploaded.
- If a driver is inactive, exclude the driver.
- Keep the `device_id` check so invalid Jetson devices still get `404`.
- Do not modify Jetson FaceVerifier or the face comparison algorithm.

For the current data:

```text
0199190080 -> Nguyen Minh Tung -> included after sync
0198883744 -> Le Duy Tung -> excluded until face image is uploaded
```

---

## Files And Surfaces

### Modify

- `WebQuanLi/app/api/vehicles.py`
  - Change `_build_driver_registry_manifest()` driver query.
  - Add a helper to dispatch registry sync for a driver upload even when the driver has no assigned vehicle.
  - Use that helper from `upload_face_image()`.

- `WebQuanLi/tests/test_driver_registry_sync.py`
  - Update manifest test to expect active drivers with face images across the system.
  - Add test that an unassigned driver with a newly uploaded face triggers registry sync to online active vehicle devices.
  - Keep existing manual sync behavior test.

### Do Not Modify

- `Version3/main.py`
- `Version3/camera/face_verifier.py`
- `Version3/storage/driver_registry.py`
- WebQuanLi database schema
- WebQuanLi dashboard UI
- Jetson launcher/env files

---

## Rollback

If the change is wrong, revert only these files:

```powershell
git diff -- WebQuanLi/app/api/vehicles.py WebQuanLi/tests/test_driver_registry_sync.py
```

If changes are not committed, restore manually from the diff or ask before using any destructive git command.

No database migration is involved.

---

### Task 1: Update Registry Sync Tests First

**Files:**
- Modify: `WebQuanLi/tests/test_driver_registry_sync.py`

- [ ] **Step 1: Add seeded drivers for the new global behavior**

In `_create_schema_and_seed()`, keep existing drivers and add two more drivers before `db.add_all(...)`:

```python
            unassigned_with_face = Driver(
                name="Unassigned Face Driver",
                rfid_tag="RFID-UNASSIGNED",
                vehicle_id=None,
                face_image_path="/static/faces/driver_unassigned.jpg",
            )
            unassigned_upload_target = Driver(
                name="Unassigned Upload Target",
                rfid_tag="RFID-UP-UNASSIGNED",
                vehicle_id=None,
            )
```

Then update the `db.add_all(...)` call to include them:

```python
            db.add_all([
                assigned,
                no_face,
                other_vehicle_driver,
                inactive,
                upload_target,
                unassigned_with_face,
                unassigned_upload_target,
            ])
```

And return the unassigned upload target id:

```python
            return {
                "vehicle_id": vehicle.id,
                "upload_target_id": upload_target.id,
                "unassigned_upload_target_id": unassigned_upload_target.id,
            }
```

- [ ] **Step 2: Replace the old manifest expectation**

Rename:

```python
    def test_registry_endpoint_returns_only_active_assigned_drivers_with_faces(self):
```

to:

```python
    def test_registry_endpoint_returns_active_drivers_with_faces_without_vehicle_filter(self):
```

Replace the assertion body after `payload = response.json()` with:

```python
        self.assertEqual(payload["device_id"], "jetson-nano-001")

        by_rfid = {driver["rfid_tag"]: driver for driver in payload["drivers"]}
        self.assertEqual(
            set(by_rfid),
            {"RFID-A", "RFID-C", "RFID-UNASSIGNED"},
        )
        self.assertEqual(by_rfid["RFID-A"]["name"], "Assigned Driver")
        self.assertEqual(
            by_rfid["RFID-A"]["face_image_url"],
            "http://test/static/faces/driver_assigned.jpg",
        )
        self.assertEqual(by_rfid["RFID-C"]["name"], "Other Vehicle Driver")
        self.assertEqual(
            by_rfid["RFID-C"]["face_image_url"],
            "http://test/static/faces/driver_other.jpg",
        )
        self.assertEqual(by_rfid["RFID-UNASSIGNED"]["name"], "Unassigned Face Driver")
        self.assertEqual(
            by_rfid["RFID-UNASSIGNED"]["face_image_url"],
            "http://test/static/faces/driver_unassigned.jpg",
        )
        self.assertNotIn("RFID-B", by_rfid)
        self.assertNotIn("RFID-D", by_rfid)
```

This proves:

- Assigned active driver with face is included.
- Other-vehicle active driver with face is included.
- Unassigned active driver with face is included.
- Active driver without face is excluded.
- Inactive driver is excluded.

- [ ] **Step 3: Add test for unassigned upload dispatch**

Add this test after `test_upload_face_triggers_registry_sync_command_for_online_vehicle`:

```python
    def test_upload_face_for_unassigned_driver_syncs_all_online_active_vehicle_registries(self):
        with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
            "app.ws.jetson_handler.manager.active",
            {
                "jetson-nano-001": object(),
                "jetson-other-002": object(),
            },
            clear=True,
        ):
            response = asyncio.run(
                self._request(
                    "POST",
                    f"/api/drivers/{self.ids['unassigned_upload_target_id']}/face",
                    files={"file": ("face.jpg", b"\xff\xd8\xff\xe0demo-image", "image/jpeg")},
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(send_command.await_count, 2)

        calls = send_command.await_args_list
        sent_by_device = {call.args[0]: call.args[1] for call in calls}
        self.assertEqual(set(sent_by_device), {"jetson-nano-001", "jetson-other-002"})
        for device_id, command in sent_by_device.items():
            self.assertEqual(command["action"], "sync_driver_registry")
            self.assertTrue(command["manifest_url"].endswith(f"/api/jetson/{device_id}/driver-registry"))
```

- [ ] **Step 4: Run the target test and confirm it fails before implementation**

Run:

```powershell
python -m pytest WebQuanLi/tests/test_driver_registry_sync.py -q
```

Expected before implementation:

```text
FAILED WebQuanLi/tests/test_driver_registry_sync.py::DriverRegistrySyncTest::test_registry_endpoint_returns_active_drivers_with_faces_without_vehicle_filter
FAILED WebQuanLi/tests/test_driver_registry_sync.py::DriverRegistrySyncTest::test_upload_face_for_unassigned_driver_syncs_all_online_active_vehicle_registries
```

The first failure should show only one driver in the manifest or missing `RFID-C` / `RFID-UNASSIGNED`.
The second failure should show no sync command for the unassigned upload target.

---

### Task 2: Change WebQuanLi Registry Manifest To System-Wide Active Drivers With Faces

**Files:**
- Modify: `WebQuanLi/app/api/vehicles.py`

- [ ] **Step 1: Keep device validation but remove driver vehicle filter**

In `_build_driver_registry_manifest()`, keep this block unchanged:

```python
    vehicle_result = await db.execute(
        select(Vehicle).where(
            Vehicle.device_id == device_id,
            Vehicle.is_active.is_(True),
        )
    )
    vehicle = vehicle_result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Thiet bi khong tim thay")
```

Replace the driver query:

```python
    driver_result = await db.execute(
        select(Driver).where(
            Driver.vehicle_id == vehicle.id,
            Driver.is_active.is_(True),
            Driver.face_image_path.is_not(None),
        ).order_by(Driver.id)
    )
```

with:

```python
    driver_result = await db.execute(
        select(Driver).where(
            Driver.is_active.is_(True),
            Driver.face_image_path.is_not(None),
        ).order_by(Driver.id)
    )
```

This makes identity verification use the central driver list instead of the vehicle assignment.

- [ ] **Step 2: Run the manifest test**

Run:

```powershell
python -m pytest WebQuanLi/tests/test_driver_registry_sync.py::DriverRegistrySyncTest::test_registry_endpoint_returns_active_drivers_with_faces_without_vehicle_filter -q
```

Expected:

```text
1 passed
```

If this fails, inspect the returned `payload["drivers"]`; do not change Jetson code.

---

### Task 3: Dispatch Registry Sync For Unassigned Driver Face Uploads

**Files:**
- Modify: `WebQuanLi/app/api/vehicles.py`

- [ ] **Step 1: Add helper for driver-based sync dispatch**

Add this helper immediately after `_dispatch_driver_registry_sync()`:

```python
async def _dispatch_driver_registry_sync_for_driver(request: Request, db: AsyncSession, driver: Driver) -> bool:
    if driver.vehicle_id:
        vehicle = await _get_vehicle_or_404(db, driver.vehicle_id)
        return await _dispatch_driver_registry_sync(request, vehicle)

    result = await db.execute(
        select(Vehicle).where(
            Vehicle.is_active.is_(True),
            Vehicle.device_id.is_not(None),
        ).order_by(Vehicle.id)
    )
    vehicles = result.scalars().all()

    sent = False
    for vehicle in vehicles:
        sent = await _dispatch_driver_registry_sync(request, vehicle) or sent
    return sent
```

Behavior:

- Assigned driver upload syncs the assigned vehicle exactly like today.
- Unassigned driver upload syncs all active vehicles with a device id that are currently online in `manager.active`.
- Offline devices are skipped by the existing `_dispatch_driver_registry_sync()` guard.

- [ ] **Step 2: Use the helper from upload**

In `upload_face_image()`, replace:

```python
    if driver.vehicle_id:
        vehicle = await _get_vehicle_or_404(db, driver.vehicle_id)
        await _dispatch_driver_registry_sync(request, vehicle)
```

with:

```python
    await _dispatch_driver_registry_sync_for_driver(request, db, driver)
```

- [ ] **Step 3: Run the unassigned upload sync test**

Run:

```powershell
python -m pytest WebQuanLi/tests/test_driver_registry_sync.py::DriverRegistrySyncTest::test_upload_face_for_unassigned_driver_syncs_all_online_active_vehicle_registries -q
```

Expected:

```text
1 passed
```

---

### Task 4: Run Focused WebQuanLi Tests

**Files:**
- Test only.

- [ ] **Step 1: Run registry sync test file**

Run:

```powershell
python -m pytest WebQuanLi/tests/test_driver_registry_sync.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 2: Run related API validation tests**

Run:

```powershell
python -m pytest WebQuanLi/tests/test_api_validation_contract.py WebQuanLi/tests/test_ws_session_flow.py WebQuanLi/tests/test_webquanli_contract.py -q
```

Expected:

```text
passed
```

If unrelated tests fail because WebQuanLi dependencies are missing, report the missing dependency and do not fake a pass.

---

### Task 5: Verify Manifest With Current Demo Data

**Files:**
- No code edits.

- [ ] **Step 1: Start WebQuanLi with the updated code**

Run on Windows:

```powershell
cmd /c "D:\DATN-testing1\start_webquanli.bat"
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 2: Query manifest through Windows localhost**

Run:

```powershell
powershell -Command "(Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/jetson/JETSON-001/driver-registry' -UseBasicParsing -TimeoutSec 5).Content"
```

Expected JSON contains:

```json
{
  "rfid_tag": "0199190080",
  "face_image_url": "http://127.0.0.1:8000/static/faces/driver_2.jpg"
}
```

Expected JSON does not contain:

```json
{
  "rfid_tag": "0198883744"
}
```

because Le Duy Tung has no face image yet.

- [ ] **Step 3: Query manifest through Windows Tailscale IP**

Run:

```powershell
powershell -Command "(Invoke-WebRequest -Uri 'http://100.91.225.22:8000/api/jetson/JETSON-001/driver-registry' -UseBasicParsing -TimeoutSec 5).Content"
```

Expected JSON contains:

```json
{
  "rfid_tag": "0199190080",
  "face_image_url": "http://100.91.225.22:8000/static/faces/driver_2.jpg"
}
```

The Tailscale URL is the one Jetson can download.

---

### Task 6: Sync And Verify On Jetson

**Files:**
- Runtime data generated on Jetson:
  - `/home/nano/Version3/storage/driver_registry.json`
  - `/home/nano/Version3/storage/driver_faces/...`
- No Jetson source code edits.

- [ ] **Step 1: Confirm Jetson can download the manifest and face image**

Run on Jetson:

```bash
curl -sS -m 5 http://100.91.225.22:8000/api/jetson/JETSON-001/driver-registry
curl -I -m 5 http://100.91.225.22:8000/static/faces/driver_2.jpg
```

Expected:

```text
"rfid_tag":"0199190080"
HTTP/1.1 200 OK
content-type: image/jpeg
```

- [ ] **Step 2: Trigger registry sync through the existing Jetson code path**

Preferred if Jetson is connected over WebSocket: upload the face again or call the manual sync endpoint from WebQuanLi session.

If a direct one-off sync is needed for verification, run on Jetson:

```bash
cd /home/nano/Version3
python3 - <<'PY'
from camera.face_verifier import FaceVerifier

manifest_url = "http://100.91.225.22:8000/api/jetson/JETSON-001/driver-registry"
manifest = FaceVerifier().sync_from_manifest_url(manifest_url)
print("drivers", len(manifest.get("drivers", [])))
for driver in manifest.get("drivers", []):
    print(driver.get("rfid_tag"), driver.get("name"), driver.get("reference_image"))
PY
```

Expected:

```text
0199190080 Nguyen Minh Tung
```

- [ ] **Step 3: Confirm local Jetson registry exists**

Run on Jetson:

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("/home/nano/Version3/storage/driver_registry.json")
print("exists", p.exists())
data = json.loads(p.read_text())
for driver in data.get("drivers", []):
    print(driver.get("rfid_tag"), driver.get("name"), driver.get("reference_image"))
PY
find /home/nano/Version3/storage/driver_faces -type f | sed -n '1,20p'
```

Expected:

```text
exists True
0199190080 Nguyen Minh Tung
```

At least one face image file should be present under `driver_faces`.

- [ ] **Step 4: Run identity verification demo**

Start:

```text
/home/nano/Desktop/DrowsiGuard-Full.desktop
```

Then scan RFID:

```text
0199190080
```

Expected:

- Jetson enters `VERIFYING_DRIVER`.
- Camera captures current face.
- If face matches uploaded image: `VERIFIED`, session starts.
- If face does not match: `MISMATCH` or `LOW_CONFIDENCE`, session does not start.

Scan RFID:

```text
0198883744
```

Expected until Le Duy Tung has a face upload:

- `NO_ENROLLMENT`
- Session does not start.

---

## Stop Conditions

Stop and report before changing more code if any of these happen:

- Manifest endpoint for `JETSON-001` returns `404`.
- Manifest contains `0198883744` before Le Duy Tung has a face image.
- Manifest contains inactive drivers.
- Jetson cannot download `http://100.91.225.22:8000/static/faces/driver_2.jpg`.
- Jetson registry sync downloads the manifest but fails to save `driver_registry.json`.
- Face verification still reports `NO_ENROLLMENT` after local registry contains `0199190080`.

## Expected Outcome

After implementation and sync:

```text
RFID 0199190080 -> loads Nguyen Minh Tung reference image -> camera verifies identity.
RFID 0198883744 -> no face image yet -> NO_ENROLLMENT until image is uploaded.
```

This keeps the demo behavior aligned with the intended rule:

```text
RFID belongs to a driver in the central system. Face ID verifies that the person currently in front of the camera matches that RFID.
```

## Self-Review

- Scope is limited to WebQuanLi registry sync and tests.
- No Jetson algorithm or FaceVerifier source changes are planned.
- No schema migration is needed.
- The plan handles the current Nguyen Minh Tung case and the future Le Duy Tung upload case.
- Verification uses both local tests and real Jetson registry artifacts.
