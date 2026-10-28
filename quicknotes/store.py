"""Archivio delle note: i file Markdown sono la fonte di verita', SQLite e' solo un indice.

L'indice (<cartella note>/.quicknotes/index.db) si aggiorna da solo confrontando data
di modifica e dimensione dei file, quindi le note possono essere modificate anche con
qualsiasi altro editor. Se lo cancelli viene ricostruito al prossimo accesso.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from . import parser

SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS notes(
    path TEXT PRIMARY KEY, id TEXT, type TEXT, title TEXT, date TEXT,
    project TEXT, mtime REAL, size INTEGER);
CREATE INDEX IF NOT EXISTS notes_id ON notes(id);
CREATE INDEX IF NOT EXISTS notes_date ON notes(date);
CREATE TABLE IF NOT EXISTS note_people(path TEXT, person TEXT, key TEXT);
CREATE INDEX IF NOT EXISTS note_people_path ON note_people(path);
CREATE TABLE IF NOT EXISTS note_tags(path TEXT, tag TEXT);
CREATE INDEX IF NOT EXISTS note_tags_path ON note_tags(path);
CREATE TABLE IF NOT EXISTS actions(path TEXT, line_no INTEGER, text TEXT, done INTEGER, owner TEXT, due TEXT);
CREATE INDEX IF NOT EXISTS actions_path ON actions(path);
CREATE TABLE IF NOT EXISTS decisions(path TEXT, line_no INTEGER, text TEXT);
CREATE INDEX IF NOT EXISTS decisions_path ON decisions(path);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    path UNINDEXED, title, body, people, tags, tokenize='unicode61 remove_diacritics 2');
"""
CHILD_TABLES = ("note_people", "note_tags", "actions", "decisions", "notes_fts")

WEEKDAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
NOTE_TYPES = ("meeting", "daily", "note")
FILENAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d{2})(\d{2}))?")
HEADING_RE = re.compile(r"^#\s+(.+)$", re.M)


@dataclass
class Note:
    id: str
    path: Path
    meta: dict
    body: str

    @property
    def type(self) -> str:
        return str(self.meta.get("type") or "note")

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.id)

    @property
    def date(self) -> str:
        return parser.normalize_date(self.meta.get("date"))

    @property
    def people(self) -> list[str]:
        return parser.as_list(self.meta.get("people"))

    @property
    def project(self) -> str:
        return str(self.meta.get("project") or "")

    @property
    def tags(self) -> list[str]:
        return parser.as_list(self.meta.get("tags"))

    def text(self) -> str:
        return parser.render(self.meta, self.body)


class NoteNotFound(KeyError):
    pass


class NoteStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        index_dir = self.root / ".quicknotes"
        index_dir.mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(index_dir / "index.db", check_same_thread=False, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=10000")
        self._init_schema()
        self.refresh()

    # ------------------------------------------------------------------ indice
    def _init_schema(self) -> None:
        with self._lock, self._db:
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version != SCHEMA_VERSION:
                for table in ("notes",) + CHILD_TABLES:
                    self._db.execute(f"DROP TABLE IF EXISTS {table}")
            self._db.executescript(SCHEMA)
            self._db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def _rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def _scan(self) -> dict[str, tuple[float, int]]:
        found = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.endswith(".md") and not name.startswith("."):
                    full = Path(dirpath) / name
                    try:
                        st = full.stat()
                    except OSError:
                        continue
                    found[self._rel(full)] = (st.st_mtime, st.st_size)
        return found

    def refresh(self) -> int:
        """Allinea l'indice ai file su disco. Restituisce il numero di file reindicizzati."""
        with self._lock:
            on_disk = self._scan()
            indexed = {r["path"]: (r["mtime"], r["size"]) for r in
                       self._db.execute("SELECT path, mtime, size FROM notes")}
            changed = [p for p, sig in on_disk.items() if indexed.get(p) != sig]
            removed = [p for p in indexed if p not in on_disk]
            if not changed and not removed:
                return 0
            with self._db:
                for rel in removed:
                    self._delete_rows(rel)
                for rel in changed:
                    self._index(rel, *on_disk[rel])
            return len(changed)

    def _delete_rows(self, rel: str) -> None:
        self._db.execute("DELETE FROM notes WHERE path=?", (rel,))
        for table in CHILD_TABLES:
            self._db.execute(f"DELETE FROM {table} WHERE path=?", (rel,))

    def _index(self, rel: str, mtime: float, size: int) -> None:
        try:
            text = (self.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        note = self._make_note(self.root / rel, text, mtime)
        ex = parser.extract(note.body)
        people = parser._dedupe(note.people + ex.people)
        tags = parser._dedupe([t.lower().lstrip("#") for t in note.tags] + ex.tags)
        self._delete_rows(rel)
        self._db.execute(
            "INSERT INTO notes(path,id,type,title,date,project,mtime,size) VALUES(?,?,?,?,?,?,?,?)",
            (rel, note.id, note.type, note.title, note.date, note.project.lower(), mtime, size))
        self._db.executemany("INSERT INTO note_people VALUES(?,?,?)",
                             [(rel, p, p.lower()) for p in people])
        self._db.executemany("INSERT INTO note_tags VALUES(?,?)", [(rel, t) for t in tags])
        self._db.executemany("INSERT INTO actions VALUES(?,?,?,?,?,?)",
                             [(rel, a.line_no, a.text, int(a.done), a.owner, a.due) for a in ex.actions])
        self._db.executemany("INSERT INTO decisions VALUES(?,?,?)",
                             [(rel, d.line_no, d.text) for d in ex.decisions])
        self._db.execute("INSERT INTO notes_fts(path,title,body,people,tags) VALUES(?,?,?,?,?)",
                         (rel, note.title, note.body, " ".join(people), " ".join(tags)))

    def _make_note(self, path: Path, text: str, mtime: float | None = None) -> Note:
        meta, body = parser.split_frontmatter(text)
        note_id = path.stem
        if not meta.get("date"):
            m = FILENAME_DATE_RE.match(note_id)
            if m:
                meta["date"] = m.group(1) + (f"T{m.group(2)}:{m.group(3)}" if m.group(2) else "")
            elif mtime:
                meta["date"] = dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M")
        if not meta.get("title"):
            h = HEADING_RE.search(body)
            meta["title"] = h.group(1).strip() if h else note_id
        return Note(id=note_id, path=path, meta=meta, body=body)

    # ------------------------------------------------------------ lettura/scrittura
    def _path_for_id(self, note_id: str) -> Path | None:
        note_id = note_id.strip().removesuffix(".md")
        row = self._db.execute("SELECT path FROM notes WHERE id=? OR path=? ORDER BY mtime DESC LIMIT 1",
                               (note_id, note_id + ".md")).fetchone()
        return self.root / row["path"] if row else None

    def read(self, note_id: str) -> Note:
        with self._lock:
            path = self._path_for_id(note_id)
            if path is None or not path.exists():
                self.refresh()
                path = self._path_for_id(note_id)
            if path is None or not path.exists():
                raise NoteNotFound(f"Nota non trovata: {note_id}")
            # titolo e data mancanti vengono dedotti (intestazione, nome file) e,
            # al primo salvataggio, scritti esplicitamente nel frontmatter
            return self._make_note(path, path.read_text(encoding="utf-8"), path.stat().st_mtime)

    def save(self, note: Note) -> Note:
        """Scrive la nota su disco (in modo atomico) e aggiorna l'indice."""
        with self._lock:
            note.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=note.path.parent, prefix=".tmp-", suffix=".md")
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(note.text())
            os.replace(tmp, note.path)
            st = note.path.stat()
            with self._db:
                self._index(self._rel(note.path), st.st_mtime, st.st_size)
            return note

    def _unique_path(self, base_id: str, folder: Path) -> tuple[str, Path]:
        candidate, n = base_id, 2
        while (folder / f"{candidate}.md").exists() or self._path_for_id(candidate):
            candidate, n = f"{base_id}-{n}", n + 1
        return candidate, folder / f"{candidate}.md"

    def create_note(self, title: str, body: str = "", note_type: str = "meeting",
                    people: list[str] | None = None, project: str | None = None,
                    tags: list[str] | None = None, when: dt.datetime | None = None,
                    extra_meta: dict | None = None) -> Note:
        when = when or dt.datetime.now()
        title = (title or "").strip() or ("Meeting" if note_type == "meeting" else "Nota")
        folder = self.root / f"{when:%Y}" / f"{when:%m}"
        with self._lock:
            note_id, path = self._unique_path(f"{when:%Y-%m-%d-%H%M}-{parser.slugify(title)}", folder)
            meta = {"type": note_type, "title": title, "date": when.strftime("%Y-%m-%dT%H:%M"),
                    "people": list(people or []), "project": project or "", "tags": list(tags or [])}
            meta.update(extra_meta or {})
            body = body if body.endswith("\n") or not body else body + "\n"
            return self.save(Note(id=note_id, path=path, meta=meta, body=body))

    def daily(self, day: dt.date | str | None = None, create: bool = True) -> Note | None:
        """Nota della giornata (una per data), creata se manca."""
        if isinstance(day, str):
            day = dt.date.fromisoformat(day[:10])
        day = day or dt.date.today()
        note_id = f"{day.isoformat()}-giornata"
        with self._lock:
            try:
                return self.read(note_id)
            except NoteNotFound:
                if not create:
                    return None
            title = f"Giornata di {WEEKDAYS_IT[day.weekday()]} {day:%d/%m/%Y}"
            path = self.root / f"{day:%Y}" / f"{day:%m}" / f"{note_id}.md"
            return self.save(Note(id=note_id, path=path,
                                  meta={"type": "daily", "title": title, "date": day.isoformat()},
                                  body=""))

    def update(self, note_id: str, body: str | None = None, meta: dict | None = None) -> Note:
        with self._lock:
            note = self.read(note_id)
            if body is not None:
                note.body = body
            if meta:
                note.meta.update(meta)
            return self.save(note)

    def append(self, note_id: str, text: str, heading: str | None = None) -> Note:
        with self._lock:
            note = self.read(note_id)
            block = text.strip("\n")
            if heading:
                block = f"### {heading}\n{block}"
            base = note.body.rstrip("\n")
            note.body = (base + "\n\n" if base else "") + block + "\n"
            return self.save(note)

    def append_to_daily(self, text: str, day: dt.date | str | None = None,
                        timestamp: bool = True) -> Note:
        note = self.daily(day)
        text = text.strip()
        now = dt.datetime.now().strftime("%H:%M")
        if timestamp and "\n" not in text and not text.startswith(("-", "*", "#")):
            return self.append(note.id, f"- {now} {text}")
        return self.append(note.id, text, heading=now if timestamp else None)

    def note_files(self, note_id: str) -> list[Path]:
        """Il file della nota seguito dalle sue registrazioni audio (audio/<id>-HHMMSS.wav)."""
        note = self.read(note_id)
        audio_dir = note.path.parent / "audio"
        audio_re = re.compile(re.escape(note.id) + r"-\d{6}\.wav")
        audio = sorted(p for p in audio_dir.glob("*.wav") if audio_re.fullmatch(p.name)) if audio_dir.is_dir() else []
        return [note.path, *audio]

    def delete(self, note_id: str, discard=None) -> list[Path]:
        """Elimina una nota e le sue registrazioni. `discard(path)` decide come rimuovere ogni file
        (l'app li sposta nel Cestino); di default vengono cancellati. Restituisce i file rimossi."""
        discard = discard or (lambda p: p.unlink())
        with self._lock:
            files = self.note_files(note_id)
            rel = self._rel(files[0])
            discard(files[0])  # se fallisce non si tocca nient'altro
            with self._db:
                self._delete_rows(rel)
            for path in files[1:]:
                try:
                    discard(path)
                except OSError:
                    pass  # un audio rimasto non deve bloccare l'eliminazione della nota
            return files

    def set_action_status(self, note_id: str, action_text: str, done: bool) -> dict:
        """Spunta (o riapre) un'azione cercandola per testo dentro la nota."""
        with self._lock:
            note = self.read(note_id)
            lines = note.body.split("\n")
            wanted = action_text.strip().lower()
            matches = []
            for i, line in enumerate(lines):
                m = parser.ACTION_RE.match(line)
                if m:
                    text = m.group(2).strip().lower()
                    score = 2 if text == wanted else 1 if wanted and wanted in text else 0
                    if score:
                        matches.append((score, i))
            if not matches:
                raise NoteNotFound(f"Nessuna azione che contenga '{action_text}' in {note_id}")
            _, idx = max(matches)
            lines[idx] = re.sub(r"\[( |x|X)\]", "[x]" if done else "[ ]", lines[idx], count=1)
            note.body = "\n".join(lines)
            self.save(note)
            return {"note_id": note.id, "line": idx + 1, "text": lines[idx].strip(), "done": done}

    # ---------------------------------------------------------------- interrogazioni
    @staticmethod
    def _filters(date_from=None, date_to=None, person=None, project=None, note_type=None):
        where, params = [], []
        if date_from:
            where.append("substr(n.date,1,10) >= ?")
            params.append(str(date_from)[:10])
        if date_to:
            where.append("substr(n.date,1,10) <= ?")
            params.append(str(date_to)[:10])
        if person:
            where.append("n.path IN (SELECT path FROM note_people WHERE key LIKE ?)")
            params.append(f"%{person.lower().lstrip('@')}%")
        if project:
            p = project.lower().lstrip("#")
            where.append("(n.project = ? OR n.path IN (SELECT path FROM note_tags WHERE tag = ?))")
            params += [p, p]
        if note_type:
            where.append("n.type = ?")
            params.append(note_type)
        return where, params

    def _people_of(self, rel: str) -> list[str]:
        return [r[0] for r in self._db.execute("SELECT person FROM note_people WHERE path=?", (rel,))]

    def _row_to_summary(self, row, snippet: str | None = None) -> dict:
        out = {"id": row["id"], "title": row["title"], "type": row["type"], "date": row["date"],
               "project": row["project"] or None, "people": self._people_of(row["path"]),
               "path": row["path"]}
        if snippet is not None:
            out["snippet"] = snippet
        return out

    @staticmethod
    def _fts_query(query: str, op: str) -> str:
        terms = re.findall(r"\w[\w'’.\-]*", query, re.U)
        return f" {op} ".join('"' + t.replace('"', "") + '"*' for t in terms)

    def search(self, query: str = "", date_from=None, date_to=None, person=None, project=None,
               note_type=None, limit: int = 20) -> list[dict]:
        """Ricerca testuale (tutte le parole, poi almeno una) con filtri opzionali."""
        with self._lock:
            self.refresh()
            where, params = self._filters(date_from, date_to, person, project, note_type)
            if not query.strip():
                return self.list_notes(date_from, date_to, person, project, note_type, limit)
            for op in ("AND", "OR"):
                fts = self._fts_query(query, op)
                if not fts:
                    return self.list_notes(date_from, date_to, person, project, note_type, limit)
                sql = ("SELECT n.*, snippet(notes_fts, 2, '«', '»', ' … ', 16) AS snip "
                       "FROM notes_fts JOIN notes n ON n.path = notes_fts.path "
                       "WHERE notes_fts MATCH ? " + "".join(f"AND {w} " for w in where) +
                       "ORDER BY bm25(notes_fts, 0, 6.0, 1.0, 3.0, 3.0) LIMIT ?")
                rows = self._db.execute(sql, [fts, *params, limit]).fetchall()
                if rows:
                    return [self._row_to_summary(r, r["snip"]) for r in rows]
            return []

    def list_notes(self, date_from=None, date_to=None, person=None, project=None,
                   note_type=None, limit: int = 50) -> list[dict]:
        with self._lock:
            self.refresh()
            where, params = self._filters(date_from, date_to, person, project, note_type)
            sql = ("SELECT n.* FROM notes n " + ("WHERE " + " AND ".join(where) if where else "") +
                   " ORDER BY n.date DESC, n.mtime DESC LIMIT ?")
            return [self._row_to_summary(r) for r in self._db.execute(sql, [*params, limit])]

    def actions(self, status: str = "open", owner=None, project=None, due_before=None,
                date_from=None, date_to=None, limit: int = 200) -> list[dict]:
        with self._lock:
            self.refresh()
            where, params = self._filters(date_from, date_to, None, project, None)
            if status == "open":
                where.append("a.done = 0")
            elif status == "done":
                where.append("a.done = 1")
            if owner:
                where.append("lower(coalesce(a.owner,'')) LIKE ?")
                params.append(f"%{owner.lower().lstrip('@')}%")
            if due_before:
                where.append("a.due IS NOT NULL AND a.due <= ?")
                params.append(str(due_before)[:10])
            sql = ("SELECT a.*, n.id, n.title, n.date FROM actions a JOIN notes n ON n.path = a.path " +
                   ("WHERE " + " AND ".join(where) if where else "") +
                   " ORDER BY a.due IS NULL, a.due, n.date DESC LIMIT ?")
            return [{"text": r["text"], "done": bool(r["done"]), "owner": r["owner"], "due": r["due"],
                     "note_id": r["id"], "note_title": r["title"], "note_date": r["date"],
                     "line": r["line_no"]} for r in self._db.execute(sql, [*params, limit])]

    def decisions(self, date_from=None, date_to=None, person=None, project=None,
                  query: str = "", limit: int = 100) -> list[dict]:
        with self._lock:
            self.refresh()
            where, params = self._filters(date_from, date_to, person, project, None)
            for term in re.findall(r"\w+", query or ""):
                where.append("lower(d.text) LIKE ?")
                params.append(f"%{term.lower()}%")
            sql = ("SELECT d.*, n.id, n.title, n.date, n.project FROM decisions d "
                   "JOIN notes n ON n.path = d.path " +
                   ("WHERE " + " AND ".join(where) if where else "") +
                   " ORDER BY n.date DESC LIMIT ?")
            return [{"text": r["text"], "note_id": r["id"], "note_title": r["title"],
                     "date": r["date"], "project": r["project"] or None}
                    for r in self._db.execute(sql, [*params, limit])]

    def people(self) -> list[dict]:
        with self._lock:
            self.refresh()
            sql = ("SELECT max(p.person) AS name, count(DISTINCT p.path) AS notes, max(n.date) AS last "
                   "FROM note_people p JOIN notes n ON n.path = p.path GROUP BY p.key ORDER BY notes DESC")
            return [{"name": r["name"], "notes": r["notes"], "last_seen": r["last"]}
                    for r in self._db.execute(sql)]

    def projects(self) -> list[dict]:
        with self._lock:
            self.refresh()
            sql = ("SELECT name, count(DISTINCT path) AS notes, max(date) AS last FROM ("
                   " SELECT n.project AS name, n.path, n.date FROM notes n WHERE n.project <> ''"
                   " UNION ALL SELECT t.tag, t.path, n.date FROM note_tags t JOIN notes n ON n.path = t.path"
                   ") GROUP BY name ORDER BY notes DESC")
            return [{"name": r["name"], "notes": r["notes"], "last_seen": r["last"]}
                    for r in self._db.execute(sql)]

    def counts(self, today: str | None = None) -> dict:
        """Numero di note per tipo, in totale e con data odierna (per la barra laterale)."""
        today = today or dt.date.today().isoformat()
        with self._lock:
            self.refresh()
            out = {"all": 0, "today": 0, **{t: 0 for t in NOTE_TYPES}}
            sql = "SELECT type, count(*) AS n, sum(substr(date,1,10) = ?) AS today FROM notes GROUP BY type"
            for r in self._db.execute(sql, (today,)):
                out[r["type"]] = out.get(r["type"], 0) + r["n"]
                out["all"] += r["n"]
                out["today"] += r["today"] or 0
            return out

    def previews(self, paths: list[str], length: int = 400) -> dict[str, str]:
        """Inizio del testo delle note indicate (per l'anteprima nell'elenco)."""
        if not paths:
            return {}
        with self._lock:
            sql = (f"SELECT path, substr(body, 1, ?) AS body FROM notes_fts "
                   f"WHERE path IN ({','.join('?' * len(paths))})")
            return {r["path"]: r["body"] or "" for r in self._db.execute(sql, [length, *paths])}

    def close(self) -> None:
        with self._lock:
            self._db.close()
