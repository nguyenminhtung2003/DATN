import asyncio
import sys
import uuid
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Driver, User, Vehicle


class DriverRegistrySyncTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"driver_registry_{uuid.uuid4().hex}.db"
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

        self.ids = asyncio.run(self._create_schema_and_seed())

    def tearDown(self):
        app.dependency_overrides.clear()
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
            other_vehicle = Vehicle(
                plate_number="59A-67890",
                name="Xe Demo 02",
                device_id="jetson-other-002",
                manager_phone="0907654321",
            )
            db.add_all([vehicle, other_vehicle])
            await db.flush()

            assigned = Driver(
                name="Assigned Driver",
                rfid_tag="RFID-A",
                vehicle_id=vehicle.id,
                face_image_path="/static/faces/driver_assigned.jpg",
            )
            no_face = Driver(
                name="No Face Driver",
                rfid_tag="RFID-B",
                vehicle_id=vehicle.id,
            )
            other_vehicle_driver = Driver(
                name="Other Vehicle Driver",
                rfid_tag="RFID-C",
                vehicle_id=other_vehicle.id,
                face_image_path="/static/faces/driver_other.jpg",
            )
            inactive = Driver(
                name="Inactive Driver",
                rfid_tag="RFID-D",
                vehicle_id=vehicle.id,
                face_image_path="/static/faces/driver_inactive.jpg",
                is_active=False,
            )
            upload_target = Driver(
                name="Upload Target",
                rfid_tag="RFID-UP",
                vehicle_id=vehicle.id,
            )
            db.add_all([assigned, no_face, other_vehicle_driver, inactive, upload_target])
            await db.commit()

            return {
                "vehicle_id": vehicle.id,
                "upload_target_id": upload_target.id,
            }

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_registry_endpoint_returns_only_active_assigned_drivers_with_faces(self):
        response = asyncio.run(self._request("GET", "/api/jetson/jetson-nano-001/driver-registry"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["device_id"], "jetson-nano-001")
        self.assertEqual(len(payload["drivers"]), 1)
        self.assertEqual(payload["drivers"][0]["name"], "Assigned Driver")
        self.assertEqual(payload["drivers"][0]["rfid_tag"], "RFID-A")
        self.assertEqual(payload["drivers"][0]["face_image_url"], "http://test/static/faces/driver_assigned.jpg")

    def test_upload_face_triggers_registry_sync_command_for_online_vehicle(self):
        with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
            "app.ws.jetson_handler.manager.active",
            {"jetson-nano-001": object()},
            clear=True,
        ):
            response = asyncio.run(
                self._request(
                    "POST",
                    f"/api/drivers/{self.ids['upload_target_id']}/face",
                    files={"file": ("face.jpg", b"\xff\xd8\xff\xe0demo-image", "image/jpeg")},
                )
            )

        self.assertEqual(response.status_code, 200)
        send_command.assert_awaited_once()
        device_id, command = send_command.await_args.args
        self.assertEqual(device_id, "jetson-nano-001")
        self.assertEqual(command["action"], "sync_driver_registry")
        self.assertTrue(command["manifest_url"].endswith("/api/jetson/jetson-nano-001/driver-registry"))

    def test_manual_sync_endpoint_dispatches_driver_registry_command(self):
        with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
            "app.ws.jetson_handler.manager.active",
            {"jetson-nano-001": object()},
            clear=True,
        ):
            response = asyncio.run(
                self._request("POST", f"/api/vehicles/{self.ids['vehicle_id']}/sync-driver-registry")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sent")
        send_command.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
