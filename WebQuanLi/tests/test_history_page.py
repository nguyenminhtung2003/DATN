import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import AlertLevel, AlertType, Driver, DriverSession, SystemAlert, User, Vehicle


class HistoryPageTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"history_page_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        self.admin = User(username="admin", role="admin")
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.admin
        app.dependency_overrides[check_admin] = lambda: self.admin
        self.ids = asyncio.run(self._seed())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(plate_number="59A-12345", name="Xe Demo 01", device_id="JETSON-001")
            driver = Driver(name="Nguyen Van A", rfid_tag="RFID-A", vehicle=vehicle)
            db.add_all([vehicle, driver])
            await db.flush()
            for idx in range(30):
                db.add(SystemAlert(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    alert_type=AlertType.DROWSINESS,
                    alert_level=AlertLevel.LEVEL_1,
                    message=f"alert {idx}",
                    timestamp=datetime(2026, 4, 27, 17, 0, 0) - timedelta(minutes=idx),
                ))
            db.add(DriverSession(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                checkin_at=datetime(2026, 4, 27, 16, 0, 0),
                checkout_at=datetime(2026, 4, 27, 17, 0, 0),
            ))
            await db.commit()
            return {"vehicle_id": vehicle.id}

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_history_page_displays_vietnam_time_search_and_sessions(self):
        response = asyncio.run(self._request("GET", "/history"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("00:00:00 - 28/04/2026", html)
        self.assertIn('name="q"', html)
        self.assertIn("Ca lam viec", html)
        self.assertIn("Nguyen Van A", html)
        self.assertIn("23:00:00 - 27/04/2026", html)

    def test_history_pagination_preserves_filters_and_uses_alert_page(self):
        response = asyncio.run(self._request("GET", "/history?q=alert&date_from=2026-04-27&alert_page=1"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("alert_page=2", response.text)
        self.assertIn("q=alert", response.text)
        self.assertIn("date_from=2026-04-27", response.text)
        self.assertNotIn("vehicle_id=", response.text)
        self.assertNotIn("alert_type=", response.text)

    def test_history_ignores_empty_filter_query_values_from_old_links(self):
        response = asyncio.run(self._request("GET", "/history?date_from=&date_to=&vehicle_id=&alert_type="))

        self.assertEqual(response.status_code, 200)
        self.assertIn("00:00:00 - 28/04/2026", response.text)

    def test_admin_can_delete_filtered_alert_history_without_deleting_sessions(self):
        response = asyncio.run(self._request("POST", "/history/alerts/delete", data={"q": "alert 29"}))

        self.assertEqual(response.status_code, 303)

        async def count_rows():
            async with self.session_factory() as db:
                alerts = (await db.execute(select(SystemAlert))).scalars().all()
                sessions = (await db.execute(select(DriverSession))).scalars().all()
                return len(alerts), len(sessions)

        alert_count, session_count = asyncio.run(count_rows())
        self.assertEqual(alert_count, 29)
        self.assertEqual(session_count, 1)


if __name__ == "__main__":
    unittest.main()
