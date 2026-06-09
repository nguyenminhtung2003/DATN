from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import check_admin, get_current_user
from app.config import settings
from app.database import get_db
from app.models import Driver, DriverPenalty, User, Vehicle
from app.services.driver_safety_service import (
    apply_penalty_deduction,
    calculate_driver_safety_score,
    refund_penalty_deduction,
)
from app.services.time_service import format_vn_datetime, local_date_to_utc_bounds


router = APIRouter(tags=["penalties"])
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

VALID_REVIEW_STATUSES = {"pending", "confirmed", "cancelled"}
REVIEW_STATUS_LABELS = {
    "pending": "Chưa xử lý",
    "confirmed": "Đã xác nhận phạt",
    "cancelled": "Đã hủy / cảnh báo sai",
}
RECOMMENDED_ACTION_LABELS = {
    "penalty_only": "Phạt tiền + Telegram",
    "warning": "Đề xuất cảnh cáo",
    "suspend_driving": "Đề xuất tạm ngưng lái",
    "discipline_review": "Đề xuất xem xét kỷ luật cao nhất",
}


def _clean_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _format_money_vnd(amount: int | None) -> str:
    return f"{int(amount or 0):,}".replace(",", ".")


def _display_penalty_reason(reason: str | None) -> str:
    if reason == "Canh bao buon ngu muc 3":
        return "Cảnh báo buồn ngủ mức 3"
    return reason or "N/A"


def _safe_next_url(value: str | None) -> str:
    value = value or "/penalties"
    if not value.startswith("/") or value.startswith("//"):
        return "/penalties"
    return value


def _penalty_filters(*, driver_id=None, vehicle_id=None, review_status=None, date_from=None, date_to=None):
    filters = []
    driver_id = _clean_int(driver_id)
    vehicle_id = _clean_int(vehicle_id)
    review_status = _clean_text(review_status)
    start_utc, end_utc = local_date_to_utc_bounds(date_from, date_to)

    if driver_id is not None:
        filters.append(DriverPenalty.driver_id == driver_id)
    if vehicle_id is not None:
        filters.append(DriverPenalty.vehicle_id == vehicle_id)
    if review_status in VALID_REVIEW_STATUSES:
        filters.append(DriverPenalty.review_status == review_status)
    if start_utc:
        filters.append(DriverPenalty.violation_time >= start_utc)
    if end_utc:
        filters.append(DriverPenalty.violation_time < end_utc)
    return filters


def _penalty_item(penalty: DriverPenalty, driver: Driver, vehicle: Vehicle) -> dict:
    review_status = penalty.review_status or "pending"
    recommended_action = penalty.recommended_action or "penalty_only"
    return {
        "id": penalty.id,
        "time": format_vn_datetime(penalty.violation_time),
        "driver_name": driver.name if driver else "N/A",
        "plate_number": vehicle.plate_number if vehicle else "N/A",
        "reason": _display_penalty_reason(penalty.reason),
        "amount": _format_money_vnd(penalty.amount_vnd),
        "review_status": review_status,
        "review_status_label": REVIEW_STATUS_LABELS.get(review_status, review_status),
        "recommended_action": recommended_action,
        "recommended_action_label": RECOMMENDED_ACTION_LABELS.get(recommended_action, recommended_action),
        "driver_telegram_status": penalty.driver_telegram_status,
        "assistant_telegram_status": penalty.assistant_telegram_status,
        "admin_telegram_status": penalty.admin_telegram_status,
        "admin_note": penalty.admin_note or "",
        "resolved_at": format_vn_datetime(penalty.resolved_at, empty=""),
        "resolved_by": penalty.resolved_by or "",
    }


async def _list_penalty_items(
    db: AsyncSession,
    *,
    driver_id=None,
    vehicle_id=None,
    review_status=None,
    date_from=None,
    date_to=None,
) -> list[dict]:
    filters = _penalty_filters(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
    )
    query = (
        select(DriverPenalty, Driver, Vehicle)
        .join(Driver, Driver.id == DriverPenalty.driver_id)
        .join(Vehicle, Vehicle.id == DriverPenalty.vehicle_id)
        .order_by(desc(DriverPenalty.violation_time), desc(DriverPenalty.id))
    )
    if filters:
        query = query.where(and_(*filters))
    result = await db.execute(query.limit(200))
    return [_penalty_item(penalty, driver, vehicle) for penalty, driver, vehicle in result.all()]


async def _penalty_summary(
    db: AsyncSession,
    *,
    driver_id=None,
    vehicle_id=None,
    review_status=None,
    date_from=None,
    date_to=None,
) -> dict:
    filters = _penalty_filters(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
    )
    query = select(
        func.count(DriverPenalty.id),
        func.coalesce(
            func.sum(case((DriverPenalty.review_status == "pending", 1), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((DriverPenalty.review_status == "confirmed", 1), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((DriverPenalty.review_status == "cancelled", 1), else_=0)),
            0,
        ),
        func.coalesce(func.sum(DriverPenalty.amount_vnd), 0),
    )
    if filters:
        query = query.where(and_(*filters))
    row = (await db.execute(query)).one()
    total_count, pending_count, confirmed_count, cancelled_count, total_amount = row
    return {
        "total_count": int(total_count or 0),
        "pending_count": int(pending_count or 0),
        "confirmed_count": int(confirmed_count or 0),
        "cancelled_count": int(cancelled_count or 0),
        "total_amount": f"{_format_money_vnd(total_amount)}đ",
    }


async def _filter_options(db: AsyncSession) -> tuple[list[Driver], list[Vehicle]]:
    drivers_result = await db.execute(select(Driver).order_by(Driver.name, Driver.id))
    vehicles_result = await db.execute(select(Vehicle).order_by(Vehicle.plate_number, Vehicle.id))
    return drivers_result.scalars().all(), vehicles_result.scalars().all()


@router.get("/penalties", response_class=HTMLResponse)
async def penalties_page(
    request: Request,
    driver_id: int | None = Query(None),
    vehicle_id: int | None = Query(None),
    review_status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await _list_penalty_items(
        db,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
    )
    summary = await _penalty_summary(
        db,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
    )
    drivers, vehicles = await _filter_options(db)
    return templates.TemplateResponse(request=request, name="penalties.html", context={
        "request": request,
        "user": user,
        "penalties": items,
        "summary": summary,
        "drivers": drivers,
        "vehicles": vehicles,
        "filters": {
            "driver_id": driver_id,
            "vehicle_id": vehicle_id,
            "review_status": review_status or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
        "review_status_labels": REVIEW_STATUS_LABELS,
        "current_url": str(request.url),
    })


@router.get("/api/penalties")
async def list_penalties_api(
    driver_id: int | None = Query(None),
    vehicle_id: int | None = Query(None),
    review_status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {
        "items": await _list_penalty_items(
            db,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            review_status=review_status,
            date_from=date_from,
            date_to=date_to,
        )
    }


@router.post("/api/penalties/{penalty_id}/review")
async def update_penalty_review(
    penalty_id: int,
    review_status: str = Form(...),
    admin_note: str | None = Form(None),
    next_url: str = Form("/penalties"),
    user: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db),
):
    if review_status not in VALID_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="Trang thai xu ly khong hop le")

    penalty = await db.get(DriverPenalty, penalty_id)
    if not penalty:
        raise HTTPException(status_code=404, detail="Ban ghi xu phat khong tim thay")

    penalty.admin_note = _clean_text(admin_note)
    penalty.review_status = review_status
    if review_status in {"confirmed", "cancelled"}:
        penalty.resolved_at = datetime.now(timezone.utc)
        penalty.resolved_by = user.username
    else:
        penalty.resolved_at = None
        penalty.resolved_by = None

    await db.flush()
    if review_status == "cancelled":
        await refund_penalty_deduction(db, penalty, created_by=user.username)
    elif review_status == "confirmed":
        await apply_penalty_deduction(db, penalty, created_by=user.username)

    score = await calculate_driver_safety_score(db, penalty.driver_id, as_of=penalty.violation_time)
    penalty.recommended_action = score.recommended_action

    await db.commit()
    return RedirectResponse(_safe_next_url(next_url), status_code=303)
