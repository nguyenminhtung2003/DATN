# DrowsiGuard Boundaries Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lam ro ranh gioi trach nhiem trong Version3 va WebQuanLi ma khong lam thay doi hanh vi dang chay tot tren Jetson Nano A02.

**Architecture:** Thuc hien theo huong refactor bao thu: them test contract truoc, tach logic bang wrapper/delegation truoc, giu payload WebSocket va luong runtime hien tai. Moi task phai chay duoc doc lap va co the dung lai neu test fail.

**Tech Stack:** Python 3, pytest, FastAPI/Pydantic trong WebQuanLi, MediaPipe/OpenCV runtime trong Version3, websocket-client, Jetson Nano A02.

---

## Safety Rules

- Khong sua code truoc khi user duyet plan nay.
- Khong deploy len Jetson truoc khi test local pass.
- Neu can SSH Jetson: dung `ssh nano@192.168.2.17`; neu khong ket noi duoc thi hoi lai IP, khong tu doan IP khac.
- `Version3` hien khong co `.git`, nen moi task phai ghi ro file da sua va giu diff nho. `WebQuanLi` co git nhung dang dirty nhieu file; khong revert thay doi san co.
- Refactor va thay doi thuat toan EAR khong duoc tron trong cung mot task lon.

## File Structure Target

- `D:\DATN-testing1\Version3\main.py`
  - Giu vai tro orchestration/startup.
  - Giam dan logic calibration/classifier/verification/payload dang nam trong file nay.
- `D:\DATN-testing1\Version3\ai\threshold_policy.py`
  - Noi duy nhat tinh/normalize nguong EAR/MAR/pitch tu config va calibration profile.
- `D:\DATN-testing1\Version3\ai\session_controller.py`
  - Quan ly DriverCalibrator, DrowsinessClassifier, reset AI session, update metrics, payload calibration/threshold.
- `D:\DATN-testing1\Version3\camera\face_verifier.py`
  - Giu nhiem vu verify/compare face.
  - Sau refactor, enrollment se duoc delegate.
- `D:\DATN-testing1\Version3\camera\face_enrollment.py`
  - Quan ly enroll tu frame Jetson IR va metadata source.
- `D:\DATN-testing1\Version3\storage\driver_registry.py`
  - Giu manifest/cache va them metadata source reference.
- `D:\DATN-testing1\Version3\tests\fixtures\websocket_payloads.py`
  - Fixture payload WebSocket chung cho contract tests.
- `D:\DATN-testing1\WebQuanLi\tests\test_websocket_contract_fixtures.py`
  - Test WebQuanLi parse duoc payload tu fixture chung.
- `D:\DATN-testing1\Version3\docs\protocol.md`
  - Cap nhat schema/contract optional fields neu co them metadata.

---

## Task 0: Baseline Safety Snapshot

**Files:**
- Read only: `D:\DATN-testing1\Version3`
- Read only: `D:\DATN-testing1\WebQuanLi`

- [ ] **Step 1: Record current working state**

Run:

```powershell
git status --short
```

in `D:\DATN-testing1\WebQuanLi`.

Expected: shows existing dirty files. Do not revert them.

- [ ] **Step 2: Run Version3 focused baseline tests**

Run:

```powershell
python -m pytest tests/test_calibration.py tests/test_drowsiness_classifier.py tests/test_face_registry_sync.py tests/test_webquanli_contract.py -q
```

in `D:\DATN-testing1\Version3`.

Expected: PASS before refactor. If import path in `tests/test_webquanli_contract.py` points to old `CodeEnhance\WebQuanLi`, pause and fix only that test path in Task 1.

- [ ] **Step 3: Run WebQuanLi focused baseline tests**

Run:

```powershell
python -m pytest tests/test_ws_session_flow.py tests/test_api_validation_contract.py tests/test_driver_registry_sync.py -q
```

in `D:\DATN-testing1\WebQuanLi`.

Expected: PASS before refactor. If tests fail from existing dirty work, capture failing names and ask user before continuing.

---

## Task 1: Centralize WebSocket Contract Fixtures

**Files:**
- Create: `D:\DATN-testing1\Version3\tests\fixtures\websocket_payloads.py`
- Create: `D:\DATN-testing1\Version3\tests\fixtures\__init__.py`
- Modify: `D:\DATN-testing1\Version3\tests\test_webquanli_contract.py`
- Create: `D:\DATN-testing1\WebQuanLi\tests\test_websocket_contract_fixtures.py`
- Modify: `D:\DATN-testing1\Version3\docs\protocol.md`

- [ ] **Step 1: Write failing Version3 fixture import test**

Add a test in `Version3\tests\test_webquanli_contract.py` that imports:

```python
from tests.fixtures.websocket_payloads import (
    alert_payload,
    hardware_payload,
    verify_snapshot_payload,
)
```

Expected initial failure: `ModuleNotFoundError: No module named 'tests.fixtures'`.

- [ ] **Step 2: Run failing Version3 contract test**

Run:

```powershell
python -m pytest tests/test_webquanli_contract.py -q
```

Expected: FAIL because fixture module does not exist.

- [ ] **Step 3: Create shared fixture payloads**

Create fixture functions returning current-compatible payloads:

```python
def alert_payload():
    return {
        "level": "DANGER",
        "ear": 0.2,
        "mar": 0.4,
        "pitch": -12.0,
        "perclos": 0.5,
        "ai_state": "DROWSY",
        "ai_confidence": 0.9,
        "ai_reason": "classifier",
    }


def hardware_payload():
    return {
        "power": True,
        "cellular": True,
        "gps": False,
        "camera": True,
        "rfid": True,
        "speaker": True,
        "camera_ok": True,
        "rfid_reader_ok": True,
        "gps_uart_ok": True,
        "gps_fix_ok": False,
        "bluetooth_adapter_ok": True,
        "bluetooth_speaker_connected": False,
        "speaker_output_ok": True,
        "websocket_ok": True,
        "queue_pending": 0,
        "details": {"rfid_reason": "OPEN_OK"},
    }


def verify_snapshot_payload():
    return {
        "rfid_tag": "UID-123",
        "status": "VERIFIED",
        "message": "Face verification matched registered driver",
        "timestamp": 1710000000.0,
    }
```

- [ ] **Step 4: Add WebQuanLi fixture validation test**

In `WebQuanLi\tests\test_websocket_contract_fixtures.py`, import the fixture file by absolute workspace path and validate with:

```python
from app.schemas import AlertData, HardwareData, VerifySnapshotData


def test_webquanli_accepts_version3_alert_fixture(payloads):
    AlertData(**payloads.alert_payload())


def test_webquanli_accepts_version3_hardware_fixture(payloads):
    HardwareData(**payloads.hardware_payload())


def test_webquanli_accepts_version3_verify_snapshot_fixture(payloads):
    VerifySnapshotData(**payloads.verify_snapshot_payload())
```

- [ ] **Step 5: Run both contract test sets**

Run in `Version3`:

```powershell
python -m pytest tests/test_webquanli_contract.py -q
```

Run in `WebQuanLi`:

```powershell
python -m pytest tests/test_websocket_contract_fixtures.py -q
```

Expected: PASS.

---

## Task 2: Create Canonical Threshold Policy Without Changing Behavior

**Files:**
- Create: `D:\DATN-testing1\Version3\ai\threshold_policy.py`
- Create: `D:\DATN-testing1\Version3\tests\test_threshold_policy.py`
- Modify: `D:\DATN-testing1\Version3\ai\calibration.py`
- Modify: `D:\DATN-testing1\Version3\ai\drowsiness_classifier.py`
- Modify: `D:\DATN-testing1\Version3\alerts\alert_manager.py`

- [ ] **Step 1: Write failing tests for current threshold behavior**

Create tests that assert:

```python
from ai.calibration import CalibrationProfile
from ai.threshold_policy import ThresholdPolicy


def test_threshold_policy_uses_profile_thresholds():
    profile = CalibrationProfile(
        valid=True,
        reason="OK",
        ear_open_median=0.29,
        mar_closed_median=0.12,
        pitch_neutral=0.0,
        ear_closed_threshold=0.24,
        mar_yawn_threshold=0.45,
        pitch_down_threshold=-15.0,
        sample_count=40,
    )

    thresholds = ThresholdPolicy.from_profile(profile).to_dict()

    assert thresholds == {
        "ear_closed": 0.24,
        "mar_yawn": 0.45,
        "pitch_down": -15.0,
    }
```

Expected initial failure: `ModuleNotFoundError: No module named 'ai.threshold_policy'`.

- [ ] **Step 2: Run failing threshold tests**

Run:

```powershell
python -m pytest tests/test_threshold_policy.py -q
```

Expected: FAIL because `ThresholdPolicy` does not exist.

- [ ] **Step 3: Implement behavior-preserving ThresholdPolicy**

Create a small class that only reads existing `CalibrationProfile` fields and config fallback values. No adaptive threshold tuning in this task.

- [ ] **Step 4: Replace duplicate threshold dictionary creation**

Use `ThresholdPolicy.from_profile(profile).to_dict()` in:

- `DrowsinessClassifier._thresholds()`
- `DrowsiGuard._ai_thresholds_payload()`
- `AlertManager` threshold setup

Keep public payload shape exactly:

```python
{
    "ear_closed": float_value,
    "mar_yawn": float_value,
    "pitch_down": float_value,
}
```

- [ ] **Step 5: Run focused AI tests**

Run:

```powershell
python -m pytest tests/test_threshold_policy.py tests/test_calibration.py tests/test_drowsiness_classifier.py tests/test_alert_ai_state.py -q
```

Expected: PASS.

---

## Task 3: Extract AI Session Controller From Version3 main.py

**Files:**
- Create: `D:\DATN-testing1\Version3\ai\session_controller.py`
- Create: `D:\DATN-testing1\Version3\tests\test_ai_session_controller.py`
- Modify: `D:\DATN-testing1\Version3\main.py`
- Modify: `D:\DATN-testing1\Version3\tests\test_main_plan_completion.py`
- Modify: `D:\DATN-testing1\Version3\tests\test_runtime_status.py`

- [ ] **Step 1: Write failing controller tests**

Test the controller without camera/OpenCV:

```python
from ai.session_controller import AiSessionController
from ai.drowsiness_classifier import AIState


def sample_metrics(ear=0.29, mar=0.12, pitch=0.0):
    class Metrics:
        face_present = True
        face_bbox = (100, 80, 220, 230)
        left_ear = ear
        right_ear = ear
        ear_used = ear
        face_quality = {"usable": True, "reason": "OK"}
        eye_quality = {"usable": True, "selected": "both", "reason": "OK"}
    metrics = Metrics()
    metrics.ear = ear
    metrics.mar = mar
    metrics.pitch = pitch
    return metrics


def test_ai_session_controller_reset_starts_collecting():
    controller = AiSessionController(target_fps=10)

    controller.reset_session()

    assert controller.last_result["state"] == AIState.UNKNOWN
    assert controller.calibration_payload()["reason"] in ("COLLECTING", "NOT_ENOUGH_SAMPLES")


def test_ai_session_controller_update_returns_classifier_result():
    controller = AiSessionController(target_fps=10)

    result = controller.update(sample_metrics(), perclos=0.0)

    assert "state" in result
    assert "thresholds" in result
```

Expected initial failure: `ModuleNotFoundError: No module named 'ai.session_controller'`.

- [ ] **Step 2: Run failing controller tests**

Run:

```powershell
python -m pytest tests/test_ai_session_controller.py -q
```

Expected: FAIL because controller does not exist.

- [ ] **Step 3: Implement AiSessionController by moving logic, not rewriting**

Move these responsibilities from `DrowsiGuard` into `AiSessionController`:

- create/reset `DriverCalibrator`
- hold calibration profile
- call `DrowsinessClassifier.update()`
- expose `thresholds_payload()`
- expose `calibration_payload(session_active=False)`

Keep `DrowsiGuard` methods as thin delegating wrappers first, so existing tests and callers still work.

- [ ] **Step 4: Wire main.py to controller**

In `DrowsiGuard.__init__`, create:

```python
self.ai_session = AiSessionController(
    classifier=self.ai_classifier,
    calibrator=self.calibrator,
)
```

Then delegate:

- `_reset_ai_session_state()`
- `_update_calibration_from_metrics()`
- `_ai_thresholds_payload()`
- `_calibration_payload()`

- [ ] **Step 5: Run main/runtime focused tests**

Run:

```powershell
python -m pytest tests/test_ai_session_controller.py tests/test_main_plan_completion.py tests/test_runtime_status.py tests/test_drowsiness_classifier.py -q
```

Expected: PASS. Runtime payload keys must stay unchanged.

---

## Task 4: Separate Face Enrollment Metadata From Face Verification

**Files:**
- Create: `D:\DATN-testing1\Version3\camera\face_enrollment.py`
- Create: `D:\DATN-testing1\Version3\tests\test_face_enrollment_metadata.py`
- Modify: `D:\DATN-testing1\Version3\camera\face_verifier.py`
- Modify: `D:\DATN-testing1\Version3\storage\driver_registry.py`
- Modify: `D:\DATN-testing1\Version3\tests\test_face_registry_sync.py`

- [ ] **Step 1: Write failing metadata tests**

Add tests that assert local Jetson enrollment writes source metadata:

```python
def test_enroll_from_jetson_frame_records_ir_source(verifier):
    face = make_face_matrix()

    assert verifier.enroll_driver("UID-001", face, driver_name="Driver Demo")

    manifest = verifier.registry.load_manifest()
    driver = manifest["drivers"][0]
    assert driver["rfid_tag"] == "UID-001"
    assert driver["reference_source"] == "jetson_ir"
    assert driver["reference_role"] == "primary"
```

Expected initial failure: missing `reference_source` and `reference_role`.

- [ ] **Step 2: Run failing face registry tests**

Run:

```powershell
python -m pytest tests/test_face_registry_sync.py tests/test_face_enrollment_metadata.py -q
```

Expected: FAIL on new metadata assertions.

- [ ] **Step 3: Add metadata to DriverRegistry without changing verify**

Update manifest entries to include:

```python
{
    "reference_source": "jetson_ir",
    "reference_role": "primary",
}
```

for local enrollments, and:

```python
{
    "reference_source": "webquanli_sync",
    "reference_role": "fallback",
}
```

for WebQuanLi synced images unless the manifest explicitly says the image was captured from Jetson IR.

- [ ] **Step 4: Extract enrollment wrapper**

Create `FaceEnrollmentService` and make `FaceVerifier.enroll_driver()` delegate to it. Keep method names on `FaceVerifier` for backward compatibility.

- [ ] **Step 5: Run verification tests**

Run:

```powershell
python -m pytest tests/test_face_registry_sync.py tests/test_verify_flow.py tests/test_reverify_flow.py -q
```

Expected: PASS. Verification result behavior must remain unchanged.

---

## Task 5: Document WebSocket and Reference Image Boundaries

**Files:**
- Modify: `D:\DATN-testing1\Version3\docs\protocol.md`
- Create: `D:\DATN-testing1\docs\superpowers\specs\2026-04-27-drowsiguard-boundaries.md`

- [ ] **Step 1: Document stable WebSocket payloads**

Add examples for:

- `hardware`
- `alert`
- `verify_snapshot`
- `verify_error`
- `session_start`
- `session_end`

State that added fields must be optional and backward compatible.

- [ ] **Step 2: Document reference image source policy**

Write the source policy:

```text
Primary verification reference should come from Jetson IR camera capture.
WebQuanLi/RGB image sync is allowed as fallback only unless metadata proves Jetson IR origin.
Existing verify payloads do not change.
```

- [ ] **Step 3: Run docs-neutral contract tests**

Run:

```powershell
python -m pytest tests/test_webquanli_contract.py -q
```

in `Version3`.

Expected: PASS.

---

## Task 6: Final Local Verification Before Any Jetson Deployment

**Files:**
- No code changes.

- [ ] **Step 1: Run Version3 focused suite**

Run:

```powershell
python -m pytest tests/test_calibration.py tests/test_drowsiness_classifier.py tests/test_threshold_policy.py tests/test_ai_session_controller.py tests/test_face_registry_sync.py tests/test_webquanli_contract.py -q
```

Expected: PASS.

- [ ] **Step 2: Run WebQuanLi focused suite**

Run:

```powershell
python -m pytest tests/test_ws_session_flow.py tests/test_api_validation_contract.py tests/test_driver_registry_sync.py tests/test_websocket_contract_fixtures.py -q
```

Expected: PASS.

- [ ] **Step 3: Python compile check**

Run:

```powershell
python -m py_compile Version3\main.py Version3\ai\calibration.py Version3\ai\drowsiness_classifier.py Version3\alerts\alert_manager.py Version3\camera\face_verifier.py Version3\storage\driver_registry.py
```

from `D:\DATN-testing1`.

Expected: no output and exit code 0.

- [ ] **Step 4: Ask before Jetson sync**

Ask user before copying files to Jetson. If approved, copy only changed files, then run remote compile.

Expected remote compile command:

```powershell
ssh nano@192.168.2.17 "cd /home/nano/Version3 && python3 -m py_compile main.py ai/calibration.py ai/drowsiness_classifier.py alerts/alert_manager.py camera/face_verifier.py storage/driver_registry.py"
```

If SSH fails, ask user for the correct IP.

---

## Out Of Scope For This Plan

- Changing EAR adaptive math for glasses drivers. That should be a separate plan after the boundary refactor is stable.
- Replacing MediaPipe/OpenCV pipeline.
- Renaming WebSocket message types.
- Rewriting WebQuanLi UI.
- Initializing git inside `Version3` without user approval.

## Self-Review

- Scope coverage: addresses main.py responsibility boundaries, duplicated threshold concept, WebSocket contract sprawl, and face reference source metadata.
- Placeholder scan: no implementation placeholders remain; each task has concrete files, commands, and expected result.
- Type consistency: planned names are stable across tasks: `ThresholdPolicy`, `AiSessionController`, `FaceEnrollmentService`, `reference_source`, `reference_role`.
