from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Driver, DriverSession, SystemAlert, Vehicle
from app.services.time_service import format_vn_datetime, local_date_to_utc_bounds


ALERT_RETENTION_DAYS = 7
DEFAULT_ALERT_DISPLAY_LIMIT = 100
DEFAULT_PER_PAGE = 25


def _utc_naive(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _retention_cutoff(now_utc: datetime | None = None) -> datetime:
    return _utc_naive(now_utc) - timedelta(days=ALERT_RETENTION_DAYS)


def _clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _clean_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _enum_text(value, default="N/A"):
    if value is None:
        return default
    return getattr(value, "value", str(value))


def _metric_text(value):
    if value is None:
        return "-"
    return "%.2f" % value


def _vehicle_label(vehicle):
    if not vehicle:
        return "N/A"
    if vehicle.name:
        return "%s - %s" % (vehicle.plate_number, vehicle.name)
    return vehicle.plate_number or "N/A"


def _duration_text(start, end):
    if not start:
        return "-"
    end = end or datetime.now(timezone.utc).replace(tzinfo=None)
    total = max(0, int((end - start).total_seconds()))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def _alert_filters(
    *,
    date_from=None,
    date_to=None,
    vehicle_id=None,
    alert_type=None,
    q=None,
    now_utc=None,
):
    filters = [SystemAlert.timestamp >= _retention_cutoff(now_utc)]
    vehicle_id = _clean_int(vehicle_id)
    alert_type = _clean_text(alert_type)
    q = _clean_text(q)
    start_utc, end_utc = local_date_to_utc_bounds(date_from, date_to)

    if vehicle_id is not None:
        filters.append(SystemAlert.vehicle_id == vehicle_id)
    if alert_type:
        filters.append(SystemAlert.alert_type == alert_type)
    if start_utc:
        filters.append(SystemAlert.timestamp >= start_utc)
    if end_utc:
        filters.append(SystemAlert.timestamp < end_utc)
    if q:
        pattern = "%%%s%%" % q
        filters.append(or_(
            SystemAlert.message.ilike(pattern),
            SystemAlert.alert_type.ilike(pattern),
            SystemAlert.alert_level.ilike(pattern),
            Vehicle.plate_number.ilike(pattern),
            Vehicle.name.ilike(pattern),
            Driver.name.ilike(pattern),
        ))
    return filters


def _has_alert_filter(date_from=None, date_to=None, vehicle_id=None, alert_type=None, q=None):
    return any([
        _clean_text(date_from),
        _clean_text(date_to),
        _clean_int(vehicle_id) is not None,
        _clean_text(alert_type),
        _clean_text(q),
    ])


def _alert_item(alert, vehicle, driver):
    return {
        "id": alert.id,
        "display_time": format_vn_datetime(alert.timestamp),
        "alert_type": _enum_text(alert.alert_type),
        "alert_level": _enum_text(alert.alert_level),
        "ear_text": _metric_text(alert.ear_value),
        "mar_text": _metric_text(alert.mar_value),
        "pitch_text": _metric_text(alert.pitch_value),
        "message": alert.message or "-",
        "vehicle_label": _vehicle_label(vehicle),
        "driver_name": driver.name if driver else "N/A",
        "is_face_mismatch": _enum_text(alert.alert_type) == "FACE_MISMATCH",
    }


async def purge_old_alerts(db: AsyncSession, now_utc: datetime | None = None) -> int:
    cutoff = _retention_cutoff(now_utc)
    count_result = await db.execute(
        select(func.count()).select_from(SystemAlert).where(SystemAlert.timestamp < cutoff)
    )
    deleted = count_result.scalar() or 0
    if deleted:
        await db.execute(delete(SystemAlert).where(SystemAlert.timestamp < cutoff))
        await db.commit()
    return deleted


async def delete_alert_history(db: AsyncSession, filters: dict | None = None, now_utc: datetime | None = None) -> int:
    filters = filters or {}
    clauses = _alert_filters(
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        vehicle_id=filters.get("vehicle_id"),
        alert_type=filters.get("alert_type"),
        q=filters.get("q"),
        now_utc=now_utc,
    )
    count_result = await db.execute(
        select(func.count())
        .select_from(SystemAlert)
        .outerjoin(Vehicle, SystemAlert.vehicle_id == Vehicle.id)
        .outerjoin(Driver, SystemAlert.driver_id == Driver.id)
        .where(and_(*clauses))
    )
    deleted = count_result.scalar() or 0
    if deleted:
        ids_result = await db.execute(
            select(SystemAlert.id)
            .outerjoin(Vehicle, SystemAlert.vehicle_id == Vehicle.id)
            .outerjoin(Driver, SystemAlert.driver_id == Driver.id)
            .where(and_(*clauses))
        )
        ids = [row[0] for row in ids_result.all()]
        await db.execute(delete(SystemAlert).where(SystemAlert.id.in_(ids)))
        await db.commit()
    return deleted


async def list_alert_history(
    db: AsyncSession,
    *,
    date_from=None,
    date_to=None,
    vehicle_id=None,
    alert_type=None,
    q=None,
    page=1,
    per_page=DEFAULT_PER_PAGE,
    now_utc=None,
) -> dict:
    page = max(1, int(page or 1))
    per_page = max(1, min(100, int(per_page or DEFAULT_PER_PAGE)))
    clauses = _alert_filters(
        date_from=date_from,
        date_to=date_to,
        vehicle_id=vehicle_id,
        alert_type=alert_type,
        q=q,
        now_utc=now_utc,
    )
    filtered = _has_alert_filter(date_from, date_to, vehicle_id, alert_type, q)

    count_query = (
        select(func.count())
        .select_from(SystemAlert)
        .outerjoin(Vehicle, SystemAlert.vehicle_id == Vehicle.id)
        .outerjoin(Driver, SystemAlert.driver_id == Driver.id)
        .where(and_(*clauses))
    )
    retained_total = (await db.execute(count_query)).scalar() or 0
    total = retained_total if filtered else min(retained_total, DEFAULT_ALERT_DISPLAY_LIMIT)

    offset = (page - 1) * per_page
    limit = per_page
    if not filtered:
        if offset >= DEFAULT_ALERT_DISPLAY_LIMIT:
            limit = 0
        else:
            limit = min(per_page, DEFAULT_ALERT_DISPLAY_LIMIT - offset)

    rows = []
    if limit > 0:
        result = await db.execute(
            select(SystemAlert, Vehicle, Driver)
            .outerjoin(Vehicle, SystemAlert.vehicle_id == Vehicle.id)
            .outerjoin(Driver, SystemAlert.driver_id == Driver.id)
            .where(and_(*clauses))
            .order_by(SystemAlert.timestamp.desc(), SystemAlert.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.all()

    return {
        "items": [_alert_item(alert, vehicle, driver) for alert, vehicle, driver in rows],
        "total": total,
        "retained_total": retained_total,
        "page": page,
        "per_page": per_page,
        "default_limited": not filtered,
        "max_default_alerts": DEFAULT_ALERT_DISPLAY_LIMIT,
        "retention_days": ALERT_RETENTION_DAYS,
    }


def _session_filters(*, date_from=None, date_to=None, vehicle_id=None, q=None):
    filters = []
    vehicle_id = _clean_int(vehicle_id)
    q = _clean_text(q)
    start_utc, end_utc = local_date_to_utc_bounds(date_from, date_to)
    if vehicle_id is not None:
        filters.append(DriverSession.vehicle_id == vehicle_id)
    if start_utc:
        filters.append(DriverSession.checkin_at >= start_utc)
    if end_utc:
        filters.append(DriverSession.checkin_at < end_utc)
    if q:
        pattern = "%%%s%%" % q
        filters.append(or_(
            Vehicle.plate_number.ilike(pattern),
            Vehicle.name.ilike(pattern),
            Driver.name.ilike(pattern),
        ))
    return filters


def _session_item(session, vehicle, driver, now_utc=None):
    return {
        "id": session.id,
        "driver_name": driver.name if driver else "N/A",
        "vehicle_label": _vehicle_label(vehicle),
        "checkin_display": format_vn_datetime(session.checkin_at),
        "checkout_display": format_vn_datetime(session.checkout_at, empty="Dang chay"),
        "duration_text": _duration_text(session.checkin_at, session.checkout_at or _utc_naive(now_utc)),
        "is_active": session.checkout_at is None,
        "status_text": "Dang chay" if session.checkout_at is None else "Da ket thuc",
    }


async def list_session_history(
    db: AsyncSession,
    *,
    date_from=None,
    date_to=None,
    vehicle_id=None,
    q=None,
    page=1,
    per_page=DEFAULT_PER_PAGE,
    now_utc=None,
) -> dict:
    page = max(1, int(page or 1))
    per_page = max(1, min(100, int(per_page or DEFAULT_PER_PAGE)))
    clauses = _session_filters(date_from=date_from, date_to=date_to, vehicle_id=vehicle_id, q=q)

    count_query = (
        select(func.count())
        .select_from(DriverSession)
        .outerjoin(Vehicle, DriverSession.vehicle_id == Vehicle.id)
        .outerjoin(Driver, DriverSession.driver_id == Driver.id)
    )
    query = (
        select(DriverSession, Vehicle, Driver)
        .outerjoin(Vehicle, DriverSession.vehicle_id == Vehicle.id)
        .outerjoin(Driver, DriverSession.driver_id == Driver.id)
        .order_by(DriverSession.checkin_at.desc(), DriverSession.id.desc())
    )
    if clauses:
        count_query = count_query.where(and_(*clauses))
        query = query.where(and_(*clauses))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    rows = result.all()

    return {
        "items": [_session_item(session, vehicle, driver, now_utc=now_utc) for session, vehicle, driver in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
