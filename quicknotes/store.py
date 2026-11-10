"""Archivio delle note: i file Markdown sono la fonte di verità, l'indice SQLite si ricostruisce da loro.

Un salvataggio non riscrive ciò che non è cambiato: il frontmatter resta il testo originale finché i
metadati non vengono modificati, e gli a capo restano quelli del file. Le scritture sono atomiche.
"""

from __future__ import annotations

import os
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from . import dates, edit, index, parser
from . import projects as prj
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


_UNSET_ARG = object()


def project_template(name: str, aliases: list[str] | None = None, areas: list[str] | None = None,
                     status: str = "attivo") -> tuple[dict, str]:
    """Frontmatter e corpo di una nota di progetto nuova: obiettivo, prossime azioni per area, note collegate."""
    name = " ".join(name.split())
    areas = [a for a in dict.fromkeys(prj.key_of(a) for a in (areas or [])) if a]
    meta = {"type": "project", "title": name, "project": prj.key_of(name), "status": prj.project_status(status),
            "aliases": [a.strip() for a in (aliases or []) if a.strip()], "areas": areas}
    body = "## Obiettivo\n\n\n## Prossime azioni\n" + "".join(f"\n### {a}\n" for a in areas) + "\n## Note collegate\n"
    return meta, body


# La nota delle azioni scritte senza progetto dalla vista Azioni: in cima alla cartella, come i progetti fuori dai mesi.
INBOX_ID = "da-smistare"
INBOX_BODY = ("Le azioni aggiunte dalla vista Azioni senza un progetto. Spostale nel progetto giusto, pianificale o "
              "chiudile.\n\n## Azioni\n")


def _with_presets(line: str, due: date | None = None, tag: str | None = None, priority: str | None = None,
                  scheduled: date | None = None) -> str:
    """La riga di un'azione nuova con scadenza, etichetta, priorità e `scheduled:` scelti fuori dal testo; ciascuno
    solo se il testo non ne ha già uno, perché vale quello che l'utente ha scritto."""
    written = parser.extract(line).actions
    written = written[0] if written else None
    if due and (written is None or written.due is None):
        line = edit.with_due(line, dates.iso(due))
    if tag and (written is None or not written.tags):
        line = edit.with_tag(line, tag)
    priority = parser.priority_name(priority)
    if priority and (written is None or written.priority is None):
        line = edit.with_priority(line, priority)
    if scheduled and (written is None or written.scheduled is None):
        line = edit.with_scheduled(line, dates.iso(scheduled))
    return line


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
        self._closed = False

    def close(self) -> None:
        """Chiude l'indice dopo che le letture e le scritture in corso sono finite. Dopo, un allineamento non
        fa nulla e un salvataggio scrive solo il file: l'indice si riallinea al prossimo avvio."""
        with self._write_lock, self._read_lock:
            self._closed = True
            self._writer.close()
            self._reader.close()

    def _read(self, query, *args):
        with self._read_lock:
            if self._closed:
                raise QuickNotesError("QuickNotes si sta chiudendo")
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
            if self._closed:
                return []
            db = self._writer
            known = index.signatures(db)
            changed = [(p, sig) for p, sig in on_disk.items() if known.get(p) != sig]
            removed = [p for p in known if p not in on_disk]
            if not changed and not removed:
                return []
            ids = [Path(p).stem for p in removed]
            db.execute("BEGIN")
            try:
                before = index.registry(db).signature()
                old_projects = index.project_paths(db)
                for rel in removed:
                    index.delete_rows(db, rel)
                notes = []
                for rel, (mtime, size) in changed:
                    path = self.root / rel
                    try:
                        text = read_text(path)
                    except (OSError, UnicodeDecodeError):
                        continue  # un file illeggibile non deve fermare gli altri
                    notes.append((rel, Note(path, text, mtime), mtime, size))
                # Prima le note di progetto: le altre le usano per sapere a che progetto appartengono.
                done = set()
                for rel, note, mtime, size in notes:
                    if note.note_type == "project" or rel in old_projects:
                        index.index_note(db, rel, note, mtime, size, known=rel in known)
                        done.add(rel)
                reg = index.registry(db)
                if reg.signature() != before:
                    self._resolve_all(db, reg, on_disk, done)
                else:
                    for rel, note, mtime, size in notes:
                        if rel not in done:
                            index.index_note(db, rel, note, mtime, size, known=rel in known, reg=reg)
                ids.extend(note.id for _, note, _, _ in notes)
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
            return ids

    def _resolve_all(self, db, reg: prj.Registry, on_disk: dict[str, tuple[int, int]], skip: set[str]) -> None:
        """Rilegge tutte le note: è cambiato un progetto, quindi può cambiare il progetto di ogni azione. Con
        mille note ci vuole meno di un secondo."""
        for rel, (mtime, size) in on_disk.items():
            if rel in skip:
                continue
            path = self.root / rel
            try:
                note = Note(path, read_text(path), mtime)
            except (OSError, UnicodeDecodeError):
                continue
            index.index_note(db, rel, note, mtime, size, reg=reg)

    def refresh(self) -> int:
        return len(self.refresh_changes())

    def reindex(self) -> int:
        with self._write_lock:
            if self._closed:
                return 0
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
            if self._closed:
                return
            db = self._writer
            db.execute("BEGIN")
            try:
                was_project = rel in index.project_paths(db)
                is_project = was_project or note.note_type == "project"
                before = index.registry(db).signature() if is_project else None
                index.index_note(db, rel, note, _mtime_ms(st), st.st_size)
                if is_project:
                    reg = index.registry(db)
                    if reg.signature() != before:
                        self._resolve_all(db, reg, self._scan(), {rel})
                db.execute("COMMIT")
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

    # ---- rinomina ed elimina
    def rename(self, note_id: str, title: str) -> tuple[Note, list[str]]:
        """Cambia il titolo e, con lui, il nome del file: resta la data in testa, il resto segue il titolo. I
        [[link]] delle altre note che la citano vengono aggiornati. Restituisce la nota e gli id delle note
        riscritte."""
        title = " ".join(title.split())
        if not title:
            raise QuickNotesError("Il titolo non può essere vuoto")
        with self.edit_lock:
            note = self.read(note_id)
            if note.note_type == "daily" or note.id.endswith("-giornata"):
                raise QuickNotesError("La nota del giorno prende il nome dalla data: non si rinomina")
            old_id, old_title, old_path = note.id, note.title, note.path
            if title == old_title:
                return note, []
            refs = self._read(index.backlinks, old_id, old_title)
            self._set_title(note, title)
            new_path = self._renamed_path(note, title)
            if new_path != old_path:
                note.path, note.id = new_path, new_path.stem
            self.save(note)
            if new_path != old_path:
                old_path.unlink(missing_ok=True)
                self._forget(old_path)
            changed = self._relink(refs, old_id, old_title, note.id, title)
            return note, changed

    @staticmethod
    def _set_title(note: Note, title: str) -> None:
        """Il titolo sta dove l'utente l'ha messo: nel frontmatter, oppure nel primo `# Titolo` se il frontmatter
        non lo ha."""
        h1 = parser.first_h1(note.body)
        if parser.meta_str(note.meta, "title") or h1 is None:
            note.meta["title"] = title
            note.meta_dirty = True
        else:
            lines = parser.lines_of(note.body)
            i = next(i for i, l in enumerate(lines) if l.startswith("# ") and l[2:].strip() == h1)
            lines[i] = f"# {title}"
            note.body = "\n".join(lines) + ("\n" if note.body.endswith("\n") else "")
        note.title = title

    def _renamed_path(self, note: Note, title: str) -> Path:
        """Il nuovo file nella stessa cartella. Le note dell'app hanno data e ora in testa (`2026-11-06-1030-`),
        che restano; un file senza data prende solo il titolo."""
        m = re.match(r"^\d{4}-\d{2}-\d{2}-(?:\d{4}-)?", note.id)
        base = (m.group(0) if m else "") + parser.slugify(title)
        if re.fullmatch(re.escape(base) + r"(-\d+)?", note.id):
            return note.path  # stesso nome di prima, magari con il numero che lo distingue da un'altra nota
        candidate, n = base, 2
        while True:
            path = note.path.with_name(f"{candidate}.md")
            if candidate.lower() == note.id.lower() or (not path.exists() and self._path_for_id(candidate) is None):
                return path
            candidate = f"{base}-{n}"
            n += 1

    def _forget(self, path: Path) -> None:
        """Toglie dall'indice un file che non c'è più."""
        with self._write_lock:
            if self._closed:
                return
            self._writer.execute("BEGIN")
            try:
                rel = self.rel(path)
                was_project = rel in index.project_paths(self._writer)
                index.delete_rows(self._writer, rel)
                if was_project:
                    self._resolve_all(self._writer, index.registry(self._writer), self._scan(), {rel})
                self._writer.execute("COMMIT")
            except BaseException:
                self._writer.execute("ROLLBACK")
                raise

    def _relink(self, refs: list[dict], old_id: str, old_title: str, new_id: str, new_title: str) -> list[str]:
        """Riscrive i [[link]] alla nota rinominata, solo sulle righe che l'indice indica."""
        keys = {old_id.lower(), old_title.lower()}

        def fix(m: re.Match) -> str:
            inner = m.group(1)
            target, sep, label = inner.partition("|")
            t = target.strip()
            if t.lower() not in keys:
                return m.group(0)
            if t.lower() == old_id.lower():
                # [[id|Titolo]]: cambia l'id; il testo mostrato segue il titolo solo se era il titolo.
                shown = new_title if sep and label.strip().lower() == old_title.lower() else label
                return f"[[{new_id}{sep}{shown}]]"
            return f"[[{new_title}{sep}{label}]]"

        lines_by_note: dict[str, set[int]] = {}
        for r in refs:
            lines_by_note.setdefault(r["note_id"], set()).add(r["line"])
        changed = []
        for ref_id, line_nos in lines_by_note.items():
            try:
                ref = self.read(ref_id)
            except NoteNotFound:
                continue
            lines = parser.lines_of(ref.body)
            before = list(lines)
            for n in line_nos:
                if 1 <= n <= len(lines):
                    # Non i `![[...]]`, che incorporano immagini.
                    lines[n - 1] = re.sub(r"(?<!!)\[\[([^\]\n]+)\]\]", fix, lines[n - 1])
            if lines != before:
                ref.body = "\n".join(lines) + ("\n" if ref.body.endswith("\n") else "")
                self.save(ref)
                changed.append(ref.id)
        return changed

    def trash(self, note_id: str, to_recycle_bin=None) -> bool:
        """Elimina la nota senza perderla: nel Cestino di Windows, oppure, dove il Cestino non c'è, in
        `.quicknotes/cestino`. True se è andata nel Cestino di Windows. Le immagini restano: un'altra nota
        potrebbe usarle."""
        with self.edit_lock:
            note = self.read(note_id)
            path = note.path
            if to_recycle_bin is not None and to_recycle_bin(path):
                recycled = True
            else:
                recycled = False
                folder = self.root / ".quicknotes" / "cestino"
                folder.mkdir(parents=True, exist_ok=True)
                dest, n = folder / path.name, 2
                while dest.exists():
                    dest = folder / f"{path.stem}-{n}.md"
                    n += 1
                os.replace(path, dest)
            self._forget(path)
            return recycled

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

    def add_action(self, today: date, text: str, due: date | None = None, tag: str | None = None,
                   priority: str | None = None) -> Note:
        """Una nuova azione nella nota del giorno, sezione "Priorità". Scadenza, etichetta e priorità si
        aggiungono solo se il testo non ne ha già una: vale quello che l'utente ha scritto."""
        daily = self.daily(today, True)
        line = _with_presets(f"- [ ] {text.strip()}", due, tag, priority)
        return self.add_to_section(daily.id, "Priorità", line)

    def inbox(self, create: bool) -> Note | None:
        """La nota "Da smistare": raccoglie le azioni scritte senza un progetto, finché non trovano posto."""
        try:
            return self.read(INBOX_ID)
        except NoteNotFound:
            if not create:
                return None
        with self.edit_lock:
            path = self.root / f"{INBOX_ID}.md"
            if path.exists():
                return self._read_path(path)
            note = Note.new(path, {"type": "inbox", "title": "Da smistare"}, INBOX_BODY)
            self.save(note)
            return note

    def quick_action(self, text: str, project: str | None = None, area: str | None = None, due: date | None = None,
                     priority: str | None = None, scheduled: date | None = None) -> dict:
        """Una nuova azione dove deve stare: nella nota del progetto, sotto l'area, oppure in "Da smistare".
        Il progetto è quello indicato o la prima etichetta della riga che è un progetto (`#progetto/area`); quella
        etichetta sparisce, perché il posto dice già il progetto. Scadenza, priorità e `scheduled:` scritti nel
        testo hanno la precedenza."""
        text = text.strip()
        if not text:
            raise QuickNotesError("L'azione è vuota")
        line = text if parser.ACTION_RE.match(text) else f"- [ ] {text}"
        reg = self.registry()
        key = reg.match(project) if project else None
        if project and key is None:
            raise QuickNotesError(f"Progetto sconosciuto: {project}")
        for start, end in parser.tag_spans(line):
            head, _, rest = line[start + 1:end].partition("/")
            found = reg.match(head)
            if found and (key is None or found == key):
                key = found
                area = area or rest.strip("/") or None
                line = edit._squeeze(line[:start] + line[end:])
                break
        line = _with_presets(line, due, None, priority, scheduled)
        if key is None:
            note = self.inbox(True)
            self.add_to_section(note.id, "Azioni", line)
            return {"id": note.id, "title": note.title, "project": None, "area": None}
        hub_id = reg.projects[key].note_id
        area = prj.key_of(area) if area else None
        with self.edit_lock:
            hub = self.read(hub_id)
            self._hub_insert(hub, area, line)
            self.save(hub)
        return {"id": hub.id, "title": hub.title, "project": key, "area": area}

    def postpone_late(self, today: date) -> tuple[int, list[str]]:
        """Sposta a domani le azioni di primo livello in ritardo, tranne quelle dei progetti in pausa o chiusi (la
        vista Azioni non le mostra). Una riga cambiata nel frattempo resta com'è."""
        tomorrow = dates.iso(today + timedelta(days=1))
        moved, ids = 0, []
        for row in self.actions(include_paused=False):
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

    def set_action_state(self, note_id: str, line_no: int, expected: str | None, status: str, today: date) -> dict:
        """Cambia lo stato dell'azione alla riga indicata: todo, doing, waiting, question, cancelled, done."""
        if status not in parser.STATUSES:
            raise QuickNotesError(f"Stato sconosciuto: {status}")
        with self.edit_lock:
            note = self.read(note_id)
            _check_line(note, line_no, expected)
            text = _change_line(note, line_no, lambda l: edit.with_status(l, status, dates.iso(today)))
            self.save(note)
            return {"note_id": note.id, "line": line_no, "text": text.strip(), "status": status,
                    "done": status == "done"}

    def set_action_status(self, note_id: str, action_text: str, done_on: date | None, status: str | None = None,
                          scheduled=_UNSET_ARG, today: date | None = None) -> dict:
        """Cambia lo stato di un'azione cercandola per testo dentro la nota. Lo usa il server MCP. Senza
        `status`, `done_on` la spunta (con una data) o la riapre (None), come prima."""
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
        today = today or date.today()
        if scheduled is not _UNSET_ARG:
            self.set_action_details(note_id, best[1], None, scheduled=scheduled)
        if status is not None:
            return self.set_action_state(note_id, best[1], None, status, done_on or today)
        if scheduled is not _UNSET_ARG:
            line = parser.lines_of(self.read(note_id).body)[best[1] - 1]
            m = parser.ACTION_RE.match(line)
            st = parser.STATUS_OF_MARK[m.group(2).lower()] if m else "todo"
            return {"note_id": note.id, "line": best[1], "text": line.strip(), "status": st, "done": st == "done"}
        return self.set_action_done(note_id, best[1], None, done_on)

    def complete_with_children(self, note_id: str, line_no: int, expected: str | None, today: date) -> int:
        """Chiude l'azione madre e le figlie aperte con una sola scrittura. Le figlie già chiuse conservano la
        loro data."""
        with self.edit_lock:
            note = self.read(note_id)
            _check_line(note, line_no, expected)
            day = dates.iso(today)
            targets = [a.line_no for a in parser.extract(note.body).actions
                       if not a.closed and (a.line_no == line_no or a.parent_line == line_no)]
            for line in targets:
                _change_line(note, line, lambda l: edit.with_checked(l, day))
            self.save(note)
            return len(targets)

    _UNSET = object()

    def set_action_details(self, note_id: str, line_no: int, expected: str | None, *, due=_UNSET,
                           person: tuple[int, str | None] | None = None, tag=_UNSET, priority=_UNSET,
                           description: str | None = None, scheduled=_UNSET) -> Note:
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
                if priority is not self._UNSET:
                    line = edit.with_priority(line, parser.priority_name(priority))
                if scheduled is not self._UNSET:
                    line = edit.with_scheduled(line, scheduled)
                return line
            _change_line(note, line_no, change)
            if description is not None:
                note.body = edit.with_description(note.body, line_no, description)
            self.save(note)
            return note

    # ---- progetti
    def registry(self) -> prj.Registry:
        return self._read(index.registry)

    def project(self, key: str) -> prj.Project:
        reg = self.registry()
        found = reg.match(key)
        if found is None:
            raise QuickNotesError(f"Progetto sconosciuto: {key}")
        return reg.projects[found]

    def project_rows(self) -> list[dict]:
        return self._read(index.project_rows)

    def logs(self, project: str, date_from: str | None = None) -> list[dict]:
        return self._read(index.logs, project, date_from)

    def create_project(self, name: str, aliases: list[str] | None = None, areas: list[str] | None = None,
                       status: str = "attivo") -> Note:
        """La nota di un progetto nuovo, in `progetti/`: frontmatter, obiettivo, prossime azioni per area."""
        name = " ".join(name.split())
        key = prj.key_of(name)
        if not key:
            raise QuickNotesError("Il nome del progetto non può essere vuoto")
        if self.registry().match(name) or self.registry().match(key):
            raise QuickNotesError(f"Il progetto {name} esiste già")
        meta, body = project_template(name, aliases, areas, status)
        with self.edit_lock:
            path = self._unique_path(key, self.root / "progetti")
            note = Note.new(path, meta, body)
            self.save(note)
        return note

    def set_project_status(self, key: str, status: str) -> Note:
        if status not in prj.PROJECT_STATUSES:
            raise QuickNotesError(f"Stato del progetto sconosciuto: {status}")
        project = self.project(key)
        with self.edit_lock:
            note = self.read(project.note_id)
            note.meta["status"] = status
            note.meta_dirty = True
            self.save(note)
            return note

    def _hub_insert(self, hub: Note, area: str | None, block: str) -> None:
        """Mette un blocco nella nota di progetto, sotto l'area; un'area nuova entra anche nel frontmatter."""
        area = prj.key_of(area) if area else None
        hub.body = edit.add_to_area(hub.body, area, block)
        if area:
            declared = parser.meta_list(hub.meta, "areas")
            if area not in [prj.key_of(a) for a in declared]:
                hub.meta["areas"] = [*declared, area]
                hub.meta_dirty = True

    def add_project_action(self, key: str, text: str, area: str | None = None) -> Note:
        """Una nuova azione nella nota di progetto, sotto l'area scelta."""
        project = self.project(key)
        text = text.strip()
        if not text:
            raise QuickNotesError("L'azione è vuota")
        line = text if parser.ACTION_RE.match(text) else f"- [ ] {text}"
        with self.edit_lock:
            hub = self.read(project.note_id)
            self._hub_insert(hub, area, line)
            self.save(hub)
            return hub

    def move_action(self, note_id: str, line_no: int, expected: str | None, target_id: str,
                    section: str | None = None) -> dict:
        """Sposta un'azione, con figlie e descrizione, in un'altra nota. In una nota di progetto va sotto
        `### <section>` in "Prossime azioni"; altrove in fondo alla sezione indicata. Nella nota di partenza resta
        `- ↗ testo → [[nota]]`. Si scrive prima la destinazione: se qualcosa va storto l'azione c'è due volte,
        non zero."""
        with self.edit_lock:
            src = self.read(note_id)
            _check_line(src, line_no, expected)
            target = self.read(target_id)
            if target.path == src.path:
                raise QuickNotesError("L'azione è già in questa nota")
            lines = parser.lines_of(src.body)
            start = line_no - 1
            m = parser.ACTION_RE.match(lines[start]) if 0 <= start < len(lines) else None
            if m is None:
                raise QuickNotesError(f"Alla riga {line_no} non c'è un'azione")
            end = edit.block_end(lines, start)
            block = "\n".join(edit.dedent_block(lines[start:end]))
            if target.note_type == "project":
                self._hub_insert(target, section, block)
            else:
                target.body = edit.add_to_section(target.body, section, block)
            self.save(target)
            indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
            shown = parser.action_display_text(m.group(3).strip())
            lines[start:end] = [f"{indent}- \u2197 {shown} \u2192 [[{target.id}|{target.title}]]"]
            src.body = "\n".join(lines) + ("\n" if src.body.endswith("\n") else "")
            self.save(src)
            return {"note_id": target.id, "title": target.title, "from": src.id}

    def archive_done(self, key: str, today: date) -> dict:
        """Sposta dalla nota di progetto all'archivio (`<progetto>.archivio.md`, accanto) le azioni chiuse di primo
        livello che hanno anche tutte le figlie chiuse, raggruppate per mese di completamento."""
        project = self.project(key)
        with self.edit_lock:
            hub = self.read(project.note_id)
            ex = parser.extract(hub.body)
            lines = parser.lines_of(hub.body)
            children: dict[int, list] = {}
            for a in ex.actions:
                if a.parent_line is not None:
                    children.setdefault(a.parent_line, []).append(a)
            picked = []
            for a in ex.actions:
                if a.parent_line is None and a.closed and all(c.closed for c in children.get(a.line_no, [])):
                    start = a.line_no - 1
                    picked.append((start, edit.block_end(lines, start), (a.done_on or dates.iso(today))[:7]))
            if not picked:
                return {"archived": 0, "archive_id": None}
            by_month: dict[str, list[str]] = {}
            for start, end, month in picked:
                by_month.setdefault(month, []).extend(edit.dedent_block(lines[start:end]))
            path = hub.path.with_name(f"{hub.id}.archivio.md")
            if path.exists():
                archive = self._read_path(path)
            else:
                archive = Note.new(path, {"type": "archivio", "title": f"{hub.title} · archivio",
                                          "project": project.key}, "")
            for month in sorted(by_month):
                archive.body = edit.add_to_section(archive.body, month, "\n".join(by_month[month]))
            self.save(archive)
            for start, end, _ in sorted(picked, reverse=True):
                del lines[start:end]
                # Niente righe vuote doppie dove c'era il blocco.
                if 0 < start < len(lines) and not lines[start].strip() and not lines[start - 1].strip():
                    del lines[start]
            hub.body = "\n".join(lines) + ("\n" if hub.body.endswith("\n") else "")
            self.save(hub)
            return {"archived": len(picked), "archive_id": archive.id}

    # ---- interrogazioni
    def search(self, text: str, flt: Filter | None = None, limit: int = 20) -> list[dict]:
        return self._read(index.search, text, flt or Filter(), limit)

    def list_notes(self, flt: Filter | None = None, limit: int = 50) -> list[dict]:
        return self._read(index.list_notes, flt or Filter(), limit)

    def actions(self, **query) -> list[dict]:
        try:
            return self._read(lambda db: index.actions(db, **query))
        except ValueError as e:
            raise QuickNotesError(str(e)) from None

    def done_since(self, day: str) -> int:
        return self._read(index.done_since, day)

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
