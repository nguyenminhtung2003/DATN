# WebQuanLi Python36 Schema Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `WebQuanLi/app/schemas.py` import and validate Version3 contract payloads on Jetson Nano Python 3.6 without changing Version3 runtime or EAR logic.

**Architecture:** Keep the schema definitions in one file, but replace Python 3.8+/Pydantic v2-only imports with small local compatibility helpers. Use `typing_extensions.Literal` on Python 3.6, map `field_validator` to Pydantic v1 `validator`, map before-model validators to Pydantic v1 `root_validator(pre=True)`, and replace `AliasChoices(validation_alias=...)` with explicit pre-validation alias normalization. This fixes the exact Nano blocker while preserving local Pydantic v2 behavior.

**Tech Stack:** Python 3.6 on Jetson Nano, Python 3.14 local, Pydantic v1.8.2 on Nano, Pydantic v2 locally, pytest.

---

## Root Cause Summary

After fixing the Version3 MediaPipe/protobuf import blocker, Nano targeted tests reached `tests/test_webquanli_contract.py` and failed while importing `/home/nano/WebQuanLi/app/schemas.py`:

```text
from typing import Any, Dict, Literal, Optional
ImportError: cannot import name 'Literal'
```

Further environment check on Nano:

```text
pydantic VERSION 1.8.2
has field_validator False
has AliasChoices False
typing_extensions OK True
```

So the blocker is not only `typing.Literal`. The schema file also imports Pydantic v2-only APIs:

```python
from pydantic import AliasChoices, BaseModel, Field, field_validator
```

and uses:

```python
Field(validation_alias=AliasChoices(...))
@field_validator(...)
```

This is incompatible with Python 3.6 + Pydantic 1.8.2 on the Jetson Nano. The fix should be limited to `WebQuanLi/app/schemas.py` and schema tests.

---

## File Structure

- Modify: `WebQuanLi/app/schemas.py`
  - Replace direct `Literal`, `AliasChoices`, and `field_validator` imports with compatibility helpers.
  - Add pre-validation alias normalization for the three fields that currently use `AliasChoices`.
- Modify: `WebQuanLi/tests/test_api_validation_contract.py`
  - Add direct tests for alternate aliases on both Pydantic v1 and v2.
- No change: `Version3/`
  - Version3 runtime import and smoke construction already pass after the MediaPipe/protobuf fix.
- No change: dependencies
  - Do not install or upgrade Pydantic on Nano as part of this plan. The point is compatibility with the current Nano environment.

---

## Task 1: Add Failing WebQuanLi Schema Compatibility Tests

**Files:**
- Modify: `WebQuanLi/tests/test_api_validation_contract.py`

- [ ] **Step 1: Inspect existing test file**

Run:

```powershell
Get-Content -Path D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\tests\test_api_validation_contract.py | Select-Object -First 220
```

Expected: file exists and imports schema classes from `app.schemas`.

- [ ] **Step 2: Add alias compatibility tests**

Append these tests to `WebQuanLi/tests/test_api_validation_contract.py`:

```python
from app.schemas import AlertData, DriverData


def test_alert_data_accepts_legacy_confidence_aliases():
    parsed = AlertData(
        level="DANGER",
        confidence=0.91,
        reason="classifier",
    )

    assert parsed.ai_confidence == 0.91
    assert parsed.ai_reason == "classifier"


def test_driver_data_accepts_rfid_tag_alias():
    parsed = DriverData(name="Nguyen Van A", rfid_tag="UID-123")

    assert parsed.rfid == "UID-123"
```

If the file already imports `AlertData` or `DriverData`, merge the imports instead of duplicating them.

- [ ] **Step 3: Run local tests before implementation**

Run:

```powershell
cd D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_api_validation_contract.py::test_alert_data_accepts_legacy_confidence_aliases tests/test_api_validation_contract.py::test_driver_data_accepts_rfid_tag_alias -q
```

Expected on local Pydantic v2: likely PASS because `validation_alias=AliasChoices(...)` already supports these aliases. That is acceptable: the real red test is Nano import/runtime under Pydantic v1.8.2 in Task 1 Step 4.

- [ ] **Step 4: Run Nano reproduction**

Run:

```bash
cd /home/nano/WebQuanLi
PYTHONPATH=/home/nano/WebQuanLi python3 -m pytest tests/test_api_validation_contract.py::test_alert_data_accepts_legacy_confidence_aliases tests/test_api_validation_contract.py::test_driver_data_accepts_rfid_tag_alias -q
```

Expected before implementation: FAIL during import with:

```text
ImportError: cannot import name 'Literal'
```

or, after only fixing `Literal`, fail with missing `field_validator` / `AliasChoices`. Do not stop after fixing only the first import error.

---

## Task 2: Add Pydantic v1/v2 Compatibility Helpers

**Files:**
- Modify: `WebQuanLi/app/schemas.py`

- [ ] **Step 1: Replace imports**

At the top of `WebQuanLi/app/schemas.py`, replace:

```python
import re
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import AliasChoices, BaseModel, Field, field_validator
```

with:

```python
import re
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

from pydantic import BaseModel, Field

try:
    from pydantic import field_validator, model_validator
except ImportError:
    from pydantic import root_validator
    from pydantic import validator as field_validator

    def model_validator(*, mode):
        return root_validator(pre=(mode == "before"))
```

- [ ] **Step 2: Add alias normalization helper**

Immediately after `GENDER_VALUES = ...`, add:

```python
def _normalize_aliases(values, aliases):
    if not isinstance(values, dict):
        return values
    values = dict(values)
    for target, source_names in aliases.items():
        if target in values:
            continue
        for source_name in source_names:
            if source_name in values:
                values[target] = values[source_name]
                break
    return values
```

This helper copies alternate input keys into the canonical field name before Pydantic validates the model. It replaces `AliasChoices` behavior without depending on Pydantic v2.

---

## Task 3: Replace Pydantic v2 AliasChoices Usage

**Files:**
- Modify: `WebQuanLi/app/schemas.py`
- Test: `WebQuanLi/tests/test_api_validation_contract.py`

- [ ] **Step 1: Replace `AlertData` fields**

In `class AlertData`, replace:

```python
    ai_confidence: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("ai_confidence", "confidence"),
    )
    ai_reason: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ai_reason", "reason"),
    )
```

with:

```python
    ai_confidence: Optional[float] = None
    ai_reason: Optional[str] = None
```

Then add this method inside `AlertData`, before `lat`:

```python
    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values):
        return _normalize_aliases(
            values,
            {
                "ai_confidence": ("confidence",),
                "ai_reason": ("reason",),
            },
        )
```

- [ ] **Step 2: Replace `DriverData` field**

In `class DriverData`, replace:

```python
    rfid: str = Field(validation_alias=AliasChoices("rfid", "rfid_tag"))
```

with:

```python
    rfid: str
```

Then add this method inside `DriverData`:

```python
    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values):
        return _normalize_aliases(values, {"rfid": ("rfid_tag",)})
```

- [ ] **Step 3: Verify no `AliasChoices` references remain**

Run:

```powershell
Select-String -Path D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi\app\schemas.py -Pattern "AliasChoices|validation_alias"
```

Expected: no output.

- [ ] **Step 4: Run local WebQuanLi schema tests**

Run:

```powershell
cd D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention\WebQuanLi
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest tests/test_api_validation_contract.py tests/test_websocket_contract_fixtures.py tests/test_verify_snapshot_contract.py -q
```

Expected: PASS.

---

## Task 4: Deploy WebQuanLi Fix To Nano

**Files:**
- Deployment target: `/home/nano/WebQuanLi`

- [ ] **Step 1: Backup Nano WebQuanLi**

Run:

```powershell
ssh nano@192.168.2.17 'cd /home/nano && backup=".codex_backups/WebQuanLi-before-python36-schema-compat-$(date +%Y%m%d-%H%M%S)" && mkdir -p .codex_backups && if [ -d WebQuanLi ]; then mv WebQuanLi "$backup"; fi && echo "BACKUP=$backup"'
```

Expected output includes:

```text
BACKUP=.codex_backups/WebQuanLi-before-python36-schema-compat-...
```

- [ ] **Step 2: Package WebQuanLi**

Run:

```powershell
$webArchive='D:\DATN-testing1\.deploy\webquanli-python36-schema-compat.tar.gz'
if (Test-Path $webArchive) { Remove-Item -LiteralPath $webArchive -Force }
tar -czf $webArchive --exclude='__pycache__' --exclude='.pytest_cache' -C 'D:\DATN-testing1\.worktrees\webquanli-history-timezone-retention' WebQuanLi
```

Expected: archive exists at `D:\DATN-testing1\.deploy\webquanli-python36-schema-compat.tar.gz`.

- [ ] **Step 3: Copy and extract WebQuanLi**

Run:

```powershell
scp D:\DATN-testing1\.deploy\webquanli-python36-schema-compat.tar.gz nano@192.168.2.17:/home/nano/webquanli-python36-schema-compat.tar.gz
ssh nano@192.168.2.17 'cd /home/nano && tar -xzf webquanli-python36-schema-compat.tar.gz && test -f /home/nano/WebQuanLi/app/schemas.py && echo WEBQUANLI_DEPLOYED'
```

Expected:

```text
WEBQUANLI_DEPLOYED
```

---

## Task 5: Verify On Nano

**Files:**
- No source changes.

- [ ] **Step 1: Import schema directly**

Run:

```bash
cd /home/nano/WebQuanLi
PYTHONPATH=/home/nano/WebQuanLi python3 - <<'PY'
from app.schemas import AlertData, DriverData, VerifySnapshotData, WsCommandOut
print("SCHEMAS_IMPORT_OK")
print(AlertData(level="DANGER", confidence=0.9, reason="classifier").ai_confidence)
print(DriverData(name="A", rfid_tag="UID-123").rfid)
PY
```

Expected:

```text
SCHEMAS_IMPORT_OK
0.9
UID-123
```

- [ ] **Step 2: Run Version3 WebQuanLi contract tests**

Run:

```bash
cd /home/nano/Version3
PYTHONPATH=/usr/lib/python3/dist-packages:/home/nano/Version3 python3 -m pytest tests/test_webquanli_contract.py -q
```

Expected: PASS, or reveal the next genuine contract mismatch. If it fails, report the exact failure; do not alter Version3/EAR code.

- [ ] **Step 3: Run targeted tests previously verified**

Run:

```bash
cd /home/nano/Version3
PYTHONPATH=/usr/lib/python3/dist-packages:/home/nano/Version3 python3 -m pytest \
  tests/test_mediapipe_compat.py \
  tests/test_main_local_gui.py \
  tests/test_python36_compat.py \
  tests/test_config_defaults.py \
  tests/test_calibration.py \
  tests/test_threshold_policy.py \
  tests/test_drowsiness_classifier.py \
  tests/test_ai_session_controller.py \
  tests/test_runtime_status.py \
  tests/test_local_monitor_gui.py \
  -q
```

Expected: PASS. Before this plan, these groups passed as `28 passed` and `40 passed`.

- [ ] **Step 4: Report**

Report:

```text
WebQuanLi Python 3.6 schema fix:
- schemas import:
- alias compatibility:
- Version3 webquanli contract:
- previous targeted Version3 tests:
- remaining issues:
```

---

## Non-Goals

- Do not upgrade Python on Nano.
- Do not install or upgrade Pydantic on Nano.
- Do not change Version3 drowsiness/EAR logic.
- Do not modify `/home/nano/start_drowsiguard_full.sh`.
- Do not start or reconfigure WebQuanLi service unless separately requested.

---

## Rollback Plan

If this breaks WebQuanLi schema behavior on Nano, restore the backup:

```bash
cd /home/nano
rm -rf WebQuanLi
mv .codex_backups/WebQuanLi-before-python36-schema-compat-YYYYMMDD-HHMMSS WebQuanLi
test -f /home/nano/WebQuanLi/app/schemas.py && echo WEBQUANLI_RESTORED
```

---

## Self-Review

- Spec coverage: Targets the exact remaining error after Version3 import fix: WebQuanLi schemas not compatible with Nano Python 3.6/Pydantic 1.8.2.
- Placeholder scan: No TODO/TBD placeholders; every step has exact code and commands.
- Type consistency: Helper names `_normalize_aliases`, `model_validator`, and `field_validator` are defined before use; schema classes use those exact names.
