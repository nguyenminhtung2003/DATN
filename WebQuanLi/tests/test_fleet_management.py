import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timezone
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
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
                manager_phone="0901234567",
            )
            active_driver = Driver(
                name="Active Driver",
                rfid_tag="RFID-A",
                is_active=True,
                telegram_chat_id="186667059",
            )
            assistant_driver = Driver(
                name="Assistant Driver",
                rfid_tag="RFID-AST",
                is_active=True,
                telegram_chat_id="186667060",
            )
            inactive_driver = Driver(name="Inactive Driver", rfid_tag="RFID-I", is_active=False)
            db.add_all([vehicle, active_driver, assistant_driver, inactive_driver])
            await db.flush()
            vehicle.assistant_driver_id = assistant_driver.id
            penalty = DriverPenalty(
                driver_id=active_driver.id,
                vehicle_id=vehicle.id,
                violation_time=datetime.now(timezone.utc),
                reason="Canh bao buon ngu muc 3",
                amount_vnd=200000,
                driver_telegram_status="sent",
                assistant_telegram_status="sent",
            )
            db.add(penalty)
            await db.flush()
            await apply_penalty_deduction(db, penalty, created_by="system")
            await db.commit()
            return {"active_driver_id": active_driver.id, "assistant_driver_id": assistant_driver.id}

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

    def test_sidebar_hides_api_docs_link(self):
        response = asyncio.run(self._request("GET", "/fleet"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id="nav-docs"', response.text)
        self.assertNotIn("API Docs", response.text)

    def test_fleet_page_renders_telegram_and_assistant_driver_controls(self):
        response = asyncio.run(self._request("GET", "/fleet"))
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("Quản Lý Đội Xe & Tài Xế", html)
        self.assertIn("Danh sách xe", html)
        self.assertIn("Biển số", html)
        self.assertIn("Tài xế phụ", html)
        self.assertIn("Trạng thái", html)
        self.assertIn("Danh sách tài xế", html)
        self.assertIn("Ảnh mặt", html)
        self.assertIn("Giới tính", html)
        self.assertIn('name="telegram_chat_id"', html)
        self.assertIn('name="assistant_driver_id"', html)
        self.assertIn('id="edit-vehicle-form"', html)
        self.assertIn("btn-edit-vehicle", html)
        self.assertIn("Assistant Driver", html)
        self.assertIn("186667059", html)

    def test_fleet_page_renders_driver_safety_scores_and_hides_penalty_history(self):
        response = asyncio.run(self._request("GET", "/fleet"))
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertNotIn("Lịch sử xử phạt", html)
        self.assertIn("Điểm an toàn", html)
        self.assertIn("Mức đánh giá", html)
        self.assertIn("btn-safety-score", html)
        self.assertIn("safety-score-overlay", html)
        self.assertIn("85/100", html)
        self.assertIn("100/100", html)
        self.assertIn("An toàn", html)

    def test_fleet_page_uses_toast_instead_of_browser_alerts(self):
        response = asyncio.run(self._request("GET", "/fleet"))
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("/static/js/toast.js", html)
        self.assertIn("toast-container", html)
        self.assertIn("showToast(", html)
        self.assertNotIn("alert('", html)
        self.assertNotIn('alert("', html)

    def test_admin_can_manually_set_and_reset_driver_safety_score(self):
        async def run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                set_response = await client.post(
                    f"/api/drivers/{self.ids['active_driver_id']}/safety-score",
                    json={"score": 80, "note": "Dieu chinh demo"},
                )
                reset_response = await client.post(
                    f"/api/drivers/{self.ids['active_driver_id']}/safety-score/reset",
                    json={"note": "Reset demo"},
                )

            async with self.session_factory() as db:
                score = await calculate_driver_safety_score(db, self.ids["active_driver_id"])
                result = await db.execute(
                    select(DriverSafetyAdjustment)
                    .where(DriverSafetyAdjustment.driver_id == self.ids["active_driver_id"])
                    .order_by(DriverSafetyAdjustment.id)
                )
                adjustments = result.scalars().all()
            return set_response, reset_response, score, adjustments

        set_response, reset_response, score, adjustments = asyncio.run(run())

        self.assertEqual(set_response.status_code, 200)
        self.assertEqual(set_response.json()["score"], 80)
        self.assertEqual(reset_response.status_code, 200)
        self.assertEqual(reset_response.json()["score"], 100)
        self.assertEqual(score.score, 100)
        self.assertEqual([a.source_type for a in adjustments], ["penalty_deduct", "manual_set", "reset"])
        self.assertEqual([a.delta_points for a in adjustments], [-15, -5, 20])

    def test_manual_score_set_uses_raw_ledger_score_before_clamping(self):
        async def run():
            async with self.session_factory() as db:
                db.add(
                    DriverSafetyAdjustment(
                        driver_id=self.ids["active_driver_id"],
                        delta_points=-200,
                        reason="Heavy historical deduction",
                        source_type="manual_set",
                        created_by="test",
                    )
                )
                await db.commit()

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    f"/api/drivers/{self.ids['active_driver_id']}/safety-score",
                    json={"score": 80, "note": "Set from clamped score"},
                )

            async with self.session_factory() as db:
                score = await calculate_driver_safety_score(db, self.ids["active_driver_id"])
                result = await db.execute(
                    select(DriverSafetyAdjustment)
                    .where(DriverSafetyAdjustment.driver_id == self.ids["active_driver_id"])
                    .order_by(DriverSafetyAdjustment.id)
                )
                adjustments = result.scalars().all()
            return response, score, adjustments

        response, score, adjustments = asyncio.run(run())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["score"], 80)
        self.assertEqual(score.score, 80)
        self.assertEqual(adjustments[-1].delta_points, 195)


if __name__ == "__main__":
    unittest.main()
