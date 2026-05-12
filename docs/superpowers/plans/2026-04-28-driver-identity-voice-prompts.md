# Driver Identity Voice Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local WAV voice prompts to the Jetson driver identity verification flow, using the five files already created in `Version3/wav`, while keeping WebQuanLi synchronization and existing alert audio behavior compatible.

**Architecture:** Keep drowsiness alert audio and driver verification voice prompts as separate concepts. Extend the existing `Speaker` adapter with generic file/prompt playback, then call prompt names from `DrowsiGuard` verification states. WebQuanLi contract messages remain unchanged: `driver`, `verify_snapshot`, `verify_error`, `face_mismatch`, `session_start`, and `session_end` continue to synchronize the outcome.

**Tech Stack:** Python 3.6-compatible code on Jetson Nano, `paplay`/`aplay` local WAV playback, existing FastAPI local dashboard, existing pytest/unittest test suite.

---

## Current Code Map

- `Version3/main.py`
  - `DrowsiGuard._on_rfid_scan()` receives RFID and starts verification.
  - `DrowsiGuard._verify_driver()` captures face crop and handles `MATCH`, `MISMATCH`, `NO_ENROLLMENT`, `NO_FACE_FRAME`, and `LOW_CONFIDENCE`.
  - `DrowsiGuard._start_verified_session()` sends `verify_snapshot` and `session_start`.
  - `DrowsiGuard._reject_verification()` sends `verify_error`.
- `Version3/alerts/speaker.py`
  - Currently only plays alert levels `1`, `2`, `3` from `Version3/sounds`.
  - Uses `paplay` or `aplay`.
- `Version3/config.py`
  - Currently defines drowsiness alert WAV paths only.
- `Version3/dashboard/app.py`
  - Currently has test endpoints for alert level audio only.
- `Version3/healthcheck.py`
  - Currently checks only alert audio files.
- `Version3/wav`
  - Already contains:
    - `verify_prepare_countdown.wav`
    - `verify_success.wav`
    - `verify_failed_identity.wav`
    - `verify_no_face.wav`
    - `verify_no_enrollment.wav`

## Target File Structure

Line ranges below refer to the current baseline before executing this plan. Later tasks may shift exact line numbers, but each task names the surrounding function or constant block to edit.

- `Version3/config.py:142-144`
  - Owns audio path configuration.
  - Add verification prompt paths and feature flags next to existing alert audio paths.
- `Version3/alerts/speaker.py:12-106`
  - Owns local WAV playback through `paplay` or `aplay`.
  - Keep `play_alert(level)` for drowsiness alerts and add `play_prompt(prompt_name, wait=False, timeout=None)` for identity prompts.
- `Version3/main.py:449-529`, `Version3/main.py:650-698`, `Version3/main.py:756-787`, `Version3/main.py:850-852`
  - Owns RFID-triggered verification state changes.
  - Add prompt calls without changing WebQuanLi message schemas.
- `Version3/dashboard/app.py:14-190`
  - Owns Jetson local dashboard and audio test endpoints.
  - Add prompt test buttons and `/api/audio/prompt/{prompt_name}`.
- `Version3/healthcheck.py:238-256`
  - Owns pre-demo runtime checks.
  - Add verification prompt file checks near existing alert audio checks.
- `Version3/tests/test_config_defaults.py`, `Version3/tests/test_bluetooth_audio.py`, `Version3/tests/test_verify_flow.py`, `Version3/tests/test_dashboard_api.py`, `Version3/tests/test_healthcheck_dashboard.py`
  - Own TDD coverage for config, playback adapter, verification behavior, local dashboard, and healthcheck output.
- `Version3/docs/jetson_demo_checklist.md`
  - Owns manual Jetson validation steps for demo day.

## Prompt Mapping

Use exactly the five existing WAV files:

| Prompt name | WAV file | Trigger |
| --- | --- | --- |
| `prepare_countdown` | `Version3/wav/verify_prepare_countdown.wav` | RFID accepted in `IDLE`, before face capture |
| `success` | `Version3/wav/verify_success.wav` | Face matches RFID, before/while entering `RUNNING` |
| `failed_identity` | `Version3/wav/verify_failed_identity.wav` | Face mismatch, or periodic reverify reaches mismatch-alert state |
| `no_face` | `Version3/wav/verify_no_face.wav` | No usable face frame, camera unavailable during verify, or low confidence |
| `no_enrollment` | `Version3/wav/verify_no_enrollment.wav` | Missing verifier, missing local enrollment, or verifier returns `BLOCKED` |

The `prepare_countdown` prompt must block face capture until the prompt finishes or a timeout is reached. Result prompts are non-blocking.

---

### Task 1: Register Verification Prompt Config And Assets

**Files:**
- Modify: `Version3/config.py:142-144`
- Verify asset files exist: `Version3/wav/verify_prepare_countdown.wav`, `Version3/wav/verify_success.wav`, `Version3/wav/verify_failed_identity.wav`, `Version3/wav/verify_no_face.wav`, `Version3/wav/verify_no_enrollment.wav`
- Test: `Version3/tests/test_config_defaults.py`

- [ ] **Step 1: Write the failing config test**

Append to `Version3/tests/test_config_defaults.py`:

```python
def test_verify_prompt_config_points_to_existing_wav_files():
    import os
    import config

    expected = {
        "prepare_countdown",
        "success",
        "failed_identity",
        "no_face",
        "no_enrollment",
    }

    assert set(config.VERIFY_PROMPT_FILES.keys()) == expected
    for prompt_name, path in config.VERIFY_PROMPT_FILES.items():
        assert path.endswith(".wav"), prompt_name
        assert os.path.exists(path), path
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_config_defaults.py::test_verify_prompt_config_points_to_existing_wav_files -q
```

Expected before implementation:

```text
FAILED ... AttributeError: module 'config' has no attribute 'VERIFY_PROMPT_FILES'
```

- [ ] **Step 3: Add prompt config**

In `Version3/config.py`, below the existing `AUDIO_ALERT_LEVEL3` constants, add:

```python
# Driver identity verification voice prompts.
VERIFY_PROMPTS_ENABLED = env_bool("DROWSIGUARD_VERIFY_PROMPTS_ENABLED", True)
VERIFY_PROMPT_DIR = os.getenv(
    "DROWSIGUARD_VERIFY_PROMPT_DIR",
    os.path.join(os.path.dirname(__file__), "wav"),
)
VERIFY_PROMPT_PREPARE_COUNTDOWN = os.getenv(
    "DROWSIGUARD_VERIFY_PROMPT_PREPARE_COUNTDOWN",
    os.path.join(VERIFY_PROMPT_DIR, "verify_prepare_countdown.wav"),
)
VERIFY_PROMPT_SUCCESS = os.getenv(
    "DROWSIGUARD_VERIFY_PROMPT_SUCCESS",
    os.path.join(VERIFY_PROMPT_DIR, "verify_success.wav"),
)
VERIFY_PROMPT_FAILED_IDENTITY = os.getenv(
    "DROWSIGUARD_VERIFY_PROMPT_FAILED_IDENTITY",
    os.path.join(VERIFY_PROMPT_DIR, "verify_failed_identity.wav"),
)
VERIFY_PROMPT_NO_FACE = os.getenv(
    "DROWSIGUARD_VERIFY_PROMPT_NO_FACE",
    os.path.join(VERIFY_PROMPT_DIR, "verify_no_face.wav"),
)
VERIFY_PROMPT_NO_ENROLLMENT = os.getenv(
    "DROWSIGUARD_VERIFY_PROMPT_NO_ENROLLMENT",
    os.path.join(VERIFY_PROMPT_DIR, "verify_no_enrollment.wav"),
)
VERIFY_PROMPT_WAIT_TIMEOUT_SEC = env_float("DROWSIGUARD_VERIFY_PROMPT_WAIT_TIMEOUT", 8.0)
VERIFY_PROMPT_FILES = {
    "prepare_countdown": VERIFY_PROMPT_PREPARE_COUNTDOWN,
    "success": VERIFY_PROMPT_SUCCESS,
    "failed_identity": VERIFY_PROMPT_FAILED_IDENTITY,
    "no_face": VERIFY_PROMPT_NO_FACE,
    "no_enrollment": VERIFY_PROMPT_NO_ENROLLMENT,
}
```

- [ ] **Step 4: Run the config test**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_config_defaults.py::test_verify_prompt_config_points_to_existing_wav_files -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

Run:

```powershell
cd D:\DATN-testing1
git add Version3/config.py Version3/tests/test_config_defaults.py Version3/wav
git commit -m "feat: register driver verification voice prompts"
```

---

### Task 2: Extend Speaker With Named Prompt Playback

**Files:**
- Modify: `Version3/alerts/speaker.py:12-106`
- Test: `Version3/tests/test_bluetooth_audio.py`

- [ ] **Step 1: Write failing tests for prompt playback**

Append to the end of `Version3/tests/test_bluetooth_audio.py`:

```python
def test_speaker_plays_named_verify_prompt(monkeypatch, tmp_path):
    calls = []
    prompt_file = tmp_path / "verify_success.wav"
    prompt_file.write_bytes(b"RIFFdemo")

    def fake_popen(args):
        calls.append(args)

        class Process:
            def poll(self):
                return None

            def terminate(self):
                calls.append(["terminate"])

        return Process()

    speaker = Speaker(
        enabled=True,
        backend="paplay",
        alert_files={},
        prompt_files={"success": str(prompt_file)},
        popen=fake_popen,
    )

    assert speaker.play_prompt("success") is True
    speaker.stop()
    assert calls[0] == ["paplay", str(prompt_file)]
    assert calls[1] == ["terminate"]
    assert speaker.last_prompt == "success"


def test_speaker_waits_for_countdown_prompt_when_requested(monkeypatch, tmp_path):
    calls = []
    prompt_file = tmp_path / "verify_prepare_countdown.wav"
    prompt_file.write_bytes(b"RIFFdemo")

    class Process:
        def poll(self):
            return None

        def wait(self, timeout=None):
            calls.append(["wait", timeout])
            return 0

        def terminate(self):
            calls.append(["terminate"])

    def fake_popen(args):
        calls.append(args)
        return Process()

    speaker = Speaker(
        enabled=True,
        backend="aplay",
        alert_files={},
        prompt_files={"prepare_countdown": str(prompt_file)},
        popen=fake_popen,
    )

    assert speaker.play_prompt("prepare_countdown", wait=True, timeout=8.0) is True
    assert calls[0] == ["aplay", str(prompt_file)]
    assert calls[1] == ["wait", 8.0]
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_bluetooth_audio.py::test_speaker_plays_named_verify_prompt tests/test_bluetooth_audio.py::test_speaker_waits_for_countdown_prompt_when_requested -q
```

Expected before implementation:

```text
FAILED ... TypeError: __init__() got an unexpected keyword argument 'prompt_files'
```

- [ ] **Step 3: Update `Speaker.__init__()` state**

Modify `Version3/alerts/speaker.py:15-30` so `Speaker.__init__()` accepts `prompt_files`, stores prompt state, and keeps existing alert state:

```python
class Speaker:
    """Audio alert playback through paplay/aplay, with mock-safe state recording."""

    def __init__(self, enabled=None, backend=None, alert_files=None, prompt_files=None, popen=None):
        self.enabled = config.HAS_SPEAKER if enabled is None else bool(enabled)
        self.backend = backend or getattr(config, "AUDIO_BACKEND", "auto")
        self.alert_files = alert_files or {
            1: config.AUDIO_ALERT_LEVEL1,
            2: config.AUDIO_ALERT_LEVEL2,
            3: config.AUDIO_ALERT_LEVEL3,
        }
        self.prompt_files = prompt_files or dict(getattr(config, "VERIFY_PROMPT_FILES", {}))
        self.last_level = None
        self.last_prompt = None
        self.last_command = None
        self._last_process = None
        self._popen = popen or subprocess.Popen
        if not self.enabled:
            logger.warning("Speaker initialized without hardware; using mock adapter")
```

- [ ] **Step 4: Replace `play_alert()` with a wrapper around generic file playback**

Modify `Version3/alerts/speaker.py:34-60`. Replace the existing `play_alert()` body with:

```python
    def play_alert(self, level):
        self.last_level = level
        self.last_prompt = None
        sound_path = self.alert_files.get(int(level))
        if not sound_path:
            logger.warning("No audio file configured for alert level=%s", level)
            return False
        return self.play_file(sound_path, label="alert level=%s" % level)
```

- [ ] **Step 5: Add `play_prompt()` and `play_file()`**

In `Version3/alerts/speaker.py:34-64`, add these methods directly below `play_alert()`:

```python
    def play_prompt(self, prompt_name, wait=False, timeout=None):
        self.last_prompt = prompt_name
        sound_path = self.prompt_files.get(prompt_name)
        if not sound_path:
            logger.warning("No audio file configured for verification prompt=%s", prompt_name)
            return False
        return self.play_file(sound_path, label="verification prompt=%s" % prompt_name, wait=wait, timeout=timeout)

    def play_file(self, sound_path, label="audio", wait=False, timeout=None):
        if not self.enabled:
            logger.info("Speaker %s skipped; hardware disabled", label)
            return False
        if not os.path.exists(sound_path):
            logger.warning("Audio file does not exist for %s: %s", label, sound_path)
            return False

        backend = self._resolve_backend()
        if not backend:
            logger.warning("No usable audio backend found for speaker playback")
            return False

        command = self._build_command(sound_path, backend=backend)
        self.last_command = command
        try:
            self.stop()
            self._last_process = self._popen(command)
            if wait and hasattr(self._last_process, "wait"):
                self._last_process.wait(timeout=timeout)
                self._last_process = None
            return True
        except Exception as exc:
            logger.error("Speaker playback failed: %s", exc)
            return False
```

- [ ] **Step 6: Replace `status()` with alert and prompt file output**

Modify `Version3/alerts/speaker.py:91-104`. Replace the existing `status()` method with:

```python
    def status(self):
        return {
            "enabled": self.enabled,
            "available": self.is_available,
            "backend": self._resolve_backend() or self.backend,
            "last_level": self.last_level,
            "last_prompt": self.last_prompt,
            "files": {
                str(level): {
                    "path": path,
                    "exists": os.path.exists(path),
                }
                for level, path in self.alert_files.items()
            },
            "prompts": {
                str(name): {
                    "path": path,
                    "exists": os.path.exists(path),
                }
                for name, path in self.prompt_files.items()
            },
        }
```

- [ ] **Step 7: Run speaker tests**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_bluetooth_audio.py tests/test_alert_output_adapters.py -q
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 8: Commit**

Run:

```powershell
cd D:\DATN-testing1
git add Version3/alerts/speaker.py Version3/tests/test_bluetooth_audio.py
git commit -m "feat: play named verification voice prompts"
```

---

### Task 3: Play Prompts In RFID Verification Flow

**Files:**
- Modify: `Version3/main.py:449-529`
- Modify: `Version3/main.py:650-698`
- Modify: `Version3/main.py:756-787`
- Modify: `Version3/main.py:850-852`
- Test: `Version3/tests/test_verify_flow.py`
- Test: `Version3/tests/test_webquanli_contract.py`

- [ ] **Step 1: Write failing tests for prompt order and outcomes**

Insert these methods inside class `TestVerifyFlow` in `Version3/tests/test_verify_flow.py`, after `test_rfid_scan_emits_driver_event_before_verification()` and before the `if __name__ == "__main__":` block:

```python
    def attach_prompt_speaker(self):
        speaker = Mock()
        speaker.play_prompt.return_value = True
        self.app.speaker = speaker
        return speaker

    def test_rfid_scan_plays_countdown_before_face_capture(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = False
        self.app.verifier = mock_verifier

        with patch.object(self.app, "_verify_driver") as verify_driver:
            self.app._on_rfid_scan("UID-123")

        speaker.play_prompt.assert_called_once_with(
            "prepare_countdown",
            wait=True,
            timeout=config.VERIFY_PROMPT_WAIT_TIMEOUT_SEC,
        )
        verify_driver.assert_called_once_with("UID-123")

    def test_match_plays_success_prompt_and_starts_session(self):
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        mock_verifier.extract_face.side_effect = lambda frame, bbox: frame
        mock_verifier.verify.return_value = VerifyResult.MATCH
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("success")
        self.assertEqual(self.app.state.state, State.RUNNING)
        self.verify_snapshot_called("VERIFIED")

    def test_mismatch_plays_failed_identity_prompt_and_queues_face_mismatch(self):
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        mock_verifier.extract_face.side_effect = lambda frame, bbox: frame
        mock_verifier.verify.return_value = VerifyResult.MISMATCH
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch("time.sleep", return_value=None):
            self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("failed_identity")
        self.verify_rejection_called("face_mismatch", "expected", "unknown")

    def test_no_face_plays_no_face_prompt(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = (None, None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch("time.sleep", return_value=None):
            self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("no_face")
        self.verify_rejection_called("verify_error", "reason", "NO_FACE_FRAME")

    def test_no_enrollment_plays_no_enrollment_prompt(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = False
        self.app.verifier = mock_verifier

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch("time.sleep", return_value=None):
            self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("no_enrollment")
        self.verify_rejection_called("verify_error", "reason", "NO_ENROLLMENT")
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_verify_flow.py -q
```

Expected before implementation:

```text
FAILED ... Expected 'play_prompt' to be called
```

- [ ] **Step 3: Add `_play_verify_prompt()` helper**

Add this method directly above `_set_verify_status()` in `Version3/main.py:850`:

```python
    def _play_verify_prompt(self, prompt_name: str, wait: bool = False) -> bool:
        if not getattr(config, "VERIFY_PROMPTS_ENABLED", True):
            return False
        if not self.speaker:
            logger.warning("[VERIFY AUDIO] prompt=%s skipped; speaker not available", prompt_name)
            return False
        play_prompt = getattr(self.speaker, "play_prompt", None)
        if not callable(play_prompt):
            logger.warning("[VERIFY AUDIO] prompt=%s skipped; speaker has no play_prompt()", prompt_name)
            return False
        ok = bool(play_prompt(
            prompt_name,
            wait=wait,
            timeout=getattr(config, "VERIFY_PROMPT_WAIT_TIMEOUT_SEC", 8.0),
        ))
        if not ok:
            logger.warning("[VERIFY AUDIO] prompt=%s failed", prompt_name)
        return ok
```

- [ ] **Step 4: Add `_prompt_for_verify_failure()` helper**

Add this method directly below `_play_verify_prompt()` and above `_set_verify_status()` in `Version3/main.py:850`:

```python
    @staticmethod
    def _prompt_for_verify_failure(reason: str):
        if reason in ("NO_ENROLLMENT", "MISSING_VERIFIER", "BLOCKED"):
            return "no_enrollment"
        if reason in ("NO_FACE_FRAME", "LOW_CONFIDENCE", "UNKNOWN_ERROR"):
            return "no_face"
        return None
```

- [ ] **Step 5: Play countdown after RFID state transition**

In `Version3/main.py:449-463`, inside `_on_rfid_scan()`, after transitioning to `VERIFYING_DRIVER` and before `_verify_driver(uid)`, add:

```python
            self._play_verify_prompt("prepare_countdown", wait=True)
```

- [ ] **Step 6: Play success prompt on verified session start**

In `Version3/main.py:650-657`, inside `_start_verified_session()`, after `_set_verify_status("VERIFIED", ...)` and before `logger.info(...)`, add:

```python
        self._play_verify_prompt("success")
```

- [ ] **Step 7: Play failed identity prompt on initial mismatch**

In `Version3/main.py:503-516`, inside the `VerifyResult.MISMATCH` branch of `_verify_driver()`, after `_set_verify_status("MISMATCH", ...)`, add:

```python
            self._play_verify_prompt("failed_identity")
```

- [ ] **Step 8: Play mapped failure prompt on rejected verification**

In `Version3/main.py:696-699`, inside `_reject_verification()`, before `time.sleep(2.0)`, add:

```python
        prompt_name = self._prompt_for_verify_failure(reason)
        if prompt_name:
            self._play_verify_prompt(prompt_name)
```

- [ ] **Step 9: Play failed identity prompt on repeated reverify failure**

In `Version3/main.py:756-787`, inside `_run_reverification_once()`, in the `if self._reverify_fail_count >= config.REVERIFY_MAX_CONSECUTIVE_FAILS:` block before `_end_session()`, add:

```python
            self._play_verify_prompt("failed_identity")
```

- [ ] **Step 10: Run verify and contract tests**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_verify_flow.py tests/test_webquanli_contract.py tests/test_reverify_flow.py -q
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 11: Commit**

Run:

```powershell
cd D:\DATN-testing1
git add Version3/main.py Version3/tests/test_verify_flow.py
git commit -m "feat: announce driver identity verification results"
```

---

### Task 4: Add Local Dashboard And Healthcheck Support For Prompt Testing

**Files:**
- Modify: `Version3/dashboard/app.py:14-190`
- Modify: `Version3/healthcheck.py:238-256`
- Modify: `Version3/tests/test_dashboard_api.py:200`
- Modify: `Version3/tests/test_healthcheck_dashboard.py:68`

- [ ] **Step 1: Write failing dashboard API test**

Append to `Version3/tests/test_dashboard_api.py`:

```python
def test_dashboard_prompt_test_endpoint_uses_speaker_prompt():
    from fastapi.testclient import TestClient

    class SpeakerStub:
        def __init__(self):
            self.prompts = []

        def play_prompt(self, prompt_name):
            self.prompts.append(prompt_name)
            return True

        def status(self):
            return {"enabled": True, "available": True}

        def stop(self):
            pass

    speaker = SpeakerStub()
    client = TestClient(create_app(speaker=speaker))

    response = client.post("/api/audio/prompt/success")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "prompt": "success"}
    assert speaker.prompts == ["success"]
```

- [ ] **Step 2: Write failing healthcheck test**

Append to `Version3/tests/test_healthcheck_dashboard.py`:

```python
def test_run_healthcheck_reports_verify_prompt_files(monkeypatch, capsys):
    monkeypatch.setattr(healthcheck.config, "FEATURES", {
        "camera": False,
        "drowsiness": True,
        "rfid": False,
        "gps": False,
        "buzzer": False,
        "led": False,
        "speaker": True,
        "websocket": False,
        "ota": True,
        "face_verify": True,
    })
    monkeypatch.setattr(healthcheck.config, "BLUETOOTH_SPEAKER_MAC", "")
    monkeypatch.setattr(healthcheck.config, "VERIFY_PROMPT_FILES", {
        "success": "/demo/verify_success.wav",
        "no_face": "/demo/verify_no_face.wav",
    })
    monkeypatch.setattr(healthcheck, "_module_available", lambda name: True)
    monkeypatch.setattr(healthcheck, "_writable_parent", lambda path: True)
    monkeypatch.setattr(healthcheck, "_file_exists", lambda path: True)
    monkeypatch.setattr(healthcheck, "_dashboard_port_status", lambda port: ("PASS", "dashboard_port", str(port)))
    monkeypatch.setattr(healthcheck, "_command_available", lambda name: name == "paplay")

    class FakeBluetoothManager:
        def status(self):
            return {"adapter": True, "connected": False}

    monkeypatch.setattr(healthcheck, "BluetoothManager", FakeBluetoothManager)

    exit_code = healthcheck.run_healthcheck(quick=True)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "verify_prompt_files" in output
```

- [ ] **Step 3: Run failing tests**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_dashboard_api.py::test_dashboard_prompt_test_endpoint_uses_speaker_prompt tests/test_healthcheck_dashboard.py::test_run_healthcheck_reports_verify_prompt_files -q
```

Expected before implementation:

```text
FAILED ... 404 Not Found
FAILED ... assert 'verify_prompt_files' in output
```

- [ ] **Step 4: Add dashboard JavaScript helper**

In `Version3/dashboard/app.py:79-87`, add `testPrompt()` after the existing `testAudio()` helper:

```javascript
    async function testPrompt(promptName) {
      await fetch('/api/audio/prompt/' + promptName, {method: 'POST'});
      refresh();
    }
```

- [ ] **Step 5: Add dashboard buttons for each verification prompt**

In `Version3/dashboard/app.py:44-48`, in the Audio section of `INDEX_HTML`, add buttons after `Test Level 3`:

```html
      <button onclick="testPrompt('prepare_countdown')">Verify Countdown</button>
      <button onclick="testPrompt('success')">Verify Success</button>
      <button onclick="testPrompt('failed_identity')">Verify Failed</button>
      <button onclick="testPrompt('no_face')">Verify No Face</button>
      <button onclick="testPrompt('no_enrollment')">Verify No Enrollment</button>
```

- [ ] **Step 6: Add prompt playback endpoint**

In `Version3/dashboard/app.py:184-188`, add this endpoint below `alerts_test()`:

```python
    @app.post("/api/audio/prompt/{prompt_name}")
    def audio_prompt(prompt_name: str):
        allowed = set(getattr(config, "VERIFY_PROMPT_FILES", {}).keys())
        if prompt_name not in allowed:
            raise HTTPException(status_code=400, detail="unknown verification prompt")
        play_prompt = getattr(speaker, "play_prompt", None)
        if not callable(play_prompt):
            return {"ok": False, "prompt": prompt_name}
        return {"ok": bool(play_prompt(prompt_name)), "prompt": prompt_name}
```

- [ ] **Step 7: Add healthcheck for prompt files**

In `Version3/healthcheck.py:238-256`, near the existing `audio_files` check and before the `audio_backend` check, add:

```python
    verify_prompt_files = list(getattr(config, "VERIFY_PROMPT_FILES", {}).values())
    missing_prompts = [path for path in verify_prompt_files if not _file_exists(path)]
    _record(
        results,
        "PASS" if not missing_prompts else "WARN",
        "verify_prompt_files",
        "all verification prompt files exist" if not missing_prompts else "missing: " + ", ".join(missing_prompts),
    )
```

- [ ] **Step 8: Run dashboard and healthcheck tests**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests/test_dashboard_api.py tests/test_healthcheck_dashboard.py -q
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 9: Commit**

Run:

```powershell
cd D:\DATN-testing1
git add Version3/dashboard/app.py Version3/healthcheck.py Version3/tests/test_dashboard_api.py Version3/tests/test_healthcheck_dashboard.py
git commit -m "feat: expose verification voice prompt tests"
```

---

### Task 5: Document Manual Jetson Validation

**Files:**
- Modify: `Version3/docs/jetson_demo_checklist.md:93`

- [ ] **Step 1: Add manual validation section**

Append to `Version3/docs/jetson_demo_checklist.md`:

````markdown
## Driver Identity Voice Prompts

The Jetson uses local WAV files for identity verification prompts. The files must exist under:

```text
/home/nano/Version3/wav/
```

Required files:

```text
verify_prepare_countdown.wav
verify_success.wav
verify_failed_identity.wav
verify_no_face.wav
verify_no_enrollment.wav
```

After pairing the Bluetooth speaker and restarting services, test each prompt:

```bash
curl -X POST http://127.0.0.1:8080/api/audio/prompt/prepare_countdown
curl -X POST http://127.0.0.1:8080/api/audio/prompt/success
curl -X POST http://127.0.0.1:8080/api/audio/prompt/failed_identity
curl -X POST http://127.0.0.1:8080/api/audio/prompt/no_face
curl -X POST http://127.0.0.1:8080/api/audio/prompt/no_enrollment
```

Expected RFID verification behavior:

- RFID in `IDLE`: play countdown, then capture face.
- Match: play success, send `verify_snapshot` and `session_start`.
- Mismatch: play failed identity, send `verify_snapshot` and `face_mismatch`.
- No usable face: play no-face prompt, send `verify_error` with `NO_FACE_FRAME`.
- Missing enrollment: play no-enrollment prompt, send `verify_error` with `NO_ENROLLMENT`.
````

- [ ] **Step 2: Run doc-safe checks**

Run:

```powershell
cd D:\DATN-testing1
git diff --check
```

Expected:

```text
no output
```

- [ ] **Step 3: Commit**

Run:

```powershell
cd D:\DATN-testing1
git add Version3/docs/jetson_demo_checklist.md
git commit -m "docs: document driver identity voice prompts"
```

---

### Task 6: Full Regression And Jetson Deployment Check

**Files:**
- No source changes expected.
- Uses modified files from previous tasks.

- [ ] **Step 1: Run Version3 regression suite locally**

Run:

```powershell
cd D:\DATN-testing1\Version3
python -m pytest tests -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: Confirm WebQuanLi contract tests still pass**

Run:

```powershell
cd D:\DATN-testing1\WebQuanLi
python -m pytest tests -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 3: Deploy only the changed Jetson runtime files**

Run after user approval:

```powershell
cd D:\DATN-testing1
scp Version3/config.py Version3/main.py Version3/alerts/speaker.py Version3/dashboard/app.py Version3/healthcheck.py nano@192.168.2.17:/home/nano/Version3/
scp Version3/wav/*.wav nano@192.168.2.17:/home/nano/Version3/wav/
ssh nano@192.168.2.17 "sudo systemctl restart drowsiguard drowsiguard-dashboard"
```

Expected:

```text
services restart without error
```

- [ ] **Step 4: Run Jetson healthcheck**

Run:

```powershell
ssh nano@192.168.2.17 "cd /home/nano/Version3 && python3 healthcheck.py --quick"
```

Expected:

```text
verify_prompt_files PASS
audio_files PASS
audio_backend PASS
```

- [ ] **Step 5: Manual prompt smoke test on Jetson**

Run:

```powershell
ssh nano@192.168.2.17 "curl -X POST http://127.0.0.1:8080/api/audio/prompt/prepare_countdown && curl -X POST http://127.0.0.1:8080/api/audio/prompt/success && curl -X POST http://127.0.0.1:8080/api/audio/prompt/failed_identity && curl -X POST http://127.0.0.1:8080/api/audio/prompt/no_face && curl -X POST http://127.0.0.1:8080/api/audio/prompt/no_enrollment"
```

Expected:

```text
Each response contains "ok": true and the Bluetooth speaker plays the matching prompt.
```

- [ ] **Step 6: Manual cross-project verification**

1. Start WebQuanLi on Windows.
2. Confirm Jetson WebSocket is connected in WebQuanLi.
3. Confirm driver exists in WebQuanLi with RFID and face registry synced/enrolled on Jetson.
4. Scan correct RFID with correct driver face:
   - Jetson plays countdown.
   - Jetson plays success.
   - WebQuanLi receives `session_start`.
5. Scan correct RFID with wrong face:
   - Jetson plays countdown.
   - Jetson plays failed identity.
   - WebQuanLi receives `face_mismatch`.
6. Scan RFID while hiding face:
   - Jetson plays countdown.
   - Jetson plays no-face.
   - WebQuanLi receives `verify_error`.

- [ ] **Step 7: Confirm deployment did not create source changes**

Run:

```powershell
cd D:\DATN-testing1
git status --short
```

Expected:

```text
No modified `Version3` or `WebQuanLi` source files are listed after deployment validation.
Runtime-only files on the Jetson are not committed from this step.
```

---

## Self-Review

- Spec coverage:
  - RFID countdown before capture: Task 3.
  - Success voice prompt: Task 3.
  - Wrong identity voice prompt: Task 3.
  - No face/no enrollment prompts: Task 3.
  - Local WAV instead of TTS API: Tasks 1 and 2.
  - WebQuanLi synchronization preserved: Task 3 contract tests and Task 6 cross-project validation.
  - Manual Jetson testing: Tasks 4, 5, and 6.
- Completion marker scan:
  - No unfinished markers, generic file tokens, or unspecified implementation steps remain.
- Type consistency:
  - Prompt names are stable: `prepare_countdown`, `success`, `failed_identity`, `no_face`, `no_enrollment`.
  - New speaker API is stable: `play_prompt(prompt_name, wait=False, timeout=None)`.
  - Existing alert API remains stable: `play_alert(level)`.
