"""Comandi chiamati dalla pagina con `window.pywebview.api.invoke(nome, argomenti)`.

Nomi e dati sono quelli che il frontend si aspetta. Gli argomenti arrivano in camelCase (`noteId`) e diventano
parametri in snake_case (`note_id`). La pagina non riceve mai percorsi da usare direttamente.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from . import __version__, dates, parser, system, views
from .store import QuickNotesError

if TYPE_CHECKING:
    from .app import Shell

RELEASES = "https://github.com/dotmat3/quicknotes/releases"


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


class Commands:
    def __init__(self, shell: Shell):
        self.shell = shell
        self.store = shell.store
        self.config = shell.config

    def dispatch(self, command: str, args: dict | None) -> dict:
        """Una chiamata della pagina: `{ok}`, `{err}` con un messaggio da mostrare, o `{missing}`."""
        func = getattr(self, f"cmd_{command}", None)
        if func is None:
            return {"missing": True}
        try:
            kwargs = {_snake(k): v for k, v in (args or {}).items()}
            return {"ok": func(**kwargs)}
        except QuickNotesError as e:
            return {"err": str(e)}
        except Exception as e:  # noqa: BLE001 - qualsiasi errore va mostrato nella pagina, non perso
            self.shell.log.exception("comando %s", command)
            return {"err": f"{type(e).__name__}: {e}"}

    # ---- finestre
    def cmd_app_ready(self):
        self.shell.page_ready()

    def cmd_set_title(self, title: str):
        self.shell.set_title(title)

    def cmd_hide_main(self):
        self.shell.hide_main()

    def cmd_hide_capture(self):
        self.shell.hide_capture()

    def cmd_quit(self):
        self.shell.quit()

    def cmd_save_ui(self, ui: dict):
        with self.shell.config_lock:
            self.config.set_ui(ui)
            self.config.save()

    # ---- barra laterale e note
    def cmd_sidebar(self):
        today = date.today()
        today_iso = dates.iso(today)
        top = [a for a in self.store.actions() if a["parent_line"] is None]
        done = total = 0
        daily = self.store.daily(today, False)
        if daily:
            for a in parser.extract(daily.body).actions:
                if a.parent_line is None:
                    total += 1
                    done += a.done
        return {"todayDone": done, "todayTotal": total, "open": len(top),
                "late": sum(1 for a in top if a["due"] and a["due"] < today_iso), "people": len(self.store.people())}

    def cmd_recent_notes(self, limit: int):
        return self.store.list_notes(None, limit)

    def cmd_top_people(self, limit: int):
        return self.store.people()[:limit]

    def cmd_all_tags(self):
        return [f["name"] for f in self.store.projects()]

    def cmd_search_titles(self, query: str, limit: int):
        return self.store.search(query, None, limit)

    def cmd_resolve_link(self, target: str):
        """Il bersaglio di un `[[link]]`: id oppure titolo."""
        try:
            note = self.store.read(target)
            return {"id": note.id, "title": note.title}
        except QuickNotesError:
            pass
        for n in self.store.search(target, None, 20):
            if n["title"].lower() == target.lower():
                return {"id": n["id"], "title": n["title"]}
        return None

    def cmd_read_note(self, id: str):  # noqa: A002 - nome deciso dalla pagina
        note = self.store.read(id)
        is_daily = note.note_type == "daily" or note.id.endswith("-giornata")
        day = dates.parse_day(note.date) if is_daily else None
        title = dates.daily_title(day) if day else note.title
        tab_title = f"Oggi · {dates.short_day(day)}" if day and day == date.today() else title
        ex = parser.extract(note.body)
        people = list(note.people)
        for p in ex.people:
            if not any(x.lower() == p.lower() for x in people):
                people.append(p)
        top = [a for a in ex.actions if a.parent_line is None]
        parsed = dates.parse_day(note.date)
        return {
            "id": note.id, "title": title, "tab_title": tab_title, "is_daily": is_daily, "date": note.date,
            "date_label": dates.short_day(parsed) if parsed else "", "path": self.store.rel(note.path),
            "body": note.body, "people": people, "actions_done": sum(a.done for a in top), "actions_total": len(top),
            "links_in": self.store.backlinks(note.id),
            # Note citate con `[[link]]` che esistono davvero.
            "links_out": [l for l in self.store.outgoing_links(note.id) if l["note_id"] and l["note_id"] != note.id],
        }

    def cmd_save_note(self, id: str, base: str, body: str):  # noqa: A002
        return self.store.save_if_unchanged(id, base, body)

    def cmd_save_conflict(self, id: str, body: str):  # noqa: A002
        copy = self.store.save_conflict_copy(id, body)
        return {"id": copy.id, "title": copy.title}

    def cmd_daily_note(self, date: str, delta: int):  # noqa: A002
        """La nota del giorno a `delta` giorni da `date`, creata se manca."""
        day = dates.parse_day(date)
        if day is None:
            raise QuickNotesError("Data non valida")
        day += timedelta(days=delta)
        note = self.store.daily(day, True)
        return {"id": note.id, "title": dates.daily_title(day)}

    def cmd_today_info(self):
        return self.shell.today_info()

    def cmd_new_note(self, title: str, note_type: str):
        note = self.store.create_note(title, "", note_type)
        return {"id": note.id, "title": note.title}

    def cmd_capture_save(self, text: str, section: str, open: bool):  # noqa: A002
        """La nota rapida: va nella nota del giorno, nella sezione scelta."""
        today = date.today()
        daily = self.store.daily(today, True)
        note = self.store.add_to_section(daily.id, section, text)
        self.shell.emit("note-changed", [note.id])
        self.shell.emit("index-updated", 1)
        if open:
            self.shell.emit("open-page", {"page": f"note:{note.id}", "title": f"Oggi · {dates.short_day(today)}"})
            self.shell.show_main()

    # ---- azioni
    def cmd_action_board(self):
        return views.action_board(self.store, date.today())

    def cmd_set_action_done(self, note_id: str, line: int, text: str, done: bool):
        self.store.set_action_done(note_id, line, text, date.today() if done else None)

    def cmd_complete_action(self, note_id: str, line: int, text: str):
        self.store.complete_with_children(note_id, line, text, date.today())

    def cmd_set_action_field(self, note_id: str, line: int, text: str, field: str, index: int | None = None,
                             value: str | None = None):
        """Cambia un solo dettaglio. `field`: due, person, tag, description."""
        value = value if value and value.strip() else None
        if field == "due":
            self.store.set_action_details(note_id, line, text, due=value)
        elif field == "person":
            self.store.set_action_details(note_id, line, text, person=(index or 0, value))
        elif field == "tag":
            self.store.set_action_details(note_id, line, text, tag=value)
        elif field == "description":
            self.store.set_action_details(note_id, line, text, description=value or "")
        else:
            raise QuickNotesError(f"Campo sconosciuto: {field}")

    def cmd_add_action(self, text: str, due: str | None = None, tag: str | None = None):
        """Una nuova azione nella nota di oggi, sezione "Priorità". Restituisce l'id della nota."""
        return self.store.add_action(date.today(), text, dates.parse_day(due), tag).id

    def cmd_postpone_late(self):
        moved, ids = self.store.postpone_late(date.today())
        return {"moved": moved, "ids": ids}

    # ---- viste
    def cmd_person_page(self, name: str):
        return views.person_page(self.store, name, date.today())

    def cmd_people_list(self):
        return views.people_list(self.store, date.today())

    def cmd_tag_page(self, tag: str):
        return views.tag_page(self.store, tag, date.today())

    def cmd_calendar_data(self, **kw):
        # `from` è una parola riservata in Python.
        return views.calendar_data(self.store, kw["from"], kw["to"], date.today())

    def cmd_full_graph(self):
        return views.full_graph(self.store)

    def cmd_search_all(self, query: str):
        return views.search_all(self.store, query, date.today())

    # ---- sistema
    def cmd_open_url(self, url: str):
        """Apre un link della nota nel browser. Solo http e https: niente file, niente altri protocolli."""
        if not re.match(r"^https?://[^/\s]+", url, re.I):
            raise QuickNotesError(f"Si aprono solo i link http e https: {url}")
        system.open_external(url)

    def cmd_open_notes_folder(self):
        system.open_external(str(self.store.root))

    def cmd_notes_settings(self):
        c = self.config
        return {"notesDir": str(self.store.root), "whisperModel": c.whisper_model(), "language": c.language(),
                "keepAudio": c.keep_audio(), "timestamps": c.transcript_timestamps()}

    def cmd_set_notes_setting(self, key: str, value: Any):
        with self.shell.config_lock:
            self.config.set_recording(key, value)
            self.config.save()

    def cmd_app_info(self):
        return {"version": __version__, "releases": RELEASES, "autostart": system.autostart_enabled()}

    def cmd_set_autostart(self, on: bool):
        system.set_autostart(on)

    def cmd_claude_config(self):
        """Il blocco da copiare in Claude, con il Python di questa installazione."""
        python = system.console_python()
        desktop = {"mcpServers": {"quicknotes": {"command": python, "args": ["-m", "quicknotes", "mcp"]}}}
        return {"exists": True, "desktop": json.dumps(desktop, indent=2, ensure_ascii=False),
                "code": f'claude mcp add --transport stdio --scope user quicknotes -- "{python}" -m quicknotes mcp'}
