import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import check_admin, get_current_user
from app.database import get_db
from app.models import Driver, User, Vehicle
from app.schemas import DriverCreate, DriverUpdate, VehicleCreate, VehicleUpdate
from app.ws.jetson_handler import manager

router = APIRouter(prefix="/api", tags=["vehicles"])
logger = logging.getLogger(__name__)

MAX_FACE_IMAGE_BYTES = 3 * 1024 * 1024
FACE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def _ensure_unique_vehicle(db: AsyncSession, data: VehicleCreate):
    result = await db.execute(select(Vehicle).where(Vehicle.plate_number == data.plate_number))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Biển số xe đã tồn tại")

    if data.device_id:
        result = await db.execute(select(Vehicle).where(Vehicle.device_id == data.device_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Device ID đã tồn tại")


async def _ensure_unique_driver_rfid(db: AsyncSession, rfid_tag: str):
    result = await db.execute(select(Driver).where(Driver.rfid_tag == rfid_tag))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="RFID đã tồn tại")


async def _get_vehicle_or_404(db: AsyncSession, vehicle_id: int) -> Vehicle:
    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Xe khong tim thay")
    return vehicle


def _absolute_face_image_url(request: Request, face_image_path: str) -> str:
    if face_image_path.startswith(("http://", "https://")):
        return face_image_path
    return f"{str(request.base_url).rstrip('/')}{face_image_path}"


async def _build_driver_registry_manifest(db: AsyncSession, request: Request, device_id: str) -> dict:
    vehicle_result = await db.execute(
        select(Vehicle).where(
            Vehicle.device_id == device_id,
            Vehicle.is_active.is_(True),
        )
    )
    vehicle = vehicle_result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Thiet bi khong tim thay")

    driver_result = await db.execute(
        select(Driver).where(
            Driver.vehicle_id == vehicle.id,
            Driver.is_active.is_(True),
            Driver.face_image_path.is_not(None),
        ).order_by(Driver.id)
    )
    drivers = driver_result.scalars().all()
    return {
        "device_id": device_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "drivers": [
            {
                "name": driver.name,
                "rfid_tag": driver.rfid_tag,
                "face_image_url": _absolute_face_image_url(request, driver.face_image_path),
            }
            for driver in drivers
        ],
    }


async def _dispatch_driver_registry_sync(request: Request, vehicle: Vehicle) -> bool:
    if not vehicle.device_id or vehicle.device_id not in manager.active:
        return False

    manifest_url = f"{str(request.base_url).rstrip('/')}/api/jetson/{vehicle.device_id}/driver-registry"
    await manager.send_command(vehicle.device_id, {
        "action": "sync_driver_registry",
        "manifest_url": manifest_url,
    })
    logger.info(f"Driver registry sync command sent to {vehicle.device_id}")
    return True


@router.get("/jetson/{device_id}/driver-registry")
async def get_driver_registry(
    device_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await _build_driver_registry_manifest(db, request, device_id)


@router.get("/vehicles")
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Vehicle).order_by(Vehicle.id))
    vehicles = result.scalars().all()
    return [
        {
            "id": v.id,
            "plate_number": v.plate_number,
            "name": v.name,
            "device_id": v.device_id,
            "manager_phone": v.manager_phone,
            "is_active": v.is_active,
        }
        for v in vehicles
    ]


@router.post("/vehicles")
async def create_vehicle(
    data: VehicleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    await _ensure_unique_vehicle(db, data)
    vehicle = Vehicle(**data.model_dump())
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return {"id": vehicle.id, "plate_number": vehicle.plate_number}


@router.put("/vehicles/{vehicle_id}")
async def update_vehicle(
    vehicle_id: int,
    data: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    vehicle = await _get_vehicle_or_404(db, vehicle_id)
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, key, val)
    await db.commit()
    return {"status": "updated"}


@router.post("/vehicles/{vehicle_id}/sync-driver-registry")
async def sync_driver_registry(
    vehicle_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    vehicle = await _get_vehicle_or_404(db, vehicle_id)
    sent = await _dispatch_driver_registry_sync(request, vehicle)
    return {
        "status": "sent" if sent else "offline",
        "device_id": vehicle.device_id,
    }


@router.get("/drivers")
async def list_drivers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Driver).order_by(Driver.id))
    drivers = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "age": d.age,
            "gender": d.gender,
            "phone": d.phone,
            "rfid_tag": d.rfid_tag,
            "vehicle_id": d.vehicle_id,
            "face_image_path": d.face_image_path,
            "is_active": d.is_active,
        }
        for d in drivers
    ]


@router.post("/drivers")
async def create_driver(
    data: DriverCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    await _ensure_unique_driver_rfid(db, data.rfid_tag)
    driver = Driver(**data.model_dump())
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return {"id": driver.id, "name": driver.name}


@router.put("/drivers/{driver_id}")
async def update_driver(
    driver_id: int,
    data: DriverUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Tai xe khong tim thay")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(driver, key, val)
    await db.commit()
    return {"status": "updated"}


@router.post("/drivers/{driver_id}/face")
async def upload_face_image(
    driver_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(check_admin),
):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Tai xe khong tim thay")

    extension = FACE_CONTENT_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(status_code=400, detail="Chi cho phep upload anh JPG, PNG hoac WEBP")

    content = await file.read()
    if len(content) > MAX_FACE_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Anh mat khong duoc vuot qua 3MB")

    from app.config import settings

    face_dir = settings.STATIC_DIR / "faces"
    face_dir.mkdir(parents=True, exist_ok=True)
    filepath = face_dir / f"driver_{driver_id}{extension}"

    with open(filepath, "wb") as fh:
        fh.write(content)

    driver.face_image_path = f"/static/faces/{Path(filepath).name}"
    await db.commit()

    if driver.vehicle_id:
        vehicle = await _get_vehicle_or_404(db, driver.vehicle_id)
        await _dispatch_driver_registry_sync(request, vehicle)

    return {"status": "uploaded", "path": driver.face_image_path}
