"""Archivio delle note: i file Markdown sono la fonte di verità, l'indice SQLite si ricostruisce da loro.

Un salvataggio non riscrive ciò che non è cambiato: il frontmatter resta il testo originale finché i
metadati non vengono modificati, e gli a capo restano quelli del file. Le scritture sono atomiche.
"""

from __future__ import annotations

import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from . import dates, edit, index, parser
from .index import Filter


class QuickNotesError(Exception):
    """Un errore da mostrare così com'è all'utente."""


class NoteNotFound(QuickNotesError):
    def __init__(self, what: str):
        super().__init__(f"Nota non trovata: {what}")


class StaleLine(QuickNotesError):
    def __init__(self):
        super().__init__("La riga è cambiata nel frattempo: ricarica la nota")


def read_text(path: Path) -> str:
    """Il testo così com'è, senza convertire gli a capo di Windows."""
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _mtime_ms(st: os.stat_result) -> int:
    return st.st_mtime_ns // 1_000_000


def _date_from_id(note_id: str) -> str | None:
    if dates.parse_day(note_id) is None:
        return None
    day = note_id[:10]
    if len(note_id) >= 15 and note_id[10] == "-" and note_id[11:15].isdigit():
        return f"{day}T{note_id[11:13]}:{note_id[13:15]}"
    return day


class Note:
    def __init__(self, path: Path, text: str, mtime_ms: int | None = None):
        self.crlf = "\r\n" in text
        if self.crlf:
            text = text.replace("\r\n", "\n")
        self.front_raw, self.meta, self.body = parser.split_frontmatter(text)
        self.meta_dirty = False
        self.path = path
        self.id = path.stem
        self.title = parser.meta_str(self.meta, "title") or parser.first_h1(self.body) or self.id
        d = parser.meta_str(self.meta, "date")
        self.date = (parser.normalize_date(d) if d else None) or _date_from_id(self.id) or (
            datetime.fromtimestamp(mtime_ms / 1000).strftime("%Y-%m-%dT%H:%M") if mtime_ms else "")

    @classmethod
    def new(cls, path: Path, meta: dict, body: str) -> Note:
        note = cls(path, parser.render_frontmatter(meta) + body)
        note.meta = meta
        return note

    @property
    def note_type(self) -> str:
        return parser.meta_str(self.meta, "type") or "note"

    @property
    def people(self) -> list[str]:
        return parser.meta_list(self.meta, "people")

    @property
    def project(self) -> str:
        return parser.meta_str(self.meta, "project") or ""

    @property
    def tags(self) -> list[str]:
        return parser.meta_list(self.meta, "tags")

    def text(self) -> str:
        """Il contenuto completo del file."""
        front = parser.render_frontmatter(self.meta) if self.meta_dirty else self.front_raw
        text = front + self.body
        return text.replace("\n", "\r\n") if self.crlf else text


def _check_line(note: Note, line_no: int, expected: str | None) -> None:
    """Prima di scrivere: la riga è ancora quella che l'utente vedeva."""
    if expected is None:
        return
    lines = parser.lines_of(note.body)
    line = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
    m = parser.ACTION_RE.match(line)
    if line != expected and (not m or m.group(3).strip() != expected):
        raise StaleLine()


def _change_line(note: Note, line_no: int, change) -> str:
    lines = parser.lines_of(note.body)
    if not 1 <= line_no <= len(lines):
        raise QuickNotesError(f"Riga {line_no} inesistente")
    lines[line_no - 1] = change(lines[line_no - 1])
    ends_nl = note.body.endswith("\n")
    note.body = "\n".join(lines) + ("\n" if ends_nl else "")
    return lines[line_no - 1]


class NoteStore:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        folder = self.root / ".quicknotes"
        folder.mkdir(exist_ok=True)
        db = folder / "index-v4.db"
        self._writer = index.open_db(db)
        index.init_schema(self._writer)
        self._reader = index.open_db(db)
        self._write_lock = threading.Lock()
        self._read_lock = threading.Lock()
        # Leggi, cambia, scrivi: due modifiche alla stessa nota non si incrociano.
        self.edit_lock = threading.RLock()

    def close(self) -> None:
        self._writer.close()
        self._reader.close()

    def _read(self, query, *args):
        with self._read_lock:
            return query(self._reader, *args)

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            raise QuickNotesError(f"Percorso fuori dalla cartella delle note: {path}") from None

    # ---- allineamento ai file
    def _scan(self) -> dict[str, tuple[int, int]]:
        """Percorso → (modifica in ms, dimensione) dei file .md, saltando file e cartelle nascosti. Su Windows
        data e dimensione arrivano con l'elenco della cartella: nessuna richiesta in più per file."""
        found = {}
        stack = [(self.root, "")]
        while stack:
            folder, prefix = stack.pop()
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for e in entries:
                if e.name.startswith("."):
                    continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append((e.path, f"{prefix}{e.name}/"))
                    elif e.name.endswith(".md"):
                        st = e.stat()
                        found[prefix + e.name] = (_mtime_ms(st), st.st_size)
                except OSError:
                    continue
        return found

    def refresh_changes(self) -> list[str]:
        """Allinea l'indice ai file e restituisce gli id delle note cambiate o sparite. Un salvataggio dell'app
        aggiorna già l'indice, quindi qui compaiono solo le modifiche esterne."""
        on_disk = self._scan()
        with self._write_lock:
            db = self._writer
            known = index.signatures(db)
            changed = [(p, sig) for p, sig in on_disk.items() if known.get(p) != sig]
            removed = [p for p in known if p not in on_disk]
            if not changed and not removed:
                return []
            ids = [Path(p).stem for p in removed]
            db.execute("BEGIN")
            try:
                for rel in removed:
                    index.delete_rows(db, rel)
                for rel, (mtime, size) in changed:
                    path = self.root / rel
                    try:
                        text = read_text(path)
                    except (OSError, UnicodeDecodeError):
                        continue  # un file illeggibile non deve fermare gli altri
                    note = Note(path, text, mtime)
                    index.index_note(db, rel, note, mtime, size, known=rel in known)
                    ids.append(note.id)
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
            return ids

    def refresh(self) -> int:
        return len(self.refresh_changes())

    def reindex(self) -> int:
        with self._write_lock:
            index.clear(self._writer)
        return self.refresh()

    # ---- lettura e scrittura
    def _path_for_id(self, note_id: str) -> Path | None:
        note_id = note_id.strip().removesuffix(".md")
        rel = self._read(index.path_for_id, note_id)
        return self.root / rel if rel else None

    def read(self, note_id: str) -> Note:
        path = self._path_for_id(note_id)
        if path is None or not path.exists():
            self.refresh()
            path = self._path_for_id(note_id)
        if path is None or not path.exists():
            raise NoteNotFound(note_id)
        return self._read_path(path)

    def _read_path(self, path: Path) -> Note:
        return Note(path, read_text(path), _mtime_ms(path.stat()))

    def save(self, note: Note) -> None:
        """Scrive la nota su disco in modo atomico e aggiorna l'indice."""
        note.path.parent.mkdir(parents=True, exist_ok=True)
        rel = self.rel(note.path)
        tmp = note.path.with_name(f".tmp-{os.getpid()}-{note.id}.md")
        try:
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(note.text())
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, note.path)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise
        st = note.path.stat()
        with self._write_lock:
            self._writer.execute("BEGIN")
            try:
                index.index_note(self._writer, rel, note, _mtime_ms(st), st.st_size)
                self._writer.execute("COMMIT")
            except BaseException:
                self._writer.execute("ROLLBACK")
                raise

    def _unique_path(self, base: str, folder: Path) -> Path:
        candidate, n = base, 2
        while (folder / f"{candidate}.md").exists() or self._path_for_id(candidate) is not None:
            candidate = f"{base}-{n}"
            n += 1
        return folder / f"{candidate}.md"

    def create_note(self, title: str = "", body: str = "", note_type: str = "", people: list[str] | None = None,
                    project: str | None = None, tags: list[str] | None = None, when: datetime | None = None,
                    source: str | None = None) -> Note:
        when = when or datetime.now()
        note_type = note_type or "meeting"
        title = title.strip() or ("Meeting" if note_type == "meeting" else "Nota")
        folder = self.root / when.strftime("%Y") / when.strftime("%m")
        meta = {"type": note_type, "title": title, "date": when.strftime("%Y-%m-%dT%H:%M"),
                "people": list(people or []), "project": project or "", "tags": list(tags or [])}
        if source:
            meta["source"] = source
        if body and not body.endswith("\n"):
            body += "\n"
        with self.edit_lock:
            path = self._unique_path(f"{when.strftime('%Y-%m-%d-%H%M')}-{parser.slugify(title)}", folder)
            note = Note.new(path, meta, body)
            self.save(note)
        return note

    def daily(self, day: date, create: bool) -> Note | None:
        """La nota del giorno, creata se manca e se richiesto."""
        note_id = f"{dates.iso(day)}-giornata"
        path = self.root / day.strftime("%Y") / day.strftime("%m") / f"{note_id}.md"
        if path.exists():
            return self._read_path(path)
        try:
            return self.read(note_id)
        except NoteNotFound:
            if not create:
                return None
        with self.edit_lock:
            if path.exists():
                return self._read_path(path)
            meta = {"type": "daily", "title": dates.daily_file_title(day), "date": dates.iso(day)}
            note = Note.new(path, meta, "")
            self.save(note)
            return note

    def update_body(self, note_id: str, body: str) -> Note:
        with self.edit_lock:
            note = self.read(note_id)
            note.body = body
            self.save(note)
            return note

    def save_if_unchanged(self, note_id: str, base: str, body: str) -> dict:
        """Salva solo se il file contiene ancora `base`, il testo da cui è partita la modifica. Altrimenti non
        scrive nulla: il file è cambiato fuori dall'app e si restituisce il suo contenuto."""
        with self.edit_lock:
            note = self.read(note_id)
            if note.body == body:
                return {"status": "saved"}
            if note.body != base:
                return {"status": "conflict", "disk": note.body}
            note.body = body
            self.save(note)
            return {"status": "saved"}

    def save_conflict_copy(self, note_id: str, body: str, now: datetime | None = None) -> Note:
        """Conserva un testo in conflitto come nota a parte, così non si perde nulla."""
        now = now or datetime.now()
        note = self.read(note_id)
        return self.create_note(f"{note.title} (conflitto {now.strftime('%H:%M')})", body, "note", when=now)

    def append(self, note_id: str, text: str, heading: str | None = None) -> Note:
        with self.edit_lock:
            note = self.read(note_id)
            block = text.strip("\n")
            if heading:
                block = f"### {heading}\n{block}"
            base = note.body.rstrip("\n")
            note.body = f"{block}\n" if not base else f"{base}\n\n{block}\n"
            self.save(note)
            return note

    def append_to_daily(self, text: str, now: datetime | None = None, timestamp: bool = True) -> Note:
        """Aggiunge una voce alla nota del giorno, con l'orario se richiesto."""
        now = now or datetime.now()
        note = self.daily(now.date(), True)
        text = text.strip()
        time = now.strftime("%H:%M")
        if timestamp and "\n" not in text and not text.startswith(("-", "*", "#")):
            return self.append(note.id, f"- {time} {text}")
        return self.append(note.id, text, time if timestamp else None)

    def add_to_section(self, note_id: str, section: str | None, block: str) -> Note:
        with self.edit_lock:
            note = self.read(note_id)
            note.body = edit.add_to_section(note.body, section, block)
            self.save(note)
            return note

    def add_action(self, today: date, text: str, due: date | None = None, tag: str | None = None) -> Note:
        """Una nuova azione nella nota del giorno, sezione "Priorità". Scadenza ed etichetta si aggiungono solo
        se il testo non ne ha già una: vale quello che l'utente ha scritto."""
        daily = self.daily(today, True)
        line = f"- [ ] {text.strip()}"
        written = parser.extract(line).actions
        written = written[0] if written else None
        if due and (written is None or written.due is None):
            line = edit.with_due(line, dates.iso(due))
        if tag and (written is None or not written.tags):
            line = edit.with_tag(line, tag)
        return self.add_to_section(daily.id, "Priorità", line)

    def postpone_late(self, today: date) -> tuple[int, list[str]]:
        """Sposta a domani le azioni di primo livello in ritardo. Una riga cambiata nel frattempo resta com'è."""
        tomorrow = dates.iso(today + timedelta(days=1))
        moved, ids = 0, []
        for row in self.actions():
            if row["parent_line"] is not None:
                continue
            if dates.due_group(dates.parse_day(row["due"]), today) != "late":
                continue
            try:
                self.set_action_details(row["note_id"], row["line"], row["text"], due=tomorrow)
            except StaleLine:
                continue
            moved += 1
            if row["note_id"] not in ids:
                ids.append(row["note_id"])
        return moved, ids

    # ---- azioni
    def set_action_done(self, note_id: str, line_no: int, expected: str | None, done_on: date | None) -> dict:
        """Spunta o riapre l'azione alla riga indicata, se è ancora quella attesa. Vale una sola riga."""
        with self.edit_lock:
            note = self.read(note_id)
            _check_line(note, line_no, expected)
            day = dates.iso(done_on) if done_on else None
            text = _change_line(note, line_no, lambda l: edit.with_checked(l, day))
            self.save(note)
            return {"note_id": note.id, "line": line_no, "text": text.strip(), "done": done_on is not None}

    def set_action_status(self, note_id: str, action_text: str, done_on: date | None) -> dict:
        """Spunta o riapre un'azione cercandola per testo dentro la nota. Lo usa il server MCP."""
        note = self.read(note_id)
        wanted = action_text.strip().lower()
        best = None
        for i, line in enumerate(parser.lines_of(note.body)):
            m = parser.ACTION_RE.match(line)
            if not m:
                continue
            text = m.group(3).strip().lower()
            score = 2 if text == wanted else 1 if wanted and wanted in text else 0
            if score and (best is None or score >= best[0]):
                best = (score, i + 1)
        if best is None:
            raise QuickNotesError(f"Nota non trovata: nessuna azione che contenga '{action_text}' in {note_id}")
        return self.set_action_done(note_id, best[1], None, done_on)

    def complete_with_children(self, note_id: str, line_no: int, expected: str | None, today: date) -> int:
        """Chiude l'azione madre e le figlie aperte con una sola scrittura. Le figlie già chiuse conservano la
        loro data."""
        with self.edit_lock:
            note = self.read(note_id)
            _check_line(note, line_no, expected)
            day = dates.iso(today)
            targets = [a.line_no for a in parser.extract(note.body).actions
                       if not a.done and (a.line_no == line_no or a.parent_line == line_no)]
            for line in targets:
                _change_line(note, line, lambda l: edit.with_checked(l, day))
            self.save(note)
            return len(targets)

    _UNSET = object()

    def set_action_details(self, note_id: str, line_no: int, expected: str | None, *, due=_UNSET,
                           person: tuple[int, str | None] | None = None, tag=_UNSET,
                           description: str | None = None) -> Note:
        """Modifica i dettagli di un'azione. Un dettaglio non passato resta com'è; None lo toglie.
        Se la riga è cambiata nel frattempo non scrive."""
        with self.edit_lock:
            note = self.read(note_id)
            _check_line(note, line_no, expected)

            def change(line: str) -> str:
                if due is not self._UNSET:
                    line = edit.with_due(line, due)
                if person is not None:
                    line = edit.with_person(line, person[0], person[1])
                if tag is not self._UNSET:
                    line = edit.with_tag(line, tag)
                return line
            _change_line(note, line_no, change)
            if description is not None:
                note.body = edit.with_description(note.body, line_no, description)
            self.save(note)
            return note

    # ---- interrogazioni
    def search(self, text: str, flt: Filter | None = None, limit: int = 20) -> list[dict]:
        return self._read(index.search, text, flt or Filter(), limit)

    def list_notes(self, flt: Filter | None = None, limit: int = 50) -> list[dict]:
        return self._read(index.list_notes, flt or Filter(), limit)

    def actions(self, **query) -> list[dict]:
        with self._read_lock:
            return index.actions(self._reader, **query)

    def decisions(self, flt: Filter | None = None, query: str = "", limit: int = 100) -> list[dict]:
        return self._read(index.decisions, flt or Filter(), query, limit)

    def people(self) -> list[dict]:
        return self._read(index.people)

    def projects(self) -> list[dict]:
        return self._read(index.projects)

    def backlinks(self, note_id: str) -> list[dict]:
        note = self.read(note_id)
        return self._read(index.backlinks, note.id, note.title)

    def outgoing_links(self, note_id: str) -> list[dict]:
        note = self.read(note_id)
        return self._read(index.outgoing_links, self.rel(note.path))

    def graph_rows(self) -> dict:
        return self._read(index.graph_rows)

    def bodies(self, paths: list[str], containing: list[str] = ()) -> list[tuple[str, str]]:
        """Il testo delle note con questi percorsi, letto dai file: per poche note costa meno che cercarle
        nell'indice. Con `containing` restano solo i testi con almeno una di quelle parole."""
        out = []
        for p in paths:
            try:
                text = read_text(self.root / p)
            except (OSError, UnicodeDecodeError):
                continue
            if containing and not any(w in text for w in containing):
                continue
            out.append((p, parser.split_frontmatter(text)[2]))
        return out

    # ---- immagini
    def save_image(self, note_id: str, data: bytes, now: datetime | None = None) -> str:
        """Un'immagine incollata o trascinata: va in images/ accanto alla nota. Restituisce il percorso da
        scrivere nel tag Markdown."""
        if len(data) > 50 * 1024 * 1024:
            raise QuickNotesError(f"Immagine troppo grande: {len(data) // (1024 * 1024)} MB, il massimo è 50")
        kind = sniff(data)
        if not kind:
            raise QuickNotesError("Non è un'immagine PNG, JPEG, GIF, WebP o BMP")
        note = self.read(note_id)
        folder = note.path.parent / "images"
        folder.mkdir(parents=True, exist_ok=True)
        stem = (now or datetime.now()).strftime("%Y-%m-%d-%H%M%S")
        for n in range(1, 1000):
            name = f"{stem}.{kind[0]}" if n == 1 else f"{stem}-{n}.{kind[0]}"
            try:
                with open(folder / name, "xb") as f:
                    f.write(data)
                return f"images/{name}"
            except FileExistsError:
                continue
        raise QuickNotesError("Troppe immagini con lo stesso nome")

    def resolve_image(self, rel: str) -> tuple[Path, str] | None:
        """Un'immagine vera dentro la cartella delle note, oppure None."""
        parts = rel.split("/")
        if any(p in ("", ".", "..") or ":" in p or "\\" in p for p in parts):
            return None
        try:
            file = (self.root / Path(*parts)).resolve()
            file.relative_to(self.root)
            if not file.is_file():
                return None
            with open(file, "rb") as f:
                kind = sniff(f.read(32))
        except (OSError, ValueError):
            return None
        return (file, kind[1]) if kind else None


def sniff(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif", "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    if data.startswith(b"BM") and len(data) > 26:
        return "bmp", "image/bmp"
    return None
