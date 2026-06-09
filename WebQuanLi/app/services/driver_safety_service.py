from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Driver, DriverPenalty, DriverSafetyAdjustment


BASE_SAFETY_SCORE = 100
POINTS_PER_LEVEL3_PENALTY = 15
REPEAT_7_DAY_POINTS = 10
REPEAT_30_DAY_POINTS = 20
SAFETY_WINDOW_DAYS = 90

SOURCE_PENALTY_DEDUCT = "penalty_deduct"
SOURCE_PENALTY_REFUND = "penalty_refund"
SOURCE_MANUAL_SET = "manual_set"
SOURCE_RESET = "reset"

RECOMMEND_PENALTY_ONLY = "penalty_only"
RECOMMEND_WARNING = "warning"
RECOMMEND_SUSPEND_DRIVING = "suspend_driving"
RECOMMEND_DISCIPLINE_REVIEW = "discipline_review"


@dataclass(frozen=True)
class DriverSafetyScore:
    score: int
    label: str
    level: str
    recommended_action: str
    penalty_count_7d: int
    penalty_count_30d: int
    penalty_count_90d: int


def _utc_naive(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _clamp_score(score: int) -> int:
    return max(0, min(BASE_SAFETY_SCORE, int(score)))


def _score_label(score: int) -> tuple[str, str]:
    if score >= 80:
        return "An toàn", "safe"
    if score >= 60:
        return "Cần theo dõi", "watch"
    if score >= 40:
        return "Cảnh cáo", "warning"
    if score >= 20:
        return "Tạm ngưng lái", "suspend"
    return "Xem xét kỷ luật", "discipline"


def _recommended_action(count_7: int, count_30: int, count_90: int, score: int) -> str:
    if count_30 >= 5 or count_90 >= 10 or score < 20:
        return RECOMMEND_DISCIPLINE_REVIEW
    if count_7 >= 3 or score < 40:
        return RECOMMEND_SUSPEND_DRIVING
    if count_7 >= 2 or score < 60:
        return RECOMMEND_WARNING
    return RECOMMEND_PENALTY_ONLY


def _active_penalty_filter():
    return or_(DriverPenalty.review_status.is_(None), DriverPenalty.review_status != "cancelled")


async def _driver_penalty_count_since(db: AsyncSession, driver_id: int, since: datetime, until: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(DriverPenalty)
        .where(
            DriverPenalty.driver_id == driver_id,
            DriverPenalty.violation_time >= since,
            DriverPenalty.violation_time <= until,
            _active_penalty_filter(),
        )
    )
    return int(result.scalar() or 0)


async def _driver_counts(db: AsyncSession, driver_id: int, as_of: datetime) -> tuple[int, int, int]:
    return (
        await _driver_penalty_count_since(db, driver_id, as_of - timedelta(days=7), as_of),
        await _driver_penalty_count_since(db, driver_id, as_of - timedelta(days=30), as_of),
        await _driver_penalty_count_since(db, driver_id, as_of - timedelta(days=SAFETY_WINDOW_DAYS), as_of),
    )


async def _adjustment_sum(db: AsyncSession, driver_id: int) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(DriverSafetyAdjustment.delta_points), 0))
        .where(DriverSafetyAdjustment.driver_id == driver_id)
    )
    return int(result.scalar() or 0)


async def _raw_safety_score(db: AsyncSession, driver_id: int) -> int:
    return BASE_SAFETY_SCORE + await _adjustment_sum(db, driver_id)


async def calculate_driver_safety_score(
    db: AsyncSession,
    driver_id: int,
    *,
    as_of: datetime | None = None,
) -> DriverSafetyScore:
    as_of = _utc_naive(as_of)
    score = _clamp_score(await _raw_safety_score(db, driver_id))
    count_7, count_30, count_90 = await _driver_counts(db, driver_id, as_of)
    label, level = _score_label(score)
    return DriverSafetyScore(
        score=score,
        label=label,
        level=level,
        recommended_action=_recommended_action(count_7, count_30, count_90, score),
        penalty_count_7d=count_7,
        penalty_count_30d=count_30,
        penalty_count_90d=count_90,
    )


async def calculate_driver_safety_map(
    db: AsyncSession,
    drivers: list[Driver],
    *,
    as_of: datetime | None = None,
) -> dict[int, DriverSafetyScore]:
    as_of = _utc_naive(as_of)
    return {
        driver.id: await calculate_driver_safety_score(db, driver.id, as_of=as_of)
        for driver in drivers
    }


async def calculate_penalty_deduction_points(
    db: AsyncSession,
    driver_id: int,
    violation_time: datetime,
) -> int:
    violation_time = _utc_naive(violation_time)
    count_7, count_30, _ = await _driver_counts(db, driver_id, violation_time)
    points = POINTS_PER_LEVEL3_PENALTY
    if count_7 >= 2:
        points += REPEAT_7_DAY_POINTS
    if count_30 >= 5:
        points += REPEAT_30_DAY_POINTS
    return points


async def _penalty_adjustments(db: AsyncSession, penalty_id: int) -> list[DriverSafetyAdjustment]:
    result = await db.execute(
        select(DriverSafetyAdjustment)
        .where(
            DriverSafetyAdjustment.penalty_id == penalty_id,
            DriverSafetyAdjustment.source_type.in_([SOURCE_PENALTY_DEDUCT, SOURCE_PENALTY_REFUND]),
        )
        .order_by(DriverSafetyAdjustment.id)
    )
    return result.scalars().all()


async def apply_penalty_deduction(
    db: AsyncSession,
    penalty: DriverPenalty,
    *,
    created_by: str | None = None,
) -> DriverSafetyAdjustment | None:
    await db.flush()
    adjustments = await _penalty_adjustments(db, penalty.id)
    net_delta = sum(item.delta_points for item in adjustments)
    if net_delta < 0:
        return None

    previous_deductions = [
        abs(item.delta_points)
        for item in adjustments
        if item.source_type == SOURCE_PENALTY_DEDUCT and item.delta_points < 0
    ]
    points = previous_deductions[-1] if previous_deductions else await calculate_penalty_deduction_points(
        db,
        penalty.driver_id,
        penalty.violation_time,
    )
    adjustment = DriverSafetyAdjustment(
        driver_id=penalty.driver_id,
        penalty_id=penalty.id,
        delta_points=-points,
        reason=f"Trừ điểm do {penalty.reason}",
        source_type=SOURCE_PENALTY_DEDUCT,
        created_by=created_by,
    )
    db.add(adjustment)
    await db.flush()
    return adjustment


async def refund_penalty_deduction(
    db: AsyncSession,
    penalty: DriverPenalty,
    *,
    created_by: str | None = None,
) -> DriverSafetyAdjustment | None:
    await db.flush()
    adjustments = await _penalty_adjustments(db, penalty.id)
    outstanding = -sum(item.delta_points for item in adjustments)
    if outstanding <= 0:
        return None

    adjustment = DriverSafetyAdjustment(
        driver_id=penalty.driver_id,
        penalty_id=penalty.id,
        delta_points=outstanding,
        reason=f"Hoàn điểm do hủy {penalty.reason}",
        source_type=SOURCE_PENALTY_REFUND,
        created_by=created_by,
    )
    db.add(adjustment)
    await db.flush()
    return adjustment


async def set_driver_safety_score(
    db: AsyncSession,
    driver_id: int,
    target_score: int,
    *,
    created_by: str | None = None,
    reason: str | None = None,
    source_type: str = SOURCE_MANUAL_SET,
) -> DriverSafetyScore:
    if target_score < 0 or target_score > BASE_SAFETY_SCORE:
        raise ValueError("Safety score must be between 0 and 100")

    raw_score = await _raw_safety_score(db, driver_id)
    delta = int(target_score) - raw_score
    adjustment = DriverSafetyAdjustment(
        driver_id=driver_id,
        penalty_id=None,
        delta_points=delta,
        reason=reason or "Điều chỉnh điểm an toàn",
        source_type=source_type,
        created_by=created_by,
    )
    db.add(adjustment)
    await db.flush()
    return await calculate_driver_safety_score(db, driver_id)


async def reset_driver_safety_score(
    db: AsyncSession,
    driver_id: int,
    *,
    created_by: str | None = None,
    reason: str | None = None,
) -> DriverSafetyScore:
    return await set_driver_safety_score(
        db,
        driver_id,
        BASE_SAFETY_SCORE,
        created_by=created_by,
        reason=reason or "Reset điểm an toàn về 100",
        source_type=SOURCE_RESET,
    )


async def recommend_penalty_action(
    db: AsyncSession,
    driver_id: int,
    violation_time: datetime,
) -> str:
    current = await calculate_driver_safety_score(db, driver_id, as_of=violation_time)
    deduction = POINTS_PER_LEVEL3_PENALTY
    count_7, count_30, count_90 = await _driver_counts(db, driver_id, _utc_naive(violation_time))
    count_7 += 1
    count_30 += 1
    count_90 += 1
    if count_7 >= 2:
        deduction += REPEAT_7_DAY_POINTS
    if count_30 >= 5:
        deduction += REPEAT_30_DAY_POINTS
    return _recommended_action(count_7, count_30, count_90, _clamp_score(current.score - deduction))


async def backfill_penalty_safety_adjustments(db: AsyncSession) -> int:
    result = await db.execute(
        select(DriverPenalty)
        .where(_active_penalty_filter())
        .order_by(DriverPenalty.violation_time, DriverPenalty.id)
    )
    backfilled = 0
    for penalty in result.scalars().all():
        adjustments = await _penalty_adjustments(db, penalty.id)
        if any(item.source_type == SOURCE_PENALTY_DEDUCT for item in adjustments):
            continue
        if await apply_penalty_deduction(db, penalty, created_by="backfill"):
            score = await calculate_driver_safety_score(db, penalty.driver_id, as_of=penalty.violation_time)
            penalty.recommended_action = score.recommended_action
            backfilled += 1
    if backfilled:
        await db.commit()
    return backfilled
