import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.models import AlertLevel, AlertType, Driver, DriverSession, SystemAlert, Vehicle


class HistoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"history_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.ids = asyncio.run(self._seed())

    def tearDown(self):
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

            for idx in range(130):
                db.add(SystemAlert(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    alert_type=AlertType.DROWSINESS,
                    alert_level=AlertLevel.LEVEL_1,
                    message=f"alert searchable-{idx}",
                    timestamp=datetime(2026, 4, 27, 17, 0, 0) - timedelta(minutes=idx),
                ))

            db.add(SystemAlert(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_2,
                message="older than retention",
                timestamp=datetime(2026, 4, 18, 17, 0, 0),
            ))
            db.add(DriverSession(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                checkin_at=datetime(2026, 4, 27, 16, 0, 0),
                checkout_at=datetime(2026, 4, 27, 17, 0, 0),
            ))
            await db.commit()
            return {"vehicle_id": vehicle.id}

    def test_default_alert_history_is_capped_to_newest_100(self):
        async def run():
            from app.services.history_service import list_alert_history
            async with self.session_factory() as db:
                return await list_alert_history(db, now_utc=datetime(2026, 4, 28, 0, 0, 0))

        history = asyncio.run(run())

        self.assertEqual(history["total"], 100)
        self.assertEqual(history["retained_total"], 130)
        self.assertEqual(len(history["items"]), 25)
        self.assertEqual(history["items"][0]["display_time"], "00:00:00 - 28/04/2026")

    def test_search_finds_retained_alert_beyond_default_100_cap(self):
        async def run():
            from app.services.history_service import list_alert_history
            async with self.session_factory() as db:
                return await list_alert_history(db, q="searchable-120", now_utc=datetime(2026, 4, 28, 0, 0, 0))

        history = asyncio.run(run())

        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["message"], "alert searchable-120")

    def test_purge_old_alerts_deletes_records_older_than_7_days(self):
        async def run():
            from app.services.history_service import purge_old_alerts
            async with self.session_factory() as db:
                deleted = await purge_old_alerts(db, now_utc=datetime(2026, 4, 28, 0, 0, 0))
                remaining = (await db.execute(select(SystemAlert))).scalars().all()
                return deleted, remaining

        deleted, remaining = asyncio.run(run())

        self.assertEqual(deleted, 1)
        self.assertEqual(len(remaining), 130)

    def test_session_history_returns_checkin_checkout_and_duration(self):
        async def run():
            from app.services.history_service import list_session_history
            async with self.session_factory() as db:
                return await list_session_history(db, now_utc=datetime(2026, 4, 28, 0, 0, 0))

        history = asyncio.run(run())

        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["driver_name"], "Nguyen Van A")
        self.assertEqual(history["items"][0]["checkin_display"], "23:00:00 - 27/04/2026")
        self.assertEqual(history["items"][0]["checkout_display"], "00:00:00 - 28/04/2026")
        self.assertEqual(history["items"][0]["duration_text"], "01:00:00")


if __name__ == "__main__":
    unittest.main()
