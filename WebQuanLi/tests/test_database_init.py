import asyncio
import shutil
import sys
import unittest
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import database
from app.auth.utils import verify_password
from app.database import Base
from app.models import User, Vehicle


class DatabaseInitTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"init_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.db_path.parent / f"init_data_{uuid.uuid4().hex}"
        self.upload_dir = self.data_dir / "updates"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        self.original_engine = database.engine
        self.original_session_factory = database.async_session_factory
        self.original_data_dir = database.settings.DATA_DIR
        self.original_upload_dir = database.settings.UPLOAD_DIR
        self.original_admin_username = database.settings.ADMIN_USERNAME
        self.original_admin_password = database.settings.ADMIN_PASSWORD

        database.engine = self.engine
        database.async_session_factory = self.session_factory
        database.settings.DATA_DIR = self.data_dir
        database.settings.UPLOAD_DIR = self.upload_dir
        database.settings.ADMIN_USERNAME = "admin"
        database.settings.ADMIN_PASSWORD = "admin"

    def tearDown(self):
        asyncio.run(self.engine.dispose())
        database.engine = self.original_engine
        database.async_session_factory = self.original_session_factory
        database.settings.DATA_DIR = self.original_data_dir
        database.settings.UPLOAD_DIR = self.original_upload_dir
        database.settings.ADMIN_USERNAME = self.original_admin_username
        database.settings.ADMIN_PASSWORD = self.original_admin_password
        shutil.rmtree(self.data_dir, ignore_errors=True)
        self.db_path.unlink(missing_ok=True)

    def test_init_db_does_not_duplicate_demo_vehicle_when_admin_is_missing(self):
        async def run():
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with self.session_factory() as session:
                session.add(
                    User(
                        username="minhtung2003",
                        hashed_password="existing",
                        role="admin",
                    )
                )
                session.add(
                    Vehicle(
                        plate_number="59A-12345",
                        name="Xe Demo 01",
                        device_id="JETSON-001",
                        manager_phone="0901234567",
                    )
                )
                await session.commit()

            await database.init_db()

            async with self.session_factory() as session:
                users = (await session.execute(select(User).order_by(User.username))).scalars().all()
                vehicles = (await session.execute(select(Vehicle).order_by(Vehicle.id))).scalars().all()
                return users, vehicles

        users, vehicles = asyncio.run(run())

        self.assertEqual([user.username for user in users], ["admin", "minhtung2003"])
        self.assertTrue(verify_password("admin", users[0].hashed_password))
        self.assertEqual(len(vehicles), 1)
        self.assertEqual(vehicles[0].device_id, "JETSON-001")


if __name__ == "__main__":
    unittest.main()
