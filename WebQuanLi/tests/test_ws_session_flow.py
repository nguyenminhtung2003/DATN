import asyncio
import sys
import uuid
import unittest
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.models import Driver, DriverSession, SystemAlert, Vehicle


class JetsonSessionFlowTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"ws_session_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.ids = asyncio.run(self._create_schema_and_seed())

    def tearDown(self):
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _create_schema_and_seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(
                plate_number="59A-12345",
                name="Xe Demo 01",
                device_id="jetson-nano-001",
                manager_phone="0901234567",
            )
            driver_a = Driver(
                name="Driver A",
                age=30,
                gender="Nam",
                phone="0900000001",
                rfid_tag="RFID-A",
                face_image_path="/static/faces/driver_a.jpg",
            )
            driver_b = Driver(
                name="Driver B",
                age=31,
                gender="Nam",
                phone="0900000002",
                rfid_tag="RFID-B",
            )
            db.add_all([vehicle, driver_a, driver_b])
            await db.commit()
            return {"vehicle_id": vehicle.id, "driver_a_id": driver_a.id, "driver_b_id": driver_b.id}

    def test_resolve_driver_by_rfid_returns_none_for_unknown_rfid(self):
        async def run():
            from app.services.jetson_session_service import resolve_driver_by_rfid

            async with self.session_factory() as db:
                known = await resolve_driver_by_rfid(db, "RFID-A")
                unknown = await resolve_driver_by_rfid(db, "UNKNOWN")
                return known, unknown

        known, unknown = asyncio.run(run())

        self.assertEqual(known.name, "Driver A")
        self.assertIsNone(unknown)

    def test_start_or_reuse_session_does_not_duplicate_same_driver(self):
        async def run():
            from app.services.jetson_session_service import start_or_reuse_session

            async with self.session_factory() as db:
                first = await start_or_reuse_session(db, self.ids["vehicle_id"], self.ids["driver_a_id"])
                second = await start_or_reuse_session(db, self.ids["vehicle_id"], self.ids["driver_a_id"])
                result = await db.execute(select(DriverSession))
                sessions = result.scalars().all()
                return first, second, sessions

        first, second, sessions = asyncio.run(run())

        self.assertEqual(first.id, second.id)
        self.assertEqual(len(sessions), 1)
        self.assertIsNone(sessions[0].checkout_at)

    def test_start_or_reuse_session_closes_previous_driver_before_new_driver(self):
        async def run():
            from app.services.jetson_session_service import start_or_reuse_session

            async with self.session_factory() as db:
                first = await start_or_reuse_session(db, self.ids["vehicle_id"], self.ids["driver_a_id"])
                second = await start_or_reuse_session(db, self.ids["vehicle_id"], self.ids["driver_b_id"])
                result = await db.execute(select(DriverSession).order_by(DriverSession.id))
                sessions = result.scalars().all()
                return first.id, second.id, sessions

        first_id, second_id, sessions = asyncio.run(run())

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(sessions), 2)
        self.assertIsNotNone(sessions[0].checkout_at)
        self.assertIsNone(sessions[1].checkout_at)
        self.assertEqual(sessions[1].driver_id, self.ids["driver_b_id"])

    def test_create_drowsiness_alert_links_active_session_and_driver(self):
        async def run():
            from app.models import AlertLevel
            from app.services.jetson_session_service import create_drowsiness_alert, start_or_reuse_session

            async with self.session_factory() as db:
                session = await start_or_reuse_session(db, self.ids["vehicle_id"], self.ids["driver_a_id"])
                alert = await create_drowsiness_alert(
                    db,
                    vehicle_id=self.ids["vehicle_id"],
                    level=AlertLevel.LEVEL_1,
                    ear=0.2,
                    mar=0.1,
                    pitch=1.0,
                )
                result = await db.execute(select(SystemAlert))
                alerts = result.scalars().all()
                return session.id, session.driver_id, alert.id, alerts

        session_id, driver_id, alert_id, alerts = asyncio.run(run())

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].id, alert_id)
        self.assertEqual(alerts[0].session_id, session_id)
        self.assertEqual(alerts[0].driver_id, driver_id)

    def test_close_active_session_marks_checkout(self):
        async def run():
            from app.services.jetson_session_service import close_active_session, start_or_reuse_session

            async with self.session_factory() as db:
                session = await start_or_reuse_session(db, self.ids["vehicle_id"], self.ids["driver_a_id"])
                closed = await close_active_session(db, self.ids["vehicle_id"])
                return session.id, closed.id, closed.checkout_at

        session_id, closed_id, checkout_at = asyncio.run(run())

        self.assertEqual(session_id, closed_id)
        self.assertIsNotNone(checkout_at)

    def test_create_drowsiness_alert_deduplicates_same_vehicle_timestamp_and_level(self):
        async def run():
            from app.models import AlertLevel
            from app.services.jetson_session_service import create_drowsiness_alert

            ts = 1_713_662_400.5
            async with self.session_factory() as db:
                first = await create_drowsiness_alert(
                    db,
                    vehicle_id=self.ids["vehicle_id"],
                    level=AlertLevel.LEVEL_2,
                    ear=0.18,
                    mar=0.61,
                    pitch=-8.0,
                    perclos=0.42,
                    ai_state="DROWSY",
                    ai_confidence=0.91,
                    ai_reason="reconnect replay",
                    lat=10.762622,
                    lng=106.660172,
                    timestamp=ts,
                )
                second = await create_drowsiness_alert(
                    db,
                    vehicle_id=self.ids["vehicle_id"],
                    level=AlertLevel.LEVEL_2,
                    ear=0.18,
                    mar=0.61,
                    pitch=-8.0,
                    perclos=0.42,
                    ai_state="DROWSY",
                    ai_confidence=0.91,
                    ai_reason="reconnect replay",
                    lat=10.762622,
                    lng=106.660172,
                    timestamp=ts,
                )
                result = await db.execute(select(SystemAlert).order_by(SystemAlert.id))
                alerts = result.scalars().all()
                return first.id, second.id, alerts

        first_id, second_id, alerts = asyncio.run(run())

        self.assertEqual(first_id, second_id)
        self.assertEqual(len(alerts), 1)


if __name__ == "__main__":
    unittest.main()
