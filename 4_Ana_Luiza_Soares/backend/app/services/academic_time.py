from datetime import date, datetime
from zoneinfo import ZoneInfo

ACADEMIC_TIMEZONE = ZoneInfo("America/Sao_Paulo")
WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def local_today() -> date:
    return datetime.now(ACADEMIC_TIMEZONE).date()


def next_date_for_weekday(day: str, reference: date | None = None) -> date:
    current = reference or local_today()
    return current.fromordinal(current.toordinal() + (WEEKDAY_INDEX[day] - current.weekday()) % 7)
