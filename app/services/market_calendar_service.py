import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
CALENDAR_DIR = Path(__file__).resolve().parents[2] / "data" / "market_calendar"


@dataclass(frozen=True)
class BistCalendarCheck:
    date: str
    is_trading_day: bool
    reason: str
    calendar_warning: str | None = None


def configured_market_holidays() -> set[str]:
    return {value.strip() for value in settings.bist_market_holidays.split(",") if value.strip()}


def _calendar_path(year: int) -> Path:
    return CALENDAR_DIR / f"bist_holidays_{year}.json"


def _load_year_calendar(year: int) -> tuple[set[str], set[str], str | None]:
    path = _calendar_path(year)
    if not path.exists():
        return configured_market_holidays(), set(), f"calendar_missing:{year}"

    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    holidays = {value.strip() for value in payload.get("holidays", []) if value.strip()}
    half_days = {value.strip() for value in payload.get("half_days", []) if value.strip()}
    return holidays, half_days, None


def check_bist_trading_day(value: date | datetime | None = None) -> BistCalendarCheck:
    current = value or datetime.now(ISTANBUL_TZ)
    if isinstance(current, datetime):
        current_date = current.astimezone(ISTANBUL_TZ).date()
    else:
        current_date = current

    date_value = current_date.isoformat()
    if current_date.weekday() >= 5:
        return BistCalendarCheck(date=date_value, is_trading_day=False, reason="weekend")

    holidays, _half_days, warning = _load_year_calendar(current_date.year)
    if date_value in holidays:
        return BistCalendarCheck(date=date_value, is_trading_day=False, reason="holiday", calendar_warning=warning)
    return BistCalendarCheck(date=date_value, is_trading_day=True, reason="trading_day", calendar_warning=warning)


def is_bist_trading_day(value: date | datetime | None = None) -> bool:
    return check_bist_trading_day(value).is_trading_day
