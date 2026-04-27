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


def local_date_to_utc_bounds(
    date_from: str | None,
    date_to: str | None,
) -> tuple[datetime | None, datetime | None]:
    start_date = _parse_local_date(date_from)
    end_date = _parse_local_date(date_to)
    start_utc = _to_sqlite_utc_naive(_local_start_of_day(start_date)) if start_date else None
    end_utc = _to_sqlite_utc_naive(_local_start_of_day(end_date + timedelta(days=1))) if end_date else None
    return start_utc, end_utc
