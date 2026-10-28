"""Logica dell'interfaccia senza grafica: navigazione, elenchi, apertura e salvataggio delle note.

Usata dall'interfaccia (app.py). Restituisce solo dati serializzabili in JSON.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .formatting import (TYPE_ICONS, TYPE_LABELS, action_text, avatar_color, date_group, due_badge, due_group,
                         friendly_date, initials, preview_text, short_when)
from .store import Note, NoteNotFound, NoteStore

def _view_filters(view: str) -> dict:
    if view in ("meeting", "note"):
        return {"note_type": view}
    if view == "today":
        return {"date_from": dt.date.today().isoformat()}
    if view.startswith("project:"):
        return {"project": view.split(":", 1)[1]}
    return {}


def person(name: str) -> dict:
    return {"name": name, "initials": initials(name), "color": avatar_color(name)}


def nav_items(store: NoteStore) -> list[dict]:
    counts = store.counts()
    actions = store.actions("open")
    overdue = sum(1 for a in actions if due_group(a["due"]) == "Scadute")
    entries = [
        {"key": "today", "label": "Oggi", "icon": "sun", "count": counts["today"]},
        {"key": "all", "label": "Tutte le note", "icon": "notes", "count": counts["all"]},
        {"key": "meeting", "label": "Meeting", "icon": "users", "count": counts.get("meeting", 0)},
        {"key": "note", "label": "Note", "icon": "pen", "count": counts.get("note", 0)},
        {"key": "actions", "label": "Azioni", "icon": "check-square", "count": overdue or len(actions),
         "alert": overdue > 0},
    ]
    projects = sorted(store.projects(), key=lambda p: (-p["notes"], p["name"].lower()))[:15]
    entries += [{"key": f"project:{p['name']}", "label": p["name"], "icon": "hash", "count": p["notes"],
                 "group": "Progetti"} for p in projects]
    return [{"alert": False, "group": "", **e} for e in entries]


def note_items(store: NoteStore, view: str, search: str = "") -> list[dict]:
    """Note della vista, filtrate dalla ricerca (parole, @persona, #progetto)."""
    person_q = next(iter(re.findall(r"@([\w.\-]+)", search)), None)
    project_q = next(iter(re.findall(r"#([\w\-/]+)", search)), None)
    query = re.sub(r"[@#][\w.\-/]+", " ", search).strip()
    filters = _view_filters(view)
    if project_q:
        filters["project"] = project_q
    results = store.search(query, person=person_q, limit=200, **filters)
    previews = store.previews([r["path"] for r in results])
    items = []
    for r in results:
        preview = r.get("snippet") or previews.get(r["path"], "")
        items.append({
            "id": r["id"], "title": r["title"] or "Senza titolo", "when": short_when(r["date"]),
            "preview": preview_text(preview.replace("«", "").replace("»", "")),
            "section": "Risultati" if query else date_group(r["date"]),
            "type": r["type"], "icon": TYPE_ICONS.get(r["type"], "pen"),
            "project": r.get("project") or "", "people": r.get("people") or [],
        })
    return items


def action_items(store: NoteStore, search: str = "") -> list[dict]:
    needle = search.strip().lower()
    items = []
    for a in store.actions("open"):
        if needle and needle not in f"{a['text']} {a['note_title']}".lower():
            continue
        label, level = due_badge(a["due"]) if a["due"] else ("", "")
        items.append({"key": f"{a['note_id']}\n{a['line']}\n{a['text']}", "text": action_text(a["text"]),
                      "raw": a["text"], "due": label, "level": level, "noteId": a["note_id"],
                      "noteTitle": a["note_title"], "section": due_group(a["due"]), "owner": a["owner"] or ""})
    return items


def note_payload(note: Note) -> dict:
    return {
        "id": note.id, "type": note.type, "typeLabel": TYPE_LABELS.get(note.type, "Nota"),
        "icon": TYPE_ICONS.get(note.type, "pen"), "title": note.title,
        "date": note.date, "dateLabel": friendly_date(note.date),
        "people": [person(p) for p in note.people], "project": note.project,
        "body": note.body, "mtime": note.path.stat().st_mtime,
    }


def draft_payload(note_type: str) -> dict:
    now = dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
    return {
        "id": None, "type": note_type, "typeLabel": TYPE_LABELS.get(note_type, "Nota"),
        "icon": TYPE_ICONS.get(note_type, "pen"), "title": "", "date": now, "dateLabel": friendly_date(now),
        "people": [], "project": "", "body": "", "mtime": 0,
    }


def save_note(store: NoteStore, data: dict, force: bool = False) -> dict:
    """Salva la nota mandata dall'interfaccia.

    data: id (None = bozza), type, date, title, people (nomi), project, body, mtime (versione caricata).
    Risponde con {"status": "saved", note...}, {"status": "empty"} per una bozza vuota,
    oppure {"status": "conflict", "disk": note} se il file e' cambiato su disco nel frattempo.
    """
    title, body = (data.get("title") or "").strip(), data.get("body") or ""
    people = [p.strip() for p in data.get("people") or [] if p.strip()]
    project = (data.get("project") or "").strip().lstrip("#")
    if not data.get("id"):
        if not (body.strip() or title):
            return {"status": "empty"}
        when = dt.datetime.fromisoformat(data["date"]) if data.get("date") else None
        note = store.create_note(title, body, data.get("type") or "note", people, project, when=when)
        return {"status": "saved", "note": note_payload(note)}
    try:
        note = store.read(data["id"])
    except NoteNotFound:
        return {"status": "missing"}
    if not force and note.path.stat().st_mtime > float(data.get("mtime") or 0) + 0.001:
        return {"status": "conflict", "disk": note_payload(note)}
    meta = {"title": title or note.title}
    if note.type != "daily":
        meta.update(people=people, project=project)
    note = store.update(note.id, body=body, meta=meta)
    return {"status": "saved", "note": note_payload(note)}


def changed_on_disk(store: NoteStore, note_id: str, mtime: float) -> dict | None:
    """La nota aperta se e' stata modificata fuori dall'app (es. da Claude), altrimenti None."""
    try:
        note = store.read(note_id)
    except NoteNotFound:
        return None
    return note_payload(note) if note.path.stat().st_mtime > mtime + 0.001 else None


def complete_action(store: NoteStore, note_id: str, raw: str) -> dict:
    return store.set_action_status(note_id, raw, True)


def delete_info(store: NoteStore, note_id: str) -> dict:
    """Titolo e numero di registrazioni audio di una nota, per la conferma di eliminazione."""
    note = store.read(note_id)
    return {"id": note.id, "title": note.title, "audio": len(store.note_files(note_id)) - 1}


def move_to_trash(path: Path) -> None:
    from send2trash import send2trash
    send2trash(str(path))


def delete_note(store: NoteStore, note_id: str, permanent: bool = False) -> dict:
    """Sposta nel Cestino (o elimina) una nota e le sue registrazioni.

    Risponde {"status": "deleted"}, {"status": "missing"} o {"status": "no-trash"} se il Cestino
    non e' disponibile per quella cartella (l'interfaccia puo' allora chiedere l'eliminazione definitiva).
    """
    try:
        store.delete(note_id, discard=None if permanent else move_to_trash)
    except NoteNotFound:
        return {"status": "missing"}
    except (OSError, ImportError):
        return {"status": "no-trash"}
    return {"status": "deleted"}
