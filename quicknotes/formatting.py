"""Testi per l'interfaccia: date leggibili, gruppi, scadenze, anteprime, iniziali. Solo funzioni pure."""

from __future__ import annotations

import datetime as dt
import re

from . import parser

MONTHS = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")
MONTHS_FULL = ("Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto",
               "Settembre", "Ottobre", "Novembre", "Dicembre")
TYPE_LABELS = {"meeting": "Meeting", "daily": "Nota del giorno", "note": "Nota"}
TYPE_ICONS = {"meeting": "users", "daily": "sun", "note": "pen"}
AVATAR_COLORS = ("#c4553a", "#2961ae", "#1e7b46", "#7444bb", "#a15f0f", "#0e7c86", "#b03a6f")


def _parse(value: str | None) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat((value or "").replace(" ", "T"))
    except ValueError:
        return None


def friendly_date(value: str) -> str:
    """'2026-10-27T14:30' -> 'Oggi, 14:30';  '2026-03-02' -> '2 mar'."""
    d = _parse(value)
    if d is None:
        return value or ""
    today = dt.date.today()
    if d.date() == today:
        day = "Oggi"
    elif d.date() == today - dt.timedelta(days=1):
        day = "Ieri"
    else:
        day = f"{d.day} {MONTHS[d.month - 1]}" + ("" if d.year == today.year else f" {d.year}")
    return f"{day}, {d:%H:%M}" if len(value) > 10 else day


def short_when(value: str) -> str:
    """Data compatta per l'elenco: '14:30', 'Ieri', '27 ott', '27/10/25'."""
    d = _parse(value)
    if d is None:
        return ""
    today = dt.date.today()
    if d.date() == today:
        return f"{d:%H:%M}" if len(value) > 10 else "Oggi"
    if d.date() == today - dt.timedelta(days=1):
        return "Ieri"
    if d.year == today.year:
        return f"{d.day} {MONTHS[d.month - 1]}"
    return f"{d:%d/%m/%y}"


def date_group(value: str) -> str:
    d = _parse(value)
    if d is None:
        return "Senza data"
    today = dt.date.today()
    days = (today - d.date()).days
    if days <= 0:
        return "Oggi"
    if days == 1:
        return "Ieri"
    if days < 7:
        return "Ultimi 7 giorni"
    return MONTHS_FULL[d.month - 1] + ("" if d.year == today.year else f" {d.year}")


def due_badge(due: str) -> tuple[str, str]:
    """Etichetta e livello ('danger', 'warning', 'normal') della scadenza di un'azione."""
    try:
        d = dt.date.fromisoformat(due[:10])
    except ValueError:
        return due, "normal"
    days = (d - dt.date.today()).days
    short = f"{d.day} {MONTHS[d.month - 1]}"
    if days < 0:
        return f"Scaduta il {short}", "danger"
    if days == 0:
        return "Oggi", "warning"
    if days == 1:
        return "Domani", "warning"
    return short, "normal"


def due_group(due: str | None) -> str:
    if not due:
        return "Senza scadenza"
    try:
        days = (dt.date.fromisoformat(due[:10]) - dt.date.today()).days
    except ValueError:
        return "Senza scadenza"
    if days < 0:
        return "Scadute"
    if days == 0:
        return "Oggi"
    if days <= 7:
        return "Prossimi 7 giorni"
    return "Più avanti"


def preview_text(body: str) -> str:
    """Testo leggibile per l'anteprima: senza marcatori Markdown, intestazioni e link audio."""
    parts = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("🎙"):
            continue
        s = re.sub(r"^(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s*)?", "", s)
        s = parser.DUE_RE.sub("", parser.DECISION_RE.sub("", s))
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"^\[\d+:\d{2}(?::\d{2})?\]\s*", "", s).strip()
        if s:
            parts.append(s)
    return "  ".join(parts)


def action_text(text: str) -> str:
    """Testo di un'azione senza la scadenza (mostrata a parte come etichetta)."""
    return re.sub(r"\s{2,}", " ", parser.DUE_RE.sub("", text)).strip()


def initials(name: str) -> str:
    parts = [p for p in re.split(r"[\s._-]+", name.strip().lstrip("@")) if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def avatar_color(name: str) -> str:
    return AVATAR_COLORS[sum(map(ord, name.lower())) % len(AVATAR_COLORS)]
