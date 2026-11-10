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
            # La data dell'ultima revisione la scrive anche `review_done`: una pagina aperta prima non la cancella.
            old = self.config.ui().get("lastReview")
            if isinstance(old, str) and old > str(ui.get("lastReview") or ""):
                ui = {**ui, "lastReview": old}
            self.config.set_ui(ui)
            self.config.save()

    # ---- barra laterale e note
    def cmd_sidebar(self):
        today = date.today()
        today_iso = dates.iso(today)
        # Come la vista Azioni: senza i progetti in pausa o chiusi.
        top = [a for a in self.store.actions(include_paused=False) if a["parent_line"] is None]
        done = total = 0
        daily = self.store.daily(today, False)
        if daily:
            for a in parser.extract(daily.body).actions:
                if a.parent_line is None and a.status != "cancelled":
                    total += 1
                    done += a.done
        last = dates.parse_day(self.config.ui().get("lastReview"))
        return {"todayDone": done, "todayTotal": total, "open": len(top),
                "late": sum(1 for a in top if a["due"] and a["due"] < today_iso), "people": len(self.store.people()),
                "reviewDue": last is None or (today - last).days > views.REVIEW_DAYS,
                "projects": self.store.project_rows()}

    def cmd_recent_notes(self, limit: int):
        return self.store.list_notes(None, limit)

    def cmd_top_people(self, limit: int):
        return self.store.people()[:limit]

    def cmd_all_tags(self):
        """Le etichette usate, più `progetto` e `progetto/area` di ogni nota di progetto: l'editor le propone
        dopo `#`."""
        names = [f["name"] for f in self.store.projects()]
        for p in self.store.project_rows():
            names += [p["key"], *(f"{p['key']}/{a}" for a in p["areas"])]
        return list(dict.fromkeys(names))

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
        top = [a for a in ex.actions if a.parent_line is None and a.status != "cancelled"]
        parsed = dates.parse_day(note.date)
        return {
            "id": note.id, "title": title, "tab_title": tab_title, "is_daily": is_daily, "date": note.date,
            "date_label": dates.short_day(parsed) if parsed else "", "path": self.store.rel(note.path),
            "body": note.body, "people": people, "actions_done": sum(a.done for a in top), "actions_total": len(top),
            "project": self._project_of(note),
            "links_in": self.store.backlinks(note.id),
            # Note citate con `[[link]]` che esistono davvero.
            "links_out": [l for l in self.store.outgoing_links(note.id) if l["note_id"] and l["note_id"] != note.id],
        }

    def _project_of(self, note) -> dict | None:
        """Il progetto di una nota di progetto (o del suo archivio), per i pulsanti in testa alla nota."""
        key = parser.meta_str(note.meta, "project") if note.note_type in ("project", "archivio") else None
        if note.note_type == "project" or key:
            try:
                p = self.store.project(key or note.title)
            except QuickNotesError:
                return None
            return {"key": p.key, "title": p.title, "status": p.status}
        return None

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

    def cmd_rename_note(self, id: str, title: str):  # noqa: A002
        """Nuovo titolo e nuovo nome del file. Le note con i [[link]] aggiornati si ricaricano nella pagina."""
        note, changed = self.store.rename(id, title)
        if changed:
            self.shell.emit("note-changed", changed)
        self.shell.emit("index-updated", 1 + len(changed))
        return {"id": note.id, "title": note.title, "relinked": len(changed)}

    def cmd_delete_note(self, id: str):  # noqa: A002
        """La nota va nel Cestino. Quella di oggi resta: l'app la riaprirebbe subito, vuota."""
        if id == f"{dates.iso(date.today())}-giornata":
            raise QuickNotesError("La nota di oggi non si elimina")
        recycled = self.store.trash(id, system.to_recycle_bin)
        self.shell.emit("index-updated", 1)
        return {"recycled": recycled}

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
        """Cambia un solo dettaglio. `field`: due, person, tag, priority, description."""
        value = value if value and value.strip() else None
        if field == "due":
            self.store.set_action_details(note_id, line, text, due=value)
        elif field == "person":
            self.store.set_action_details(note_id, line, text, person=(index or 0, value))
        elif field == "tag":
            self.store.set_action_details(note_id, line, text, tag=value)
        elif field == "priority":
            if value and parser.priority_name(value) is None:
                raise QuickNotesError(f"Priorità sconosciuta: {value}")
            self.store.set_action_details(note_id, line, text, priority=value)
        elif field == "description":
            self.store.set_action_details(note_id, line, text, description=value or "")
        elif field == "scheduled":
            if value and dates.parse_day(value) is None:
                raise QuickNotesError(f"Data non valida: {value}")
            self.store.set_action_details(note_id, line, text, scheduled=value)
        elif field == "status":
            self.cmd_set_action_status(note_id, line, text, value or "todo")
        else:
            raise QuickNotesError(f"Campo sconosciuto: {field}")

    def cmd_add_action(self, text: str, due: str | None = None, tag: str | None = None, priority: str | None = None):
        """Una nuova azione nella nota di oggi, sezione "Priorità". Restituisce l'id della nota."""
        return self.store.add_action(date.today(), text, dates.parse_day(due), tag, priority).id

    def cmd_quick_action(self, text: str, project: str | None = None, area: str | None = None, due: str | None = None,
                         priority: str | None = None, scheduled: str | None = None):
        """Aggiunta rapida dalla vista Azioni: nella nota del progetto (anche da `#progetto/area` nel testo),
        altrimenti nella nota "Da smistare". Restituisce dove è finita."""
        return self.store.quick_action(text, project or None, area or None, dates.parse_day(due), priority or None,
                                       dates.parse_day(scheduled))

    def cmd_postpone_late(self):
        moved, ids = self.store.postpone_late(date.today())
        return {"moved": moved, "ids": ids}

    def cmd_set_action_status(self, note_id: str, line: int, text: str, status: str):
        return self.store.set_action_state(note_id, line, text, status, date.today())

    def cmd_set_scheduled(self, note_id: str, line: int, text: str, value: str | None = None):
        """`scheduled:` di un'azione: una data AAAA-MM-GG, `oggi`, `domani`, oppure niente per toglierlo."""
        today = date.today()
        names = {"oggi": today, "domani": today + timedelta(days=1)}
        day = names.get((value or "").strip().lower()) or dates.parse_day(value)
        if value and day is None:
            raise QuickNotesError(f"Data non valida: {value}")
        self.store.set_action_details(note_id, line, text, scheduled=dates.iso(day) if day else None)

    def cmd_move_action(self, note_id: str, line: int, text: str, target: str, section: str | None = None):
        """Sposta un'azione nella nota di un progetto (`target` è il progetto o l'id di una nota)."""
        try:
            target_id = self.store.project(target).note_id
        except QuickNotesError:
            target_id = target
        moved = self.store.move_action(note_id, line, text, target_id, section or None)
        ids = [moved["from"], moved["note_id"]]
        self.shell.emit("index-updated", 2)
        return {**moved, "ids": ids}

    def cmd_archive_done(self, project: str):
        r = self.store.archive_done(project, date.today())
        if r["archived"]:
            self.shell.emit("index-updated", 2)
        return {**r, "ids": [self.store.project(project).note_id] + ([r["archive_id"]] if r["archive_id"] else [])}

    def cmd_projects(self):
        return self.store.project_rows()

    def cmd_create_project(self, name: str, aliases: list[str] | None = None, areas: list[str] | None = None):
        note = self.store.create_project(name, aliases or [], areas or [])
        self.shell.emit("index-updated", 1)
        return {"id": note.id, "title": note.title, "key": parser.meta_str(note.meta, "project")}

    def cmd_set_project_status(self, project: str, status: str):
        note = self.store.set_project_status(project, status)
        self.shell.emit("index-updated", 1)
        return {"id": note.id}

    def cmd_add_project_action(self, project: str, text: str, area: str | None = None):
        note = self.store.add_project_action(project, text, area or None)
        return note.id

    # ---- migrazione delle note al formato con progetti
    def cmd_migration_plan(self):
        from . import migrate
        return migrate.plan(self.store.root, date.today())

    def cmd_migration_apply(self, choices: dict):
        """Applica le scelte della vista Migrazione: prima la copia della cartella, poi progetti e righe."""
        from . import migrate
        done = migrate.apply(self.store, choices if isinstance(choices, dict) else {})
        self._last_backup = done["backup"]
        if done["changed"]:
            self.shell.emit("note-changed", done["changed"])
        self.shell.emit("index-updated", len(done["changed"]))
        return done

    def cmd_open_backup(self):
        """Apre la copia fatta dall'ultima migrazione, e solo quella."""
        path = getattr(self, "_last_backup", None)
        if not path:
            raise QuickNotesError("Nessuna copia da aprire")
        system.open_external(path)

    def cmd_agenda(self, project: str | None = None, include_paused: bool = False):
        return views.agenda(self.store, date.today(), project or None, include_paused)

    def cmd_project_page(self, slug: str):
        return views.project_page(self.store, slug, date.today())

    def cmd_weekly_review(self):
        return views.weekly_review(self.store, date.today(), self.config.ui().get("lastReview"))

    def cmd_review_done(self):
        """Fine revisione: la data va in `config.ui.lastReview`. La pagina la salva anche fra le sue preferenze."""
        today = dates.iso(date.today())
        with self.shell.config_lock:
            ui = dict(self.config.ui())
            ui["lastReview"] = today
            self.config.set_ui(ui)
            self.config.save()
        return today

    def cmd_create_review_note(self):
        """La nota "Revisione settimana NN" con il riepilogo della Revisione."""
        today = date.today()
        review = views.weekly_review(self.store, today, self.config.ui().get("lastReview"))
        note = self.store.create_note(f"Revisione settimana {review['week_number']}", views.review_note_body(review),
                                      "note", tags=["revisione"])
        self.shell.emit("index-updated", 1)
        return {"id": note.id, "title": note.title}

    # ---- Micio
    def cmd_pet_done(self, since: str):
        """Le azioni completate da quando c'è Micio: ognuna vale crocchette."""
        if dates.parse_day(since) is None:
            raise QuickNotesError("Data non valida")
        return self.store.done_since(since)

    # ---- viste
    def cmd_person_page(self, name: str):
        return views.person_page(self.store, name, date.today())

    def cmd_people_list(self):
        return views.people_list(self.store, date.today())

    def cmd_tag_page(self, tag: str):
        return views.tag_page(self.store, tag, date.today())

    def cmd_calendar_data(self, **kw):
        # `from` è una parola riservata in Python.
        return views.calendar_data(self.store, kw["from"], kw["to"], date.today(), kw.get("project") or None)

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
