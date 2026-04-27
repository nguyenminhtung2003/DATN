import hashlib
import io
import re
import zipfile

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import check_admin
from app.config import settings
from app.core.event_bus import event_bus
from app.database import get_db
from app.models import AlertLevel, AlertType, OtaAuditLog, SystemAlert, User, Vehicle
from app.schemas import WsCommandOut
from app.ws.jetson_handler import manager

router = APIRouter(prefix="/api", tags=["control"])

SAFE_UPDATE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ALLOWED_UPDATE_SUFFIXES = {".py", ".zip"}


def _sanitize_update_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not SAFE_UPDATE_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_UPDATE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Chi cho phep file .py hoac .zip")
    return filename


def _validate_update_package(filename: str, content: bytes):
    if filename.endswith(".py"):
        return
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if "manifest.json" not in archive.namelist():
                raise HTTPException(status_code=400, detail="Package OTA phai co manifest.json")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Package OTA khong phai zip hop le")


def _monitoring_button_html(vehicle_id: int, state: str, message: str, is_warning: bool = False) -> str:
    next_state = "disconnect" if state == "connect" else "connect"
    label = "Ngat giam sat" if state == "connect" else "Ket noi giam sat"
    btn_class = "btn btn-outline-danger" if state == "connect" else "btn btn-primary"
    status_class = "alert-warning" if is_warning else "alert-success"
    return (
        f'<div id="monitoring-control">'
        f'<button hx-post="/api/vehicles/{vehicle_id}/monitoring" '
        f'hx-vals=\'{{"state": "{next_state}"}}\' '
        f'hx-target="#monitoring-control" hx-swap="outerHTML" '
        f'class="{btn_class}">{label}</button>'
        f'<div class="{status_class}" id="monitoring-status">{message}</div>'
        f'</div>'
    )


def _monitoring_payload(device_id: str | None, state: str, message: str, sent: bool) -> dict:
    if not sent:
        return {
            "state": "offline",
            "next_state": "connect",
            "connection_status": "offline",
            "device_id": device_id,
            "message": message,
            "sent": False,
        }
    return {
        "state": state,
        "next_state": "disconnect" if state == "connect" else "connect",
        "connection_status": "online",
        "device_id": device_id,
        "message": message,
        "sent": True,
    }


def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "").lower()


@router.post("/vehicles/{vehicle_id}/monitoring")
async def set_monitoring_state(
    vehicle_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    form = await request.form()
    state = form.get("state", "connect")
    if state not in ("connect", "disconnect"):
        raise HTTPException(status_code=400, detail="Trang thai monitoring khong hop le")

    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Xe khong tim thay")

    action = "connect_monitoring" if state == "connect" else "disconnect_monitoring"
    command = WsCommandOut(action=action).model_dump(exclude_none=True)
    if vehicle.device_id and vehicle.device_id in manager.active:
        await manager.send_command(vehicle.device_id, command)
        await event_bus.publish(
            f"vehicle:{vehicle.device_id}",
            "monitoring",
            {"status": state, "device_id": vehicle.device_id},
        )
        message = "Da gui lenh ket noi giam sat" if state == "connect" else "Da gui lenh ngat giam sat"
        if _wants_json(request):
            return JSONResponse(_monitoring_payload(vehicle.device_id, state, message, sent=True))
        return HTMLResponse(_monitoring_button_html(vehicle.id, state, message))

    message = "Jetson dang offline, chua gui duoc lenh"
    if _wants_json(request):
        return JSONResponse(
            _monitoring_payload(vehicle.device_id, "offline", message, sent=False),
            status_code=409,
        )
    return HTMLResponse(
        _monitoring_button_html(
            vehicle.id,
            "disconnect",
            message,
            is_warning=True,
        )
    )


@router.post("/vehicles/{vehicle_id}/update")
async def upload_ota_code(
    vehicle_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    filename = _sanitize_update_filename(file.filename)

    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Xe khong tim thay")

    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    _validate_update_package(filename, content)
    checksum = hashlib.sha256(content).hexdigest()
    filepath = settings.UPLOAD_DIR / filename

    async with aiofiles.open(str(filepath), "wb") as f:
        await f.write(content)

    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/static/updates/{filename}"

    status = "stored_offline"
    if vehicle.device_id and vehicle.device_id in manager.active:
        await manager.send_command(vehicle.device_id, {
            "action": "update_software",
            "download_url": download_url,
            "filename": filename,
            "checksum": checksum,
        })
        status = "sent"

    db.add(OtaAuditLog(
        vehicle_id=vehicle.id,
        username=user.username,
        filename=filename,
        checksum=checksum,
        status=status,
        message=f"OTA file saved to {filepath.name}",
    ))
    await db.commit()

    if status == "sent":
        return HTMLResponse(
            f'<div class="alert-success" id="upload-status">'
            f'File <strong>{filename}</strong> da gui den Jetson. Dang cap nhat...</div>'
        )

    return HTMLResponse(
        '<div class="alert-warning" id="upload-status">'
        'File da luu nhung Jetson dang offline. Se cap nhat khi ket noi lai.</div>'
    )


@router.post("/vehicles/{vehicle_id}/test")
async def test_alert(
    vehicle_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    form = await request.form()
    try:
        level = int(form.get("level", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Muc canh bao phai la so 1, 2 hoac 3")
    state = form.get("state", "on")
    if level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Muc canh bao chi duoc la 1, 2 hoac 3")
    if state not in ("on", "off"):
        raise HTTPException(status_code=400, detail="Trang thai test alert chi duoc la on hoac off")

    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Xe khong tim thay")

    if vehicle.device_id and vehicle.device_id in manager.active:
        await manager.send_command(vehicle.device_id, {
            "action": "test_alert",
            "level": level,
            "state": state,
        })

    new_state = "off" if state == "on" else "on"
    level_labels = {1: "info", 2: "warning", 3: "danger"}
    level_names = {1: "Muc 1", 2: "Muc 2", 3: "Muc 3"}
    btn_class = level_labels.get(level, "info")

    if state == "on":
        return HTMLResponse(
            f'<button hx-post="/api/vehicles/{vehicle_id}/test" '
            f'hx-vals=\'{{"level": {level}, "state": "{new_state}"}}\' '
            f'hx-swap="outerHTML" '
            f'class="btn btn-{btn_class} active">Tat {level_names[level]}</button>'
        )

    return HTMLResponse(
        f'<button hx-post="/api/vehicles/{vehicle_id}/test" '
        f'hx-vals=\'{{"level": {level}, "state": "{new_state}"}}\' '
        f'hx-swap="outerHTML" '
        f'class="btn btn-outline-{btn_class}">Bat {level_names[level]}</button>'
    )


@router.post("/vehicles/{vehicle_id}/test-alert-log")
async def create_test_alert(
    vehicle_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    form = await request.form()
    level = int(form.get("level", 1))

    level_map = {1: AlertLevel.LEVEL_1, 2: AlertLevel.LEVEL_2, 3: AlertLevel.LEVEL_3}
    alert = SystemAlert(
        vehicle_id=vehicle_id,
        alert_type=AlertType.TEST,
        alert_level=level_map.get(level, AlertLevel.LEVEL_1),
        message=f"Test alert muc {level} boi admin {user.username}",
    )
    db.add(alert)
    await db.commit()
    return {"status": "logged"}
