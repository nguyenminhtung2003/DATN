from datetime import datetime, timezone

from sqlalchemy import and_, desc, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.event_bus import event_bus
from app.models import Driver, DriverSession, HardwareIncident, Vehicle
from app.services.location_message_service import location_message_lines
from app.services.telegram_service import send_telegram_message
from app.services.time_service import format_vn_datetime


HEARTBEAT_TIMEOUT_SECONDS = 15

DEVICE_RULES = {
    "camera": {
        "label": "Camera",
        "severity": "critical",
        "reason": "Camera mất kết nối",
        "keys": ("camera_ok", "camera"),
    },
    "rfid": {
        "label": "RFID",
        "severity": "critical",
        "reason": "RFID reader mất kết nối",
        "keys": ("rfid_reader_ok", "rfid"),
    },
    "gps": {
        "label": "GPS",
        "severity": "warning",
        "reason": "GPS mất tín hiệu module",
        "keys": ("gps_uart_ok", "gps"),
    },
    "bluetooth": {
        "label": "Bluetooth",
        "severity": "warning",
        "reason": "Bluetooth hoặc loa Bluetooth mất kết nối",
        "keys": ("bluetooth_adapter_ok", "bluetooth_adapter", "bluetooth_speaker_connected", "bluetooth"),
        "mode": "all_true",
    },
    "speaker": {
        "label": "Loa",
        "severity": "warning",
        "reason": "Loa cảnh báo không khả dụng",
        "keys": ("speaker_output_ok", "speaker"),
    },
    "wifi": {
        "label": "Wi-Fi/WebSocket",
        "severity": "critical",
        "reason": "Wi-Fi hoặc WebSocket mất kết nối",
        "keys": ("wifi", "websocket_ok", "cellular"),
    },
}

JETSON_RULE = {
    "label": "Jetson",
    "severity": "critical",
    "reason": "Jetson mất heartbeat quá 15 giây",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _telegram_status(result: dict) -> tuple[str, str | None]:
    if result.get("ok"):
        return "sent", None
    return "failed", result.get("description") or "unknown error"


def _payload_status(payload: dict, rule: dict) -> bool | None:
    values = [bool(payload[key]) for key in rule["keys"] if key in payload and payload[key] is not None]
    if not values:
        return None
    if rule.get("mode") == "all_true":
        return all(values)
    return values[0]


async def _active_session(db: AsyncSession, vehicle_id: int) -> DriverSession | None:
    result = await db.execute(
        select(DriverSession)
        .options(selectinload(DriverSession.driver))
        .where(
            DriverSession.vehicle_id == vehicle_id,
            DriverSession.checkout_at.is_(None),
        )
        .order_by(DriverSession.checkin_at.desc(), DriverSession.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _vehicle(db: AsyncSession, vehicle_id: int) -> Vehicle | None:
    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    return result.scalar_one_or_none()


async def _open_incident(db: AsyncSession, vehicle_id: int, device_key: str) -> HardwareIncident | None:
    result = await db.execute(
        select(HardwareIncident)
        .where(
            HardwareIncident.vehicle_id == vehicle_id,
            HardwareIncident.device_key == device_key,
            HardwareIncident.resolved_at.is_(None),
        )
        .order_by(HardwareIncident.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _latest_gps_payload(vehicle: Vehicle | None) -> dict:
    if not vehicle or not vehicle.device_id:
        return {}
    state = event_bus.get_state(f"vehicle:{vehicle.device_id}")
    gps_payload = state.get("gps") or {}
    return gps_payload if isinstance(gps_payload, dict) else {}


def _incident_location_lines(vehicle: Vehicle | None) -> list[str]:
    gps_payload = _latest_gps_payload(vehicle)
    return location_message_lines(gps_payload.get("lat"), gps_payload.get("lng"))


def _incident_message(incident: HardwareIncident, vehicle: Vehicle | None, driver: Driver | None) -> str:
    label = DEVICE_RULES.get(incident.device_key, JETSON_RULE).get("label", incident.device_key)
    return "\n".join(
        [
            "CANH BAO THIET BI",
            f"Xe: {vehicle.plate_number if vehicle else 'Khong xac dinh'}",
            f"Thiet bi: {label}",
            f"Trang thai: {incident.reason}",
            f"Tai xe dang lai: {driver.name if driver else 'Khong co phien lai'}",
            *_incident_location_lines(vehicle),
            f"Thoi gian: {incident.first_seen_at.isoformat()}",
            "Yeu cau kiem tra thiet bi tren xe.",
        ]
    )


async def _send_incident_notifications(db: AsyncSession, incident: HardwareIncident) -> None:
    vehicle = await _vehicle(db, incident.vehicle_id)
    driver = await db.get(Driver, incident.driver_id) if incident.driver_id else None
    message = _incident_message(incident, vehicle, driver)

    admin_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
    if admin_chat_id:
        admin_result = await send_telegram_message(admin_chat_id, message)
        incident.admin_telegram_status, incident.admin_telegram_error = _telegram_status(admin_result)
    else:
        incident.admin_telegram_status = "missing_chat_id"
        incident.admin_telegram_error = "missing ADMIN_TELEGRAM_CHAT_ID"

    if driver is None:
        incident.driver_telegram_status = "not_applicable"
        incident.driver_telegram_error = None
    elif driver.telegram_chat_id:
        driver_result = await send_telegram_message(driver.telegram_chat_id, message)
        incident.driver_telegram_status, incident.driver_telegram_error = _telegram_status(driver_result)
    else:
        incident.driver_telegram_status = "missing_chat_id"
        incident.driver_telegram_error = "missing driver telegram_chat_id"


async def _create_incident(
    db: AsyncSession,
    vehicle_id: int,
    device_key: str,
    rule: dict,
    now: datetime,
) -> HardwareIncident:
    session = await _active_session(db, vehicle_id)
    incident = HardwareIncident(
        vehicle_id=vehicle_id,
        driver_id=session.driver_id if session else None,
        session_id=session.id if session else None,
        device_key=device_key,
        severity=rule["severity"],
        reason=rule["reason"],
        old_status="ok",
        new_status="error",
        first_seen_at=now,
        last_seen_at=now,
        admin_telegram_status="pending",
        driver_telegram_status="pending" if session else "not_applicable",
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    await _send_incident_notifications(db, incident)
    await db.commit()
    await db.refresh(incident)
    return incident


async def _resolve_incident(incident: HardwareIncident, now: datetime) -> HardwareIncident:
    incident.last_seen_at = now
    incident.resolved_at = now
    incident.new_status = "ok"
    return incident


async def process_hardware_payload(
    db: AsyncSession,
    vehicle_id: int,
    payload: dict,
    *,
    now: datetime | None = None,
) -> list[HardwareIncident]:
    now = now or _now()
    changed: list[HardwareIncident] = []

    jetson_incident = await _open_incident(db, vehicle_id, "jetson")
    if jetson_incident:
        changed.append(await _resolve_incident(jetson_incident, now))

    for device_key, rule in DEVICE_RULES.items():
        status = _payload_status(payload, rule)
        if status is None:
            continue

        existing = await _open_incident(db, vehicle_id, device_key)
        if status is False:
            if existing:
                existing.last_seen_at = now
                changed.append(existing)
            else:
                changed.append(await _create_incident(db, vehicle_id, device_key, rule, now))
        elif existing:
            changed.append(await _resolve_incident(existing, now))

    await db.commit()
    return changed


async def process_heartbeat_timeout(
    db: AsyncSession,
    vehicle_id: int,
    *,
    last_seen: datetime | None,
    now: datetime | None = None,
    threshold_seconds: int = HEARTBEAT_TIMEOUT_SECONDS,
) -> HardwareIncident | None:
    if last_seen is None:
        return None
    now = now or _now()
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    if (now - last_seen).total_seconds() <= threshold_seconds:
        return None

    existing = await _open_incident(db, vehicle_id, "jetson")
    if existing:
        existing.last_seen_at = now
        await db.commit()
        return existing

    return await _create_incident(db, vehicle_id, "jetson", JETSON_RULE, now)


async def process_vehicle_heartbeat_timeouts(
    db: AsyncSession,
    *,
    active_devices: set[str],
    last_seen_by_device: dict[str, datetime],
    now: datetime | None = None,
    threshold_seconds: int = HEARTBEAT_TIMEOUT_SECONDS,
) -> list[HardwareIncident]:
    now = now or _now()
    result = await db.execute(select(Vehicle).where(Vehicle.is_active.is_(True), Vehicle.device_id.is_not(None)))
    incidents = []
    for vehicle in result.scalars().all():
        if vehicle.device_id in active_devices:
            continue
        incident = await process_heartbeat_timeout(
            db,
            vehicle.id,
            last_seen=last_seen_by_device.get(vehicle.device_id),
            now=now,
            threshold_seconds=threshold_seconds,
        )
        if incident:
            incidents.append(incident)
    return incidents


def _vehicle_label(vehicle: Vehicle | None) -> str:
    if not vehicle:
        return "N/A"
    return f"{vehicle.plate_number} - {vehicle.name}" if vehicle.name else vehicle.plate_number


def format_hardware_incident(incident: HardwareIncident, vehicle: Vehicle | None, driver: Driver | None) -> dict:
    rule = DEVICE_RULES.get(incident.device_key, JETSON_RULE)
    is_open = incident.resolved_at is None
    return {
        "id": incident.id,
        "device_key": incident.device_key,
        "device_label": rule.get("label", incident.device_key),
        "severity": incident.severity,
        "reason": incident.reason,
        "first_seen_display": format_vn_datetime(incident.first_seen_at),
        "last_seen_display": format_vn_datetime(incident.last_seen_at),
        "resolved_display": format_vn_datetime(incident.resolved_at, empty="-"),
        "status_text": "Đang lỗi" if is_open else "Đã khôi phục",
        "is_open": is_open,
        "vehicle_label": _vehicle_label(vehicle),
        "driver_name": driver.name if driver else "N/A",
        "admin_telegram_status": incident.admin_telegram_status,
        "driver_telegram_status": incident.driver_telegram_status,
    }


async def list_hardware_incidents(
    db: AsyncSession,
    *,
    vehicle_id: int | None = None,
    open_only: bool = False,
    limit: int = 100,
) -> list[dict]:
    clauses = []
    if vehicle_id is not None:
        clauses.append(HardwareIncident.vehicle_id == vehicle_id)
    if open_only:
        clauses.append(HardwareIncident.resolved_at.is_(None))

    query = (
        select(HardwareIncident, Vehicle, Driver)
        .join(Vehicle, Vehicle.id == HardwareIncident.vehicle_id)
        .outerjoin(Driver, Driver.id == HardwareIncident.driver_id)
        .order_by(desc(HardwareIncident.first_seen_at), desc(HardwareIncident.id))
        .limit(limit)
    )
    if clauses:
        query = query.where(and_(*clauses))

    try:
        rows = (await db.execute(query)).all()
    except OperationalError as exc:
        if "hardware_incidents" in str(exc):
            return []
        raise
    return [format_hardware_incident(incident, vehicle, driver) for incident, vehicle, driver in rows]
