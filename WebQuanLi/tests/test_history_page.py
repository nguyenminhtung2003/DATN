import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import AlertLevel, AlertType, Driver, DriverSession, HardwareIncident, SystemAlert, User, Vehicle
from app.services.time_service import format_vn_datetime, to_vn_datetime


class HistoryPageTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"history_page_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        self.admin = User(username="admin", role="admin")
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.admin
        app.dependency_overrides[check_admin] = lambda: self.admin
        self.latest_alert_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(hours=1)
        self.session_checkin_at = self.latest_alert_at - timedelta(hours=1)
        self.history_date_from = to_vn_datetime(self.latest_alert_at).date().isoformat()
        self.ids = asyncio.run(self._seed())

    def tearDown(self):
        app.dependency_overrides.clear()
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
            for idx in reversed(range(30)):
                message = f"alert {idx}"
                if idx == 0:
                    message = "AI=DROWSY confidence=0.98 reason=Eyes closed for 3.0s; PERCLOS 0.55 perclos=0.781"
                db.add(SystemAlert(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    alert_type=AlertType.DROWSINESS,
                    alert_level=AlertLevel.LEVEL_1,
                    message=message,
                    timestamp=self.latest_alert_at - timedelta(minutes=idx),
                ))
            for idx in reversed(range(12)):
                db.add(DriverSession(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    checkin_at=self.session_checkin_at - timedelta(hours=idx),
                    checkout_at=self.latest_alert_at - timedelta(hours=idx),
                ))
            db.add(HardwareIncident(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                device_key="rfid",
                severity="critical",
                reason="RFID reader mất kết nối",
                first_seen_at=self.latest_alert_at - timedelta(minutes=10),
                last_seen_at=self.latest_alert_at - timedelta(minutes=8),
                resolved_at=self.latest_alert_at - timedelta(minutes=7),
                admin_telegram_status="sent",
                driver_telegram_status="sent",
            ))
            db.add(HardwareIncident(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                device_key="gps",
                severity="warning",
                reason="GPS mất tín hiệu module",
                first_seen_at=self.latest_alert_at - timedelta(minutes=5),
                last_seen_at=self.latest_alert_at - timedelta(minutes=1),
                resolved_at=self.latest_alert_at,
                admin_telegram_status="sent",
                driver_telegram_status="sent",
            ))
            for idx in range(10):
                db.add(HardwareIncident(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    device_key="rfid",
                    severity="critical",
                    reason=f"RFID incident extra {idx}",
                    first_seen_at=self.latest_alert_at - timedelta(minutes=20 + idx),
                    last_seen_at=self.latest_alert_at - timedelta(minutes=19 + idx),
                    resolved_at=self.latest_alert_at - timedelta(minutes=18 + idx),
                    admin_telegram_status="sent",
                    driver_telegram_status="sent",
                ))
            await db.commit()
            return {"vehicle_id": vehicle.id}

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def _history_section(self, html: str, heading: str) -> str:
        return html.split(f'<h2 class="panel-title">{heading}', 1)[1]

    def test_history_page_displays_vietnam_time_search_and_sessions(self):
        response = asyncio.run(self._request("GET", "/history"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn(format_vn_datetime(self.latest_alert_at), html)
        self.assertIn('name="q"', html)
        self.assertIn("Ca làm việc", html)
        self.assertIn("Nguyen Van A", html)
        self.assertIn(format_vn_datetime(self.session_checkin_at), html)
        self.assertIn("/history/alerts/delete", html)
        self.assertNotIn("Mặc định hiển thị tối đa 100 cảnh báo mới nhất trong 7 ngày", html)
        self.assertNotIn("Mac dinh hien thi toi da 100 canh bao moi nhat trong 7 ngay", html)
        self.assertIn("return confirm", html)
        self.assertIn("Lịch sử cảnh báo và ca làm việc", html)
        self.assertIn("Bộ lọc", html)
        self.assertIn("Nhật ký cảnh báo", html)
        self.assertIn("Lịch sử sự cố thiết bị", html)
        self.assertIn("GPS mất tín hiệu module", html)
        self.assertIn("Đã khôi phục", html)
        filter_form = html.split('id="history-filter"', 1)[1].split("</form>", 1)[0]
        self.assertLess(filter_form.index('id="btn-reset"'), filter_form.index('id="btn-delete-history"'))

    def test_history_tables_number_rows_by_visible_order_not_database_id(self):
        response = asyncio.run(self._request("GET", "/history"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        alert_section = self._history_section(html, "Nhật ký cảnh báo").split("Lịch sử sự cố thiết bị", 1)[0]
        incident_section = self._history_section(html, "Lịch sử sự cố thiết bị").split("Ca làm việc", 1)[0]
        session_section = self._history_section(html, "Ca làm việc")

        alert_first_row = alert_section.split("<tbody>", 1)[1].split("</tr>", 1)[0]
        incident_first_row = incident_section.split("<tbody>", 1)[1].split("</tr>", 1)[0]
        session_first_row = session_section.split("<tbody>", 1)[1].split("</tr>", 1)[0]

        self.assertEqual(alert_section.count('<td data-label="#">'), 10)
        self.assertEqual(incident_section.count('<td data-label="#">'), 10)
        self.assertEqual(session_section.count('<td data-label="#">'), 10)
        self.assertIn('<td data-label="#">1</td>', alert_first_row)
        self.assertIn("AI=DROWSY | conf=0.98 | PERCLOS=0.781", alert_first_row)
        self.assertNotIn("reason=Eyes closed", alert_first_row)
        self.assertNotIn('<td data-label="#">30</td>', alert_first_row)
        self.assertIn('<td data-label="#">1</td>', incident_first_row)
        self.assertIn("GPS mất tín hiệu module", incident_first_row)
        self.assertNotIn('<td data-label="#">2</td>', incident_first_row)
        self.assertIn('<td data-label="#">1</td>', session_first_row)
        self.assertIn(format_vn_datetime(self.session_checkin_at), session_first_row)
        self.assertNotIn('<td data-label="#">2</td>', session_first_row)

    def test_history_pagination_preserves_filters_and_uses_alert_page(self):
        response = asyncio.run(self._request("GET", f"/history?q=alert&date_from={self.history_date_from}&alert_page=1"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("alert_page=2", response.text)
        self.assertIn("q=alert", response.text)
        self.assertIn(f"date_from={self.history_date_from}", response.text)
        self.assertNotIn("vehicle_id=", response.text)
        self.assertNotIn("alert_type=", response.text)

    def test_alert_history_row_numbers_continue_across_pages(self):
        response = asyncio.run(self._request("GET", f"/history?q=alert&date_from={self.history_date_from}&alert_page=2"))

        self.assertEqual(response.status_code, 200)
        alert_section = self._history_section(response.text, "Nhật ký cảnh báo").split("Lịch sử sự cố thiết bị", 1)[0]
        alert_first_row = alert_section.split("<tbody>", 1)[1].split("</tr>", 1)[0]

        self.assertIn('<td data-label="#">11</td>', alert_first_row)
        self.assertIn("alert 11", alert_first_row)

    def test_history_ignores_empty_filter_query_values_from_old_links(self):
        response = asyncio.run(self._request("GET", "/history?date_from=&date_to=&vehicle_id=&alert_type="))

        self.assertEqual(response.status_code, 200)
        self.assertIn(format_vn_datetime(self.latest_alert_at), response.text)

    def test_admin_can_delete_filtered_alert_history_without_deleting_sessions(self):
        response = asyncio.run(self._request("POST", "/history/alerts/delete", data={"q": "alert 29"}))

        self.assertEqual(response.status_code, 303)

        async def count_rows():
            async with self.session_factory() as db:
                alerts = (await db.execute(select(SystemAlert))).scalars().all()
                sessions = (await db.execute(select(DriverSession))).scalars().all()
                return len(alerts), len(sessions)

        alert_count, session_count = asyncio.run(count_rows())
        self.assertEqual(alert_count, 29)
        self.assertEqual(session_count, 12)


if __name__ == "__main__":
    unittest.main()
