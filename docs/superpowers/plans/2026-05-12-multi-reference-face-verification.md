# Multi-Reference Face Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve same-driver verification for the thesis demo by comparing the live face crop against 3-5 local reference images per RFID and accepting the best score.

**Architecture:** Keep this as a Jetson-side, one-day refinement. `DriverRegistry` remains the owner of `RFID -> local face files`; it keeps the existing `reference.jpg` contract and adds sorted `ref_*.jpg` optional references. `FaceVerifier` loads all valid references for the scanned RFID, compares the live crop against each one, logs the best score, and decides `MATCH`, `LOW_CONFIDENCE`, or `MISMATCH` from that best score.

**Tech Stack:** Python 3, OpenCV if available, existing fallback image similarity, existing Version3 registry and verification flow, pytest.

---

## Current Problem

Current Jetson evidence shows the runtime is not failing because the camera cannot see a face. The log has repeatedly shown:

```text
Fallback score UID=0199190080: 0.798
Verify returned LOW_CONFIDENCE - DEMO_MODE_ALLOW_UNVERIFIED is False. Rejecting session.
```

That means `FaceVerifier` saw a usable face crop and compared it, but the single reference image did not score high enough. The local monitor/audio text is misleading because `LOW_CONFIDENCE` is currently mapped to the `no_face` prompt.

The current verifier uses only:

```text
/home/nano/Version3/storage/driver_faces/RFID_VALUE/reference.jpg
```

That is fragile because the fallback similarity is sensitive to pose, face scale, lighting, crop size, and background.

## Desired Behavior

For each RFID, Jetson can keep:

```text
storage/driver_faces/0199190080/reference.jpg
storage/driver_faces/0199190080/ref_01.jpg
storage/driver_faces/0199190080/ref_02.jpg
storage/driver_faces/0199190080/ref_03.jpg
storage/driver_faces/0199190080/ref_04.jpg
storage/driver_faces/0199190080/ref_05.jpg
```

Verification should compute scores like:

```text
reference.jpg -> 0.764
ref_01.jpg    -> 0.798
ref_02.jpg    -> 0.823
ref_03.jpg    -> 0.790
best          -> 0.823 => MATCH
```

Rules:

- Keep `reference.jpg` backward compatible with existing WebQuanLi sync.
- Do not require WebQuanLi schema or dashboard changes for the first implementation.
- Keep extra local references under the existing RFID directory.
- Sync from WebQuanLi may update `reference.jpg`, but must not delete `ref_*.jpg` while the RFID remains active.
- If all references are missing or unreadable, return `NO_ENROLLMENT`.
- If at least one reference is valid, decide from the best score.
- Keep current threshold configurable through `DROWSIGUARD_FACE_VERIFY_THRESHOLD`.
- Stop using the `no_face` prompt for `LOW_CONFIDENCE`; use the existing `failed_identity` prompt so users are not told the camera missed their face when the real result is low similarity.

## Scope

### In Scope

- Jetson local registry support for multiple reference images.
- Face verifier best-score matching.
- A small helper script for adding a captured image into a numbered reference slot.
- Unit tests for registry paths, best-score verification, and prompt mapping.
- Local validation, then optional Jetson copy and smoke test after approval.

### Out Of Scope

- Deep-learning face embedding model such as FaceNet, ArcFace, or SFace.
- WebQuanLi database migration for storing multiple face images.
- WebQuanLi UI for uploading multiple images per driver.
- Automatic retraining or TensorRT optimization.
- Changing the drowsiness AI pipeline.

## Files And Responsibilities

### Modify

- `Version3/storage/driver_registry.py`
  - Add `reference_paths(rfid_uid)` to return `reference.jpg` plus sorted `ref_*.jpg`.
  - Add `reference_slot_path(rfid_uid, slot)` and `add_reference_file(...)` for the helper script.
  - Preserve `reference.jpg` behavior for existing WebQuanLi sync.

- `Version3/camera/face_verifier.py`
  - Replace single-reference comparison with best-score comparison over `registry.reference_paths(rfid_uid)`.
  - Log `reference_count`, `best_reference`, and `best_score`.
  - Keep current `MATCH`, `MISMATCH`, `LOW_CONFIDENCE`, `NO_ENROLLMENT` result names.

- `Version3/main.py`
  - Change prompt mapping so `LOW_CONFIDENCE` uses `failed_identity`, while `NO_FACE_FRAME` still uses `no_face`.

- `Version3/tests/test_face_registry_sync.py`
  - Add registry-path tests and best-score verification tests.

- `Version3/tests/test_verify_flow.py`
  - Add or update prompt test so `LOW_CONFIDENCE` does not play `no_face`.

### Create

- `Version3/scripts/add_face_reference.py`
  - CLI helper to copy a good captured image into `storage/driver_faces/RFID_VALUE/ref_NN.jpg`.
  - Does not call WebQuanLi.
  - Does not modify the database.

### Do Not Modify

- `WebQuanLi/app/models.py`
- `WebQuanLi/app/api/vehicles.py`
- WebQuanLi database schema
- Jetson launcher/env in the local implementation phase
- Drowsiness classifier, calibration, alert policy, GPS, RFID reader

## Rollback

Before implementation, check:

```powershell
git status --short
```

If the change is not accepted, revert only these files manually from the diff or ask before using destructive git commands:

```text
Version3/storage/driver_registry.py
Version3/camera/face_verifier.py
Version3/main.py
Version3/tests/test_face_registry_sync.py
Version3/tests/test_verify_flow.py
Version3/scripts/add_face_reference.py
```

On Jetson, copy backups before replacing files:

```bash
cp /home/nano/Version3/storage/driver_registry.py /home/nano/Version3/storage/driver_registry.py.bak-multiref
cp /home/nano/Version3/camera/face_verifier.py /home/nano/Version3/camera/face_verifier.py.bak-multiref
cp /home/nano/Version3/main.py /home/nano/Version3/main.py.bak-multiref
```

---

### Task 1: Add Registry Support For Multiple Reference Paths

**Files:**
- Modify: `Version3/storage/driver_registry.py`
- Test: `Version3/tests/test_face_registry_sync.py`

- [ ] **Step 1: Write the failing registry path test**

Add this test method to `FaceRegistrySyncTest` in `Version3/tests/test_face_registry_sync.py`:

```python
    def test_reference_paths_include_primary_and_sorted_extra_references(self):
        driver_dir = Path(config.FACE_DATA_DIR) / "UID-001"
        driver_dir.mkdir(parents=True, exist_ok=True)
        self._write_matrix_file(driver_dir / "reference.jpg", self._make_face())
        self._write_matrix_file(driver_dir / "ref_02.jpg", self._make_face(eye_shift=2))
        self._write_matrix_file(driver_dir / "ref_01.jpg", self._make_face(eye_shift=1))
        self._write_matrix_file(driver_dir / "note.txt", self._make_face(eye_shift=3))

        paths = self.registry.reference_paths("UID-001")

        self.assertEqual(
            [Path(path).name for path in paths],
            ["reference.jpg", "ref_01.jpg", "ref_02.jpg"],
        )
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_face_registry_sync.py::FaceRegistrySyncTest::test_reference_paths_include_primary_and_sorted_extra_references -q
```

Expected:

```text
FAILED ... AttributeError: 'DriverRegistry' object has no attribute 'reference_paths'
```

- [ ] **Step 3: Implement the registry methods**

Add these methods to `DriverRegistry` after `reference_path()`:

```python
    def reference_paths(self, rfid_uid: str) -> list[str]:
        driver_dir = Path(self.driver_dir(rfid_uid))
        paths = []

        primary = Path(self.reference_path(rfid_uid))
        if primary.exists():
            paths.append(primary)

        if driver_dir.exists():
            paths.extend(
                path
                for path in sorted(driver_dir.glob("ref_*.jpg"))
                if path.is_file() and path != primary
            )

        return [str(path) for path in paths]

    def reference_slot_path(self, rfid_uid: str, slot: int) -> str:
        if slot < 1 or slot > 99:
            raise ValueError("reference slot must be between 1 and 99")
        return os.path.join(self.driver_dir(rfid_uid), f"ref_{slot:02d}.jpg")

    def add_reference_file(self, rfid_uid: str, source_path: str, slot: int) -> str:
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(source_path)

        destination = Path(self.reference_slot_path(rfid_uid, slot))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
        return str(destination)
```

- [ ] **Step 4: Run the registry test**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_face_registry_sync.py::FaceRegistrySyncTest::test_reference_paths_include_primary_and_sorted_extra_references -q
```

Expected:

```text
1 passed
```

---

### Task 2: Make FaceVerifier Use Best Score Across References

**Files:**
- Modify: `Version3/camera/face_verifier.py`
- Test: `Version3/tests/test_face_registry_sync.py`

- [ ] **Step 1: Write the failing best-reference test**

Add this test method to `FaceRegistrySyncTest`:

```python
    def test_verify_uses_best_score_from_extra_reference(self):
        driver_dir = Path(config.FACE_DATA_DIR) / "UID-001"
        driver_dir.mkdir(parents=True, exist_ok=True)
        self._write_matrix_file(driver_dir / "reference.jpg", self._make_face(eye_shift=8, background=5))
        self._write_matrix_file(driver_dir / "ref_01.jpg", self._make_face())

        self.registry.upsert_local_driver("UID-001", driver_name="Driver Demo")

        result = self.verifier.verify(self._make_face(), "UID-001")

        self.assertEqual(result, VerifyResult.MATCH)
```

- [ ] **Step 2: Run the test and confirm it fails on current implementation**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_face_registry_sync.py::FaceRegistrySyncTest::test_verify_uses_best_score_from_extra_reference -q
```

Expected:

```text
FAILED ... AssertionError: 'LOW_CONFIDENCE' != 'MATCH'
```

The exact current result may be `MISMATCH` depending on the fallback score, but it must not be `MATCH` before implementation.

- [ ] **Step 3: Refactor the comparison into a helper**

In `Version3/camera/face_verifier.py`, add this helper method before `verify()`:

```python
    def _verify_against_reference(self, reference_path: str, probe_gray):
        reference = self._load_image(reference_path)
        if self._is_empty_image(reference):
            logger.warning(f"Reference image could not be read: {reference_path}")
            return None

        reference_gray = self._prepare_image(reference)
        if reference_gray is None:
            logger.warning(f"Failed to normalize reference image: {reference_path}")
            return None

        if self._should_try_lbph():
            lbph_result = self._verify_with_lbph(reference_gray, probe_gray)
            if lbph_result == VerifyResult.MATCH:
                return {
                    "path": reference_path,
                    "result": VerifyResult.MATCH,
                    "score": 1.0,
                    "method": "lbph",
                }

        score = self._fallback_similarity(reference_gray, probe_gray)
        return {
            "path": reference_path,
            "result": None,
            "score": score,
            "method": "fallback",
        }
```

- [ ] **Step 4: Replace the single-reference block in `verify()`**

Replace this current block:

```python
        reference = self._load_image(self.registry.reference_path(rfid_uid))
        if self._is_empty_image(reference):
            logger.warning(f"Enrollment image for UID={rfid_uid} could not be read")
            return VerifyResult.BLOCKED

        probe_gray = self._prepare_image(face_frame)
        reference_gray = self._prepare_image(reference)
        if probe_gray is None or reference_gray is None:
            logger.warning("Failed to normalize face image for comparison")
            return VerifyResult.LOW_CONFIDENCE

        if self._should_try_lbph():
            lbph_result = self._verify_with_lbph(reference_gray, probe_gray)
            if lbph_result is not None:
                return lbph_result

        score = self._fallback_similarity(reference_gray, probe_gray)
        logger.info(f"[FaceVerifier] Fallback score UID={rfid_uid}: {score:.3f}")
        if score >= config.FACE_VERIFY_THRESHOLD:
            return VerifyResult.MATCH
        if score <= max(0.0, config.FACE_VERIFY_THRESHOLD - 0.18):
            return VerifyResult.MISMATCH
        return VerifyResult.LOW_CONFIDENCE
```

with:

```python
        probe_gray = self._prepare_image(face_frame)
        if probe_gray is None:
            logger.warning("Failed to normalize probe face image for comparison")
            return VerifyResult.LOW_CONFIDENCE

        reference_paths = self.registry.reference_paths(rfid_uid)
        if not reference_paths:
            logger.warning(f"No readable enrollment images found for UID={rfid_uid}")
            return VerifyResult.BLOCKED

        scores = []
        for reference_path in reference_paths:
            score_info = self._verify_against_reference(reference_path, probe_gray)
            if score_info is None:
                continue
            if score_info["result"] == VerifyResult.MATCH:
                logger.info(
                    "[FaceVerifier] LBPH match UID=%s ref=%s refs=%d",
                    rfid_uid,
                    os.path.basename(score_info["path"]),
                    len(reference_paths),
                )
                return VerifyResult.MATCH
            scores.append(score_info)

        if not scores:
            logger.warning(f"No usable enrollment images found for UID={rfid_uid}")
            return VerifyResult.BLOCKED

        best = max(scores, key=lambda item: item["score"])
        logger.info(
            "[FaceVerifier] Best fallback score UID=%s: %.3f ref=%s refs=%d",
            rfid_uid,
            best["score"],
            os.path.basename(best["path"]),
            len(reference_paths),
        )
        if best["score"] >= config.FACE_VERIFY_THRESHOLD:
            return VerifyResult.MATCH
        if best["score"] <= max(0.0, config.FACE_VERIFY_THRESHOLD - 0.18):
            return VerifyResult.MISMATCH
        return VerifyResult.LOW_CONFIDENCE
```

- [ ] **Step 5: Run focused verifier tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_face_registry_sync.py -q
```

Expected:

```text
6 passed
```

The exact count may be higher if additional tests already exist in the file; the command must finish with zero failures.

---

### Task 3: Add A Small Helper For Numbered Reference Images

**Files:**
- Create: `Version3/scripts/add_face_reference.py`
- Test: `Version3/tests/test_face_registry_sync.py`

- [ ] **Step 1: Write the failing registry copy test**

Add this test method to `FaceRegistrySyncTest`:

```python
    def test_add_reference_file_copies_source_to_numbered_slot(self):
        source_dir = Path(self.temp_dir) / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_image = source_dir / "driver.face"
        self._write_matrix_file(source_image, self._make_face())

        destination = self.registry.add_reference_file("UID-001", str(source_image), slot=3)

        self.assertEqual(Path(destination).name, "ref_03.jpg")
        self.assertTrue(Path(destination).exists())
        self.assertEqual(
            [Path(path).name for path in self.registry.reference_paths("UID-001")],
            ["ref_03.jpg"],
        )
```

- [ ] **Step 2: Run the test**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_face_registry_sync.py::FaceRegistrySyncTest::test_add_reference_file_copies_source_to_numbered_slot -q
```

Expected:

```text
1 passed
```

This may already pass after Task 1 because `add_reference_file()` was added there. If it passes, keep the test as coverage.

- [ ] **Step 3: Create the helper script**

Create `Version3/scripts/add_face_reference.py`:

```python
import argparse
from pathlib import Path

from storage.driver_registry import DriverRegistry


def parse_args():
    parser = argparse.ArgumentParser(description="Add a local face reference image for one RFID.")
    parser.add_argument("--rfid", required=True, help="RFID tag, for example 0199190080")
    parser.add_argument("--source", required=True, help="Source image path on this machine")
    parser.add_argument("--slot", type=int, required=True, help="Reference slot number, 1-5 for demo use")
    return parser.parse_args()


def main():
    args = parse_args()
    registry = DriverRegistry()
    destination = registry.add_reference_file(args.rfid, args.source, args.slot)
    print(f"saved {Path(destination).name} for RFID {args.rfid}: {destination}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Compile the helper script**

Run:

```powershell
python -m py_compile Version3/scripts/add_face_reference.py
```

Expected: exit code `0`.

- [ ] **Step 5: Document the Jetson helper command in the final handoff**

Use this command format on Jetson after implementation:

```bash
cd /home/nano/Version3
python3 scripts/add_face_reference.py --rfid 0199190080 --source storage/enrollment_captures/driver_20260512-160556_full.jpg --slot 1
```

Repeat for slots `2` through `5` with different good images.

---

### Task 4: Correct LOW_CONFIDENCE Prompt Mapping

**Files:**
- Modify: `Version3/main.py`
- Test: `Version3/tests/test_verify_flow.py`

- [ ] **Step 1: Write the failing prompt test**

Add this test method near the existing prompt tests in `Version3/tests/test_verify_flow.py`:

```python
    def test_low_confidence_plays_failed_identity_prompt(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        mock_verifier.extract_face.side_effect = lambda frame, bbox: frame
        mock_verifier.verify.return_value = VerifyResult.LOW_CONFIDENCE
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch("time.sleep", return_value=None):
            self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("failed_identity")
        self.verify_rejection_called("verify_error", "reason", "LOW_CONFIDENCE")
```

- [ ] **Step 2: Run the prompt test and confirm it fails**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_verify_flow.py::TestVerifyFlow::test_low_confidence_plays_failed_identity_prompt -q
```

Expected:

```text
FAILED ... Expected verify_error with reason=LOW_CONFIDENCE but not found
```

or:

```text
FAILED ... expected call not found ... failed_identity
```

- [ ] **Step 3: Change failure handling in `main.py`**

In `DrowsiGuard._prompt_for_verify_failure()`, replace:

```python
        if reason in {"NO_FACE_FRAME", "LOW_CONFIDENCE", "UNKNOWN_ERROR"}:
            return "no_face"
```

with:

```python
        if reason == "NO_FACE_FRAME":
            return "no_face"
        if reason in {"LOW_CONFIDENCE", "MISMATCH"}:
            return "failed_identity"
        if reason == "UNKNOWN_ERROR":
            return "failed_identity"
```

In `_verify_driver()`, keep `NO_FACE_FRAME` for the case where `get_good_face_frame()` returns no frame. For `VerifyResult.LOW_CONFIDENCE`, keep the reason as:

```python
reason = "LOW_CONFIDENCE"
```

and send that reason to `_reject_verification(...)`.

- [ ] **Step 4: Run focused verify-flow tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_verify_flow.py -q
```

Expected: all tests in `test_verify_flow.py` pass with zero failures.

---

### Task 5: Run Local Regression Tests

**Files:**
- Validate only; no source changes in this task.

- [ ] **Step 1: Run face registry and verify-flow tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest Version3/tests/test_face_registry_sync.py Version3/tests/test_face_enrollment_metadata.py Version3/tests/test_verify_flow.py -q
```

Expected:

```text
passed
```

with zero failures.

- [ ] **Step 2: Run WebQuanLi registry contract tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_driver_registry_sync.py Version3/tests/test_webquanli_contract.py -q
```

Expected:

```text
passed
```

with zero failures.

- [ ] **Step 3: Compile touched runtime files**

Run:

```powershell
python -m py_compile Version3/storage/driver_registry.py Version3/camera/face_verifier.py Version3/main.py Version3/scripts/add_face_reference.py
```

Expected: exit code `0`.

---

### Task 6: Jetson Deployment And Demo Smoke Test

**Files:**
- Deploy: `Version3/storage/driver_registry.py`
- Deploy: `Version3/camera/face_verifier.py`
- Deploy: `Version3/main.py`
- Deploy: `Version3/scripts/add_face_reference.py`

- [ ] **Step 1: Confirm SSH**

Run from Windows PowerShell:

```powershell
ssh nano@192.168.2.29 "echo SSH_OK && hostname"
```

Expected:

```text
SSH_OK
jetson
```

- [ ] **Step 2: Copy runtime files**

Run:

```powershell
scp Version3\storage\driver_registry.py nano@192.168.2.29:/home/nano/Version3/storage/
scp Version3\camera\face_verifier.py nano@192.168.2.29:/home/nano/Version3/camera/
scp Version3\main.py nano@192.168.2.29:/home/nano/Version3/
scp Version3\scripts\add_face_reference.py nano@192.168.2.29:/home/nano/Version3/scripts/
```

Expected: all `scp` commands exit `0`.

- [ ] **Step 3: Compile on Jetson**

Run:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && python3 -m py_compile storage/driver_registry.py camera/face_verifier.py main.py scripts/add_face_reference.py"
```

Expected: exit code `0`.

- [ ] **Step 4: Add 3-5 good local references for the demo RFID**

Use real filenames from `storage/enrollment_captures/`:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && python3 scripts/add_face_reference.py --rfid 0199190080 --source storage/enrollment_captures/driver_20260512-160556_full.jpg --slot 1"
```

Repeat with different high-quality captures that already existed during the 2026-05-12 Jetson checks:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && python3 scripts/add_face_reference.py --rfid 0199190080 --source storage/enrollment_captures/driver_20260512-125547_full.jpg --slot 2"
ssh nano@192.168.2.29 "cd /home/nano/Version3 && python3 scripts/add_face_reference.py --rfid 0199190080 --source storage/enrollment_captures/driver_20260512-112911_full.jpg --slot 3"
```

If a file is missing, list the available captures and choose another good image:

```powershell
ssh nano@192.168.2.29 "ls -1t /home/nano/Version3/storage/enrollment_captures/*.jpg | head"
```

- [ ] **Step 5: Restart the Jetson manual launcher**

If `main.py` is already running:

```powershell
ssh nano@192.168.2.29 "pkill -TERM -f 'python3 .*main.py' || true"
```

Start through the existing launcher:

```powershell
ssh nano@192.168.2.29 "bash -lc 'nohup /home/nano/start_drowsiguard_full.sh > /home/nano/Version3/logs/start_drowsiguard_multiref.log 2>&1 < /dev/null &'"
```

Expected:

```powershell
ssh nano@192.168.2.29 "pgrep -af '[p]ython3 .*main.py'"
```

prints one `python3 main.py` process.

- [ ] **Step 6: Test correct driver**

Scan RFID `0199190080`, keep face centered for 3 seconds, then read log:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && tail -120 logs/drowsiguard.log | grep -E 'RFID scanned|Best fallback score|LOW_CONFIDENCE|MATCH|VERIFIED|Rejecting session'"
```

Expected correct-driver result:

```text
Best fallback score UID=0199190080: 0.823 ref=ref_02.jpg refs=4
VERIFIED
```

or a state transition into `RUNNING`.

- [ ] **Step 7: Test wrong driver**

Scan RFID `0199190080` but put a different person's face in front of the camera.

Expected wrong-driver result:

```text
Best fallback score UID=0199190080: 0.612 ref=reference.jpg refs=4
LOW_CONFIDENCE
```

or:

```text
MISMATCH
```

The wrong person must not enter `RUNNING`.

---

## Acceptance Criteria

- Local tests pass with zero failures.
- Jetson process starts with the updated files.
- Correct RFID plus correct face can pass using the best of 3-5 references.
- Wrong face for the same RFID is rejected.
- Log shows `Best fallback score` with reference file name and reference count.
- `LOW_CONFIDENCE` no longer plays the misleading `no_face` prompt.

## Practical Demo Notes

Use 3-5 images that differ slightly:

- one face centered and neutral
- one slightly closer
- one slightly farther
- one with small head tilt
- one under the same room lighting used during demo

Do not use blurry full-body frames. Keep the face large in the frame and avoid captures where the camera points down at the table or background.
