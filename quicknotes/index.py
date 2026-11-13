"""Indice SQLite: si può cancellare in ogni momento, perché si ricostruisce dai file."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from . import parser
from . import projects as prj
from .projects import HIDDEN_STATUSES, Registry

if TYPE_CHECKING:
    from .store import Note

# 5: le righe di notes_fts hanno lo stesso rowid della nota, così si cancellano senza scorrere la tabella.
# 6: la priorità delle azioni.
# 7: stati, `scheduled:`, progetto e aree delle azioni; progetti, log dei daily, progetto delle decisioni.
SCHEMA_VERSION = 7
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
    done_on TEXT, parent_line INTEGER, people TEXT, tags TEXT, description TEXT, priority TEXT,
    status TEXT, scheduled TEXT, project TEXT, topics TEXT, seen_key TEXT);
CREATE INDEX IF NOT EXISTS actions_path ON actions(path);
CREATE INDEX IF NOT EXISTS actions_done ON actions(done, due);
CREATE INDEX IF NOT EXISTS actions_project ON actions(project);
CREATE TABLE IF NOT EXISTS decisions(path TEXT, line_no INTEGER, text TEXT, project TEXT);
CREATE INDEX IF NOT EXISTS decisions_path ON decisions(path);
CREATE TABLE IF NOT EXISTS projects(
    path TEXT, key TEXT, title TEXT, status TEXT, aliases TEXT, areas TEXT, note_id TEXT);
CREATE INDEX IF NOT EXISTS projects_path ON projects(path);
CREATE TABLE IF NOT EXISTS logs(path TEXT, line_no INTEGER, text TEXT, project TEXT, topics TEXT, date TEXT);
CREATE INDEX IF NOT EXISTS logs_path ON logs(path);
CREATE INDEX IF NOT EXISTS logs_project ON logs(project);
CREATE TABLE IF NOT EXISTS links(path TEXT, line_no INTEGER, target TEXT, key TEXT, label TEXT, line TEXT);
CREATE INDEX IF NOT EXISTS links_path ON links(path);
CREATE INDEX IF NOT EXISTS links_key ON links(key);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    path UNINDEXED, title, body, people, tags, tokenize='unicode61 remove_diacritics 2');
"""
TABLES = ["notes", "note_people", "note_tags", "actions", "decisions", "links", "notes_fts", "projects", "logs"]
# Fuori da TABLES: sopravvive alla ricostruzione dell'indice. Ricorda da quando un'azione esiste e da quando ha
# il suo stato, per i task fermi e le attese lunghe; la chiave è il testo, così un'azione spostata la conserva.
SEEN_SCHEMA = """
CREATE TABLE IF NOT EXISTS action_seen(key TEXT PRIMARY KEY, first_seen TEXT, status TEXT, status_since TEXT);
"""


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
    db.executescript(SEEN_SCHEMA)
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


def registry(db: sqlite3.Connection) -> Registry:
    """I progetti nell'indice."""
    return Registry([prj.Project(key=r[0], title=r[1], status=r[2], aliases=r[3].split("\n") if r[3] else [],
                                      areas=r[4].split() if r[4] else [], path=r[5], note_id=r[6])
                     for r in db.execute("SELECT key, title, status, aliases, areas, path, note_id FROM projects")])


def project_paths(db: sqlite3.Connection) -> set[str]:
    return {r[0] for r in db.execute("SELECT path FROM projects")}


def seen_key(text: str) -> str:
    """La chiave di un'azione per `action_seen`: il testo senza date né priorità, senza maiuscole."""
    return " ".join(parser.action_display_text(text).lower().split())


def _remember(db: sqlite3.Connection, key: str, status: str, born: str, today: str) -> None:
    row = db.execute("SELECT status FROM action_seen WHERE key=?", (key,)).fetchone()
    if row is None:
        db.execute("INSERT INTO action_seen VALUES(?,?,?,?)", (key, born, status, born))
    elif row[0] != status:
        db.execute("UPDATE action_seen SET status=?, status_since=? WHERE key=?", (status, today, key))


def index_note(db: sqlite3.Connection, rel: str, note: Note, mtime: int, size: int, known: bool = True,
               reg: Registry | None = None, today: str | None = None) -> None:
    """Le righe di una nota. `known=False` quando la nota non è ancora nell'indice: niente da cancellare.
    `reg` sono i progetti conosciuti; senza, si leggono dall'indice."""
    from datetime import date as _date
    today = today or _date.today().isoformat()
    ex = parser.extract(note.body)
    people = _dedupe_ci(note.people + ex.people)
    tags = _dedupe_ci([t.lstrip("#").lower() for t in note.tags] + ex.tags)
    if known:
        delete_rows(db, rel)
    own = prj.from_note(note)
    reg = reg if reg is not None else registry(db)
    if own is not None and own.key not in reg.projects:
        reg = Registry([*reg.projects.values(), own])
    note_project = own.key if own else (reg.match(note.project) or note.project.lower() or None)
    rowid = db.execute("INSERT INTO notes(path,id,type,title,date,project,mtime,size) VALUES(?,?,?,?,?,?,?,?)",
                       (rel, note.id, note.note_type, note.title, note.date, note_project or "", mtime, size)).lastrowid
    db.executemany("INSERT INTO note_people VALUES(?,?,?)", [(rel, p, p.lower()) for p in people])
    db.executemany("INSERT INTO note_tags VALUES(?,?)", [(rel, t) for t in tags])
    if own is not None:
        db.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?)",
                   (rel, own.key, own.title, own.status, "\n".join(own.aliases), " ".join(own.areas), note.id))

    resolved: dict[int, str | None] = {}
    rows = []
    born = (note.date or "")[:10] or today
    born = min(born, today)
    for a in ex.actions:
        project, topics = prj.resolve(reg, a.tags, a.headings, a.inherited_tags,
                                           resolved.get(a.parent_line) if a.parent_line else None, note_project)
        resolved[a.line_no] = project
        key = seen_key(a.text)
        _remember(db, key, a.status, born, today)
        rows.append((rel, a.line_no, a.text, int(a.done), a.owner, a.due, a.done_on, a.parent_line,
                     " ".join(a.people), " ".join(a.tags), a.description, a.priority,
                     a.status, a.scheduled, project, " ".join(topics), key))
    db.executemany("INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    db.executemany("INSERT INTO decisions VALUES(?,?,?,?)", [
        (rel, d.line_no, d.text, prj.resolve(reg, d.tags, d.headings, note_project=note_project)[0])
        for d in ex.decisions])
    if note.note_type == "daily" or note.id.endswith("-giornata"):
        logs = []
        for l in ex.logs:
            project, topics = prj.resolve(reg, l.tags, l.headings, note_project=note_project)
            if project:
                logs.append((rel, l.line_no, l.text, project, " ".join(topics), (note.date or "")[:10]))
        db.executemany("INSERT INTO logs VALUES(?,?,?,?,?,?)", logs)
    db.executemany("INSERT INTO links VALUES(?,?,?,?,?,?)", [
        (rel, l.line_no, l.target, l.target.lower(), l.label, l.line) for l in ex.links])
    db.execute("INSERT INTO notes_fts(rowid,path,title,body,people,tags) VALUES(?,?,?,?,?,?)",
               (rowid, rel, note.title, note.body, " ".join(people), " ".join(tags)))


# ------------------------------------------------------------------ interrogazioni


def _like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass
class Filter:
    """Filtri comuni. Le date sono AAAA-MM-GG, incluse. `project` comprende le sue aree (`#progetto/area`),
    `topic` è un'area o un'etichetta in qualsiasi progetto."""
    date_from: str | None = None
    date_to: str | None = None
    person: str | None = None
    project: str | None = None
    note_type: str | None = None
    topic: str | None = None

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
            parts.append("(n.project = ? OR n.path IN (SELECT path FROM note_tags WHERE tag = ? OR tag LIKE ? ESCAPE '\\') "
                         "OR n.path IN (SELECT path FROM actions WHERE project = ?) "
                         "OR n.path IN (SELECT path FROM decisions WHERE project = ?) "
                         "OR n.path IN (SELECT path FROM logs WHERE project = ?))")
            args.extend([p, p, f"{_like(p)}/%", p, p, p])
        if self.topic:
            t = self.topic.lower().lstrip("#")
            parts.append("n.path IN (SELECT path FROM note_tags WHERE tag = ? OR tag LIKE ? ESCAPE '\\')")
            args.extend([t, f"%/{_like(t)}"])
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


def _status_sql(status: str | list[str] | None, parts: list[str], args: list) -> None:
    """`open` (non chiuse), `closed` (fatte o annullate), `done`, `all`, uno stato o un elenco di stati."""
    names = [status] if isinstance(status, str) else list(status or ["all"])
    if "all" in names:
        return
    wanted: set[str] = set()
    for n in names:
        if n == "open":
            wanted.update(s for s in parser.STATUSES if s not in parser.CLOSED)
        elif n == "closed":
            wanted.update(parser.CLOSED)
        elif n in parser.STATUSES:
            wanted.add(n)
        else:
            raise ValueError(f"Stato sconosciuto: {n}")
    parts.append(f"a.status IN ({','.join('?' * len(wanted))})")
    args.extend(sorted(wanted))


def actions(db: sqlite3.Connection, status: str | list[str] = "open", owner: str | None = None,
            project: str | None = None, due_before: str | None = None, date_from: str | None = None,
            date_to: str | None = None, text: str | None = None, limit: int = 100_000, topic: str | None = None,
            scheduled_before: str | None = None, include_paused: bool = True) -> list[dict]:
    """Le azioni, prima quelle con la scadenza più vicina. `status`: open, closed, done, all, oppure uno o più
    stati (todo, doing, waiting, question, cancelled, done). `project` vale anche per le sue aree, `topic` per
    un'area in tutti i progetti. Senza `include_paused` restano fuori i progetti in pausa o chiusi."""
    parts: list[str] = []
    args: list = []
    Filter(date_from=date_from, date_to=date_to).sql(parts, args)
    _status_sql(status, parts, args)
    if project:
        p = project.lower().lstrip("#")
        parts.append("(a.project = ? OR (' ' || a.tags || ' ') LIKE ? ESCAPE '\\' OR (' ' || a.tags || ' ') LIKE ? ESCAPE '\\')")
        args.extend([p, f"% {_like(p)} %", f"% {_like(p)}/%"])
    if topic:
        t = topic.lower().lstrip("#")
        parts.append("((' ' || a.topics || ' ' || a.tags || ' ') LIKE ? ESCAPE '\\' "
                     "OR (' ' || a.tags || ' ') LIKE ? ESCAPE '\\')")
        args.extend([f"% {_like(t)} %", f"%/{_like(t)} %"])
    if scheduled_before:
        parts.append("a.scheduled IS NOT NULL AND a.scheduled <= ?")
        args.append(scheduled_before[:10])
    if not include_paused:
        parts.append(f"coalesce(p.status, 'attivo') NOT IN ({','.join('?' * len(HIDDEN_STATUSES))})")
        args.extend(HIDDEN_STATUSES)
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
        "SELECT a.*, n.id, n.title, n.date, n.type AS note_type, p.status AS project_status, "
        "s.first_seen, s.status_since FROM actions a JOIN notes n ON n.path = a.path "
        "LEFT JOIN (SELECT key, max(status) AS status FROM projects GROUP BY key) p ON p.key = a.project "
        f"LEFT JOIN action_seen s ON s.key = a.seen_key {_where(parts)} "
        "ORDER BY a.due IS NULL, a.due, n.date DESC, a.line_no LIMIT ?", [*args, limit]).fetchall()
    reg = registry(db)

    def written(tags: list[str], project: str | None) -> bool:
        """Il progetto è scritto nella riga come etichetta (anche con un alias o come `#progetto/area`)."""
        heads = (t.partition("/")[0] for t in tags)
        return bool(project) and any((reg.match(h) or prj.key_of(h)) == project for h in heads)

    out = []
    for r in rows:
        topics = r["topics"].split() if r["topics"] else []
        tags = r["tags"].split()
        out.append({
            "text": r["text"], "done": bool(r["done"]), "owner": r["owner"], "due": r["due"], "done_on": r["done_on"],
            "note_id": r["id"], "note_title": r["title"], "note_date": r["date"], "line": r["line_no"],
            "parent_line": r["parent_line"], "description": r["description"], "people": r["people"].split(),
            "tags": tags, "project": r["project"] or None, "project_in_text": written(tags, r["project"]),
            "priority": r["priority"],
            "status": r["status"], "scheduled": r["scheduled"], "topics": topics,
            "area": topics[0] if topics else None, "project_status": r["project_status"],
            "note_type": r["note_type"], "first_seen": r["first_seen"], "status_since": r["status_since"],
        })
    return out


def decisions(db: sqlite3.Connection, flt: Filter, query: str, limit: int) -> list[dict]:
    parts: list[str] = []
    args: list = []
    # Il progetto di una decisione è il suo, se ce l'ha; altrimenti quello della nota.
    project = flt.project.lower().lstrip("#") if flt.project else None
    Filter(date_from=flt.date_from, date_to=flt.date_to, person=flt.person, note_type=flt.note_type,
           topic=flt.topic).sql(parts, args)
    if project:
        parts.append("(d.project = ? OR (d.project IS NULL AND (n.project = ? OR n.path IN "
                     "(SELECT path FROM note_tags WHERE tag = ? OR tag LIKE ? ESCAPE '\\'))))")
        args.extend([project, project, project, f"{_like(project)}/%"])
    for term in _terms(query):
        parts.append("lower(d.text) LIKE ?")
        args.append(f"%{term.lower()}%")
    rows = db.execute(
        f"SELECT d.*, n.id, n.title, n.date FROM decisions d JOIN notes n ON n.path = d.path {_where(parts)} "
        "ORDER BY n.date DESC LIMIT ?", [*args, limit]).fetchall()
    return [{"text": r["text"], "line": r["line_no"], "note_id": r["id"], "note_title": r["title"],
             "date": r["date"], "project": r["project"] or None} for r in rows]


def _facets(db: sqlite3.Connection, sql: str) -> list[dict]:
    return [{"name": r[0], "notes": r[1], "last_seen": r[2]} for r in db.execute(sql)]


def people(db: sqlite3.Connection) -> list[dict]:
    return _facets(db, "SELECT max(p.person), count(DISTINCT p.path) AS c, max(n.date) FROM note_people p "
                       "JOIN notes n ON n.path = p.path GROUP BY p.key ORDER BY c DESC, 1")


def project_rows(db: sqlite3.Connection) -> list[dict]:
    """Le note di progetto con il numero di azioni aperte, per area."""
    out = []
    for r in db.execute("SELECT key, title, status, aliases, areas, note_id, path FROM projects ORDER BY title"):
        counts: dict[str, int] = {}
        total = 0
        for a in db.execute("SELECT topics FROM actions WHERE project = ? AND status NOT IN ('done','cancelled')",
                            (r[0],)):
            total += 1
            area = a[0].split()[0] if a[0] else ""
            counts[area] = counts.get(area, 0) + 1
        out.append({"key": r[0], "title": r[1], "status": r[2], "aliases": r[3].split("\n") if r[3] else [],
                    "areas": r[4].split() if r[4] else [], "note_id": r[5], "path": r[6], "open": total,
                    "open_by_area": counts})
    return out


def logs(db: sqlite3.Connection, project: str, date_from: str | None = None) -> list[dict]:
    rows = db.execute("SELECT l.*, n.id FROM logs l JOIN notes n ON n.path = l.path WHERE l.project = ? "
                      "AND (? IS NULL OR l.date >= ?) ORDER BY l.date DESC, l.line_no",
                      (project, date_from, date_from))
    return [{"text": r["text"], "date": r["date"], "line": r["line_no"], "note_id": r["id"],
             "topics": r["topics"].split() if r["topics"] else []} for r in rows]


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
