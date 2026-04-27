from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, SystemAlert
from app.services.time_service import local_date_to_utc_bounds

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts")
async def list_alerts(
    date_from: str = Query(None),
    date_to: str = Query(None),
    vehicle_id: int = Query(None),
    alert_type: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(SystemAlert).order_by(SystemAlert.timestamp.desc())

    filters = []
    if vehicle_id:
        filters.append(SystemAlert.vehicle_id == vehicle_id)
    if alert_type:
        filters.append(SystemAlert.alert_type == alert_type)
    start_utc, end_utc = local_date_to_utc_bounds(date_from, date_to)
    if start_utc:
        filters.append(SystemAlert.timestamp >= start_utc)
    if end_utc:
        filters.append(SystemAlert.timestamp < end_utc)

    if filters:
        query = query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(SystemAlert)
    if filters:
        count_query = count_query.where(and_(*filters))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    result = await db.execute(query)
    alerts = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": a.id,
                "vehicle_id": a.vehicle_id,
                "driver_id": a.driver_id,
                "alert_type": a.alert_type.value if a.alert_type else None,
                "alert_level": a.alert_level.value if a.alert_level else None,
                "ear_value": a.ear_value,
                "mar_value": a.mar_value,
                "pitch_value": a.pitch_value,
                "latitude": a.latitude,
                "longitude": a.longitude,
                "message": a.message,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in alerts
        ],
    }
