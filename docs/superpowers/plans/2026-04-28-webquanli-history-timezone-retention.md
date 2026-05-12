# WebQuanLi History Timezone And Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix WebQuanLi history timestamps for Vietnam time, make `/history` usable for alert search/filter/pagination, add alert cleanup controls, enforce 7-day alert retention, and show driver check-in/check-out sessions on the History tab.

**Architecture:** Keep Version3 payloads unchanged: Version3 continues sending Unix timestamps and WebQuanLi continues storing UTC internally. Add a WebQuanLi history/time service that converts Vietnam-local filter dates to UTC query bounds and converts UTC database datetimes into display strings. Update the `/history` page to use query helpers, separate alert/session pagination, and admin-only delete actions without touching unrelated dashboard or Jetson runtime behavior.

**Tech Stack:** FastAPI, Jinja2 templates, SQLAlchemy async ORM, SQLite, pytest/unittest, httpx ASGI test client, standard library `datetime.timezone(timedelta(hours=7))`; no new runtime dependency.

---

## Current Code Findings

- `D:\DATN-testing1\Version3\main.py` sends `time.time()` for `alert`, `session_start`, and `session_end`. This is correct and should not change.
- `D:\DATN-testing1\WebQuanLi\app\services\jetson_session_service.py` converts incoming Unix timestamps with `datetime.fromtimestamp(timestamp, tz=timezone.utc)`. This is correct for storage.
- SQLite stores those datetimes as naive UTC strings. Example from current DB: `2026-04-27 17:13:30.471792`, which should display as `00:13:30 28/04/2026` in Vietnam.
- `D:\DATN-testing1\WebQuanLi\templates\history.html` currently renders `alert.timestamp.strftime(...)` directly, so it displays UTC as if it were local time.
- `D:\DATN-testing1\WebQuanLi\app\api\pages.py` parses `date_from` and `date_to` with `datetime.fromisoformat(...)` and compares those local date values directly against UTC database values.
- `/history` currently shows only alerts. `DriverSession` exists in `D:\DATN-testing1\WebQuanLi\app\models.py`, and `/api/vehicles/{vehicle_id}/sessions` exists, but the History page does not render check-in/check-out history.
- Existing pagination links are hand-built and only preserve some filters. Adding search/session pagination needs a query-string helper so page/filter buttons do not lose state.
- The current filter/page URL can become `/history?date_from=&date_to=&vehicle_id=&alert_type=`. Because `vehicle_id` is declared as `int = Query(None)`, FastAPI rejects the request before the page handler runs with `int_parsing`. Empty filter values must not be emitted in pagination URLs, and the endpoint must tolerate empty form/query input.

## Assumptions To Confirm Before Implementation

- The phrase "nut fix" is treated as "fix the existing filter/search/page buttons", not as a new standalone button named "Fix".
- "Canh bao duoc luu 7 ngay" applies to `SystemAlert` records. Driver sessions are displayed on `/history` but are not deleted automatically unless you explicitly request session retention too.
- Default `/history` alert list shows at most the newest 100 retained alerts. If any filter/search is active, the query can return older retained alerts beyond the newest 100, still paginated.
- The delete history button deletes alerts, not driver sessions. It must be admin-only and require confirmation in the UI.

---

## File Structure

- Create: `D:\DATN-testing1\WebQuanLi\app\services\time_service.py`
  - Own Vietnam timezone conversion, display formatting, and date range parsing.
- Create: `D:\DATN-testing1\WebQuanLi\app\services\history_service.py`
  - Own alert/session history queries, 100-alert default cap, search/filter behavior, and alert retention/delete operations.
- Modify: `D:\DATN-testing1\WebQuanLi\app\api\pages.py`
  - Delegate `/history` to `history_service`.
  - Add `q`, `alert_page`, `session_page`, and delete-history POST endpoint.
- Modify: `D:\DATN-testing1\WebQuanLi\app\api\alerts.py`
  - Reuse the same local-date parsing for API filtering so `/api/alerts` matches `/history`.
- Modify: `D:\DATN-testing1\WebQuanLi\app\main.py`
  - Run old-alert retention cleanup at startup.
- Modify: `D:\DATN-testing1\WebQuanLi\templates\history.html`
  - Add search input, admin delete button, fixed pagination URLs, and sessions table.
- Modify: `D:\DATN-testing1\WebQuanLi\templates\partials\alert_log.html`
  - Render server-side dashboard recent alert timestamps in Vietnam time.
- Modify: `D:\DATN-testing1\WebQuanLi\templates\dashboard.html`
  - Use explicit `Asia/Ho_Chi_Minh` / `vi-VN` formatting in realtime JS helpers.
- Modify: `D:\DATN-testing1\WebQuanLi\static\css\style.css`
  - Add small styles for history actions, session status badges, and delete button if existing styles are insufficient.
- Test: `D:\DATN-testing1\WebQuanLi\tests\test_time_service.py`
- Test: `D:\DATN-testing1\WebQuanLi\tests\test_history_service.py`
- Test: `D:\DATN-testing1\WebQuanLi\tests\test_history_page.py`
- Test: `D:\DATN-testing1\WebQuanLi\tests\test_alerts_api_history_filters.py`

---

## Task 0: Safety Baseline

**Files:**
- Read only: `D:\DATN-testing1`

- [ ] **Step 1: Confirm current branch and dirty files**

Run:

```powershell
git status --short --branch
```

Expected: current workspace state is visible. Do not overwrite unrelated user changes.

- [ ] **Step 2: Create a focused implementation branch**

Run:

```powershell
git switch -c codex/webquanli-history-timezone-retention
```

Expected: branch created from current `main`.

- [ ] **Step 3: Run the current relevant WebQuanLi tests**

Run in `D:\DATN-testing1\WebQuanLi`:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_ws_session_flow.py tests/test_api_validation_contract.py tests/test_dashboard_realtime_context.py -q
```

Expected: existing tests pass before changing behavior.

---

## Task 1: Vietnam Time Service

**Files:**
- Create: `D:\DATN-testing1\WebQuanLi\app\services\time_service.py`
- Create: `D:\DATN-testing1\WebQuanLi\tests\test_time_service.py`

- [ ] **Step 1: Write failing tests for UTC-to-Vietnam display and local date bounds**

Create `tests/test_time_service.py`:

```python
from datetime import datetime, timezone

from app.services.time_service import (
    format_vn_datetime,
    local_date_to_utc_bounds,
    to_vn_datetime,
)


def test_format_vn_datetime_converts_naive_utc_from_sqlite():
    stored = datetime(2026, 4, 27, 17, 13, 30, 471792)

    assert format_vn_datetime(stored) == "00:13:30 - 28/04/2026"


def test_to_vn_datetime_keeps_aware_utc_correct():
    stored = datetime(2026, 4, 27, 17, 13, 30, tzinfo=timezone.utc)

    vn_dt = to_vn_datetime(stored)

    assert vn_dt.hour == 0
    assert vn_dt.day == 28
    assert vn_dt.utcoffset().total_seconds() == 7 * 3600


def test_local_date_to_utc_bounds_for_single_vietnam_day():
    start_utc, end_utc = local_date_to_utc_bounds("2026-04-28", "2026-04-28")

    assert start_utc == datetime(2026, 4, 27, 17, 0, 0)
    assert end_utc == datetime(2026, 4, 28, 17, 0, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_time_service.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'app.services.time_service'`.

- [ ] **Step 3: Implement `time_service.py`**

Create `app/services/time_service.py`:

```python
from datetime import date, datetime, time, timedelta, timezone


VN_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
DISPLAY_FORMAT = "%H:%M:%S - %d/%m/%Y"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_vn_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _as_utc(value).astimezone(VN_TZ)


def format_vn_datetime(value: datetime | None, empty: str = "N/A") -> str:
    local_value = to_vn_datetime(value)
    if local_value is None:
        return empty
    return local_value.strftime(DISPLAY_FORMAT)


def _parse_local_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _local_start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=VN_TZ)


def _to_sqlite_utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def local_date_to_utc_bounds(date_from: str | None, date_to: str | None) -> tuple[datetime | None, datetime | None]:
    start_date = _parse_local_date(date_from)
    end_date = _parse_local_date(date_to)
    start_utc = _to_sqlite_utc_naive(_local_start_of_day(start_date)) if start_date else None
    end_utc = _to_sqlite_utc_naive(_local_start_of_day(end_date + timedelta(days=1))) if end_date else None
    return start_utc, end_utc
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_time_service.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add WebQuanLi/app/services/time_service.py WebQuanLi/tests/test_time_service.py
git commit -m "feat: add vietnam time helpers"
```

---

## Task 2: History Query Service

**Files:**
- Create: `D:\DATN-testing1\WebQuanLi\app\services\history_service.py`
- Create: `D:\DATN-testing1\WebQuanLi\tests\test_history_service.py`

- [ ] **Step 1: Write failing tests for cap/search/retention/session rows**

Create `tests/test_history_service.py`:

```python
import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.models import AlertLevel, AlertType, Driver, DriverSession, SystemAlert, Vehicle


class HistoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"history_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.ids = asyncio.run(self._seed())

    def tearDown(self):
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

            for idx in range(130):
                db.add(SystemAlert(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    alert_type=AlertType.DROWSINESS,
                    alert_level=AlertLevel.LEVEL_1,
                    message=f"alert searchable-{idx}",
                    timestamp=datetime(2026, 4, 27, 17, 0, 0) - timedelta(minutes=idx),
                ))

            db.add(SystemAlert(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_2,
                message="older than retention",
                timestamp=datetime(2026, 4, 18, 17, 0, 0),
            ))
            db.add(DriverSession(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                checkin_at=datetime(2026, 4, 27, 16, 0, 0),
                checkout_at=datetime(2026, 4, 27, 17, 0, 0),
            ))
            await db.commit()
            return {"vehicle_id": vehicle.id}

    def test_default_alert_history_is_capped_to_newest_100(self):
        async def run():
            from app.services.history_service import list_alert_history
            async with self.session_factory() as db:
                return await list_alert_history(db, now_utc=datetime(2026, 4, 28, 0, 0, 0))

        history = asyncio.run(run())

        self.assertEqual(history["total"], 100)
        self.assertEqual(history["retained_total"], 130)
        self.assertEqual(len(history["items"]), 25)
        self.assertEqual(history["items"][0]["display_time"], "00:00:00 - 28/04/2026")

    def test_search_finds_retained_alert_beyond_default_100_cap(self):
        async def run():
            from app.services.history_service import list_alert_history
            async with self.session_factory() as db:
                return await list_alert_history(db, q="searchable-120", now_utc=datetime(2026, 4, 28, 0, 0, 0))

        history = asyncio.run(run())

        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["message"], "alert searchable-120")

    def test_purge_old_alerts_deletes_records_older_than_7_days(self):
        async def run():
            from app.services.history_service import purge_old_alerts
            async with self.session_factory() as db:
                deleted = await purge_old_alerts(db, now_utc=datetime(2026, 4, 28, 0, 0, 0))
                remaining = (await db.execute(select(SystemAlert))).scalars().all()
                return deleted, remaining

        deleted, remaining = asyncio.run(run())

        self.assertEqual(deleted, 1)
        self.assertEqual(len(remaining), 130)

    def test_session_history_returns_checkin_checkout_and_duration(self):
        async def run():
            from app.services.history_service import list_session_history
            async with self.session_factory() as db:
                return await list_session_history(db, now_utc=datetime(2026, 4, 28, 0, 0, 0))

        history = asyncio.run(run())

        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["driver_name"], "Nguyen Van A")
        self.assertEqual(history["items"][0]["checkin_display"], "23:00:00 - 27/04/2026")
        self.assertEqual(history["items"][0]["checkout_display"], "00:00:00 - 28/04/2026")
        self.assertEqual(history["items"][0]["duration_text"], "01:00:00")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_service.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'app.services.history_service'`.

- [ ] **Step 3: Implement `history_service.py`**

Create service with these public functions and constants:

```python
ALERT_RETENTION_DAYS = 7
DEFAULT_ALERT_DISPLAY_LIMIT = 100
DEFAULT_PER_PAGE = 25

async def purge_old_alerts(db, now_utc=None) -> int: ...
async def delete_alert_history(db, filters) -> int: ...
async def list_alert_history(db, *, date_from=None, date_to=None, vehicle_id=None, alert_type=None, q=None, page=1, per_page=25, now_utc=None) -> dict: ...
async def list_session_history(db, *, date_from=None, date_to=None, vehicle_id=None, q=None, page=1, per_page=25, now_utc=None) -> dict: ...
```

Implementation requirements:

- Treat DB datetimes as UTC-naive when comparing.
- Retention cutoff is `now_utc - timedelta(days=7)`.
- For default alert list with no filters and no `q`, cap count and paging to newest 100 retained alerts.
- For filters/search, search the full retained 7-day alert set.
- `q` should search alert message, alert type, alert level, vehicle plate/name, and driver name using `ilike`.
- Date filters are local Vietnam dates converted by `local_date_to_utc_bounds`.
- `date_to` must be exclusive next-day bound, not midnight of the same day.
- Return dictionaries suitable for templates, including `display_time`, `vehicle_label`, `driver_name`, and pagination metadata.
- Session rows must include `checkin_display`, `checkout_display`, `duration_text`, `is_active`, `vehicle_label`, and `driver_name`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_service.py tests/test_time_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add WebQuanLi/app/services/history_service.py WebQuanLi/tests/test_history_service.py
git commit -m "feat: add history query service"
```

---

## Task 3: History Page Endpoint, Delete Action, And Pagination URLs

**Files:**
- Modify: `D:\DATN-testing1\WebQuanLi\app\api\pages.py`
- Create: `D:\DATN-testing1\WebQuanLi\tests\test_history_page.py`

- [ ] **Step 1: Write failing page tests**

Create `tests/test_history_page.py`:

```python
import asyncio
import sys
import uuid
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import check_admin, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import AlertLevel, AlertType, Driver, DriverSession, SystemAlert, User, Vehicle


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
            for idx in range(30):
                db.add(SystemAlert(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    alert_type=AlertType.DROWSINESS,
                    alert_level=AlertLevel.LEVEL_1,
                    message=f"alert {idx}",
                    timestamp=datetime(2026, 4, 27, 17, 0, 0) - timedelta(minutes=idx),
                ))
            db.add(DriverSession(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                checkin_at=datetime(2026, 4, 27, 16, 0, 0),
                checkout_at=datetime(2026, 4, 27, 17, 0, 0),
            ))
            await db.commit()
            return {"vehicle_id": vehicle.id}

    async def _request(self, method, path, **kwargs):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def test_history_page_displays_vietnam_time_search_and_sessions(self):
        response = asyncio.run(self._request("GET", "/history?q=alert"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("00:00:00 - 28/04/2026", html)
        self.assertIn('name="q"', html)
        self.assertIn("Ca lam viec", html)
        self.assertIn("Nguyen Van A", html)
        self.assertIn("23:00:00 - 27/04/2026", html)

    def test_history_pagination_preserves_filters_and_uses_alert_page(self):
        response = asyncio.run(self._request("GET", "/history?q=alert&date_from=2026-04-28&alert_page=1"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("alert_page=2", response.text)
        self.assertIn("q=alert", response.text)
        self.assertIn("date_from=2026-04-28", response.text)
        self.assertNotIn("vehicle_id=", response.text)
        self.assertNotIn("alert_type=", response.text)

    def test_history_ignores_empty_filter_query_values_from_old_links(self):
        response = asyncio.run(self._request("GET", "/history?date_from=&date_to=&vehicle_id=&alert_type="))

        self.assertEqual(response.status_code, 200)
        self.assertIn("00:00:00 - 28/04/2026", response.text)

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
        self.assertEqual(session_count, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_page.py -q
```

Expected: fails because `/history` does not include search/session/delete behavior yet.

- [ ] **Step 3: Modify `app/api/pages.py`**

Implementation requirements:

- Import `Form`, `RedirectResponse`, `check_admin`, and history service helpers.
- Change `/history` params from one `page` to:
  - `q: str | None`
  - `alert_page: int = Query(1, ge=1)`
  - `session_page: int = Query(1, ge=1)`
- Call `list_alert_history(...)` and `list_session_history(...)`.
- Build pagination URLs with a helper based on current query params:

```python
from urllib.parse import urlencode


def _history_url(base_filters: dict, **updates) -> str:
    params = dict(base_filters)
    params.update(updates)
    params = {key: value for key, value in params.items() if value not in (None, "", 0)}
    return "/history?" + urlencode(params)
```

- Add admin-only endpoint:

```python
@router.post("/history/alerts/delete")
async def delete_history_alerts(
    request: Request,
    date_from: str | None = Form(None),
    date_to: str | None = Form(None),
    vehicle_id: int | None = Form(None),
    alert_type: str | None = Form(None),
    q: str | None = Form(None),
    user: User = Depends(check_admin),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_alert_history(db, {
        "date_from": date_from,
        "date_to": date_to,
        "vehicle_id": vehicle_id,
        "alert_type": alert_type,
        "q": q,
    })
    redirect_url = _history_url({
        "date_from": date_from,
        "date_to": date_to,
        "vehicle_id": vehicle_id,
        "alert_type": alert_type,
        "q": q,
    }, deleted=deleted)
    return RedirectResponse(redirect_url, status_code=303)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_page.py tests/test_history_service.py tests/test_time_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add WebQuanLi/app/api/pages.py WebQuanLi/tests/test_history_page.py
git commit -m "feat: improve history page queries"
```

---

## Task 4: History Template And Dashboard Timestamp Display

**Files:**
- Modify: `D:\DATN-testing1\WebQuanLi\templates\history.html`
- Modify: `D:\DATN-testing1\WebQuanLi\templates\partials\alert_log.html`
- Modify: `D:\DATN-testing1\WebQuanLi\templates\dashboard.html`
- Modify: `D:\DATN-testing1\WebQuanLi\static\css\style.css`

- [ ] **Step 1: Write failing template assertions**

Add these assertions to `tests/test_history_page.py`:

```python
    def test_history_page_has_delete_button_and_retention_hint(self):
        response = asyncio.run(self._request("GET", "/history"))

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("/history/alerts/delete", html)
        self.assertIn("7 ngay", html)
        self.assertIn("toi da 100", html)
        self.assertIn("onclick=\"return confirm", html)
```

Create `tests/test_dashboard_time_display.py`:

```python
from datetime import datetime

from app.services.time_service import format_vn_datetime


def test_dashboard_alert_partial_should_use_format_vn_datetime_contract():
    assert format_vn_datetime(datetime(2026, 4, 27, 17, 13, 30)) == "00:13:30 - 28/04/2026"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_page.py tests/test_dashboard_time_display.py -q
```

Expected: history template assertions fail until the UI is updated.

- [ ] **Step 3: Update `history.html`**

Implementation requirements:

- Add search input:

```html
<input type="search" id="q" name="q" value="{{ filters.q }}" placeholder="Tim theo tai xe, xe, noi dung canh bao">
```

- Keep date/vehicle/type filters and submit button.
- Add reset link to `/history`.
- Add admin-only delete form:

```html
{% if user.role == 'admin' %}
<form method="POST" action="/history/alerts/delete" class="history-delete-form">
    <input type="hidden" name="date_from" value="{{ filters.date_from }}">
    <input type="hidden" name="date_to" value="{{ filters.date_to }}">
    <input type="hidden" name="vehicle_id" value="{{ filters.vehicle_id }}">
    <input type="hidden" name="alert_type" value="{{ filters.alert_type }}">
    <input type="hidden" name="q" value="{{ filters.q }}">
    <button type="submit" class="btn btn-danger" onclick="return confirm('Xoa lich su canh bao dang loc? Ca lam viec se duoc giu lai.');">
        Xoa lich su canh bao
    </button>
</form>
{% endif %}
```

- Replace raw ORM alert fields with service view-model fields:
  - `alert.display_time`
  - `alert.alert_type`
  - `alert.alert_level`
  - `alert.ear_text`
  - `alert.mar_text`
  - `alert.message`
- Add text explaining default limit:

```html
<p class="history-note">Mac dinh hien thi toi da 100 canh bao moi nhat trong 7 ngay. Dung bo loc/tim kiem de tim canh bao cu hon trong khoang 7 ngay.</p>
```

- Add second table for sessions:
  - ID
  - driver
  - vehicle
  - check-in
  - check-out
  - duration
  - status
- Use separate alert pagination URLs and session pagination URLs from context.

- [ ] **Step 4: Update dashboard alert timestamps**

Implementation requirements:

- In `app/api/dashboard.py`, pass `format_vn_datetime` or view-model formatted strings for `recent_alerts`, then update `templates/partials/alert_log.html` to render Vietnam time.
- In `templates/dashboard.html`, centralize realtime JS formatting:

```javascript
function formatVietnamDateTime(value) {
    if (!value) return 'N/A';
    return new Date(value).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' });
}
```

- Replace realtime `new Date(...).toLocaleString('vi-VN')` calls with `formatVietnamDateTime(...)`.

- [ ] **Step 5: Run tests**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_page.py tests/test_dashboard_time_display.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add WebQuanLi/templates/history.html WebQuanLi/templates/partials/alert_log.html WebQuanLi/templates/dashboard.html WebQuanLi/static/css/style.css WebQuanLi/tests/test_history_page.py WebQuanLi/tests/test_dashboard_time_display.py
git commit -m "feat: update history and alert time UI"
```

---

## Task 5: `/api/alerts` Filter Consistency

**Files:**
- Modify: `D:\DATN-testing1\WebQuanLi\app\api\alerts.py`
- Create: `D:\DATN-testing1\WebQuanLi\tests\test_alerts_api_history_filters.py`

- [ ] **Step 1: Write failing API filter tests**

Create `tests/test_alerts_api_history_filters.py`:

```python
import asyncio
import sys
import uuid
import unittest
from datetime import datetime
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import AlertLevel, AlertType, SystemAlert, User, Vehicle


class AlertsApiHistoryFiltersTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"alerts_api_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: User(username="admin", role="admin")
        asyncio.run(self._seed())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _seed(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            vehicle = Vehicle(plate_number="59A-12345", name="Xe Demo 01", device_id="JETSON-001")
            db.add(vehicle)
            await db.flush()
            db.add(SystemAlert(
                vehicle_id=vehicle.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_1,
                message="midnight vietnam",
                timestamp=datetime(2026, 4, 27, 17, 30, 0),
            ))
            db.add(SystemAlert(
                vehicle_id=vehicle.id,
                alert_type=AlertType.DROWSINESS,
                alert_level=AlertLevel.LEVEL_1,
                message="previous vietnam day",
                timestamp=datetime(2026, 4, 27, 16, 30, 0),
            ))
            await db.commit()

    async def _get(self, path):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)

    def test_api_alerts_date_filter_uses_vietnam_day_bounds(self):
        response = asyncio.run(self._get("/api/alerts?date_from=2026-04-28&date_to=2026-04-28"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["message"], "midnight vietnam")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_alerts_api_history_filters.py -q
```

Expected: fails because `/api/alerts` currently compares local date strings directly as UTC-naive values.

- [ ] **Step 3: Update `app/api/alerts.py`**

Implementation requirements:

- Import and use `local_date_to_utc_bounds`.
- Use `>= start_utc` and `< end_utc` for date filters.
- Keep existing response shape unchanged for compatibility.
- Do not add retention cap to `/api/alerts` unless tests or UI need it; this task is only filter correctness.

- [ ] **Step 4: Run tests**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_alerts_api_history_filters.py tests/test_api_validation_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add WebQuanLi/app/api/alerts.py WebQuanLi/tests/test_alerts_api_history_filters.py
git commit -m "fix: use vietnam date bounds for alert api"
```

---

## Task 6: Startup Retention Cleanup

**Files:**
- Modify: `D:\DATN-testing1\WebQuanLi\app\main.py`
- Create or modify: `D:\DATN-testing1\WebQuanLi\tests\test_history_retention_startup.py`

- [ ] **Step 1: Write failing startup-retention unit test**

Create `tests/test_history_retention_startup.py`:

```python
import inspect

import app.main


def test_lifespan_imports_history_retention_cleanup():
    source = inspect.getsource(app.main.lifespan)

    assert "purge_old_alerts" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_retention_startup.py -q
```

Expected: fails because startup does not call `purge_old_alerts`.

- [ ] **Step 3: Update lifespan**

Modify `app/main.py` so startup runs retention after `init_db()`:

```python
from app.database import async_session_factory, init_db
from app.services.history_service import purge_old_alerts


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting WebQuanLi - Drowsiness Warning System")
    await init_db()
    async with async_session_factory() as db:
        deleted = await purge_old_alerts(db)
        if deleted:
            logger.info("Purged %s old alert history records", deleted)
    logger.info("Database initialized")
    yield
    logger.info("Shutting down")
```

Keep existing logging style as much as possible; the snippet shows behavior, not a request to rewrite unrelated strings.

- [ ] **Step 4: Run test**

Run:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_history_retention_startup.py tests/test_history_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add WebQuanLi/app/main.py WebQuanLi/tests/test_history_retention_startup.py
git commit -m "chore: purge old alert history on startup"
```

---

## Task 7: Full Verification

**Files:**
- Read only unless failures expose a focused bug.

- [ ] **Step 1: Run focused WebQuanLi suite**

Run in `D:\DATN-testing1\WebQuanLi`:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_time_service.py tests/test_history_service.py tests/test_history_page.py tests/test_alerts_api_history_filters.py tests/test_history_retention_startup.py tests/test_ws_session_flow.py tests/test_websocket_contract_fixtures.py tests/test_api_validation_contract.py tests/test_dashboard_realtime_context.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Version3 contract tests to confirm no payload break**

Run in `D:\DATN-testing1\Version3`:

```powershell
$env:PYTHONPATH='C:\Users\Tung\AppData\Roaming\Python\Python314\site-packages'
python -m pytest tests/test_webquanli_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Manual browser verification**

Run WebQuanLi:

```powershell
cd D:\DATN-testing1\WebQuanLi
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/history
```

Verify:

- Alert timestamps display Vietnam time. A stored UTC `2026-04-27 17:13:30` displays as `00:13:30 - 28/04/2026`.
- Default alert list is limited to newest 100 retained alerts.
- Date filter for `2026-04-28` includes alerts from Vietnam local day `2026-04-28 00:00:00` through before `2026-04-29 00:00:00`.
- Search finds retained alerts beyond the default newest 100.
- Pagination buttons preserve `q`, date range, vehicle, and alert type.
- Session history table shows driver, vehicle, check-in, check-out, duration, and active/ended status.
- Delete history button asks for confirmation and deletes alert rows matching current filters while keeping driver sessions.

- [ ] **Step 4: Commit final docs if needed**

If manual verification adds notes, update docs and commit:

```powershell
git add docs/superpowers/plans/2026-04-28-webquanli-history-timezone-retention.md
git commit -m "docs: plan webquanli history cleanup"
```

---

## Risks And Non-Goals

- This plan does not change Version3 timestamp payloads.
- This plan does not delete driver sessions.
- This plan does not change face verification, RFID, GPS, or adaptive EAR behavior.
- This plan does not fix mojibake/encoding text across templates unless text touched by this task is already being edited.
- If "nut fix" means a separate "Fix timestamps" button, pause before implementation and revise this plan; current design fixes display/filter logic without mutating timestamps already stored in DB.

## Self-Review

- Spec coverage: timezone display, 7-day alert retention, default 100-alert cap, search beyond the cap, delete alert history, session check-in/check-out history, pagination/filter fixes, and cross-project compatibility are covered.
- Placeholder scan: no `TBD`, no incomplete task, no vague "add tests" step without concrete test examples.
- Type consistency: public helper names are consistent across tasks: `format_vn_datetime`, `local_date_to_utc_bounds`, `list_alert_history`, `list_session_history`, `purge_old_alerts`, `delete_alert_history`.
