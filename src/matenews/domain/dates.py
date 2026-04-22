from __future__ import annotations

from datetime import datetime
from datetime import timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


try:
    ARGENTINA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
except ZoneInfoNotFoundError:
    ARGENTINA_TZ = timezone(timedelta(hours=-3), name="America/Argentina/Buenos_Aires")

DAY_NAMES = {
    0: "Lunes",
    1: "Martes",
    2: "Miercoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sabado",
    6: "Domingo",
}

DAY_CODES = {
    0: "Lu",
    1: "Ma",
    2: "Mi",
    3: "Ju",
    4: "Vi",
    5: "Sa",
    6: "Do",
}

MONTH_NAMES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def argentina_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(ARGENTINA_TZ)
    return now.astimezone(ARGENTINA_TZ)


def short_day_code(now: datetime | None = None) -> str:
    current = argentina_now(now)
    return DAY_CODES[current.weekday()]


def file_day_name(now: datetime | None = None) -> str:
    current = argentina_now(now)
    return DAY_NAMES[current.weekday()]


def file_date_name(now: datetime | None = None) -> str:
    current = argentina_now(now)
    return f"{current:%Y-%m-%d}-{file_day_name(current)}"


def frontend_date(now: datetime | None = None) -> str:
    current = argentina_now(now)
    return f"{DAY_NAMES[current.weekday()]} {current:%d} {MONTH_NAMES[current.month]} {current:%Y}"