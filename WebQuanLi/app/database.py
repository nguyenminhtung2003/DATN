from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def _ensure_sqlite_columns():
    # Best-effort runtime sync for existing SQLite DBs: fresh metadata-created DBs
    # include constraints, while write paths/API validation enforce upgraded IDs.
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    async with engine.begin() as conn:
        driver_columns = {
            row[1]
            for row in (await conn.execute(text("PRAGMA table_info(drivers)"))).fetchall()
        }
        if "telegram_chat_id" not in driver_columns:
            await conn.execute(text("ALTER TABLE drivers ADD COLUMN telegram_chat_id VARCHAR(32)"))

        vehicle_columns = {
            row[1]
            for row in (await conn.execute(text("PRAGMA table_info(vehicles)"))).fetchall()
        }
        if "assistant_driver_id" not in vehicle_columns:
            await conn.execute(text("ALTER TABLE vehicles ADD COLUMN assistant_driver_id INTEGER"))

        penalty_columns = {
            row[1]
            for row in (await conn.execute(text("PRAGMA table_info(driver_penalties)"))).fetchall()
        }
        if penalty_columns and "admin_telegram_status" not in penalty_columns:
            await conn.execute(
                text("ALTER TABLE driver_penalties ADD COLUMN admin_telegram_status VARCHAR(30) NOT NULL DEFAULT 'pending'")
            )
        if penalty_columns and "admin_telegram_error" not in penalty_columns:
            await conn.execute(text("ALTER TABLE driver_penalties ADD COLUMN admin_telegram_error TEXT"))
        if penalty_columns and "review_status" not in penalty_columns:
            await conn.execute(
                text("ALTER TABLE driver_penalties ADD COLUMN review_status VARCHAR(30) NOT NULL DEFAULT 'pending'")
            )
        if penalty_columns and "admin_note" not in penalty_columns:
            await conn.execute(text("ALTER TABLE driver_penalties ADD COLUMN admin_note TEXT"))
        if penalty_columns and "resolved_at" not in penalty_columns:
            await conn.execute(text("ALTER TABLE driver_penalties ADD COLUMN resolved_at DATETIME"))
        if penalty_columns and "resolved_by" not in penalty_columns:
            await conn.execute(text("ALTER TABLE driver_penalties ADD COLUMN resolved_by VARCHAR(50)"))
        if penalty_columns and "recommended_action" not in penalty_columns:
            await conn.execute(
                text("ALTER TABLE driver_penalties ADD COLUMN recommended_action VARCHAR(50) NOT NULL DEFAULT 'penalty_only'")
            )


async def init_db():
    from app.models import User, Vehicle, Driver, HardwareStatus, HardwareIncident, DriverSession, SystemAlert, DriverPenalty, DriverSafetyAdjustment, OtaAuditLog  # noqa: F401
    from app.config import settings as cfg
    from app.auth.utils import hash_password
    from app.services.driver_safety_service import backfill_penalty_safety_adjustments
    from sqlalchemy import or_, select

    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_sqlite_columns()

    # Seed admin user
    async with async_session_factory() as session:
        await backfill_penalty_safety_adjustments(session)

        result = await session.execute(select(User).where(User.username == cfg.ADMIN_USERNAME))
        existing = result.scalar_one_or_none()
        if not existing:
            admin = User(
                username=cfg.ADMIN_USERNAME,
                hashed_password=hash_password(cfg.ADMIN_PASSWORD),
                role="admin",
            )
            session.add(admin)

        default_plate = "59A-12345"
        default_device_id = "JETSON-001"
        result = await session.execute(
            select(Vehicle)
            .where(
                or_(
                    Vehicle.plate_number == default_plate,
                    Vehicle.device_id == default_device_id,
                )
            )
            .limit(1)
        )
        existing_vehicle = result.scalars().first()
        if not existing_vehicle:
            vehicle = Vehicle(
                plate_number=default_plate,
                name="Xe Demo 01",
                device_id=default_device_id,
                manager_phone="0901234567",
            )
            session.add(vehicle)

        await session.commit()
