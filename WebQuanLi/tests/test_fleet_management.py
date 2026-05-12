import asyncio
import sys
import uuid
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Driver, User, Vehicle


class FleetManagementTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"fleet_management_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        admin = User(username="admin", role="admin")
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: admin
        app.dependency_overrides[check_admin] = lambda: admin
        asyncio.run(self._seed())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(
                plate_number="59A-12345",
                name="Xe Demo 01",
                device_id="JETSON-001",
                manager_phone="0901234567",
            )
            active_driver = Driver(name="Active Driver", rfid_tag="RFID-A", is_active=True)
            inactive_driver = Driver(name="Inactive Driver", rfid_tag="RFID-I", is_active=False)
            db.add_all([vehicle, active_driver, inactive_driver])
            await db.commit()

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_fleet_page_has_add_vehicle_and_delete_driver_controls_for_admin(self):
        response = asyncio.run(self._request("GET", "/fleet"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('id="btn-add-vehicle"', html)
        self.assertIn('id="add-vehicle-form"', html)
        self.assertIn("fetch('/api/vehicles'", html)
        self.assertIn("btn-delete-driver", html)
        self.assertIn("fetch(`/api/drivers/${driverId}`", html)

    def test_fleet_page_hides_inactive_drivers(self):
        response = asyncio.run(self._request("GET", "/fleet"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Active Driver", html)
        self.assertNotIn("Inactive Driver", html)


if __name__ == "__main__":
    unittest.main()
