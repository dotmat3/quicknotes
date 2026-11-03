"""Comandi chiamati dalla pagina: stessi nomi e stessi dati di crates/quicknotes-app/src/commands.rs.

Per la prova ci sono solo quelli che servono a scrivere e ritrovare le note. Gli altri (Azioni, Calendario,
Grafo, schede di persone ed etichette, Ctrl K completo) rispondono `missing` e la pagina mostra il suo
valore di ripiego, come nel browser senza backend.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from . import __version__, dates
from .notes import NoteNotFound, extract

if TYPE_CHECKING:
    from .app import Shell


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


class Commands:
    def __init__(self, shell: Shell):
        self.shell = shell
        self.store = shell.store
        self.config = shell.config

    def dispatch(self, command: str, args: dict | None) -> dict:
        """Una chiamata della pagina. Le eccezioni diventano `err`, come gli errori dei comandi Tauri."""
        func = getattr(self, f"cmd_{command}", None)
        if func is None:
            return {"missing": True}
        try:
            kwargs = {_snake(k): v for k, v in (args or {}).items()}
            return {"ok": func(**kwargs)}
        except NoteNotFound as e:
            return {"err": str(e)}
        except Exception as e:  # noqa: BLE001 - qualsiasi errore va mostrato nella pagina, non perso
            self.shell.log.exception("comando %s", command)
            return {"err": f"{type(e).__name__}: {e}"}

    # ---- finestra
    def cmd_app_ready(self):
        self.shell.page_ready()

    def cmd_set_title(self, title: str):
        self.shell.set_title(title)

    def cmd_hide_main(self):
        self.shell.request_close()

    def cmd_quit(self):
        self.shell.quit()

    def cmd_save_ui(self, ui: dict):
        with self.shell.config_lock:
            self.config.set_ui(ui)
            self.config.save()

    # ---- note
    def cmd_sidebar(self):
        today = date.today()
        today_iso = today.isoformat()
        open_actions = self.store.open_actions()
        late = sum(1 for a in open_actions if a.due and a.due < today_iso)
        done = total = 0
        daily = self.store.daily(today, False)
        if daily:
            for a in extract(daily.body).actions:
                if a.parent_line is None:
                    total += 1
                    done += a.done
        return {"todayDone": done, "todayTotal": total, "open": len(open_actions), "late": late,
                "people": len(self.store.people())}

    def cmd_recent_notes(self, limit: int):
        return self.store.list_notes(limit)

    def cmd_top_people(self, limit: int):
        return self.store.people()[:limit]

    def cmd_all_tags(self):
        return [f["name"] for f in self.store.projects()]

    def cmd_search_titles(self, query: str, limit: int):
        return self.store.search(query, limit)

    def cmd_resolve_link(self, target: str):
        try:
            note = self.store.read(target)
            return {"id": note.id, "title": note.title}
        except NoteNotFound:
            pass
        for n in self.store.search(target, 20):
            if n["title"].lower() == target.lower():
                return {"id": n["id"], "title": n["title"]}
        return None

    def cmd_read_note(self, id: str):  # noqa: A002 - nome del parametro deciso dalla pagina
        note = self.store.read(id)
        is_daily = note.note_type == "daily" or note.id.endswith("-giornata")
        day = dates.parse_day(note.date) if is_daily else None
        title = dates.daily_title(day) if day else note.title
        tab_title = f"Oggi · {dates.short_day(day)}" if day and day == date.today() else title
        ex = extract(note.body)
        people = list(note.people)
        for p in ex.people:
            if not any(x.lower() == p.lower() for x in people):
                people.append(p)
        top = [a for a in ex.actions if a.parent_line is None]
        parsed = dates.parse_day(note.date)
        return {
            "id": note.id, "title": title, "tab_title": tab_title, "is_daily": is_daily,
            "date": note.date, "date_label": dates.short_day(parsed) if parsed else "",
            "path": note.path.relative_to(self.store.root).as_posix(), "body": note.body, "people": people,
            "actions_done": sum(a.done for a in top), "actions_total": len(top),
            "links_in": self.store.backlinks(note.id, note.title),
            "links_out": [l for l in self.store.outgoing_links(note.id) if l["note_id"] and l["note_id"] != note.id],
        }

    def cmd_save_note(self, id: str, base: str, body: str):  # noqa: A002
        return self.store.save_if_unchanged(id, base, body)

    def cmd_save_conflict(self, id: str, body: str):  # noqa: A002
        copy = self.store.save_conflict_copy(id, body)
        return {"id": copy.id, "title": copy.title}

    def cmd_daily_note(self, date: str, delta: int):  # noqa: A002
        day = dates.parse_day(date)
        if day is None:
            raise ValueError("Data non valida")
        day += timedelta(days=delta)
        note = self.store.daily(day, True)
        return {"id": note.id, "title": dates.daily_title(day)}

    def cmd_today_info(self):
        return self.shell.today_info()

    def cmd_new_note(self, title: str, note_type: str):
        note = self.store.create_note(title, note_type)
        return {"id": note.id, "title": note.title}

    # ---- sistema
    def cmd_open_url(self, url: str):
        if not re.match(r"^https?://[^/\s]+", url, re.I):
            raise ValueError(f"Si aprono solo i link http e https: {url}")
        os.startfile(url) if sys.platform == "win32" else subprocess.Popen(["xdg-open", url])  # noqa: S606

    def cmd_open_notes_folder(self):
        if sys.platform == "win32":
            os.startfile(self.store.root)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(self.store.root)])

    def cmd_notes_settings(self):
        c = self.config
        return {"notesDir": str(self.store.root), "whisperModel": c.whisper_model(), "language": c.language(),
                "keepAudio": c.keep_audio(), "timestamps": c.transcript_timestamps()}

    def cmd_set_notes_setting(self, key: str, value: Any):
        with self.shell.config_lock:
            self.config.set_recording(key, value)
            self.config.save()

    def cmd_app_info(self):
        return {"version": __version__, "releases": None, "autostart": False}

    def cmd_claude_config(self):
        return {"exists": False, "desktop": "Il server MCP non fa parte della prova Python.", "code": ""}
