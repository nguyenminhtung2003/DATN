# Nano MediaPipe Protobuf Launch Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `webquanli-history-timezone-retention/Version3` build import `main.py` and run targeted tests on Jetson Nano A02 without changing drowsiness/EAR behavior.

**Architecture:** Keep the current Version3 application behavior intact. Add a narrow compatibility wrapper around optional MediaPipe import so Jetson's protobuf mismatch is patched before MediaPipe loads, and update only test harness code that is not Python 3.6-safe. Treat WebQuanLi contract tests as an integration test requiring the sibling `WebQuanLi` folder on Nano.

**Tech Stack:** Python 3.6 on Jetson Nano, MediaPipe, google protobuf, pytest, SSH/SCP deployment.

---

## Root Cause Summary

Observed on Jetson Nano after deploying `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3` to `/home/nano/Version3`:

```text
from main import DrowsiGuard
main.py:32: in <module>
    from camera.face_analyzer import FaceAnalyzer
camera/face_analyzer.py:21: in <module>
    import mediapipe as mp
...
AttributeError: module 'google.protobuf.descriptor' has no attribute '_internal_create_key'
```

The code catches only `ImportError` around `import mediapipe`. On this Nano, MediaPipe is installed, but import fails with `AttributeError` because its generated protobuf modules expect `google.protobuf.descriptor._internal_create_key`. The failure happens during module import, before `main.py` can start and before tests that import `main.py` can collect.

Known working pattern from another worktree: patch `google.protobuf.descriptor._internal_create_key` before importing MediaPipe, and wrap optional MediaPipe import so non-ImportError dependency failures do not crash module import.

---

## File Structure

- Modify: `camera/face_analyzer.py`
  - Owns optional imports for `numpy`, `cv2`, and `mediapipe`.
  - Add protobuf descriptor compatibility shim and optional MediaPipe import helper.
  - Keep `FaceAnalyzer.__init__` responsible for failing when MediaPipe is truly unavailable at runtime.
- Modify: `tests/test_mediapipe_compat.py`
  - Add regression coverage for MediaPipe import failures caused by protobuf descriptor mismatch.
- Modify: `tests/test_python36_compat.py`
  - Make the compatibility test itself runnable on Python 3.6 by avoiding `ast.parse(feature_version=...)` on Python 3.6.
- No code change: `WebQuanLi/`
  - For contract tests on Nano, deploy the sibling worktree folder to `/home/nano/WebQuanLi`; `tests/test_webquanli_contract.py` expects that path via `Path(__file__).resolve().parents[2] / "WebQuanLi"`.

---

## Task 1: Add Regression Test For Broken MediaPipe Import

**Files:**
- Modify: `tests/test_mediapipe_compat.py`

- [ ] **Step 1: Add failing import-helper test**

At the top of `tests/test_mediapipe_compat.py`, change imports from:

```python
import types

import camera.face_analyzer as face_analyzer
```

to:

```python
import builtins
import types

import camera.face_analyzer as face_analyzer
```

Then add this test before `test_face_analyzer_retries_without_refine_landmarks_for_old_mediapipe`:

```python
def test_optional_mediapipe_import_handles_broken_protobuf(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mediapipe":
            raise AttributeError("module 'google.protobuf.descriptor' has no attribute '_internal_create_key'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    mp, error = face_analyzer._import_optional_mediapipe()

    assert mp is None
    assert isinstance(error, AttributeError)
```

- [ ] **Step 2: Run test to verify it fails**

Run locally from `D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\Version3`:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_mediapipe_compat.py::test_optional_mediapipe_import_handles_broken_protobuf -q
```

Expected: FAIL with:

```text
AttributeError: module 'camera.face_analyzer' has no attribute '_import_optional_mediapipe'
```

- [ ] **Step 3: Commit test if using task commits**

```powershell
git add tests/test_mediapipe_compat.py
git commit -m "test: cover broken mediapipe protobuf import"
```

---

## Task 2: Add Protobuf Descriptor Compatibility Shim

**Files:**
- Modify: `camera/face_analyzer.py`
- Test: `tests/test_mediapipe_compat.py`

- [ ] **Step 1: Replace direct MediaPipe import block**

In `camera/face_analyzer.py`, replace:

```python
try:
    import mediapipe as mp
except ImportError:
    mp = None
```

with:

```python
def _patch_protobuf_descriptor_compat():
    try:
        from google.protobuf import descriptor as protobuf_descriptor
    except Exception:
        return
    if not hasattr(protobuf_descriptor, "_internal_create_key"):
        protobuf_descriptor._internal_create_key = object()


def _import_optional_mediapipe():
    _patch_protobuf_descriptor_compat()
    try:
        import mediapipe as mediapipe_module
    except Exception as exc:
        return None, exc
    return mediapipe_module, None


mp, _MEDIAPIPE_IMPORT_ERROR = _import_optional_mediapipe()
```

- [ ] **Step 2: Improve runtime ImportError message**

In `FaceAnalyzer.__init__`, replace:

```python
        if mp is None:
            raise ImportError("mediapipe is not installed")
```

with:

```python
        if mp is None:
            if _MEDIAPIPE_IMPORT_ERROR is not None:
                raise ImportError("mediapipe import failed: %s" % _MEDIAPIPE_IMPORT_ERROR)
            raise ImportError("mediapipe is not installed")
```

- [ ] **Step 3: Run MediaPipe compatibility tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_mediapipe_compat.py -q
```

Expected: PASS.

- [ ] **Step 4: Run main import check locally**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -c "import main; print('MAIN_IMPORT_OK')"
```

Expected:

```text
MAIN_IMPORT_OK
```

- [ ] **Step 5: Commit implementation if using task commits**

```powershell
git add camera/face_analyzer.py tests/test_mediapipe_compat.py
git commit -m "fix: tolerate jetson mediapipe protobuf import mismatch"
```

---

## Task 3: Make Python 3.6 Compatibility Test Runnable On Python 3.6

**Files:**
- Modify: `tests/test_python36_compat.py`

- [ ] **Step 1: Add failing self-test on Nano**

Run on Nano before changing the test:

```bash
cd /home/nano/Version3
PYTHONPATH=/usr/lib/python3/dist-packages:/home/nano/Version3 python3 -m pytest tests/test_python36_compat.py -q
```

Expected current failure:

```text
TypeError: parse() got an unexpected keyword argument 'feature_version'
```

- [ ] **Step 2: Update imports**

In `tests/test_python36_compat.py`, replace:

```python
import ast
import re
from pathlib import Path
```

with:

```python
import ast
import re
import sys
from pathlib import Path
```

- [ ] **Step 3: Make `feature_version` conditional**

In `test_project_sources_parse_as_python36`, replace:

```python
def test_project_sources_parse_as_python36():
    failures = []
    for path in iter_project_python_files():
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path), feature_version=(3, 6))
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(PROJECT_ROOT)}:{exc.lineno}: {exc.msg}")

    assert failures == []
```

with:

```python
def test_project_sources_parse_as_python36():
    failures = []
    parse_kwargs = {"feature_version": (3, 6)} if sys.version_info >= (3, 8) else {}
    for path in iter_project_python_files():
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path), **parse_kwargs)
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(PROJECT_ROOT)}:{exc.lineno}: {exc.msg}")

    assert failures == []
```

- [ ] **Step 4: Run local compatibility tests**

Run:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_python36_compat.py tests/test_mediapipe_compat.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit test harness fix if using task commits**

```powershell
git add tests/test_python36_compat.py
git commit -m "test: run python compatibility check on python36"
```

---

## Task 4: Deploy Fixed Version3 And WebQuanLi Test Dependency To Nano

**Files:**
- No source code changes in this task.
- Deployment targets:
  - `/home/nano/Version3`
  - `/home/nano/WebQuanLi`

- [ ] **Step 1: Create Nano backup**

Run from Windows:

```powershell
ssh nano@192.168.2.17 'cd /home/nano && backup=".codex_backups/Version3-before-mediapipe-protobuf-fix-$(date +%Y%m%d-%H%M%S)" && mkdir -p .codex_backups && if [ -d Version3 ]; then mv Version3 "$backup"; fi && echo "BACKUP=$backup"'
```

Expected output includes:

```text
BACKUP=.codex_backups/Version3-before-mediapipe-protobuf-fix-...
```

- [ ] **Step 2: Package `Version3`**

Run from Windows:

```powershell
$archive='D:\DATN-testing1\.deploy\version3-webquanli-history-timezone-retention-fixed.tar.gz'
New-Item -ItemType Directory -Path D:\DATN-testing1\.deploy -Force | Out-Null
if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
tar -czf $archive --exclude='__pycache__' --exclude='.pytest_cache' --exclude='logs/*.log' --exclude='storage/runtime/latest.jpg' --exclude='storage/runtime/status.json' -C 'D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention' Version3
```

Expected: archive exists at `D:\DATN-testing1\.deploy\version3-webquanli-history-timezone-retention-fixed.tar.gz`.

- [ ] **Step 3: Copy and extract `Version3`**

Run:

```powershell
scp D:\DATN-testing1\.deploy\version3-webquanli-history-timezone-retention-fixed.tar.gz nano@192.168.2.17:/home/nano/version3-webquanli-history-timezone-retention-fixed.tar.gz
ssh nano@192.168.2.17 'cd /home/nano && tar -xzf version3-webquanli-history-timezone-retention-fixed.tar.gz && test -d /home/nano/Version3 && echo VERSION3_DEPLOYED'
```

Expected:

```text
VERSION3_DEPLOYED
```

- [ ] **Step 4: Deploy sibling WebQuanLi folder for contract tests**

`tests/test_webquanli_contract.py` expects `/home/nano/WebQuanLi/app/schemas.py`. Deploy the sibling `WebQuanLi` folder from the same worktree:

```powershell
$webArchive='D:\DATN-testing1\.deploy\webquanli-history-timezone-retention.tar.gz'
if (Test-Path $webArchive) { Remove-Item -LiteralPath $webArchive -Force }
tar -czf $webArchive --exclude='__pycache__' --exclude='.pytest_cache' -C 'D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention' WebQuanLi
scp $webArchive nano@192.168.2.17:/home/nano/webquanli-history-timezone-retention.tar.gz
ssh nano@192.168.2.17 'cd /home/nano && rm -rf WebQuanLi && tar -xzf webquanli-history-timezone-retention.tar.gz && test -f /home/nano/WebQuanLi/app/schemas.py && echo WEBQUANLI_SCHEMA_READY'
```

Expected:

```text
WEBQUANLI_SCHEMA_READY
```

Do not start WebQuanLi here unless the user explicitly asks. This task only supplies schemas for Version3 contract tests.

---

## Task 5: Verify On Nano

**Files:**
- No source changes.

- [ ] **Step 1: Syntax check**

Run:

```bash
cd /home/nano/Version3
python3 -m py_compile config.py main.py camera/face_analyzer.py ai/calibration.py ai/threshold_policy.py ai/drowsiness_classifier.py ai/session_controller.py ui/local_monitor.py
```

Expected: no output and exit code 0.

- [ ] **Step 2: Main import check**

Run:

```bash
cd /home/nano/Version3
printf "import main\nprint('MAIN_IMPORT_OK')\n" | PYTHONPATH=/usr/lib/python3/dist-packages:/home/nano/Version3 python3 -
```

Expected:

```text
MAIN_IMPORT_OK
```

- [ ] **Step 3: Targeted tests that previously blocked**

Run:

```bash
cd /home/nano/Version3
PYTHONPATH=/usr/lib/python3/dist-packages:/home/nano/Version3 python3 -m pytest \
  tests/test_mediapipe_compat.py \
  tests/test_main_local_gui.py \
  tests/test_webquanli_contract.py \
  tests/test_python36_compat.py \
  -q
```

Expected: PASS. If `tests/test_webquanli_contract.py` fails with missing `/home/nano/WebQuanLi/app/schemas.py`, repeat Task 4 Step 4.

- [ ] **Step 4: Existing non-main targeted tests**

Run:

```bash
cd /home/nano/Version3
PYTHONPATH=/usr/lib/python3/dist-packages:/home/nano/Version3 python3 -m pytest \
  tests/test_config_defaults.py \
  tests/test_calibration.py \
  tests/test_threshold_policy.py \
  tests/test_drowsiness_classifier.py \
  tests/test_ai_session_controller.py \
  tests/test_runtime_status.py \
  tests/test_local_monitor_gui.py \
  -q
```

Expected: PASS. Before this plan, this suite already passed `40 passed`.

- [ ] **Step 5: Smoke launch without camera session**

Run:

```bash
cd /home/nano/Version3
PYTHONPATH=/usr/lib/python3/dist-packages:/home/nano/Version3 python3 - <<'PY'
import config
from main import DrowsiGuard, shutdown_event

original = config.FEATURES.copy()
try:
    config.FEATURES = {
        "camera": False,
        "drowsiness": False,
        "rfid": False,
        "gps": False,
        "buzzer": False,
        "led": False,
        "speaker": False,
        "websocket": False,
        "ota": False,
        "face_verify": False,
    }
    shutdown_event.clear()
    app = DrowsiGuard()
    print("DROWSIGUARD_CONSTRUCT_OK", app.state.state)
finally:
    config.FEATURES = original
    shutdown_event.clear()
PY
```

Expected output includes:

```text
DROWSIGUARD_CONSTRUCT_OK
```

- [ ] **Step 6: Report to user before any further runtime/manual camera testing**

Report:

```text
Nano fix verification:
- py_compile:
- main import:
- mediapipe/main/webquanli/python36 targeted pytest:
- existing non-main targeted pytest:
- smoke construct:
- remaining issues:
```

Do not modify `/home/nano/start_drowsiguard_full.sh`, systemd, dependencies, or WebQuanLi service in this plan.

---

## Self-Review

- Spec coverage: Fixes the exact Nano blocker preventing `main.py` import and documents the WebQuanLi schema dependency needed for contract tests.
- Placeholder scan: No TODO/TBD placeholders remain; all commands and code snippets are explicit.
- Type consistency: `_import_optional_mediapipe()` returns `(module_or_none, error_or_none)` and `FaceAnalyzer.__init__` reads `_MEDIAPIPE_IMPORT_ERROR`; test uses the same function name.

---

## Rollback Plan

If the fixed build behaves worse on Nano, restore the backup made in Task 4:

```bash
cd /home/nano
rm -rf Version3
mv .codex_backups/Version3-before-mediapipe-protobuf-fix-YYYYMMDD-HHMMSS Version3
```

Then verify:

```bash
test -f /home/nano/Version3/main.py && echo RESTORED
```
