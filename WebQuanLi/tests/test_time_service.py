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
