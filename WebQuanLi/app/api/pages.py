from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, Vehicle, Driver, DriverSession, SystemAlert

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    date_from: str = Query(None),
    date_to: str = Query(None),
    vehicle_id: int = Query(None),
    alert_type: str = Query(None),
    page: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    per_page = 25
    query = (
        select(SystemAlert)
        .options(selectinload(SystemAlert.vehicle))
        .order_by(SystemAlert.timestamp.desc())
    )
    filters = []

    if vehicle_id:
        filters.append(SystemAlert.vehicle_id == vehicle_id)
    if alert_type:
        filters.append(SystemAlert.alert_type == alert_type)
    if date_from:
        try:
            filters.append(SystemAlert.timestamp >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            filters.append(SystemAlert.timestamp <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    if filters:
        query = query.where(and_(*filters))

    total_result = await db.execute(
        select(func.count()).select_from(SystemAlert).where(and_(*filters)) if filters
        else select(func.count()).select_from(SystemAlert)
    )
    total = total_result.scalar()

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    alerts = result.scalars().all()

    vehicles_result = await db.execute(select(Vehicle))
    vehicles = vehicles_result.scalars().all()

    return templates.TemplateResponse(request=request, name="history.html", context={
        "request": request,
        "user": user,
        "alerts": alerts,
        "vehicles": vehicles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "filters": {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "vehicle_id": vehicle_id or "",
            "alert_type": alert_type or "",
        },
    })


@router.get("/fleet", response_class=HTMLResponse)
async def fleet_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicles_result = await db.execute(select(Vehicle).order_by(Vehicle.id))
    vehicles = vehicles_result.scalars().all()

    drivers_result = await db.execute(select(Driver).order_by(Driver.id))
    drivers = drivers_result.scalars().all()

    return templates.TemplateResponse(request=request, name="fleet.html", context={
        "request": request,
        "user": user,
        "vehicles": vehicles,
        "drivers": drivers,
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
        "hourly_heatmap": hourly_counts,
        "kpi": {
            "total_alerts_week": total_alerts_week,
            "total_sessions_week": session_count,
            "total_driving_hours": round(total_hours, 1),
            "avg_session_hours": avg_hours,
        },
    }
