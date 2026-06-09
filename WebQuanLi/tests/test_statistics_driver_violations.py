import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Driver, DriverPenalty, User, Vehicle


class StatisticsDriverViolationsTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"statistics_driver_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: User(username="admin", role="admin")
        asyncio.run(self._seed())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        now = datetime.now(timezone.utc)
        async with self.session_factory() as db:
            vehicle = Vehicle(plate_number="59A-12345", name="Xe Demo 01")
            driver_a = Driver(name="Nguyễn Minh Tùng", rfid_tag="RFID-A", is_active=True)
            driver_b = Driver(name="Lê Duy Tùng", rfid_tag="RFID-B", is_active=True)
            db.add_all([vehicle, driver_a, driver_b])
            await db.flush()
            db.add_all([
                DriverPenalty(
                    vehicle_id=vehicle.id,
                    driver_id=driver_a.id,
                    violation_time=now - timedelta(days=1),
                    reason="Canh bao buon ngu muc 3",
                    amount_vnd=200000,
                    review_status="pending",
                ),
                DriverPenalty(
                    vehicle_id=vehicle.id,
                    driver_id=driver_a.id,
                    violation_time=now - timedelta(days=2),
                    reason="Canh bao buon ngu muc 3",
                    amount_vnd=200000,
                    review_status="confirmed",
                ),
                DriverPenalty(
                    vehicle_id=vehicle.id,
                    driver_id=driver_b.id,
                    violation_time=now - timedelta(days=3),
                    reason="Canh bao buon ngu muc 3",
                    amount_vnd=200000,
                    review_status="cancelled",
                ),
                DriverPenalty(
                    vehicle_id=vehicle.id,
                    driver_id=driver_a.id,
                    violation_time=now - timedelta(days=10),
                    reason="outside current week",
                    amount_vnd=200000,
                    review_status="pending",
                ),
            ])
            await db.commit()

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_statistics_api_returns_driver_violation_stats_for_current_week(self):
        response = asyncio.run(self._request("GET", "/api/statistics/summary"))

        self.assertEqual(response.status_code, 200)
        stats = response.json()["driver_violation_stats"]
        self.assertEqual(stats[0]["driver_name"], "Nguyễn Minh Tùng")
        self.assertEqual(stats[0]["level3_count"], 2)
        self.assertEqual(stats[0]["pending_count"], 1)
        self.assertEqual(stats[0]["confirmed_count"], 1)
        self.assertEqual(stats[0]["cancelled_count"], 0)
        self.assertEqual(stats[0]["active_amount_vnd"], 400000)
        self.assertEqual(stats[0]["active_amount_display"], "400.000đ")
        self.assertEqual(stats[1]["driver_name"], "Lê Duy Tùng")
        self.assertEqual(stats[1]["level3_count"], 1)
        self.assertEqual(stats[1]["active_amount_vnd"], 0)

    def test_statistics_page_has_driver_violation_table_contract(self):
        response = asyncio.run(self._request("GET", "/statistics"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("statistics-dashboard", html)
        self.assertIn("stats-overview-strip", html)
        self.assertIn("analytics-panel", html)
        self.assertIn('id="driver-violation-table"', html)
        self.assertIn("Thống kê vi phạm theo tài xế", html)
        self.assertIn("📈 Thống Kê & Báo Cáo", html)
        self.assertIn("🔔", html)
        self.assertIn("📋", html)
        self.assertIn("⏱️", html)
        self.assertIn("📊", html)
        self.assertIn("renderDriverViolationTable", Path("WebQuanLi/static/js/charts.js").read_text(encoding="utf-8"))
        self.assertIn("driver_violation_stats", Path("WebQuanLi/static/js/charts.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
