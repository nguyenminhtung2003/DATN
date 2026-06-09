import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Driver, DriverPenalty, DriverSafetyAdjustment, User, Vehicle
from app.services.driver_safety_service import (
    apply_penalty_deduction,
    calculate_driver_safety_score,
)


class PenaltyManagementTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"penalty_management_{uuid.uuid4().hex}.db"
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
        self.ids = asyncio.run(self._seed())

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
            )
            driver = Driver(name="Primary Driver", rfid_tag="RFID-PRIMARY", is_active=True)
            db.add_all([vehicle, driver])
            await db.flush()
            penalty = DriverPenalty(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                violation_time=datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
                reason="Canh bao buon ngu muc 3",
                amount_vnd=200000,
                driver_telegram_status="sent",
                assistant_telegram_status="sent",
                admin_telegram_status="sent",
                review_status="pending",
                recommended_action="warning",
            )
            db.add(penalty)
            await db.flush()
            await apply_penalty_deduction(db, penalty, created_by="system")
            await db.commit()
            return {"vehicle_id": vehicle.id, "driver_id": driver.id, "penalty_id": penalty.id}

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    async def _penalty(self):
        async with self.session_factory() as db:
            result = await db.execute(select(DriverPenalty).where(DriverPenalty.id == self.ids["penalty_id"]))
            return result.scalar_one()

    async def _safety_score(self):
        async with self.session_factory() as db:
            return await calculate_driver_safety_score(db, self.ids["driver_id"])

    async def _safety_adjustments(self):
        async with self.session_factory() as db:
            result = await db.execute(
                select(DriverSafetyAdjustment)
                .where(DriverSafetyAdjustment.driver_id == self.ids["driver_id"])
                .order_by(DriverSafetyAdjustment.id)
            )
            return result.scalars().all()

    def test_penalties_page_renders_filters_status_and_admin_actions(self):
        response = asyncio.run(self._request("GET", "/penalties"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Quản lý xử phạt", html)
        self.assertIn("Primary Driver", html)
        self.assertIn("59A-12345", html)
        self.assertIn("Đề xuất cảnh cáo", html)
        self.assertIn("Chưa xử lý", html)
        self.assertIn("Xác nhận", html)
        self.assertIn("Hủy", html)
        self.assertIn("nav-penalties", html)

    def test_penalties_page_renders_filtered_summary_cards(self):
        response = asyncio.run(self._request("GET", "/penalties?review_status=pending"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("penalty-summary-grid", html)
        self.assertIn('id="summary-total-count">1</strong>', html)
        self.assertIn('id="summary-pending-count">1</strong>', html)
        self.assertIn('id="summary-confirmed-count">0</strong>', html)
        self.assertIn('id="summary-cancelled-count">0</strong>', html)
        self.assertIn('id="summary-total-amount">200.000đ</strong>', html)

    def test_penalties_api_filters_by_status(self):
        response = asyncio.run(self._request("GET", "/api/penalties?review_status=pending"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["review_status"], "pending")

    def test_admin_can_confirm_cancel_and_note_penalty(self):
        score = asyncio.run(self._safety_score())
        self.assertEqual(score.score, 85)

        response = asyncio.run(self._request(
            "POST",
            f"/api/penalties/{self.ids['penalty_id']}/review",
            data={
                "review_status": "confirmed",
                "admin_note": "Da xac nhan voi tai xe",
                "next_url": "/penalties",
            },
        ))
        self.assertEqual(response.status_code, 303)

        penalty = asyncio.run(self._penalty())
        self.assertEqual(penalty.review_status, "confirmed")
        self.assertEqual(penalty.admin_note, "Da xac nhan voi tai xe")
        self.assertEqual(penalty.resolved_by, "admin")
        self.assertIsNotNone(penalty.resolved_at)
        score = asyncio.run(self._safety_score())
        self.assertEqual(score.score, 85)

        response = asyncio.run(self._request(
            "POST",
            f"/api/penalties/{self.ids['penalty_id']}/review",
            data={
                "review_status": "cancelled",
                "admin_note": "Canh bao sai",
                "next_url": "/penalties",
            },
        ))
        self.assertEqual(response.status_code, 303)

        penalty = asyncio.run(self._penalty())
        self.assertEqual(penalty.review_status, "cancelled")
        self.assertEqual(penalty.admin_note, "Canh bao sai")
        self.assertEqual(penalty.resolved_by, "admin")
        score = asyncio.run(self._safety_score())
        self.assertEqual(score.score, 100)

        response = asyncio.run(self._request(
            "POST",
            f"/api/penalties/{self.ids['penalty_id']}/review",
            data={
                "review_status": "cancelled",
                "admin_note": "Canh bao sai lan 2",
                "next_url": "/penalties",
            },
        ))
        self.assertEqual(response.status_code, 303)

        score = asyncio.run(self._safety_score())
        adjustments = asyncio.run(self._safety_adjustments())
        self.assertEqual(score.score, 100)
        self.assertEqual([a.delta_points for a in adjustments], [-15, 15])

        response = asyncio.run(self._request(
            "POST",
            f"/api/penalties/{self.ids['penalty_id']}/review",
            data={
                "review_status": "confirmed",
                "admin_note": "Xac nhan lai",
                "next_url": "/penalties",
            },
        ))
        self.assertEqual(response.status_code, 303)
        score = asyncio.run(self._safety_score())
        adjustments = asyncio.run(self._safety_adjustments())
        self.assertEqual(score.score, 85)
        self.assertEqual([a.delta_points for a in adjustments], [-15, 15, -15])

    def test_invalid_review_status_is_rejected(self):
        response = asyncio.run(self._request(
            "POST",
            f"/api/penalties/{self.ids['penalty_id']}/review",
            data={"review_status": "fired", "admin_note": "", "next_url": "/penalties"},
        ))

        self.assertEqual(response.status_code, 400)


class PenaltyRecommendationTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"penalty_recommendation_{uuid.uuid4().hex}.db"
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
            vehicle = Vehicle(plate_number="59A-99999", name="Xe Demo 02")
            driver = Driver(name="Repeat Driver", rfid_tag="RFID-REPEAT", is_active=True)
            db.add_all([vehicle, driver])
            await db.flush()
            await db.commit()
            return {"vehicle_id": vehicle.id, "driver_id": driver.id}

    async def _add_penalties(self, offsets_days):
        base_time = datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc)
        async with self.session_factory() as db:
            for index, offset in enumerate(offsets_days, start=1):
                db.add(
                    DriverPenalty(
                        vehicle_id=self.ids["vehicle_id"],
                        driver_id=self.ids["driver_id"],
                        violation_time=base_time - timedelta(days=offset),
                        reason=f"old penalty {index}",
                        amount_vnd=200000,
                    )
                )
            await db.commit()
        return base_time

    def test_recommendation_thresholds(self):
        async def run():
            from app.services.penalty_service import recommend_penalty_action

            base_time = datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc)
            async with self.session_factory() as db:
                first = await recommend_penalty_action(db, self.ids["driver_id"], base_time)

            await self._add_penalties([1])
            async with self.session_factory() as db:
                warning = await recommend_penalty_action(db, self.ids["driver_id"], base_time)

            await self._add_penalties([2])
            async with self.session_factory() as db:
                suspend = await recommend_penalty_action(db, self.ids["driver_id"], base_time)

            await self._add_penalties([10, 11])
            async with self.session_factory() as db:
                discipline = await recommend_penalty_action(db, self.ids["driver_id"], base_time)

            return first, warning, suspend, discipline

        first, warning, suspend, discipline = asyncio.run(run())
        self.assertEqual(first, "penalty_only")
        self.assertEqual(warning, "warning")
        self.assertEqual(suspend, "suspend_driving")
        self.assertEqual(discipline, "discipline_review")


class PenaltySchemaMigrationTest(unittest.TestCase):
    def test_backfill_creates_deductions_for_existing_active_penalties_only(self):
        async def run():
            from app.services.driver_safety_service import backfill_penalty_safety_adjustments

            db_path = Path(__file__).resolve().parents[1] / "data" / f"backfill_safety_{uuid.uuid4().hex}.db"
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                async with session_factory() as db:
                    vehicle = Vehicle(plate_number="59A-77777", name="Xe Backfill")
                    driver = Driver(name="Backfill Driver", rfid_tag="RFID-BACKFILL", is_active=True)
                    db.add_all([vehicle, driver])
                    await db.flush()
                    active = DriverPenalty(
                        vehicle_id=vehicle.id,
                        driver_id=driver.id,
                        violation_time=datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
                        reason="active old penalty",
                        amount_vnd=200000,
                        review_status="pending",
                    )
                    cancelled = DriverPenalty(
                        vehicle_id=vehicle.id,
                        driver_id=driver.id,
                        violation_time=datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
                        reason="cancelled old penalty",
                        amount_vnd=200000,
                        review_status="cancelled",
                    )
                    db.add_all([active, cancelled])
                    await db.commit()

                async with session_factory() as db:
                    backfilled = await backfill_penalty_safety_adjustments(db)
                    result = await db.execute(select(DriverSafetyAdjustment).order_by(DriverSafetyAdjustment.id))
                    adjustments = result.scalars().all()
                return db_path, engine, backfilled, adjustments, active.id, cancelled.id
            except Exception:
                await engine.dispose()
                db_path.unlink(missing_ok=True)
                raise

        db_path, engine, backfilled, adjustments, active_id, cancelled_id = asyncio.run(run())
        try:
            self.assertEqual(backfilled, 1)
            self.assertEqual(len(adjustments), 1)
            self.assertEqual(adjustments[0].penalty_id, active_id)
            self.assertNotEqual(adjustments[0].penalty_id, cancelled_id)
            self.assertEqual(adjustments[0].source_type, "penalty_deduct")
            self.assertEqual(adjustments[0].delta_points, -15)
        finally:
            asyncio.run(engine.dispose())
            db_path.unlink(missing_ok=True)

    def test_sqlite_runtime_sync_adds_penalty_management_columns(self):
        async def run():
            import app.database as database_module
            from app.config import settings

            db_path = Path(__file__).resolve().parents[1] / "data" / f"old_penalty_schema_{uuid.uuid4().hex}.db"
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
            original_engine = database_module.engine
            original_url = settings.DATABASE_URL
            settings.DATABASE_URL = f"sqlite+aiosqlite:///{db_path.as_posix()}"
            database_module.engine = engine
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("CREATE TABLE drivers (id INTEGER PRIMARY KEY, name VARCHAR(100), rfid_tag VARCHAR(50))"))
                    await conn.execute(text("CREATE TABLE vehicles (id INTEGER PRIMARY KEY, plate_number VARCHAR(20), name VARCHAR(100))"))
                    await conn.execute(text("""
                        CREATE TABLE driver_penalties (
                            id INTEGER PRIMARY KEY,
                            vehicle_id INTEGER NOT NULL,
                            driver_id INTEGER NOT NULL,
                            violation_time DATETIME NOT NULL,
                            reason TEXT NOT NULL,
                            amount_vnd INTEGER NOT NULL DEFAULT 200000,
                            driver_telegram_status VARCHAR(30) NOT NULL DEFAULT 'pending',
                            assistant_telegram_status VARCHAR(30) NOT NULL DEFAULT 'pending',
                            created_at DATETIME
                        )
                    """))

                await database_module._ensure_sqlite_columns()
                async with engine.begin() as conn:
                    columns = {
                        row[1]
                        for row in (await conn.execute(text("PRAGMA table_info(driver_penalties)"))).fetchall()
                    }
                return db_path, columns
            finally:
                settings.DATABASE_URL = original_url
                database_module.engine = original_engine
                await engine.dispose()

        db_path, columns = asyncio.run(run())
        try:
            self.assertIn("review_status", columns)
            self.assertIn("admin_note", columns)
            self.assertIn("resolved_at", columns)
            self.assertIn("resolved_by", columns)
            self.assertIn("recommended_action", columns)
        finally:
            db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
