from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, DriverSession

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/vehicles/{vehicle_id}/sessions")
async def list_sessions(
    vehicle_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(DriverSession)
        .options(selectinload(DriverSession.driver))
        .where(DriverSession.vehicle_id == vehicle_id)
        .order_by(DriverSession.checkin_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        items.append({
            "id": s.id,
            "driver_name": s.driver.name if s.driver else "N/A",
            "driver_id": s.driver_id,
            "checkin_at": s.checkin_at.isoformat() if s.checkin_at else None,
            "checkout_at": s.checkout_at.isoformat() if s.checkout_at else None,
            "is_active": s.checkout_at is None,
        })

    return {"items": items}


@router.get("/vehicles/{vehicle_id}/sessions/active")
async def get_active_session(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DriverSession)
        .options(selectinload(DriverSession.driver))
        .where(
            and_(
                DriverSession.vehicle_id == vehicle_id,
                DriverSession.checkout_at.is_(None),
            )
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"active": False}

    return {
        "active": True,
        "session_id": session.id,
        "driver_name": session.driver.name if session.driver else "N/A",
        "checkin_at": session.checkin_at.isoformat() if session.checkin_at else None,
    }
