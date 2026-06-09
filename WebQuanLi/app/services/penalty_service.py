from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import AlertLevel, AlertType, DriverPenalty, SystemAlert, Vehicle
from app.services.driver_safety_service import (
    apply_penalty_deduction,
    calculate_driver_safety_score,
    recommend_penalty_action,
)
from app.services.location_message_service import location_message_lines
from app.services.telegram_service import send_telegram_message


PENALTY_AMOUNT_VND = 200_000
PENALTY_REASON = "Canh bao buon ngu muc 3"

def _telegram_status(result: dict) -> tuple[str, str | None]:
    if result.get("ok"):
        return "sent", None
    return "failed", result.get("description") or "unknown error"


def _money_text(amount_vnd: int) -> str:
    return f"{amount_vnd:,}".replace(",", ".") + "d"


def _location_lines(alert: SystemAlert) -> list[str]:
    return location_message_lines(alert.latitude, alert.longitude)


def _driver_penalty_message(alert: SystemAlert, penalty: DriverPenalty) -> str:
    vehicle = alert.vehicle
    driver = alert.driver
    return "\n".join(
        [
            "THONG BAO XU PHAT",
            f"Tai xe: {driver.name if driver else 'Khong xac dinh'}",
            f"Xe: {vehicle.plate_number if vehicle else 'Khong xac dinh'}",
            f"Ly do: {penalty.reason}",
            f"So tien: {_money_text(penalty.amount_vnd)}",
            *_location_lines(alert),
            f"Thoi gian: {penalty.violation_time.isoformat()}",
        ]
    )


def _assistant_alert_message(alert: SystemAlert, penalty: DriverPenalty) -> str:
    vehicle = alert.vehicle
    driver = alert.driver
    return "\n".join(
        [
            "CANH BAO DOI TAI XE",
            f"Tai xe chinh: {driver.name if driver else 'Khong xac dinh'}",
            f"Xe: {vehicle.plate_number if vehicle else 'Khong xac dinh'}",
            f"Su kien: {penalty.reason}",
            *_location_lines(alert),
            "Vui long ho tro doi tai xe hoac kiem tra an toan.",
        ]
    )


def _admin_alert_message(alert: SystemAlert, penalty: DriverPenalty) -> str:
    vehicle = alert.vehicle
    driver = alert.driver
    assistant_driver = vehicle.assistant_driver if vehicle else None
    return "\n".join(
        [
            "CANH BAO BUON NGU MUC 3",
            f"Tai xe chinh: {driver.name if driver else 'Khong xac dinh'}",
            f"Tai xe phu: {assistant_driver.name if assistant_driver else 'Khong xac dinh'}",
            f"Xe: {vehicle.plate_number if vehicle else 'Khong xac dinh'}",
            f"Ly do: {penalty.reason}",
            *_location_lines(alert),
            f"Thoi gian: {penalty.violation_time.isoformat()}",
        ]
    )


async def _load_alert(db: AsyncSession, alert_id: int) -> SystemAlert | None:
    result = await db.execute(
        select(SystemAlert)
        .options(
            selectinload(SystemAlert.vehicle),
            selectinload(SystemAlert.vehicle).selectinload(Vehicle.assistant_driver),
            selectinload(SystemAlert.driver),
        )
        .where(SystemAlert.id == alert_id)
    )
    return result.scalar_one_or_none()


async def _load_penalty(db: AsyncSession, alert_id: int) -> DriverPenalty | None:
    result = await db.execute(select(DriverPenalty).where(DriverPenalty.alert_id == alert_id))
    return result.scalar_one_or_none()


async def process_level3_penalty_for_alert(db: AsyncSession, alert_id: int) -> DriverPenalty | None:
    alert = await _load_alert(db, alert_id)
    if (
        alert is None
        or alert.alert_type != AlertType.DROWSINESS
        or alert.alert_level != AlertLevel.LEVEL_3
        or alert.driver_id is None
    ):
        return None

    existing = await _load_penalty(db, alert_id)
    if existing:
        if existing.review_status != "cancelled":
            await apply_penalty_deduction(db, existing, created_by="system")
            score = await calculate_driver_safety_score(db, existing.driver_id, as_of=existing.violation_time)
            existing.recommended_action = score.recommended_action
            await db.commit()
        return existing

    penalty = DriverPenalty(
        alert_id=alert.id,
        vehicle_id=alert.vehicle_id,
        driver_id=alert.driver_id,
        session_id=alert.session_id,
        violation_time=alert.timestamp,
        reason=PENALTY_REASON,
        amount_vnd=PENALTY_AMOUNT_VND,
        driver_telegram_status="pending",
        assistant_telegram_status="pending",
        admin_telegram_status="pending",
        review_status="pending",
        recommended_action="penalty_only",
    )
    db.add(penalty)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await _load_penalty(db, alert_id)
        if existing:
            return existing
        raise
    await db.refresh(penalty)
    await apply_penalty_deduction(db, penalty, created_by="system")
    score = await calculate_driver_safety_score(db, penalty.driver_id, as_of=penalty.violation_time)
    penalty.recommended_action = score.recommended_action

    driver_result = await send_telegram_message(
        alert.driver.telegram_chat_id if alert.driver else None,
        _driver_penalty_message(alert, penalty),
    )
    penalty.driver_telegram_status, penalty.driver_telegram_error = _telegram_status(driver_result)

    assistant_driver = alert.vehicle.assistant_driver if alert.vehicle else None
    assistant_result = await send_telegram_message(
        assistant_driver.telegram_chat_id if assistant_driver else None,
        _assistant_alert_message(alert, penalty),
    )
    penalty.assistant_telegram_status, penalty.assistant_telegram_error = _telegram_status(assistant_result)

    admin_result = await send_telegram_message(
        settings.ADMIN_TELEGRAM_CHAT_ID,
        _admin_alert_message(alert, penalty),
    )
    penalty.admin_telegram_status, penalty.admin_telegram_error = _telegram_status(admin_result)

    await db.commit()
    await db.refresh(penalty)
    return penalty
