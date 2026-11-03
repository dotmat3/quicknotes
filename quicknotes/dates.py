"""Date in italiano, etichette e gruppi delle scadenze."""

from __future__ import annotations

from datetime import date, datetime, timedelta

MONTHS = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
MONTHS_FULL = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
               "settembre", "ottobre", "novembre", "dicembre"]
WEEKDAYS = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
WEEKDAYS_SHORT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


def parse_day(value: str | None) -> date | None:
    if not value or len(value) < 10:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def daily_title(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS_FULL[d.month - 1]}"


def daily_file_title(d: date) -> str:
    return f"Giornata di {WEEKDAYS[d.weekday()].lower()} {d.strftime('%d/%m/%Y')}"


def short_day(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def due_label(due: date, today: date) -> tuple[str, str]:
    """(etichetta, livello): livello `late`, `soon` o `normal`."""
    days = (due - today).days
    if days < 0:
        return short_day(due), "late"
    if days == 0:
        return "oggi", "soon"
    if days == 1:
        return "domani", "soon"
    return f"{WEEKDAYS_SHORT[due.weekday()]} {short_day(due)}", "normal"


def due_group(due: date | None, today: date) -> str:
    """La colonna della bacheca: `late`, `soon` (oggi e domani), `week` (fino a domenica), `later`, `none`."""
    if due is None:
        return "none"
    days = (due - today).days
    if days < 0:
        return "late"
    if days <= 1:
        return "soon"
    sunday = today + timedelta(days=6 - today.weekday())
    return "week" if due <= sunday else "later"


def first_day_in(group: str, today: date) -> date | None:
    """Il primo giorno che cade in una colonna: la scadenza di un'azione aggiunta con il suo "+"."""
    if group in ("late", "none"):
        return None
    for n in range(9):
        d = today + timedelta(days=n)
        if due_group(d, today) == group:
            return d
    return None
