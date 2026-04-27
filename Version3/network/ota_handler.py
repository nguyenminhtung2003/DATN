"""
DrowsiGuard OTA handler.

Safe file-level OTA: download -> checksum -> py_compile -> backup -> replace.
The caller is responsible for restarting the service after APPLIED if desired.
"""
import hashlib
import os
import py_compile
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
from urllib.request import urlopen

from utils.logger import get_logger
import config

logger = get_logger("network.ota_handler")


class OTAHandler:
    """Apply a validated Python file update with backup and status callbacks."""

    def __init__(
        self,
        on_status=None,
        project_dir: str = None,
        download_dir: str = None,
        backup_dir: str = None,
        restart_command: Optional[List[str]] = None,
    ):
        self._on_status = on_status
        self.project_dir = Path(project_dir or config.OTA_PROJECT_DIR).resolve()
        self.download_dir = Path(download_dir or config.OTA_DOWNLOAD_DIR).resolve()
        self.backup_dir = Path(backup_dir or config.OTA_BACKUP_DIR).resolve()
        self.restart_command = restart_command
        logger.info(f"OTAHandler initialized project_dir={self.project_dir}")

    def handle_update_command(self, command: dict) -> dict:
        filename = command.get("filename")
        download_url = command.get("download_url")
        checksum = command.get("checksum")

        try:
            safe_name = self._safe_filename(filename)
            if not download_url:
                raise ValueError("download_url is required")

            self._emit("DOWNLOADING", safe_name, progress=0)
            payload = self._download(download_url)
            if checksum:
                actual = hashlib.sha256(payload).hexdigest()
                if actual.lower() != checksum.lower():
                    raise ValueError("checksum mismatch")

            self.download_dir.mkdir(parents=True, exist_ok=True)
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self.download_dir / safe_name
            tmp_path.write_bytes(payload)

            py_compile.compile(str(tmp_path), doraise=True)
            self._emit("VERIFIED", safe_name, progress=50)

            target = (self.project_dir / safe_name).resolve()
            if self.project_dir not in target.parents:
                raise ValueError("filename escapes project directory")

            if target.exists():
                backup = self.backup_dir / f"{safe_name}.{int(time.time())}.bak"
                shutil.copy2(target, backup)
            shutil.copy2(tmp_path, target)

            if self.restart_command:
                subprocess.run(self.restart_command, check=True, timeout=30)

            return self._emit("APPLIED", safe_name, progress=100)
        except Exception as exc:
            logger.error(f"OTA failed: {exc}", exc_info=True)
            return self._emit("FAILED", filename, progress=0, error=str(exc))

    def _emit(self, status: str, filename: Optional[str], progress: int = 0, error: Optional[str] = None) -> dict:
        payload = {
            "status": status,
            "filename": filename,
            "progress": progress,
            "error": error,
        }
        if self._on_status:
            self._on_status(payload)
        return payload

    @staticmethod
    def _safe_filename(filename: Optional[str]) -> str:
        if not filename:
            raise ValueError("filename is required")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError("invalid filename")
        if not filename.endswith(".py"):
            raise ValueError("only .py updates are supported")
        return filename

    @staticmethod
    def _download(download_url: str) -> bytes:
        parsed = urlparse(download_url)
        if parsed.scheme == "file":
            path = url2pathname(unquote(parsed.path))
            if path.startswith("\\") and len(path) > 3 and path[2] == ":":
                path = path.lstrip("\\")
            return Path(path).read_bytes()
        with urlopen(download_url, timeout=15) as response:
            return response.read()
