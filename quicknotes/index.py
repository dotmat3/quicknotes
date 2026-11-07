"""Indice SQLite: si può cancellare in ogni momento, perché si ricostruisce dai file."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from . import parser

if TYPE_CHECKING:
    from .store import Note

# 5: le righe di notes_fts hanno lo stesso rowid della nota, così si cancellano senza scorrere la tabella.
# 6: la priorità delle azioni.
SCHEMA_VERSION = 6
SCHEMA = """
CREATE TABLE IF NOT EXISTS notes(
    path TEXT PRIMARY KEY, id TEXT, type TEXT, title TEXT, date TEXT,
    project TEXT, mtime INTEGER, size INTEGER);
CREATE INDEX IF NOT EXISTS notes_id ON notes(id);
CREATE INDEX IF NOT EXISTS notes_date ON notes(date);
CREATE TABLE IF NOT EXISTS note_people(path TEXT, person TEXT, key TEXT);
CREATE INDEX IF NOT EXISTS note_people_path ON note_people(path);
CREATE INDEX IF NOT EXISTS note_people_key ON note_people(key);
CREATE TABLE IF NOT EXISTS note_tags(path TEXT, tag TEXT);
CREATE INDEX IF NOT EXISTS note_tags_path ON note_tags(path);
CREATE INDEX IF NOT EXISTS note_tags_tag ON note_tags(tag);
CREATE TABLE IF NOT EXISTS actions(
    path TEXT, line_no INTEGER, text TEXT, done INTEGER, owner TEXT, due TEXT,
    done_on TEXT, parent_line INTEGER, people TEXT, tags TEXT, description TEXT, priority TEXT);
CREATE INDEX IF NOT EXISTS actions_path ON actions(path);
CREATE INDEX IF NOT EXISTS actions_done ON actions(done, due);
CREATE TABLE IF NOT EXISTS decisions(path TEXT, line_no INTEGER, text TEXT);
CREATE INDEX IF NOT EXISTS decisions_path ON decisions(path);
CREATE TABLE IF NOT EXISTS links(path TEXT, line_no INTEGER, target TEXT, key TEXT, label TEXT, line TEXT);
CREATE INDEX IF NOT EXISTS links_path ON links(path);
CREATE INDEX IF NOT EXISTS links_key ON links(key);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    path UNINDEXED, title, body, people, tags, tokenize='unicode61 remove_diacritics 2');
"""
TABLES = ["notes", "note_people", "note_tags", "actions", "decisions", "links", "notes_fts"]


def open_db(path: Path) -> sqlite3.Connection:
    # Ogni connessione è protetta da un lock nell'archivio: si può usare da più thread.
    db = sqlite3.connect(path, timeout=10, check_same_thread=False, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA temp_store=MEMORY")
    return db


def init_schema(db: sqlite3.Connection) -> None:
    if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        clear(db)
    db.executescript(SCHEMA)
    db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def clear(db: sqlite3.Connection) -> None:
    for table in TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table}")
    db.executescript(SCHEMA)


def signatures(db: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    return {r[0]: (r[1], r[2]) for r in db.execute("SELECT path, mtime, size FROM notes")}


def delete_rows(db: sqlite3.Connection, rel: str) -> None:
    # Prima il testo pieno, che si trova dal rowid della nota: sul percorso non ha un indice.
    db.execute("DELETE FROM notes_fts WHERE rowid IN (SELECT rowid FROM notes WHERE path=?)", (rel,))
    for table in TABLES:
        if table != "notes_fts":
            db.execute(f"DELETE FROM {table} WHERE path=?", (rel,))


def path_for_id(db: sqlite3.Connection, note_id: str) -> str | None:
    row = db.execute("SELECT path FROM notes WHERE id=? OR path=? ORDER BY mtime DESC LIMIT 1",
                     (note_id, f"{note_id}.md")).fetchone()
    return row[0] if row else None


def _dedupe_ci(items) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out


def index_note(db: sqlite3.Connection, rel: str, note: Note, mtime: int, size: int, known: bool = True) -> None:
    """Le righe di una nota. `known=False` quando la nota non è ancora nell'indice: niente da cancellare."""
    ex = parser.extract(note.body)
    people = _dedupe_ci(note.people + ex.people)
    tags = _dedupe_ci([t.lstrip("#").lower() for t in note.tags] + ex.tags)
    if known:
        delete_rows(db, rel)
    rowid = db.execute("INSERT INTO notes(path,id,type,title,date,project,mtime,size) VALUES(?,?,?,?,?,?,?,?)",
                       (rel, note.id, note.note_type, note.title, note.date, note.project.lower(), mtime, size)).lastrowid
    db.executemany("INSERT INTO note_people VALUES(?,?,?)", [(rel, p, p.lower()) for p in people])
    db.executemany("INSERT INTO note_tags VALUES(?,?)", [(rel, t) for t in tags])
    db.executemany("INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [
        (rel, a.line_no, a.text, int(a.done), a.owner, a.due, a.done_on, a.parent_line,
         " ".join(a.people), " ".join(a.tags), a.description, a.priority) for a in ex.actions])
    db.executemany("INSERT INTO decisions VALUES(?,?,?)", [(rel, d.line_no, d.text) for d in ex.decisions])
    db.executemany("INSERT INTO links VALUES(?,?,?,?,?,?)", [
        (rel, l.line_no, l.target, l.target.lower(), l.label, l.line) for l in ex.links])
    db.execute("INSERT INTO notes_fts(rowid,path,title,body,people,tags) VALUES(?,?,?,?,?,?)",
               (rowid, rel, note.title, note.body, " ".join(people), " ".join(tags)))


# ------------------------------------------------------------------ interrogazioni


@dataclass
class Filter:
    """Filtri comuni. Le date sono AAAA-MM-GG, incluse."""
    date_from: str | None = None
    date_to: str | None = None
    person: str | None = None
    project: str | None = None
    note_type: str | None = None

    def sql(self, parts: list[str], args: list) -> None:
        if self.date_from:
            parts.append("substr(n.date,1,10) >= ?")
            args.append(self.date_from[:10])
        if self.date_to:
            parts.append("substr(n.date,1,10) <= ?")
            args.append(self.date_to[:10])
        if self.person:
            parts.append("n.path IN (SELECT path FROM note_people WHERE key LIKE ?)")
            args.append(f"%{self.person.lower().lstrip('@')}%")
        if self.project:
            p = self.project.lower().lstrip("#")
            parts.append("(n.project = ? OR n.path IN (SELECT path FROM note_tags WHERE tag = ?))")
            args.extend([p, p])
        if self.note_type:
            parts.append("n.type = ?")
            args.append(self.note_type)


def _where(parts: list[str]) -> str:
    return f"WHERE {' AND '.join(parts)}" if parts else ""


def _summary(db: sqlite3.Connection, r: sqlite3.Row, snippet: str | None = None) -> dict:
    people = [p[0] for p in db.execute("SELECT person FROM note_people WHERE path=?", (r["path"],))]
    out = {"id": r["id"], "title": r["title"], "type": r["type"], "date": r["date"],
           "project": r["project"] or None, "people": people, "path": r["path"]}
    if snippet is not None:
        out["snippet"] = snippet
    return out


def fts_query(query: str, op: str) -> str:
    terms, cur = [], ""
    for c in query:
        if c.isalnum() or c == "_" or (cur and c in "'’.-"):
            cur += c
        elif cur:
            terms.append(cur)
            cur = ""
    if cur:
        terms.append(cur)
    return f" {op} ".join(f'"{t}"*' for t in terms)


def search(db: sqlite3.Connection, text: str, flt: Filter, limit: int) -> list[dict]:
    """Ricerca testuale: prima tutte le parole, poi almeno una. Senza parole applica solo i filtri."""
    if not fts_query(text, "AND"):
        return list_notes(db, flt, limit)
    parts: list[str] = []
    filter_args: list = []
    flt.sql(parts, filter_args)
    extra = "".join(f"AND {p} " for p in parts)
    sql = ("SELECT n.*, snippet(notes_fts, 2, '«', '»', ' … ', 16) AS snip "
           "FROM notes_fts JOIN notes n ON n.path = notes_fts.path "
           f"WHERE notes_fts MATCH ? {extra}ORDER BY bm25(notes_fts, 0, 6.0, 1.0, 3.0, 3.0) LIMIT ?")
    for op in ("AND", "OR"):
        rows = db.execute(sql, [fts_query(text, op), *filter_args, limit]).fetchall()
        if rows:
            return [_summary(db, r, r["snip"]) for r in rows]
    return []


def list_notes(db: sqlite3.Connection, flt: Filter, limit: int) -> list[dict]:
    parts: list[str] = []
    args: list = []
    flt.sql(parts, args)
    rows = db.execute(f"SELECT n.* FROM notes n {_where(parts)} ORDER BY n.date DESC, n.mtime DESC LIMIT ?",
                      [*args, limit]).fetchall()
    return [_summary(db, r) for r in rows]


def _terms(text: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", text) if t]


def done_since(db: sqlite3.Connection, day: str) -> int:
    """Le azioni completate da quel giorno in poi (con la data `done:`), figlie comprese."""
    return db.execute("SELECT count(*) FROM actions WHERE done = 1 AND done_on >= ?", (day[:10],)).fetchone()[0]


def actions(db: sqlite3.Connection, status: str = "open", owner: str | None = None, project: str | None = None,
            due_before: str | None = None, date_from: str | None = None, date_to: str | None = None,
            text: str | None = None, limit: int = 100_000) -> list[dict]:
    """Le azioni, prima quelle con la scadenza più vicina. `status`: open, done, all."""
    parts: list[str] = []
    args: list = []
    Filter(date_from=date_from, date_to=date_to, project=project).sql(parts, args)
    if status == "open":
        parts.append("a.done = 0")
    elif status == "done":
        parts.append("a.done = 1")
    if owner:
        parts.append("lower(coalesce(a.owner,'')) LIKE ?")
        args.append(f"%{owner.lower().lstrip('@')}%")
    if due_before:
        parts.append("a.due IS NOT NULL AND a.due <= ?")
        args.append(due_before[:10])
    for term in _terms(text or ""):
        parts.append("lower(a.text) LIKE ?")
        args.append(f"%{term.lower()}%")
    rows = db.execute(
        f"SELECT a.*, n.id, n.title, n.date, n.project FROM actions a JOIN notes n ON n.path = a.path {_where(parts)} "
        "ORDER BY a.due IS NULL, a.due, n.date DESC, a.line_no LIMIT ?", [*args, limit]).fetchall()
    return [{
        "text": r["text"], "done": bool(r["done"]), "owner": r["owner"], "due": r["due"], "done_on": r["done_on"],
        "note_id": r["id"], "note_title": r["title"], "note_date": r["date"], "line": r["line_no"],
        "parent_line": r["parent_line"], "description": r["description"], "people": r["people"].split(),
        "tags": r["tags"].split(), "project": r["project"] or None, "priority": r["priority"],
    } for r in rows]


def decisions(db: sqlite3.Connection, flt: Filter, query: str, limit: int) -> list[dict]:
    parts: list[str] = []
    args: list = []
    flt.sql(parts, args)
    for term in _terms(query):
        parts.append("lower(d.text) LIKE ?")
        args.append(f"%{term.lower()}%")
    rows = db.execute(
        f"SELECT d.*, n.id, n.title, n.date, n.project FROM decisions d JOIN notes n ON n.path = d.path {_where(parts)} "
        "ORDER BY n.date DESC LIMIT ?", [*args, limit]).fetchall()
    return [{"text": r["text"], "line": r["line_no"], "note_id": r["id"], "note_title": r["title"],
             "date": r["date"], "project": r["project"] or None} for r in rows]


def _facets(db: sqlite3.Connection, sql: str) -> list[dict]:
    return [{"name": r[0], "notes": r[1], "last_seen": r[2]} for r in db.execute(sql)]


def people(db: sqlite3.Connection) -> list[dict]:
    return _facets(db, "SELECT max(p.person), count(DISTINCT p.path) AS c, max(n.date) FROM note_people p "
                       "JOIN notes n ON n.path = p.path GROUP BY p.key ORDER BY c DESC, 1")


def projects(db: sqlite3.Connection) -> list[dict]:
    return _facets(db, "SELECT name, count(DISTINCT path) AS c, max(date) FROM ("
                       "SELECT n.project AS name, n.path, n.date FROM notes n WHERE n.project <> '' "
                       "UNION ALL SELECT t.tag, t.path, n.date FROM note_tags t JOIN notes n ON n.path = t.path"
                       ") GROUP BY name ORDER BY c DESC, name")


def backlinks(db: sqlite3.Connection, note_id: str, title: str) -> list[dict]:
    """Le note che citano questa nota, per id o per titolo."""
    rows = db.execute(
        "SELECT n.id, n.title, n.date, l.line_no, l.line FROM links l JOIN notes n ON n.path = l.path "
        "WHERE l.key IN (?, ?) AND n.id <> ? ORDER BY n.date DESC, l.line_no",
        (note_id.lower(), title.lower(), note_id))
    return [{"note_id": r[0], "note_title": r[1], "date": r[2], "line": r[3], "text": r[4]} for r in rows]


def outgoing_links(db: sqlite3.Connection, rel: str) -> list[dict]:
    rows = db.execute(
        "SELECT l.target, l.label, n.id, n.title FROM links l "
        "LEFT JOIN notes n ON n.id = l.target OR lower(n.title) = l.key "
        "WHERE l.path = ? GROUP BY l.key ORDER BY min(l.line_no)", (rel,))
    return [{"target": r[0], "label": r[1], "note_id": r[2], "note_title": r[3]} for r in rows]


def graph_rows(db: sqlite3.Connection) -> dict:
    """Tutto quello che serve al grafo completo, letto in una volta."""
    def pairs(sql):
        return [(r[0] or "", r[1] or "") for r in db.execute(sql)]
    notes = [tuple(v or "" for v in r) for r in db.execute("SELECT path, id, title, type, date FROM notes")]
    return {"notes": notes, "links": pairs("SELECT DISTINCT path, key FROM links"),
            "people": pairs("SELECT DISTINCT path, person FROM note_people"),
            "tags": pairs("SELECT DISTINCT path, tag FROM note_tags")}
