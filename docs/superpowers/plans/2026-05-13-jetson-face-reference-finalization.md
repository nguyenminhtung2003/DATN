# Jetson Face Reference Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the five Jetson-captured driver images into safe multi-reference face slots for RFID `0199190080`, then verify the live face demo without changing the threshold or the main verification policy.

**Architecture:** Keep face references local on Jetson under `storage/driver_faces/<RFID>/`. Fix only the crop helper compatibility issue if needed, generate cropped `ref_01.jpg` to `ref_05.jpg` from known full-frame captures, and verify that `FaceVerifier` uses `reference.jpg + ref_*.jpg` through the existing best-score logic.

**Tech Stack:** Python 3, OpenCV on Jetson Nano, existing `FaceVerifier`, existing `DriverRegistry`, SSH/SCP, pytest, manual RFID/camera demo checklist.

---

## Non-Negotiable Execution Rule

Do not execute all rounds in one pass.

Each round must stop and report:

1. Files changed.
2. Commands run.
3. Automated test result.
4. Jetson/manual test result if included.
5. Pass/fail decision.
6. Known risks left.
7. Rollback note.
8. Explicit question: "Tiep tuc vong tiep theo khong?"

Do not start the next round until the user confirms.

---

## Current Facts

- Jetson target: `nano@192.168.2.29`
- Jetson runtime root: `/home/nano/Version3`
- Demo RFID: `0199190080`
- Current driver reference directory:
  - `/home/nano/Version3/storage/driver_faces/0199190080/reference.jpg`
- New full-frame captures already present:
  - `/home/nano/Version3/storage/enrollment_captures/driver_20260513-141432_full.jpg`
  - `/home/nano/Version3/storage/enrollment_captures/driver_20260513-141456_full.jpg`
  - `/home/nano/Version3/storage/enrollment_captures/driver_20260513-141512_full.jpg`
  - `/home/nano/Version3/storage/enrollment_captures/driver_20260513-141536_full.jpg`
  - `/home/nano/Version3/storage/enrollment_captures/driver_20260513-141558_full.jpg`
- Current blocker:
  - `FaceVerifier.detect_and_crop_face()` crashes on Jetson OpenCV because `cv2.data` is missing.
  - Do not copy the full-frame files directly into `ref_*.jpg` unless crop detection fails and the user explicitly accepts the risk.
- Threshold must remain unchanged:
  - `DROWSIGUARD_FACE_VERIFY_THRESHOLD=0.785`

---

## File Structure

### Files that may be modified

- `D:/DATN-testing1/Version3/camera/face_verifier.py`
  - Responsibility: make `detect_and_crop_face()` robust when Jetson OpenCV lacks `cv2.data`.
- `D:/DATN-testing1/Version3/tests/test_face_crop_compat.py`
  - Responsibility: protect the OpenCV compatibility behavior so the helper does not crash on Jetson-like builds.

### Remote files/directories that may be written after approval

- `/home/nano/Version3/camera/face_verifier.py`
  - Only if Round 1 crop compatibility fix is approved and tests pass.
- `/home/nano/Version3/storage/driver_faces/0199190080/ref_01.jpg`
- `/home/nano/Version3/storage/driver_faces/0199190080/ref_02.jpg`
- `/home/nano/Version3/storage/driver_faces/0199190080/ref_03.jpg`
- `/home/nano/Version3/storage/driver_faces/0199190080/ref_04.jpg`
- `/home/nano/Version3/storage/driver_faces/0199190080/ref_05.jpg`

### Files/directories that must not be modified

- `D:/DATN-testing1/Version3/config.py`
- `D:/DATN-testing1/Version3/main.py`
- `D:/DATN-testing1/WebQuanLi/**`
- `/home/nano/Version3/drowsiguard.env`
- `/home/nano/start_drowsiguard_full.sh`
- `/home/nano/Version3/storage/driver_faces/0199190080/reference.jpg`

---

## Round 0: Read-Only Safety Snapshot

**Goal:** Record current local and Jetson state before creating any new references.

**Files:**
- Read: `D:/DATN-testing1/Version3/camera/face_verifier.py`
- Read: `D:/DATN-testing1/Version3/storage/driver_registry.py`
- Modify: none

- [ ] **Step 1: Confirm local git status**

Run from `D:/DATN-testing1`:

```powershell
git status --short
git branch --show-current
```

Expected:

```text
Current branch is recorded.
Existing modified files are documented.
No unrelated file is reverted.
```

- [ ] **Step 2: Confirm Jetson image inventory**

Run from `D:/DATN-testing1`:

```powershell
ssh nano@192.168.2.29 "find /home/nano/Version3/storage/enrollment_captures -maxdepth 1 -type f -name 'driver_20260513-*_full.jpg' -printf '%TY-%Tm-%Td %TH:%TM %s %f\n' | sort"
```

Expected:

```text
The five 2026-05-13 full-frame capture files are listed.
```

- [ ] **Step 3: Confirm current driver reference directory**

Run from `D:/DATN-testing1`:

```powershell
ssh nano@192.168.2.29 "find /home/nano/Version3/storage/driver_faces/0199190080 -maxdepth 1 -type f -name '*.jpg' -printf '%f\n' | sort"
```

Expected:

```text
reference.jpg
```

**Pass criteria:**
- Five source captures are present.
- Existing `reference.jpg` is present.
- No files were modified.

**Fail criteria:**
- One or more expected source captures are missing.
- RFID directory is missing.
- SSH target is not reachable.

**Rollback:** None; read-only round.

**Stop checkpoint:** Report evidence and wait for approval before Round 1.

---

## Round 1: Local Crop Compatibility Fix

**Goal:** Fix the Jetson OpenCV compatibility issue in the face crop helper, with a small local test before deployment.

**Files:**
- Modify: `D:/DATN-testing1/Version3/camera/face_verifier.py`
- Create: `D:/DATN-testing1/Version3/tests/test_face_crop_compat.py`

- [ ] **Step 1: Add failing compatibility test**

Create `D:/DATN-testing1/Version3/tests/test_face_crop_compat.py`:

```python
import unittest
from unittest.mock import patch

from camera.face_verifier import FaceVerifier


class FaceCropCompatTest(unittest.TestCase):
    def test_detect_and_crop_face_does_not_crash_when_cv2_data_is_missing(self):
        verifier = FaceVerifier()
        image = [[[0, 0, 0] for _ in range(64)] for _ in range(64)]

        class Cv2WithoutData:
            COLOR_BGR2GRAY = 6

            @staticmethod
            def cvtColor(value, _code):
                return value

        with patch("camera.face_verifier.cv2", Cv2WithoutData):
            result = verifier.detect_and_crop_face(image)

        self.assertIsNotNone(result)
```

- [ ] **Step 2: Run the failing test**

Run from `D:/DATN-testing1/Version3`:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_face_crop_compat.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-face-crop-red
```

Expected:

```text
FAIL because detect_and_crop_face tries to read cv2.data when cv2.data is missing.
```

- [ ] **Step 3: Add a safe cascade resolver**

Modify `D:/DATN-testing1/Version3/camera/face_verifier.py` inside `class FaceVerifier`.

Add this helper before `detect_and_crop_face()`:

```python
    @staticmethod
    def _haar_cascade_path():
        data_module = getattr(cv2, "data", None)
        data_dir = getattr(data_module, "haarcascades", "") if data_module is not None else ""
        candidates = []
        if data_dir:
            candidates.append(os.path.join(data_dir, "haarcascade_frontalface_default.xml"))
        candidates.extend([
            "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
            "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
        ])
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None
```

Replace:

```python
        cascade_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        if not cascade_path or not os.path.exists(cascade_path):
            return image
```

With:

```python
        cascade_path = self._haar_cascade_path()
        if not cascade_path:
            return image
```

- [ ] **Step 4: Run local crop test**

Run from `D:/DATN-testing1/Version3`:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_face_crop_compat.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-face-crop-green
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Run focused regression tests**

Run from `D:/DATN-testing1/Version3`:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_face_registry_sync.py tests/test_verify_flow.py tests/test_demo_readiness_script.py tests/test_face_crop_compat.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-face-crop-focused
python -m py_compile camera\face_verifier.py tests\test_face_crop_compat.py
```

Expected:

```text
All selected tests pass.
py_compile exits 0.
```

**Pass criteria:**
- New compatibility test fails before the fix and passes after the fix.
- Existing verification tests still pass.
- No threshold or verification decision logic is changed.

**Fail criteria:**
- Crop helper still crashes when `cv2.data` is missing.
- Existing verifier tests regress.

**Rollback:**
- Revert only:
  - `D:/DATN-testing1/Version3/camera/face_verifier.py`
  - `D:/DATN-testing1/Version3/tests/test_face_crop_compat.py`

**Stop checkpoint:** Report local diff and test evidence. Wait for approval before Round 2.

---

## Round 2: Deploy Crop Fix And Validate The Five Captures

**Goal:** Deploy only the crop compatibility fix to Jetson, then verify that the five full-frame captures produce cropped face outputs.

**Files:**
- Remote modify: `/home/nano/Version3/camera/face_verifier.py`
- Remote write backup: `/home/nano/Version3/camera/face_verifier.py.bak-face-ref-20260513`

- [ ] **Step 1: Backup remote face verifier**

Run from `D:/DATN-testing1`:

```powershell
ssh nano@192.168.2.29 "cp /home/nano/Version3/camera/face_verifier.py /home/nano/Version3/camera/face_verifier.py.bak-face-ref-20260513"
```

Expected:

```text
Command exits 0.
```

- [ ] **Step 2: Copy local crop fix to Jetson**

Run from `D:/DATN-testing1/Version3`:

```powershell
scp camera\face_verifier.py nano@192.168.2.29:/home/nano/Version3/camera/face_verifier.py
```

Expected:

```text
Command exits 0.
```

- [ ] **Step 3: Compile remote file**

Run from `D:/DATN-testing1`:

```powershell
ssh nano@192.168.2.29 "python3 -m py_compile /home/nano/Version3/camera/face_verifier.py"
```

Expected:

```text
Command exits 0.
```

- [ ] **Step 4: Check crop result for each full-frame capture**

Run from `D:/DATN-testing1`:

```powershell
$script = @'
from pathlib import Path
import cv2
from camera.face_verifier import FaceVerifier

capture_dir = Path("storage/enrollment_captures")
paths = sorted(capture_dir.glob("driver_20260513-*_full.jpg"))
verifier = FaceVerifier()
for path in paths:
    img = cv2.imread(str(path))
    if img is None:
        print(f"{path.name}: UNREADABLE")
        continue
    crop = verifier.detect_and_crop_face(img)
    if crop is None or verifier._is_empty_image(crop):
        print(f"{path.name}: NO_FACE full_shape={img.shape}")
        continue
    full_area = img.shape[0] * img.shape[1]
    crop_area = crop.shape[0] * crop.shape[1]
    ratio = crop_area / float(full_area)
    status = "FACE_CROP" if ratio < 0.80 else "FULL_FRAME_FALLBACK"
    print(f"{path.name}: {status} full_shape={img.shape} crop_shape={crop.shape} area_ratio={ratio:.3f}")
'@
$script | ssh nano@192.168.2.29 "cd /home/nano/Version3 && python3 -"
```

Expected:

```text
Five lines are printed.
Preferred: each line says FACE_CROP.
If any line says FULL_FRAME_FALLBACK or NO_FACE, stop and report before writing ref_*.jpg.
```

**Pass criteria:**
- Remote compile passes.
- The five capture files are readable.
- At least three images produce `FACE_CROP`.

**Fail criteria:**
- Remote compile fails.
- All images fall back to full frame.
- Any image is unreadable.

**Rollback:**

```powershell
ssh nano@192.168.2.29 "cp /home/nano/Version3/camera/face_verifier.py.bak-face-ref-20260513 /home/nano/Version3/camera/face_verifier.py"
```

**Stop checkpoint:** Report crop evidence. Wait for approval before Round 3.

---

## Round 3: Generate Reference Slots From Cropped Captures

**Goal:** Write cropped face references into `ref_01.jpg` to `ref_05.jpg` without replacing `reference.jpg`.

**Files:**
- Remote write:
  - `/home/nano/Version3/storage/driver_faces/0199190080/ref_01.jpg`
  - `/home/nano/Version3/storage/driver_faces/0199190080/ref_02.jpg`
  - `/home/nano/Version3/storage/driver_faces/0199190080/ref_03.jpg`
  - `/home/nano/Version3/storage/driver_faces/0199190080/ref_04.jpg`
  - `/home/nano/Version3/storage/driver_faces/0199190080/ref_05.jpg`
- Remote backup directory:
  - `/home/nano/Version3/storage/driver_faces/0199190080/backup-face-ref-20260513/`

- [ ] **Step 1: Backup current reference slot files**

Run from `D:/DATN-testing1`:

```powershell
ssh nano@192.168.2.29 "mkdir -p /home/nano/Version3/storage/driver_faces/0199190080/backup-face-ref-20260513 && cp -n /home/nano/Version3/storage/driver_faces/0199190080/ref_*.jpg /home/nano/Version3/storage/driver_faces/0199190080/backup-face-ref-20260513/ 2>/dev/null || true"
```

Expected:

```text
Command exits 0.
If no ref_*.jpg existed, backup directory remains empty.
```

- [ ] **Step 2: Generate cropped ref slots**

Run from `D:/DATN-testing1`:

```powershell
$script = @'
from pathlib import Path
import cv2

from camera.face_verifier import FaceVerifier
from storage.driver_registry import DriverRegistry

rfid = "0199190080"
sources = [
    Path("storage/enrollment_captures/driver_20260513-141432_full.jpg"),
    Path("storage/enrollment_captures/driver_20260513-141456_full.jpg"),
    Path("storage/enrollment_captures/driver_20260513-141512_full.jpg"),
    Path("storage/enrollment_captures/driver_20260513-141536_full.jpg"),
    Path("storage/enrollment_captures/driver_20260513-141558_full.jpg"),
]

verifier = FaceVerifier()
registry = DriverRegistry()
written = []

for slot, source in enumerate(sources, start=1):
    img = cv2.imread(str(source))
    if img is None:
        raise SystemExit(f"UNREADABLE: {source}")
    crop = verifier.detect_and_crop_face(img)
    if crop is None or verifier._is_empty_image(crop):
        raise SystemExit(f"NO_FACE: {source}")
    full_area = img.shape[0] * img.shape[1]
    crop_area = crop.shape[0] * crop.shape[1]
    ratio = crop_area / float(full_area)
    if ratio >= 0.80:
        raise SystemExit(f"FULL_FRAME_FALLBACK_NOT_ACCEPTED: {source} ratio={ratio:.3f}")
    target = Path(registry.reference_slot_path(rfid, slot))
    target.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(target), crop):
        raise SystemExit(f"WRITE_FAILED: {target}")
    written.append((slot, source.name, target.name, crop.shape, ratio))

for slot, source_name, target_name, shape, ratio in written:
    print(f"slot={slot} source={source_name} target={target_name} crop_shape={shape} area_ratio={ratio:.3f}")
print(f"WROTE {len(written)} reference slots for RFID {rfid}")
'@
$script | ssh nano@192.168.2.29 "cd /home/nano/Version3 && python3 -"
```

Expected:

```text
Five slot lines are printed.
Final line: WROTE 5 reference slots for RFID 0199190080
```

- [ ] **Step 3: Verify registry sees all references**

Run from `D:/DATN-testing1`:

```powershell
$script = @'
from storage.driver_registry import DriverRegistry
registry = DriverRegistry()
paths = registry.reference_paths("0199190080")
print("count=", len(paths))
for path in paths:
    print(path)
'@
$script | ssh nano@192.168.2.29 "cd /home/nano/Version3 && python3 -"
```

Expected:

```text
count= 6
.../reference.jpg
.../ref_01.jpg
.../ref_02.jpg
.../ref_03.jpg
.../ref_04.jpg
.../ref_05.jpg
```

- [ ] **Step 4: Run Jetson smoke checks**

Run from `D:/DATN-testing1`:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode identity-sim && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode hardware"
```

Expected:

```text
identity-sim passes.
hardware passes.
```

**Pass criteria:**
- `reference_paths("0199190080")` returns exactly 6 files.
- `reference.jpg` remains untouched.
- Smoke checks pass.

**Fail criteria:**
- Any `ref_*.jpg` cannot be written.
- Registry sees fewer than 6 references.
- Smoke check fails after writing reference files.

**Rollback:**

```powershell
ssh nano@192.168.2.29 "rm -f /home/nano/Version3/storage/driver_faces/0199190080/ref_*.jpg && cp /home/nano/Version3/storage/driver_faces/0199190080/backup-face-ref-20260513/ref_*.jpg /home/nano/Version3/storage/driver_faces/0199190080/ 2>/dev/null || true"
```

**Stop checkpoint:** Report generated reference slots and smoke test evidence. Wait for approval before Round 4.

---

## Round 4: Live RFID And Camera Demo Validation

**Goal:** Prove that the live demo now uses multi-reference verification under actual Jetson camera conditions.

**Files:**
- Modify: none
- Read logs: `/home/nano/Version3/logs/drowsiguard.log`

- [ ] **Step 1: Start normal runtime path**

Use the same launcher that will be used for the defense demo:

```bash
/home/nano/start_drowsiguard_full.sh
```

Expected:

```text
Runtime starts.
WebQuanLi shows Jetson online.
```

- [ ] **Step 2: Correct RFID + correct face**

Manual action:

```text
Scan RFID 0199190080.
Look at the camera using the normal demo posture.
```

Expected:

```text
Session starts.
Dashboard shows verified/running state.
```

Collect evidence:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && tail -160 logs/drowsiguard.log | grep -E 'Fallback best score|references=|VERIFIED|session_start|LOW_CONFIDENCE|NO_FACE|MISMATCH' || true"
```

Expected log evidence:

```text
Fallback best score UID=0199190080 references=6 best=<reference-or-ref-file> score=<value> threshold=0.785
VERIFIED or session_start appears.
```

- [ ] **Step 3: End session**

Manual action:

```text
Scan RFID 0199190080 again while session is running.
```

Expected:

```text
Session ends.
Dashboard returns to idle/available.
```

- [ ] **Step 4: Repeat correct face once**

Manual action:

```text
Scan RFID 0199190080 again.
Look at the camera.
```

Expected:

```text
Correct driver passes twice in a row without changing threshold.
```

- [ ] **Step 5: No-face rejection**

Manual action:

```text
Scan RFID 0199190080.
Move face out of camera or cover camera view.
```

Expected:

```text
NO_FACE_FRAME appears.
No session_start occurs.
Audio prompt is no_face.
```

- [ ] **Step 6: Low-confidence or poor-angle rejection**

Manual action:

```text
Scan RFID 0199190080.
Keep face visible but use poor angle/lighting.
```

Expected:

```text
LOW_CONFIDENCE appears if the face is visible but score is not high enough.
No session_start occurs.
Audio prompt is failed_identity, not no_face.
```

- [ ] **Step 7: Wrong-face rejection**

Manual action:

```text
Ask a different person to face the camera after scanning RFID 0199190080.
```

Expected:

```text
MISMATCH or LOW_CONFIDENCE appears.
No session_start occurs.
```

**Pass criteria:**
- Correct driver passes twice without threshold changes.
- Log shows `references=6`.
- No-face and low-confidence are distinguishable.
- Wrong face does not start a session.

**Fail criteria:**
- Correct driver still fails repeatedly with `LOW_CONFIDENCE`.
- Log does not show `references=6`.
- Wrong face starts a session.
- Any scenario requires lowering threshold below `0.785`.

**Rollback:**
- Remove generated `ref_*.jpg` or restore from backup.
- Restore `/home/nano/Version3/camera/face_verifier.py.bak-face-ref-20260513` if the crop compatibility fix causes unexpected runtime issues.

**Stop checkpoint:** Report live demo evidence and decide whether to freeze demo state.

---

## Final Demo Freeze Checklist

Use this only after Round 4 passes.

- [ ] Record final threshold: `0.785`.
- [ ] Record active Jetson IP: `192.168.2.29`.
- [ ] Record demo RFID: `0199190080`.
- [ ] Record reference count: `6`.
- [ ] Save log excerpt containing:
  - `references=6`
  - `VERIFIED` or `session_start`
  - `NO_FACE_FRAME`
  - `LOW_CONFIDENCE`
  - `MISMATCH` or wrong-face rejection evidence
  - `session_end`
- [ ] Do not change threshold, camera lighting, reference images, or launcher before the defense unless the full checklist is rerun.

