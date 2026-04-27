from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, Vehicle, DriverSession, SystemAlert, HardwareStatus
from app.core.event_bus import event_bus
from app.ws.jetson_handler import manager

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


def _format_last_seen(value):
    if value is None:
        return "Chưa có dữ liệu"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_gps_summary(gps_payload):
    if not gps_payload:
        return "Chưa có fix GPS"
    lat = gps_payload.get("lat")
    lng = gps_payload.get("lng")
    if lat is None or lng is None:
        return "Chưa có fix GPS"
    speed = gps_payload.get("speed")
    if speed is None:
        return f"{lat:.6f}, {lng:.6f}"
    return f"{lat:.6f}, {lng:.6f} • {speed:.1f} km/h"


def _is_recent_hardware(hw_status, max_age_seconds=20):
    if not hw_status or not getattr(hw_status, "timestamp", None):
        return False
    timestamp = hw_status.timestamp
    now = datetime.utcnow() if timestamp.tzinfo is None else datetime.now(timezone.utc)
    age_seconds = (now - timestamp).total_seconds()
    return -5 <= age_seconds <= max_age_seconds


def _pick_bool(payload, explicit_key, legacy_key=None, fallback=False):
    if payload and payload.get(explicit_key) is not None:
        return bool(payload.get(explicit_key))
    if legacy_key and payload and payload.get(legacy_key) is not None:
        return bool(payload.get(legacy_key))
    return bool(fallback)


def _optional_bool(payload, explicit_key, legacy_key=None):
    if payload and payload.get(explicit_key) is not None:
        return bool(payload.get(explicit_key))
    if legacy_key and payload and payload.get(legacy_key) is not None:
        return bool(payload.get(legacy_key))
    return None


def _combined_ok(values, fallback=False):
    explicit_values = [value for value in values if value is not None]
    if not explicit_values:
        return bool(fallback)
    return all(explicit_values)


def _build_hardware_badges(hw_status, cached_hardware):
    cached_hardware = cached_hardware or {}
    gps_uart_ok = _optional_bool(cached_hardware, "gps_uart_ok", "gps")
    gps_fix_ok = _optional_bool(cached_hardware, "gps_fix_ok")
    gps_ok = _combined_ok((gps_uart_ok, gps_fix_ok), fallback=getattr(hw_status, "gps_ok", False))
    speaker_adapter_ok = _optional_bool(cached_hardware, "bluetooth_adapter_ok", "bluetooth_adapter")
    speaker_connected_ok = _optional_bool(cached_hardware, "bluetooth_speaker_connected", "bluetooth")
    speaker_output_ok = _optional_bool(cached_hardware, "speaker_output_ok", "speaker")
    speaker_ok = _combined_ok(
        (speaker_adapter_ok, speaker_connected_ok, speaker_output_ok),
        fallback=getattr(hw_status, "speaker_ok", False),
    )
    return [
        {
            "key": "power",
            "label": "Nguồn",
            "icon": "⚡",
            "ok": _pick_bool(cached_hardware, "power", fallback=getattr(hw_status, "power_ok", False)),
        },
        {
            "key": "rfid",
            "label": "RFID",
            "icon": "💳",
            "ok": _pick_bool(cached_hardware, "rfid_reader_ok", "rfid", getattr(hw_status, "rfid_ok", False)),
        },
        {
            "key": "gps",
            "label": "GPS",
            "icon": "📍",
            "ok": gps_ok,
        },
        {
            "key": "camera",
            "label": "Camera",
            "icon": "📷",
            "ok": _pick_bool(cached_hardware, "camera_ok", "camera", getattr(hw_status, "camera_ok", False)),
        },
        {
            "key": "speaker",
            "label": "Loa",
            "icon": "🔊",
            "ok": speaker_ok,
        },
    ]


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicles_result = await db.execute(select(Vehicle).where(Vehicle.is_active == True))
    vehicles = vehicles_result.scalars().all()

    vehicle = vehicles[0] if vehicles else None
    device_id = vehicle.device_id if vehicle else "JETSON-001"

    # Get active session
    active_session = None
    if vehicle:
        sess_result = await db.execute(
            select(DriverSession).where(
                DriverSession.vehicle_id == vehicle.id,
                DriverSession.checkout_at.is_(None),
            )
        )
        active_session = sess_result.scalar_one_or_none()

    # Get recent alerts
    alerts_result = await db.execute(
        select(SystemAlert).order_by(SystemAlert.timestamp.desc()).limit(20)
    )
    recent_alerts = alerts_result.scalars().all()

    # Get latest hardware status
    hw_status = None
    if vehicle:
        hw_result = await db.execute(
            select(HardwareStatus)
            .where(HardwareStatus.vehicle_id == vehicle.id)
            .order_by(HardwareStatus.timestamp.desc())
            .limit(1)
        )
        hw_status = hw_result.scalar_one_or_none()

    # Get cached state from event bus. Hardware rows are also a reliable
    # heartbeat because Jetson publishes them every few seconds.
    state = event_bus.get_state(f"vehicle:{device_id}")
    cached_hardware = state.get("hardware") or {}
    cached_gps = state.get("gps") or {}
    is_connected = device_id in manager.active
    last_seen = manager.last_seen.get(device_id)
    if last_seen is None and _is_recent_hardware(hw_status):
        last_seen = hw_status.timestamp

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "request": request,
        "user": user,
        "vehicles": vehicles,
        "vehicle": vehicle,
        "device_id": device_id,
        "hw_status": hw_status,
        "active_session": active_session,
        "recent_alerts": recent_alerts,
        "cached_state": state,
        "connection_status": "online" if is_connected else "offline",
        "hardware_badges": _build_hardware_badges(hw_status, cached_hardware),
        "last_seen_text": _format_last_seen(last_seen),
        "queue_pending_initial": cached_hardware.get("queue_pending", 0),
        "latest_gps": cached_gps,
        "latest_gps_summary": _format_gps_summary(cached_gps),
    })
