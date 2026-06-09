import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.config import settings
from app.models import (
    AlertLevel,
    AlertType,
    Driver,
    DriverPenalty,
    DriverSafetyAdjustment,
    DriverSession,
    SystemAlert,
    Vehicle,
)


class PenaltyTelegramTest(unittest.TestCase):
    def setUp(self):
        self.original_admin_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        settings.ADMIN_TELEGRAM_CHAT_ID = "ADMIN-CHAT"
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"penalty_telegram_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.ids = asyncio.run(self._create_schema_and_seed())

    def tearDown(self):
        asyncio.run(self.engine.dispose())
        settings.ADMIN_TELEGRAM_CHAT_ID = self.original_admin_chat_id
        self.db_path.unlink(missing_ok=True)

    async def _create_schema_and_seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with self.session_factory() as db:
            vehicle = Vehicle(
                plate_number="59A-12345",
                name="Xe Demo 01",
                device_id="JETSON-001",
                manager_phone="0901234567",
            )
            primary_driver = Driver(
                name="Primary Driver",
                rfid_tag="RFID-PRIMARY",
                is_active=True,
                telegram_chat_id="186667059",
            )
            assistant_driver = Driver(
                name="Assistant Driver",
                rfid_tag="RFID-ASSISTANT",
                is_active=True,
                telegram_chat_id="186667060",
            )
            db.add_all([vehicle, primary_driver, assistant_driver])
            await db.flush()

            primary_driver.vehicle_id = vehicle.id
            assistant_driver.vehicle_id = vehicle.id
            vehicle.assistant_driver_id = assistant_driver.id
            active_session = DriverSession(
                vehicle_id=vehicle.id,
                driver_id=primary_driver.id,
                checkin_at=datetime(2026, 6, 3, 7, 30, tzinfo=timezone.utc),
                checkout_at=None,
            )
            db.add(active_session)
            await db.flush()

            level3_alert = SystemAlert(
                vehicle_id=vehicle.id,
                driver_id=primary_driver.id,
                session_id=active_session.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_3,
                latitude=10.7769,
                longitude=106.7009,
                message="Tai xe buon ngu muc 3",
                timestamp=datetime(2026, 6, 3, 7, 45, tzinfo=timezone.utc),
            )
            level2_alert = SystemAlert(
                vehicle_id=vehicle.id,
                driver_id=primary_driver.id,
                session_id=active_session.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_2,
                latitude=10.7769,
                longitude=106.7009,
                message="Tai xe buon ngu muc 2",
                timestamp=datetime(2026, 6, 3, 7, 40, tzinfo=timezone.utc),
            )
            level1_alert = SystemAlert(
                vehicle_id=vehicle.id,
                driver_id=primary_driver.id,
                session_id=active_session.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_1,
                latitude=10.7769,
                longitude=106.7009,
                message="Tai xe buon ngu muc 1",
                timestamp=datetime(2026, 6, 3, 7, 35, tzinfo=timezone.utc),
            )
            db.add_all([level3_alert, level2_alert, level1_alert])
            await db.commit()
            return {
                "vehicle_id": vehicle.id,
                "primary_driver_id": primary_driver.id,
                "session_id": active_session.id,
                "level3_alert_id": level3_alert.id,
                "level2_alert_id": level2_alert.id,
                "level1_alert_id": level1_alert.id,
            }

    async def _penalties(self):
        async with self.session_factory() as db:
            result = await db.execute(select(DriverPenalty).order_by(DriverPenalty.id))
            return result.scalars().all()

    async def _safety_adjustments(self):
        async with self.session_factory() as db:
            result = await db.execute(select(DriverSafetyAdjustment).order_by(DriverSafetyAdjustment.id))
            return result.scalars().all()

    def test_level3_alert_creates_penalty_and_sends_driver_assistant_and_admin_telegram_messages(self):
        async def run():
            from app.services.penalty_service import process_level3_penalty_for_alert

            with patch(
                "app.services.penalty_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                async with self.session_factory() as db:
                    penalty = await process_level3_penalty_for_alert(db, self.ids["level3_alert_id"])
                penalties = await self._penalties()
                adjustments = await self._safety_adjustments()
                return penalty, penalties, adjustments, send_telegram

        penalty, penalties, adjustments, send_telegram = asyncio.run(run())

        self.assertIsNotNone(penalty)
        self.assertEqual(len(penalties), 1)
        self.assertEqual(penalties[0].amount_vnd, 200000)
        self.assertEqual(penalties[0].review_status, "pending")
        self.assertEqual(penalties[0].recommended_action, "penalty_only")
        self.assertEqual(len(adjustments), 1)
        self.assertEqual(adjustments[0].penalty_id, penalties[0].id)
        self.assertEqual(adjustments[0].driver_id, self.ids["primary_driver_id"])
        self.assertEqual(adjustments[0].source_type, "penalty_deduct")
        self.assertEqual(adjustments[0].delta_points, -15)
        self.assertEqual(penalties[0].driver_telegram_status, "sent")
        self.assertEqual(penalties[0].assistant_telegram_status, "sent")
        self.assertEqual(penalties[0].admin_telegram_status, "sent")
        self.assertEqual(send_telegram.await_count, 3)
        self.assertEqual(send_telegram.await_args_list[0].args[0], "186667059")
        self.assertEqual(send_telegram.await_args_list[1].args[0], "186667060")
        self.assertEqual(send_telegram.await_args_list[2].args[0], "ADMIN-CHAT")
        self.assertIn("THONG BAO XU PHAT", send_telegram.await_args_list[0].args[1])
        self.assertIn("CANH BAO DOI TAI XE", send_telegram.await_args_list[1].args[1])
        self.assertIn("CANH BAO BUON NGU MUC 3", send_telegram.await_args_list[2].args[1])
        self.assertIn("Primary Driver", send_telegram.await_args_list[2].args[1])
        self.assertIn("59A-12345", send_telegram.await_args_list[2].args[1])
        self.assertIn("Google Maps: https://www.google.com/maps?q=10.776900,106.700900", send_telegram.await_args_list[0].args[1])
        self.assertIn("Google Maps: https://www.google.com/maps?q=10.776900,106.700900", send_telegram.await_args_list[1].args[1])
        self.assertIn("Google Maps: https://www.google.com/maps?q=10.776900,106.700900", send_telegram.await_args_list[2].args[1])

    def test_level1_or_level2_alert_does_not_create_penalty(self):
        async def run():
            from app.services.penalty_service import process_level3_penalty_for_alert

            with patch("app.services.penalty_service.send_telegram_message", new=AsyncMock()) as send_telegram:
                async with self.session_factory() as db:
                    level1_penalty = await process_level3_penalty_for_alert(db, self.ids["level1_alert_id"])
                    level2_penalty = await process_level3_penalty_for_alert(db, self.ids["level2_alert_id"])
                penalties = await self._penalties()
                return level1_penalty, level2_penalty, penalties, send_telegram

        level1_penalty, level2_penalty, penalties, send_telegram = asyncio.run(run())

        self.assertIsNone(level1_penalty)
        self.assertIsNone(level2_penalty)
        self.assertEqual(penalties, [])
        send_telegram.assert_not_awaited()

    def test_processing_same_level3_alert_twice_keeps_one_penalty(self):
        async def run():
            from app.services.penalty_service import process_level3_penalty_for_alert

            with patch(
                "app.services.penalty_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                async with self.session_factory() as db:
                    first = await process_level3_penalty_for_alert(db, self.ids["level3_alert_id"])
                    second = await process_level3_penalty_for_alert(db, self.ids["level3_alert_id"])
                penalties = await self._penalties()
                return first, second, penalties, send_telegram

        first, second, penalties, send_telegram = asyncio.run(run())

        self.assertEqual(first.id, second.id)
        self.assertEqual(len(penalties), 1)
        self.assertEqual(send_telegram.await_count, 3)

    def test_duplicate_insert_conflict_returns_existing_penalty_without_resend(self):
        async def run():
            from app.services.penalty_service import process_level3_penalty_for_alert

            with patch(
                "app.services.penalty_service.send_telegram_message",
                new=AsyncMock(return_value={"ok": True}),
            ) as send_telegram:
                async with self.session_factory() as db:
                    original_commit = db.commit
                    commit_calls = 0

                    async def conflicting_commit():
                        nonlocal commit_calls
                        commit_calls += 1
                        if commit_calls == 1:
                            async with self.session_factory() as other_db:
                                other_db.add(
                                    DriverPenalty(
                                        alert_id=self.ids["level3_alert_id"],
                                        vehicle_id=self.ids["vehicle_id"],
                                        driver_id=self.ids["primary_driver_id"],
                                        session_id=self.ids["session_id"],
                                        violation_time=datetime(2026, 6, 3, 7, 45, tzinfo=timezone.utc),
                                        reason="existing penalty from concurrent worker",
                                        amount_vnd=200000,
                                        driver_telegram_status="sent",
                                        assistant_telegram_status="sent",
                                    )
                                )
                                await other_db.commit()
                        await original_commit()

                    db.commit = conflicting_commit
                    penalty = await process_level3_penalty_for_alert(db, self.ids["level3_alert_id"])
                penalties = await self._penalties()
                return penalty, penalties, send_telegram

        penalty, penalties, send_telegram = asyncio.run(run())

        self.assertIsNotNone(penalty)
        self.assertEqual(len(penalties), 1)
        self.assertEqual(penalty.id, penalties[0].id)
        self.assertEqual(penalties[0].reason, "existing penalty from concurrent worker")
        send_telegram.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
