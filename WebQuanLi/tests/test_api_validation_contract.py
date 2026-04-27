import asyncio
import shutil
import sys
import uuid
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import OtaAuditLog, User, Vehicle


class ApiValidationContractTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"api_validation_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.original_static_dir = settings.STATIC_DIR
        self.original_upload_dir = settings.UPLOAD_DIR
        self.static_dir = self.db_path.parent / f"api_validation_static_{uuid.uuid4().hex}"
        settings.STATIC_DIR = self.static_dir
        settings.UPLOAD_DIR = self.static_dir / "updates"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        admin = User(username="admin", role="admin")
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: admin
        app.dependency_overrides[check_admin] = lambda: admin

        asyncio.run(self._create_schema_and_seed_vehicle())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        settings.STATIC_DIR = self.original_static_dir
        settings.UPLOAD_DIR = self.original_upload_dir
        if self.static_dir.resolve().is_relative_to(self.db_path.parent.resolve()):
            shutil.rmtree(self.static_dir, ignore_errors=True)
        self.db_path.unlink(missing_ok=True)

    async def _create_schema_and_seed_vehicle(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            db.add(
                Vehicle(
                    plate_number="59A-12345",
                    name="Xe Demo 01",
                    device_id="jetson-nano-001",
                    manager_phone="0901234567",
                )
            )
            await db.commit()

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_create_driver_rejects_duplicate_rfid_with_409(self):
        async def run():
            first = await self._request("POST", "/api/drivers", json={"name": "Driver A", "rfid_tag": "RFID-001"})
            second = await self._request("POST", "/api/drivers", json={"name": "Driver B", "rfid_tag": "RFID-001"})
            return first, second

        first, second = asyncio.run(run())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("RFID", second.json()["detail"])

    def test_create_vehicle_rejects_duplicate_plate_and_device_id_with_409(self):
        async def run():
            duplicate_plate = await self._request(
                "POST",
                "/api/vehicles",
                json={
                    "plate_number": "59A-12345",
                    "name": "Xe Trung Bien",
                    "device_id": "other-device",
                },
            )
            duplicate_device = await self._request(
                "POST",
                "/api/vehicles",
                json={
                    "plate_number": "59A-99999",
                    "name": "Xe Trung Device",
                    "device_id": "jetson-nano-001",
                },
            )
            return duplicate_plate, duplicate_device

        duplicate_plate, duplicate_device = asyncio.run(run())

        self.assertEqual(duplicate_plate.status_code, 409)
        self.assertIn("Biển số", duplicate_plate.json()["detail"])
        self.assertEqual(duplicate_device.status_code, 409)
        self.assertIn("Device ID", duplicate_device.json()["detail"])

    def test_upload_face_rejects_text_file_and_accepts_image(self):
        async def run():
            driver = await self._request("POST", "/api/drivers", json={"name": "Face Driver", "rfid_tag": "RFID-FACE"})
            driver_id = driver.json()["id"]
            text_upload = await self._request(
                "POST",
                f"/api/drivers/{driver_id}/face",
                files={"file": ("not-image.txt", b"not-image", "text/plain")},
            )
            image_upload = await self._request(
                "POST",
                f"/api/drivers/{driver_id}/face",
                files={"file": ("face.jpg", b"\xff\xd8\xff\xe0demo-image", "image/jpeg")},
            )
            drivers = await self._request("GET", "/api/drivers")
            return text_upload, image_upload, drivers.json()

        text_upload, image_upload, drivers = asyncio.run(run())

        self.assertEqual(text_upload.status_code, 400)
        self.assertEqual(image_upload.status_code, 200)
        self.assertTrue(image_upload.json()["path"].startswith("/static/faces/driver_"))
        self.assertEqual(drivers[0]["face_image_path"], image_upload.json()["path"])

    def test_test_alert_rejects_invalid_level_or_state_and_accepts_valid_form(self):
        async def run():
            invalid_level = await self._request("POST", "/api/vehicles/1/test", data={"level": "999", "state": "on"})
            invalid_state = await self._request("POST", "/api/vehicles/1/test", data={"level": "1", "state": "start"})
            valid = await self._request("POST", "/api/vehicles/1/test", data={"level": "1", "state": "on"})
            return invalid_level, invalid_state, valid

        invalid_level, invalid_state, valid = asyncio.run(run())

        self.assertEqual(invalid_level.status_code, 400)
        self.assertEqual(invalid_state.status_code, 400)
        self.assertEqual(valid.status_code, 200)
        self.assertIn("hx-post", valid.text)

    def test_vehicle_and_driver_payloads_reject_invalid_identifiers(self):
        async def run():
            invalid_vehicle = await self._request(
                "POST",
                "/api/vehicles",
                json={
                    "plate_number": "../59A-12345",
                    "name": "Xe Loi",
                    "device_id": "jetson id with spaces",
                    "manager_phone": "phone-number",
                },
            )
            invalid_driver = await self._request(
                "POST",
                "/api/drivers",
                json={
                    "name": "Tai Xe Loi",
                    "rfid_tag": "   ",
                    "phone": "not-a-phone",
                    "gender": "unknown",
                },
            )
            return invalid_vehicle, invalid_driver

        invalid_vehicle, invalid_driver = asyncio.run(run())

        self.assertEqual(invalid_vehicle.status_code, 422)
        self.assertEqual(invalid_driver.status_code, 422)

    def test_driver_ws_schema_accepts_rfid_tag_alias(self):
        from app.schemas import DriverData

        payload = DriverData(name="Tai xe A", rfid_tag="RFID-ALIAS")

        self.assertEqual(payload.rfid, "RFID-ALIAS")
        self.assertEqual(payload.name, "Tai xe A")

    def test_hardware_ws_schema_accepts_explicit_device_status_fields(self):
        from app.schemas import HardwareData

        payload = HardwareData(
            camera_ok=True,
            rfid_reader_ok=True,
            gps_uart_ok=True,
            gps_fix_ok=False,
            bluetooth_adapter_ok=True,
            bluetooth_speaker_connected=False,
            speaker_output_ok=True,
            websocket_ok=True,
            queue_pending=3,
            details={"gps": "NMEA seen but no fix"},
        )

        self.assertTrue(payload.camera_ok)
        self.assertTrue(payload.rfid_reader_ok)
        self.assertTrue(payload.gps_uart_ok)
        self.assertFalse(payload.gps_fix_ok)
        self.assertTrue(payload.bluetooth_adapter_ok)
        self.assertFalse(payload.bluetooth_speaker_connected)
        self.assertTrue(payload.speaker_output_ok)
        self.assertEqual(payload.queue_pending, 3)

    def test_ws_command_schema_accepts_monitoring_controls(self):
        from app.schemas import WsCommandOut

        connect = WsCommandOut(action="connect_monitoring").model_dump(exclude_none=True)
        disconnect = WsCommandOut(action="disconnect_monitoring").model_dump(exclude_none=True)

        self.assertEqual(connect["action"], "connect_monitoring")
        self.assertEqual(disconnect["action"], "disconnect_monitoring")

    def test_monitoring_endpoint_sends_connect_and_disconnect_commands(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {"jetson-nano-001": object()},
                clear=True,
            ):
                connect = await self._request(
                    "POST",
                    "/api/vehicles/1/monitoring",
                    data={"state": "connect"},
                )
                disconnect = await self._request(
                    "POST",
                    "/api/vehicles/1/monitoring",
                    data={"state": "disconnect"},
                )
            return connect, disconnect, send_command

        connect, disconnect, send_command = asyncio.run(run())

        self.assertEqual(connect.status_code, 200)
        self.assertEqual(disconnect.status_code, 200)
        sent_actions = [call.args[1]["action"] for call in send_command.await_args_list]
        self.assertEqual(sent_actions, ["connect_monitoring", "disconnect_monitoring"])

    def test_monitoring_endpoint_returns_json_for_connection_badge(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {"jetson-nano-001": object()},
                clear=True,
            ):
                connect = await self._request(
                    "POST",
                    "/api/vehicles/1/monitoring",
                    data={"state": "connect"},
                    headers={"Accept": "application/json"},
                )
            return connect, send_command

        response, send_command = asyncio.run(run())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "connect")
        self.assertEqual(response.json()["next_state"], "disconnect")
        self.assertEqual(response.json()["connection_status"], "online")
        self.assertEqual(response.json()["message"], "Da gui lenh ket noi giam sat")
        send_command.assert_awaited_once()

    def test_monitoring_endpoint_json_reports_offline_when_websocket_missing(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {},
                clear=True,
            ):
                response = await self._request(
                    "POST",
                    "/api/vehicles/1/monitoring",
                    data={"state": "connect"},
                    headers={"Accept": "application/json"},
                )
            return response, send_command

        response, send_command = asyncio.run(run())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["state"], "offline")
        self.assertEqual(response.json()["next_state"], "connect")
        self.assertEqual(response.json()["connection_status"], "offline")
        self.assertEqual(response.json()["message"], "Jetson dang offline, chua gui duoc lenh")
        send_command.assert_not_awaited()

    def test_ota_upload_rejects_path_traversal_filename(self):
        async def run():
            return await self._request(
                "POST",
                "/api/vehicles/1/update",
                files={"file": ("../evil.py", b"print('boom')", "text/x-python")},
            )

        response = asyncio.run(run())

        self.assertEqual(response.status_code, 400)
        self.assertIn("filename", response.json()["detail"].lower())

    def test_ota_upload_records_audit_log_and_sends_checksum(self):
        async def run():
            from unittest.mock import AsyncMock, patch

            with patch("app.ws.jetson_handler.manager.send_command", new=AsyncMock()) as send_command, patch.dict(
                "app.ws.jetson_handler.manager.active",
                {"jetson-nano-001": object()},
                clear=True,
            ):
                response = await self._request(
                    "POST",
                    "/api/vehicles/1/update",
                    files={"file": ("main.py", b"print('safe update')\n", "text/x-python")},
                )

            async with self.session_factory() as db:
                from sqlalchemy import select

                result = await db.execute(select(OtaAuditLog))
                audit_rows = result.scalars().all()
            return response, send_command, audit_rows

        response, send_command, audit_rows = asyncio.run(run())

        self.assertEqual(response.status_code, 200)
        send_command.assert_awaited_once()
        _, command = send_command.await_args.args
        self.assertEqual(command["action"], "update_software")
        self.assertEqual(command["filename"], "main.py")
        self.assertRegex(command["checksum"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(audit_rows), 1)
        self.assertEqual(audit_rows[0].filename, "main.py")
        self.assertEqual(audit_rows[0].status, "sent")


if __name__ == "__main__":
    unittest.main()
