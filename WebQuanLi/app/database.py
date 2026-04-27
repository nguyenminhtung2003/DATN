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


async def init_db():
    from app.models import User, Vehicle, Driver, HardwareStatus, DriverSession, SystemAlert, OtaAuditLog  # noqa: F401
    from app.config import settings as cfg
    from app.auth.utils import hash_password

    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed admin user
    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.username == cfg.ADMIN_USERNAME))
        existing = result.scalar_one_or_none()
        if not existing:
            admin = User(
                username=cfg.ADMIN_USERNAME,
                hashed_password=hash_password(cfg.ADMIN_PASSWORD),
                role="admin",
            )
            session.add(admin)

            # Seed a default vehicle
            vehicle = Vehicle(
                plate_number="59A-12345",
                name="Xe Demo 01",
                device_id="JETSON-001",
                manager_phone="0901234567",
            )
            session.add(vehicle)
            await session.commit()
