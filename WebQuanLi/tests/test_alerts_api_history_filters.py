import asyncio
import sys
import uuid
import unittest
from datetime import datetime
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import AlertLevel, AlertType, SystemAlert, User, Vehicle


class AlertsApiHistoryFiltersTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"alerts_api_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.admin = User(username="admin", role="admin")

        async def override_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.admin
        asyncio.run(self._create_schema_and_seed())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _create_schema_and_seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(
                plate_number="59A-API",
                name="Xe API",
                device_id="JETSON-API",
            )
            db.add(vehicle)
            await db.flush()
            for message, timestamp in (
                ("vn-previous-day", datetime(2026, 4, 27, 16, 59, 59)),
                ("vn-day-start", datetime(2026, 4, 27, 17, 0, 0)),
                ("vn-day-end", datetime(2026, 4, 28, 16, 59, 59)),
                ("vn-next-day", datetime(2026, 4, 28, 17, 0, 0)),
            ):
                db.add(SystemAlert(
                    vehicle_id=vehicle.id,
                    alert_type=AlertType.DROWSINESS,
                    alert_level=AlertLevel.LEVEL_1,
                    message=message,
                    timestamp=timestamp,
                ))
            await db.commit()

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_date_filter_uses_vietnam_local_day_boundaries(self):
        response = asyncio.run(self._request(
            "GET",
            "/api/alerts?date_from=2026-04-28&date_to=2026-04-28&per_page=100",
        ))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(
            [item["message"] for item in payload["items"]],
            ["vn-day-end", "vn-day-start"],
        )
