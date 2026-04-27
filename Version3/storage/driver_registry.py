"""
Local driver face registry and sync cache for demo-safe Jetson runtime.
"""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import config
from utils.logger import get_logger

logger = get_logger("storage.driver_registry")


class DriverRegistry:
    """Manage local RFID -> reference image cache."""

    def __init__(self, data_dir: str = None, registry_path: str = None):
        self.data_dir = data_dir or config.FACE_DATA_DIR
        self.registry_path = registry_path or config.FACE_REGISTRY_PATH
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)

    def driver_dir(self, rfid_uid: str) -> str:
        return os.path.join(self.data_dir, rfid_uid)

    def reference_path(self, rfid_uid: str) -> str:
        return os.path.join(self.driver_dir(rfid_uid), "reference.jpg")

    def has_enrollment(self, rfid_uid: str) -> bool:
        return os.path.exists(self.reference_path(rfid_uid))

    def load_manifest(self) -> dict:
        if not os.path.exists(self.registry_path):
            return {
                "device_id": config.DEVICE_ID,
                "generated_at": None,
                "drivers": [],
            }
        with open(self.registry_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def save_manifest(self, manifest: dict):
        normalized = {
            "device_id": manifest.get("device_id") or config.DEVICE_ID,
            "generated_at": manifest.get("generated_at") or self._now_iso(),
            "drivers": sorted(
                manifest.get("drivers", []),
                key=lambda driver: driver.get("rfid_tag", ""),
            ),
        }
        with open(self.registry_path, "w", encoding="utf-8") as fh:
            json.dump(normalized, fh, indent=2, ensure_ascii=False)

    def upsert_local_driver(
        self,
        rfid_uid: str,
        driver_name: str = None,
        source_url: str = None,
        reference_source: str = "jetson_ir",
        reference_role: str = "primary",
    ):
        manifest = self.load_manifest()
        drivers = [driver for driver in manifest.get("drivers", []) if driver.get("rfid_tag") != rfid_uid]
        drivers.append({
            "name": driver_name or rfid_uid,
            "rfid_tag": rfid_uid,
            "face_image_url": source_url,
            "local_reference_path": self.reference_path(rfid_uid),
            "reference_source": reference_source or "jetson_ir",
            "reference_role": reference_role or "primary",
        })
        manifest["generated_at"] = self._now_iso()
        manifest["drivers"] = drivers
        self.save_manifest(manifest)

    def save_reference_bytes(self, rfid_uid: str, payload: bytes):
        driver_dir = self.driver_dir(rfid_uid)
        os.makedirs(driver_dir, exist_ok=True)
        with open(self.reference_path(rfid_uid), "wb") as fh:
            fh.write(payload)

    def copy_reference_file(self, rfid_uid: str, source_path: str):
        driver_dir = self.driver_dir(rfid_uid)
        os.makedirs(driver_dir, exist_ok=True)
        shutil.copyfile(source_path, self.reference_path(rfid_uid))

    def sync_from_manifest_url(self, manifest_url: str) -> dict:
        logger.info(f"Syncing driver registry from {manifest_url}")
        with urlopen(manifest_url, timeout=getattr(config, "FACE_SYNC_TIMEOUT_SEC", 10.0)) as response:
            manifest = json.loads(response.read().decode("utf-8"))
        return self.sync_from_manifest(manifest)

    def sync_from_manifest(self, manifest: dict) -> dict:
        desired_rfids = set()
        normalized_drivers = []

        for driver in manifest.get("drivers", []):
            rfid_uid = (driver.get("rfid_tag") or "").strip()
            face_url = driver.get("face_image_url")
            if not rfid_uid or not face_url:
                continue

            desired_rfids.add(rfid_uid)
            payload = self._download_bytes(face_url)
            self.save_reference_bytes(rfid_uid, payload)
            reference_source = driver.get("reference_source") or "webquanli_sync"
            reference_role = driver.get("reference_role") or "fallback"
            normalized_drivers.append({
                "name": driver.get("name") or rfid_uid,
                "rfid_tag": rfid_uid,
                "face_image_url": face_url,
                "local_reference_path": self.reference_path(rfid_uid),
                "reference_source": reference_source,
                "reference_role": reference_role,
            })

        self._remove_stale_entries(desired_rfids)
        self.save_manifest({
            "device_id": manifest.get("device_id") or config.DEVICE_ID,
            "generated_at": manifest.get("generated_at") or self._now_iso(),
            "drivers": normalized_drivers,
        })
        logger.info(f"Driver registry sync complete. Drivers={len(normalized_drivers)}")
        return self.load_manifest()

    def _remove_stale_entries(self, desired_rfids):
        data_root = Path(self.data_dir).resolve()
        for candidate in data_root.iterdir():
            if not candidate.is_dir():
                continue
            if candidate.name in desired_rfids:
                continue
            if data_root not in candidate.resolve().parents:
                continue
            shutil.rmtree(candidate)

    def _download_bytes(self, url: str) -> bytes:
        with urlopen(url, timeout=getattr(config, "FACE_SYNC_TIMEOUT_SEC", 10.0)) as response:
            return response.read()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
