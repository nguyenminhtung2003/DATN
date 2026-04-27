from pathlib import Path
import shutil
import uuid

from storage.runtime_status import RuntimeStatusStore


def make_workspace_tmp():
    path = Path(__file__).resolve().parents[1] / "storage" / "_test_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_runtime_status_store_writes_and_reads_atomic_json():
    runtime_dir = make_workspace_tmp()
    store = RuntimeStatusStore(runtime_dir)

    try:
        payload = {
            "device": {"device_id": "JETSON-001"},
            "ai": {"state": "NORMAL", "confidence": 0.9},
            "queue": {"pending": 2},
        }
        store.write(payload)

        loaded = store.read()
        assert loaded["device"]["device_id"] == "JETSON-001"
        assert loaded["ai"]["state"] == "NORMAL"
        assert loaded["queue"]["pending"] == 2
        assert "updated_at" in loaded
        assert not Path(runtime_dir, "status.json.tmp").exists()
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)


def test_runtime_status_store_returns_default_when_missing():
    runtime_dir = make_workspace_tmp()
    store = RuntimeStatusStore(runtime_dir)

    try:
        loaded = store.read()

        assert loaded["device"]["device_id"] == "unknown"
        assert loaded["ai"]["state"] == "UNKNOWN"
        assert loaded["alert"]["level"] == "NONE"
    finally:
        shutil.rmtree(str(runtime_dir.parent), ignore_errors=True)
