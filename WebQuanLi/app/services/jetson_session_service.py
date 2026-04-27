from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AlertLevel, AlertType, Driver, DriverSession, SystemAlert


async def resolve_driver_by_rfid(db: AsyncSession, rfid_tag: str) -> Driver | None:
    result = await db.execute(select(Driver).where(Driver.rfid_tag == rfid_tag))
    return result.scalar_one_or_none()


async def get_active_session(db: AsyncSession, vehicle_id: int) -> DriverSession | None:
    result = await db.execute(
        select(DriverSession).where(
            DriverSession.vehicle_id == vehicle_id,
            DriverSession.checkout_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def start_or_reuse_session(db: AsyncSession, vehicle_id: int, driver_id: int, timestamp: float | None = None) -> DriverSession:
    active_session = await get_active_session(db, vehicle_id)
    if active_session and active_session.driver_id == driver_id:
        return active_session

    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc)

    if active_session:
        active_session.checkout_at = dt

    session = DriverSession(vehicle_id=vehicle_id, driver_id=driver_id, checkin_at=dt)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def close_active_session(db: AsyncSession, vehicle_id: int, timestamp: float | None = None) -> DriverSession | None:
    active_session = await get_active_session(db, vehicle_id)
    if not active_session:
        return None

    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc)
    active_session.checkout_at = dt
    await db.commit()
    await db.refresh(active_session)
    return active_session


async def create_drowsiness_alert(
    db: AsyncSession,
    vehicle_id: int,
    level: AlertLevel,
    ear: float | None = None,
    mar: float | None = None,
    pitch: float | None = None,
    perclos: float | None = None,
    ai_state: str | None = None,
    ai_confidence: float | None = None,
    ai_reason: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    timestamp: float | None = None,
) -> SystemAlert:
    active_session = await get_active_session(db, vehicle_id)
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc)

    if timestamp is not None:
        duplicate_query = select(SystemAlert).where(
            SystemAlert.vehicle_id == vehicle_id,
            SystemAlert.alert_type == AlertType.DROWSINESS,
            SystemAlert.alert_level == level,
            SystemAlert.timestamp == dt,
            SystemAlert.session_id == (active_session.id if active_session else None),
        )
        duplicate = (await db.execute(duplicate_query)).scalar_one_or_none()
        if duplicate:
            return duplicate
    
    msg_parts = []
    if ai_state:
        msg_parts.append(f"AI={ai_state}")
    if ai_confidence is not None:
        msg_parts.append(f"confidence={ai_confidence}")
    if ai_reason:
        msg_parts.append(f"reason={ai_reason}")
    if perclos is not None:
        msg_parts.append(f"perclos={perclos}")
        
    message = " ".join(msg_parts) if msg_parts else None

    alert = SystemAlert(
        vehicle_id=vehicle_id,
        driver_id=active_session.driver_id if active_session else None,
        session_id=active_session.id if active_session else None,
        alert_type=AlertType.DROWSINESS,
        alert_level=level,
        ear_value=ear,
        mar_value=mar,
        pitch_value=pitch,
        message=message,
        latitude=lat,
        longitude=lng,
        timestamp=dt,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert
