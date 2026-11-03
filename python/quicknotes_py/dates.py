"""Date in italiano, come in quicknotes-core/src/dates.rs."""

from __future__ import annotations

from datetime import date, datetime

MONTHS = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
MONTHS_FULL = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
               "settembre", "ottobre", "novembre", "dicembre"]
WEEKDAYS = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def parse_day(value: str | None) -> date | None:
    if not value or len(value) < 10:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def daily_title(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS_FULL[d.month - 1]}"


def daily_file_title(d: date) -> str:
    return f"Giornata di {WEEKDAYS[d.weekday()].lower()} {d.strftime('%d/%m/%Y')}"


def short_day(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"
