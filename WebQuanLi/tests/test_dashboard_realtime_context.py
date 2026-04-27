import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timezone
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import get_current_user
from app.core.event_bus import event_bus
from app.database import Base, get_db
from app.main import app
from app.models import User, Vehicle
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
            db.add(
                Vehicle(
                    plate_number="59A-12345",
                    name="Xe Demo 01",
                    device_id=self.device_id,
                    manager_phone="0901234567",
                )
            )
            await db.commit()

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_dashboard_renders_cached_queue_gps_and_last_seen(self):
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
        self.assertIn("Queue Chờ (Jetson)", response.text)
        self.assertIn(">7<", response.text)
        self.assertIn("10.762622", response.text)
        self.assertIn("106.660172", response.text)
        self.assertIn("2026-04-21 01:23:45 UTC", response.text)
        self.assertIn('<button class="connection-badge"', response.text)
        self.assertIn('id="connection-status"', response.text)
        self.assertIn('data-connection-state="online"', response.text)
        self.assertIn('data-next-monitoring-state="disconnect"', response.text)
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
