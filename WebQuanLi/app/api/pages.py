from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import get_db
from app.auth.dependencies import check_admin, get_current_user
from app.models import User, Vehicle, Driver, DriverSession, SystemAlert, DriverPenalty
from app.services.driver_safety_service import calculate_driver_safety_map
from app.services.hardware_incident_service import list_hardware_incidents
from app.services.history_service import (
    delete_alert_history,
    list_alert_history,
    list_session_history,
)

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


def _clean_query_value(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _clean_query_int(value):
    value = _clean_query_value(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _history_url(base_filters: dict, **updates) -> str:
    params = dict(base_filters)
    params.update(updates)
    params = {
        key: value
        for key, value in params.items()
        if value not in (None, "", 0)
    }
    return "/history" if not params else "/history?" + urlencode(params)


def _total_pages(total: int, per_page: int) -> int:
    if not total:
        return 1
    return ((total - 1) // per_page) + 1


def _format_money_vnd(amount: int | None) -> str:
    return f"{int(amount or 0):,}".replace(",", ".") + "đ"


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    date_from: str = Query(None),
    date_to: str = Query(None),
    vehicle_id: str = Query(None),
    alert_type: str = Query(None),
    q: str = Query(None),
    alert_page: int = Query(1, ge=1),
    session_page: int = Query(1, ge=1),
    deleted: int = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    alert_per_page = 10
    session_per_page = 10
    filters = {
        "date_from": _clean_query_value(date_from),
        "date_to": _clean_query_value(date_to),
        "vehicle_id": _clean_query_value(vehicle_id),
        "alert_type": _clean_query_value(alert_type),
        "q": _clean_query_value(q),
    }
    alert_history = await list_alert_history(
        db,
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        vehicle_id=filters["vehicle_id"],
        alert_type=filters["alert_type"],
        q=filters["q"],
        page=alert_page,
        per_page=alert_per_page,
    )
    session_history = await list_session_history(
        db,
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        vehicle_id=filters["vehicle_id"],
        q=filters["q"],
        page=session_page,
        per_page=session_per_page,
    )
    hardware_incident_history = await list_hardware_incidents(
        db,
        vehicle_id=_clean_query_int(filters["vehicle_id"]),
        limit=10,
    )

    vehicles_result = await db.execute(select(Vehicle))
    vehicles = vehicles_result.scalars().all()
    alert_total_pages = _total_pages(alert_history["total"], alert_history["per_page"])
    session_total_pages = _total_pages(session_history["total"], session_history["per_page"])

    return templates.TemplateResponse(request=request, name="history.html", context={
        "request": request,
        "user": user,
        "vehicles": vehicles,
        "alert_history": alert_history,
        "session_history": session_history,
        "hardware_incident_history": hardware_incident_history,
        "alert_total_pages": alert_total_pages,
        "session_total_pages": session_total_pages,
        "deleted": deleted,
        "filters": {
            "date_from": filters["date_from"] or "",
            "date_to": filters["date_to"] or "",
            "vehicle_id": filters["vehicle_id"] or "",
            "alert_type": filters["alert_type"] or "",
            "q": filters["q"] or "",
        },
        "alert_prev_url": _history_url(filters, alert_page=alert_page - 1, session_page=session_page) if alert_page > 1 else "",
        "alert_next_url": _history_url(filters, alert_page=alert_page + 1, session_page=session_page) if alert_page < alert_total_pages else "",
        "session_prev_url": _history_url(filters, alert_page=alert_page, session_page=session_page - 1) if session_page > 1 else "",
        "session_next_url": _history_url(filters, alert_page=alert_page, session_page=session_page + 1) if session_page < session_total_pages else "",
    })


@router.post("/history/alerts/delete")
async def delete_history_alerts(
    request: Request,
    user: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    filters = {
        "date_from": _clean_query_value(form.get("date_from")),
        "date_to": _clean_query_value(form.get("date_to")),
        "vehicle_id": _clean_query_value(form.get("vehicle_id")),
        "alert_type": _clean_query_value(form.get("alert_type")),
        "q": _clean_query_value(form.get("q")),
    }
    deleted = await delete_alert_history(db, filters)
    return RedirectResponse(_history_url(filters, deleted=deleted), status_code=303)


@router.get("/fleet", response_class=HTMLResponse)
async def fleet_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicles_result = await db.execute(
        select(Vehicle)
        .options(selectinload(Vehicle.assistant_driver))
        .order_by(Vehicle.id)
    )
    vehicles = vehicles_result.scalars().all()

    drivers_result = await db.execute(
        select(Driver).where(Driver.is_active.is_(True)).order_by(Driver.id)
    )
    drivers = drivers_result.scalars().all()
    safety_scores = await calculate_driver_safety_map(db, drivers)

    return templates.TemplateResponse(request=request, name="fleet.html", context={
        "request": request,
        "user": user,
        "vehicles": vehicles,
        "drivers": drivers,
        "safety_scores": safety_scores,
    })


@router.get("/statistics", response_class=HTMLResponse)
async def statistics_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse(request=request, name="statistics.html", context={
        "request": request,
        "user": user,
    })


@router.get("/api/statistics/summary")
async def statistics_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Alerts times for daily and hourly heatmap (optimized via tuple query)
    stmt_alert_times = select(SystemAlert.timestamp).where(SystemAlert.timestamp >= week_ago)
    times_res = await db.execute(stmt_alert_times)

    daily_counts = {}
    hourly_counts = {}
    total_alerts_week = 0

    for row in times_res:
        t = row.timestamp
        if t:
            total_alerts_week += 1
            day_str = t.strftime("%Y-%m-%d")
            hour_key = f"{day_str}_{t.hour}"
            daily_counts[day_str] = daily_counts.get(day_str, 0) + 1
            hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1

    # Top drivers with most alerts (Optimized with SQL group by and joined Driver)
    top_drivers_stmt = (
        select(SystemAlert.driver_id, Driver.name, func.count(SystemAlert.id).label("count"))
        .join(Driver, Driver.id == SystemAlert.driver_id)
        .where(
            SystemAlert.timestamp >= week_ago,
            SystemAlert.driver_id.is_not(None)
        )
        .group_by(SystemAlert.driver_id, Driver.name)
        .order_by(desc("count"))
        .limit(5)
    )
    top_drivers_result = await db.execute(top_drivers_stmt)
    
    top_driver_details = [
        {"name": row.name, "count": row.count}
        for row in top_drivers_result.all()
    ]

    review_status = func.coalesce(DriverPenalty.review_status, "pending")
    driver_violation_stmt = (
        select(
            DriverPenalty.driver_id,
            Driver.name.label("driver_name"),
            func.count(DriverPenalty.id).label("level3_count"),
            func.coalesce(func.sum(case((review_status == "pending", 1), else_=0)), 0).label("pending_count"),
            func.coalesce(func.sum(case((review_status == "confirmed", 1), else_=0)), 0).label("confirmed_count"),
            func.coalesce(func.sum(case((review_status == "cancelled", 1), else_=0)), 0).label("cancelled_count"),
            func.coalesce(
                func.sum(case((review_status != "cancelled", DriverPenalty.amount_vnd), else_=0)),
                0,
            ).label("active_amount_vnd"),
            func.max(DriverPenalty.violation_time).label("last_violation_at"),
        )
        .join(Driver, Driver.id == DriverPenalty.driver_id)
        .where(DriverPenalty.violation_time >= week_ago)
        .group_by(DriverPenalty.driver_id, Driver.name)
        .order_by(desc("level3_count"), desc("last_violation_at"))
        .limit(10)
    )
    driver_violation_result = await db.execute(driver_violation_stmt)
    driver_violation_stats = []
    for row in driver_violation_result.all():
        last_violation_at = row.last_violation_at
        driver_violation_stats.append({
            "driver_id": row.driver_id,
            "driver_name": row.driver_name,
            "level3_count": int(row.level3_count or 0),
            "pending_count": int(row.pending_count or 0),
            "confirmed_count": int(row.confirmed_count or 0),
            "cancelled_count": int(row.cancelled_count or 0),
            "active_amount_vnd": int(row.active_amount_vnd or 0),
            "active_amount_display": _format_money_vnd(row.active_amount_vnd),
            "last_violation_at": last_violation_at.isoformat() if last_violation_at else "",
        })

    # Session stats (optimized via explicit tuple queries)
    stmt_sessions = select(func.count(DriverSession.id)).where(DriverSession.checkin_at >= week_ago)
    session_count_res = await db.execute(stmt_sessions)
    session_count = session_count_res.scalar() or 0

    stmt_hours = select(DriverSession.checkin_at, DriverSession.checkout_at).where(
        DriverSession.checkin_at >= week_ago,
        DriverSession.checkout_at.is_not(None)
    )
    hours_res = await db.execute(stmt_hours)
    
    total_hours = sum((row.checkout_at - row.checkin_at).total_seconds() / 3600 for row in hours_res)
    avg_hours = round(total_hours / session_count, 1) if session_count else 0

    return {
        "daily_alerts": daily_counts,
        "top_drivers": top_driver_details,
        "driver_violation_stats": driver_violation_stats,
        "hourly_heatmap": hourly_counts,
        "kpi": {
            "total_alerts_week": total_alerts_week,
            "total_sessions_week": session_count,
            "total_driving_hours": round(total_hours, 1),
            "avg_session_hours": avg_hours,
        },
    }
