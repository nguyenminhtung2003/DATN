import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect as sqlalchemy_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import get_current_user
from app.api import dashboard as dashboard_module
from app.core.event_bus import event_bus
from app.database import Base, get_db
from app.main import app
from app.models import AlertLevel, AlertType, Driver, DriverSession, SystemAlert, User, Vehicle
from app.ws.jetson_handler import manager


class DashboardRealtimeContextTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"dashboard_context_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.admin = User(username="admin", role="admin")
        self.device_id = "JETSON-CTX-001"
        self.original_active = dict(manager.active)
        self.original_last_seen = dict(manager.last_seen)
        self.original_vehicle_state = dict(event_bus._vehicle_state)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.admin
        asyncio.run(self._create_schema_and_seed())

    def tearDown(self):
        app.dependency_overrides.clear()
        manager.active = self.original_active
        manager.last_seen = self.original_last_seen
        event_bus._vehicle_state = self.original_vehicle_state
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _create_schema_and_seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(
                plate_number="59A-12345",
                name="Xe Demo 01",
                device_id=self.device_id,
                manager_phone="0901234567",
            )
            db.add(vehicle)
            await db.flush()
            db.add(SystemAlert(
                vehicle_id=vehicle.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_1,
                ear_value=0.22,
                mar_value=0.04,
                message="timezone alert",
                timestamp=datetime(2026, 4, 27, 17, 13, 30),
            ))
            await db.commit()

    async def _seed_active_session(self):
        async with self.session_factory() as db:
            vehicle_result = await db.execute(select(Vehicle).where(Vehicle.device_id == self.device_id))
            vehicle = vehicle_result.scalar_one()
            driver = Driver(
                name="Nguyen Van A",
                age=35,
                gender="Nam",
                phone="0909999999",
                rfid_tag="RFID-ACTIVE",
                face_image_path="/static/faces/driver-active.jpg",
                vehicle_id=vehicle.id,
            )
            db.add(driver)
            await db.flush()
            db.add(DriverSession(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                checkin_at=datetime(2026, 4, 28, 1, 2, 3, tzinfo=timezone.utc),
            ))
            await db.commit()

    async def _request(self, method, path, raise_app_exceptions=True, **kwargs):
        transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_dashboard_hides_technical_summary_chips(self):
        manager.active[self.device_id] = object()
        manager.last_seen[self.device_id] = datetime(2026, 4, 21, 1, 23, 45, tzinfo=timezone.utc)
        event_bus._vehicle_state[f"vehicle:{self.device_id}"] = {
            "hardware": {
                "queue_pending": 7,
                "camera_ok": True,
                "rfid_reader_ok": True,
                "gps_uart_ok": True,
                "gps_fix_ok": False,
                "bluetooth_adapter_ok": True,
                "bluetooth_speaker_connected": False,
                "speaker_output_ok": True,
            },
            "gps": {"lat": 10.762622, "lng": 106.660172, "speed": 38.5, "fix_ok": True},
        }

        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("Phiên giám sát", response.text)
        self.assertIn("Xác minh", response.text)
        self.assertIn("Thiết bị", response.text)
        self.assertIn("Cảnh báo gần đây", response.text)
        self.assertNotIn("Queue Chờ (Jetson)", response.text)
        self.assertNotIn('id="queue-pending-count"', response.text)
        self.assertNotIn('id="last-seen-text"', response.text)
        self.assertNotIn('id="gps-latest-summary"', response.text)
        self.assertIn('<button class="connection-badge"', response.text)
        self.assertIn('id="connection-status"', response.text)
        self.assertIn('data-connection-state="online"', response.text)
        self.assertIn('data-next-monitoring-state="connect"', response.text)
        hardware_section = response.text.split('<div class="hardware-grid" id="hardware-badges">', 1)[1].split("</section>", 1)[0]
        self.assertEqual(hardware_section.count('data-hw-key="'), 5)
        self.assertIn('data-hw-key="power"', hardware_section)
        self.assertIn('data-hw-key="rfid"', hardware_section)
        self.assertIn('data-hw-key="gps"', hardware_section)
        self.assertIn('data-hw-key="camera"', hardware_section)
        self.assertIn('data-hw-key="speaker"', hardware_section)
        self.assertIn("Nguồn", response.text)
        self.assertIn("Loa", hardware_section)
        self.assertNotIn("hw-copy", hardware_section)
        self.assertIn("status-dot", response.text)
        self.assertNotIn("WebSocket", response.text)
        self.assertNotIn("GPS UART", response.text)
        self.assertNotIn("GPS Fix", response.text)
        self.assertNotIn("BT Adapter", response.text)
        self.assertNotIn("Loa Bluetooth", response.text)
        self.assertNotIn("Audio Output", response.text)

    def test_dashboard_hides_ota_upload_controls(self):
        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/api/vehicles/1/update", response.text)
        self.assertNotIn('id="ota-file-input"', response.text)
        self.assertNotIn('id="btn-upload"', response.text)
        self.assertNotIn('id="upload-status"', response.text)
        self.assertIn('id="btn-test-1"', response.text)
        self.assertIn('id="btn-test-2"', response.text)
        self.assertIn('id="btn-test-3"', response.text)

    def test_dashboard_marks_connection_offline_when_websocket_is_not_active(self):
        event_bus._vehicle_state[f"vehicle:{self.device_id}"] = {
            "connection": {"status": "online", "device_id": self.device_id},
            "hardware": {
                "camera_ok": True,
                "rfid_reader_ok": True,
                "gps_uart_ok": True,
                "gps_fix_ok": True,
                "speaker_output_ok": True,
            },
        }

        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-connection-state="offline"', response.text)
        self.assertIn('data-next-monitoring-state="connect"', response.text)

    def test_dashboard_eager_loads_active_session_driver_for_template(self):
        asyncio.run(self._seed_active_session())

        async def run():
            captured_context = {}

            def fake_template_response(*args, **kwargs):
                captured_context.update(kwargs["context"])

                class Response:
                    status_code = 200

                return Response()

            async with self.session_factory() as db:
                with patch.object(dashboard_module.templates, "TemplateResponse", side_effect=fake_template_response):
                    response = await dashboard_module.dashboard_page(request=object(), user=self.admin, db=db)
            return response, captured_context

        response, context = asyncio.run(run())
        active_session = context["active_session"]

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(active_session)
        self.assertNotIn("driver", sqlalchemy_inspect(active_session).unloaded)
        self.assertEqual(active_session.driver.name, "Nguyen Van A")

    def test_dashboard_uses_eventsource_without_twenty_second_offline_watchdog(self):
        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("new EventSource", response.text)
        self.assertIn("handleRealtimeEvent('hardware'", response.text)
        self.assertIn("handleRealtimeEvent('connection'", response.text)
        self.assertNotIn("HEARTBEAT_TIMEOUT_MS", response.text)
        self.assertNotIn("lastHeartbeatAt", response.text)
        self.assertNotIn("sse:hardware", response.text)
        self.assertNotIn("updateConnectionStatus('offline')", response.text)
        self.assertIn("function formatVietnamDateTime", response.text)
        self.assertIn("timeZone: 'Asia/Ho_Chi_Minh'", response.text)
        self.assertNotIn("new Date(data.timestamp).toLocaleString('vi-VN')", response.text)

    def test_dashboard_alert_log_displays_vietnam_time(self):
        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("00:13:30 - 28/04/2026", response.text)
        self.assertNotIn("17:13:30", response.text)

    def test_dashboard_alert_log_is_capped_to_ten_latest_alerts(self):
        async def seed_many_alerts():
            async with self.session_factory() as db:
                vehicle_result = await db.execute(select(Vehicle).where(Vehicle.device_id == self.device_id))
                vehicle = vehicle_result.scalar_one()
                for index in range(12):
                    db.add(SystemAlert(
                        vehicle_id=vehicle.id,
                        alert_type=AlertType.DROWSINESS,
                        alert_level=AlertLevel.LEVEL_1,
                        ear_value=0.20,
                        mar_value=0.10,
                        message=f"alert cap {index:02d}",
                        timestamp=datetime(2026, 5, 6, 12, index, 0, tzinfo=timezone.utc),
                    ))
                await db.commit()

        asyncio.run(seed_many_alerts())

        response = asyncio.run(self._request("GET", "/"))
        alert_section = response.text.split('id="alert-section"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(alert_section.count('class="alert-row'), 10)
        self.assertIn("alert cap 11", alert_section)
        self.assertIn("alert cap 02", alert_section)
        self.assertNotIn("alert cap 01", alert_section)
        self.assertNotIn("alert cap 00", alert_section)
        self.assertIn('id="alert-count">10', alert_section.replace("\n", ""))

    def test_dashboard_realtime_alert_insert_trims_rows_to_ten(self):
        response = asyncio.run(self._request("GET", "/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("const ALERT_LOG_LIMIT = 10;", response.text)
        self.assertIn("function trimAlertRows()", response.text)
        self.assertIn("rows.slice(ALERT_LOG_LIMIT).forEach(row => row.remove());", response.text)
        self.assertIn("refreshAlertCount();", response.text)
