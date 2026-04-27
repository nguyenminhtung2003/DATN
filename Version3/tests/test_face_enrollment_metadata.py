import os
import shutil
import uuid
from pathlib import Path

import config
from camera.face_verifier import FaceVerifier
from storage.driver_registry import DriverRegistry


def make_face_matrix(background=40):
    image = [[background for _ in range(48)] for _ in range(48)]
    for y in range(12, 18):
        for x in range(10, 16):
            image[y][x] = 220
        for x in range(30, 36):
            image[y][x] = 220
    for y in range(28, 31):
        for x in range(18, 30):
            image[y][x] = 255
    return image


def make_temp_registry():
    test_tmp_root = Path(__file__).resolve().parents[1] / "storage" / "_test_face_enrollment"
    test_tmp_root.mkdir(parents=True, exist_ok=True)
    return str(test_tmp_root / f"face-enrollment-{uuid.uuid4().hex}")


def test_enroll_from_jetson_frame_records_ir_source():
    temp_dir = make_temp_registry()
    original_face_data_dir = config.FACE_DATA_DIR
    original_registry_path = config.FACE_REGISTRY_PATH
    config.FACE_DATA_DIR = os.path.join(temp_dir, "driver_faces")
    config.FACE_REGISTRY_PATH = os.path.join(temp_dir, "driver_registry.json")

    try:
        verifier = FaceVerifier()

        assert verifier.enroll_driver("UID-001", make_face_matrix(), driver_name="Driver Demo")

        manifest = verifier.registry.load_manifest()
        driver = manifest["drivers"][0]
        assert driver["rfid_tag"] == "UID-001"
        assert driver["reference_source"] == "jetson_ir"
        assert driver["reference_role"] == "primary"
    finally:
        config.FACE_DATA_DIR = original_face_data_dir
        config.FACE_REGISTRY_PATH = original_registry_path
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sync_from_manifest_defaults_to_webquanli_fallback_metadata():
    temp_dir = make_temp_registry()
    source_dir = Path(temp_dir) / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_image = source_dir / "driver.face"
    source_image.write_text("[[1, 2], [3, 4]]", encoding="utf-8")
    original_face_data_dir = config.FACE_DATA_DIR
    original_registry_path = config.FACE_REGISTRY_PATH
    config.FACE_DATA_DIR = os.path.join(temp_dir, "driver_faces")
    config.FACE_REGISTRY_PATH = os.path.join(temp_dir, "driver_registry.json")

    try:
        registry = DriverRegistry()

        manifest = registry.sync_from_manifest({
            "drivers": [{
                "name": "Driver Sync",
                "rfid_tag": "UID-SYNC",
                "face_image_url": source_image.resolve().as_uri(),
            }],
        })

        driver = manifest["drivers"][0]
        assert driver["reference_source"] == "webquanli_sync"
        assert driver["reference_role"] == "fallback"
    finally:
        config.FACE_DATA_DIR = original_face_data_dir
        config.FACE_REGISTRY_PATH = original_registry_path
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sync_from_manifest_preserves_explicit_jetson_ir_metadata():
    temp_dir = make_temp_registry()
    source_dir = Path(temp_dir) / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_image = source_dir / "driver.face"
    source_image.write_text("[[1, 2], [3, 4]]", encoding="utf-8")
    original_face_data_dir = config.FACE_DATA_DIR
    original_registry_path = config.FACE_REGISTRY_PATH
    config.FACE_DATA_DIR = os.path.join(temp_dir, "driver_faces")
    config.FACE_REGISTRY_PATH = os.path.join(temp_dir, "driver_registry.json")

    try:
        registry = DriverRegistry()

        manifest = registry.sync_from_manifest({
            "drivers": [{
                "name": "Driver IR",
                "rfid_tag": "UID-IR",
                "face_image_url": source_image.resolve().as_uri(),
                "reference_source": "jetson_ir",
                "reference_role": "primary",
            }],
        })

        driver = manifest["drivers"][0]
        assert driver["reference_source"] == "jetson_ir"
        assert driver["reference_role"] == "primary"
    finally:
        config.FACE_DATA_DIR = original_face_data_dir
        config.FACE_REGISTRY_PATH = original_registry_path
        shutil.rmtree(temp_dir, ignore_errors=True)
