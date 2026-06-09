import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.event_bus import event_bus
from app.database import Base
from app.models import Driver, DriverSession, HardwareIncident, Vehicle


class HardwareIncidentServiceTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"hardware_incident_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.original_admin_chat_id = getattr(settings, "ADMIN_TELEGRAM_CHAT_ID", "")
        settings.ADMIN_TELEGRAM_CHAT_ID = "ADMIN-CHAT"
        event_bus._vehicle_state.clear()
        self.now = datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc)
        self.ids = asyncio.run(self._create_schema_and_seed())

    def tearDown(self):
        settings.ADMIN_TELEGRAM_CHAT_ID = self.original_admin_chat_id
        event_bus._vehicle_state.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _create_schema_and_seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(plate_number="59A-12345", name="Xe Demo 01", device_id="JETSON-001")
            driver = Driver(
                name="Nguyen Minh Tung",
                rfid_tag="RFID-PRIMARY",
                telegram_chat_id="DRIVER-CHAT",
                vehicle=vehicle,
            )
            db.add_all([vehicle, driver])
            await db.flush()
            session = DriverSession(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                checkin_at=self.now - timedelta(minutes=10),
            )
            db.add(session)
            await db.commit()
            return {"vehicle_id": vehicle.id, "driver_id": driver.id, "session_id": session.id}

    def _healthy_payload(self, **overrides):
        payload = {
            "camera_ok": True,
            "rfid_reader_ok": True,
            "gps_uart_ok": True,
            "bluetooth_adapter_ok": True,
            "bluetooth_speaker_connected": True,
            "speaker_output_ok": True,
            "wifi": True,
        }
        payload.update(overrides)
        return payload

    def _db_time(self, value):
        return value.replace(tzinfo=None)

    async def _incidents(self):
        async with self.session_factory() as db:
            result = await db.execute(select(HardwareIncident).order_by(HardwareIncident.id))
            return result.scalars().all()

    def test_hardware_failure_creates_incident_and_sends_admin_and_active_driver_telegram(self):
        async def run():
            from app.services.hardware_incident_service import process_hardware_payload

            with patch(
                "app.services.hardware_incident_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                await event_bus.publish(
                    "vehicle:JETSON-001",
                    "gps",
                    {"lat": 10.7769, "lng": 106.7009, "fix_ok": True},
                )
                async with self.session_factory() as db:
                    await process_hardware_payload(
                        db,
                        self.ids["vehicle_id"],
                        self._healthy_payload(rfid_reader_ok=False),
                        now=self.now,
                    )
                incidents = await self._incidents()
                return incidents, send_telegram

        incidents, send_telegram = asyncio.run(run())

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].device_key, "rfid")
        self.assertEqual(incidents[0].driver_id, self.ids["driver_id"])
        self.assertEqual(incidents[0].session_id, self.ids["session_id"])
        self.assertEqual(incidents[0].admin_telegram_status, "sent")
        self.assertEqual(incidents[0].driver_telegram_status, "sent")
        self.assertEqual([call.args[0] for call in send_telegram.await_args_list], ["ADMIN-CHAT", "DRIVER-CHAT"])
        self.assertIn("CANH BAO THIET BI", send_telegram.await_args_list[0].args[1])
        self.assertIn("RFID", send_telegram.await_args_list[0].args[1])
        self.assertIn("Google Maps: https://www.google.com/maps?q=10.776900,106.700900", send_telegram.await_args_list[0].args[1])

    def test_repeated_failure_does_not_duplicate_and_recovery_resolves_incident(self):
        async def run():
            from app.services.hardware_incident_service import process_hardware_payload

            with patch(
                "app.services.hardware_incident_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                async with self.session_factory() as db:
                    await process_hardware_payload(
                        db,
                        self.ids["vehicle_id"],
                        self._healthy_payload(gps_uart_ok=False),
                        now=self.now,
                    )
                    await process_hardware_payload(
                        db,
                        self.ids["vehicle_id"],
                        self._healthy_payload(gps_uart_ok=False),
                        now=self.now + timedelta(seconds=5),
                    )
                    await process_hardware_payload(
                        db,
                        self.ids["vehicle_id"],
                        self._healthy_payload(gps_uart_ok=True),
                        now=self.now + timedelta(seconds=10),
                    )
                incidents = await self._incidents()
                return incidents, send_telegram

        incidents, send_telegram = asyncio.run(run())

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].device_key, "gps")
        self.assertEqual(incidents[0].last_seen_at, self._db_time(self.now + timedelta(seconds=10)))
        self.assertEqual(incidents[0].resolved_at, self._db_time(self.now + timedelta(seconds=10)))
        self.assertEqual(send_telegram.await_count, 2)

    def test_missing_driver_chat_id_records_missing_status_but_still_sends_admin(self):
        async def run():
            from app.services.hardware_incident_service import process_hardware_payload

            with patch(
                "app.services.hardware_incident_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                async with self.session_factory() as db:
                    driver = await db.get(Driver, self.ids["driver_id"])
                    driver.telegram_chat_id = None
                    await db.commit()
                    await process_hardware_payload(
                        db,
                        self.ids["vehicle_id"],
                        self._healthy_payload(bluetooth_speaker_connected=False),
                        now=self.now,
                    )
                incidents = await self._incidents()
                return incidents, send_telegram

        incidents, send_telegram = asyncio.run(run())

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].device_key, "bluetooth")
        self.assertEqual(incidents[0].admin_telegram_status, "sent")
        self.assertEqual(incidents[0].driver_telegram_status, "missing_chat_id")
        self.assertEqual(send_telegram.await_count, 1)
        self.assertEqual(send_telegram.await_args_list[0].args[0], "ADMIN-CHAT")

    def test_heartbeat_timeout_creates_jetson_incident_and_next_hardware_resolves_it(self):
        async def run():
            from app.services.hardware_incident_service import process_hardware_payload, process_heartbeat_timeout

            with patch(
                "app.services.hardware_incident_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                async with self.session_factory() as db:
                    await process_heartbeat_timeout(
                        db,
                        self.ids["vehicle_id"],
                        last_seen=self.now - timedelta(seconds=16),
                        now=self.now,
                        threshold_seconds=15,
                    )
                    await process_hardware_payload(
                        db,
                        self.ids["vehicle_id"],
                        self._healthy_payload(),
                        now=self.now + timedelta(seconds=1),
                    )
                incidents = await self._incidents()
                return incidents, send_telegram

        incidents, send_telegram = asyncio.run(run())

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].device_key, "jetson")
        self.assertEqual(incidents[0].resolved_at, self._db_time(self.now + timedelta(seconds=1)))
        self.assertEqual(send_telegram.await_count, 2)

    def test_no_active_session_sends_only_admin(self):
        async def run():
            from app.services.hardware_incident_service import process_hardware_payload

            with patch(
                "app.services.hardware_incident_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                async with self.session_factory() as db:
                    session = await db.get(DriverSession, self.ids["session_id"])
                    session.checkout_at = self.now - timedelta(minutes=1)
                    await db.commit()
                    await process_hardware_payload(
                        db,
                        self.ids["vehicle_id"],
                        self._healthy_payload(camera_ok=False),
                        now=self.now,
                    )
                incidents = await self._incidents()
                return incidents, send_telegram

        incidents, send_telegram = asyncio.run(run())

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].device_key, "camera")
        self.assertIsNone(incidents[0].driver_id)
        self.assertEqual(incidents[0].admin_telegram_status, "sent")
        self.assertEqual(incidents[0].driver_telegram_status, "not_applicable")
        self.assertEqual(send_telegram.await_count, 1)
        self.assertEqual(send_telegram.await_args_list[0].args[0], "ADMIN-CHAT")


if __name__ == "__main__":
    unittest.main()
