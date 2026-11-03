"""Note su file e indice in memoria: la parte di quicknotes-core che serve alla prova.

I file sono gli stessi della versione Rust e si scrivono allo stesso modo: il frontmatter resta il testo
originale finché i metadati non cambiano, gli a capo restano quelli del file, la scrittura è atomica.
L'indice è in memoria e si ricostruisce dai file: non tocca `index-v3.db` della versione Rust.
"""

from __future__ import annotations

import os
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from . import dates

DUE_RE = re.compile(r"\b(?:due|entro|scadenza)\s*:\s*(\d{4}-\d{2}-\d{2})", re.I)
DONE_RE = re.compile(r"\bdone\s*:\s*(\d{4}-\d{2}-\d{2})", re.I)
DECISION_RE = re.compile(r"!(?:decisione|decision|dec)\b", re.I)
MD_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
ACTION_RE = re.compile(r"^(\s*)[-*+]\s+\[( |x|X)\]\s*(.*)$")


class NoteNotFound(Exception):
    def __init__(self, note_id: str):
        super().__init__(f"Nota non trovata: {note_id}")


# ------------------------------------------------------------------ formato


class _Loader(yaml.SafeLoader):
    """YAML senza conversione delle date: `date: 2026-10-27` resta testo, come in Rust."""


_Loader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def split_frontmatter(text: str) -> tuple[str, dict, str]:
    """(testo originale del frontmatter, metadati, corpo). Un frontmatter non valido resta nel corpo."""
    if not text.startswith("---"):
        return "", {}, text
    nl = text.find("\n", 3)
    if nl < 0 or text[3:nl].strip(" \t\r"):
        return "", {}, text
    start = pos = nl + 1
    for line in text[start:].splitlines(keepends=True):
        end = pos + len(line)
        if line.rstrip("\r\n \t") == "---":
            try:
                meta = yaml.load(text[start:pos], Loader=_Loader)
            except yaml.YAMLError:
                return "", {}, text
            if meta is None:
                meta = {}
            if not isinstance(meta, dict):
                return "", {}, text
            return text[:end], meta, text[end:]
        pos = end
    return "", {}, text


def render_frontmatter(meta: dict) -> str:
    clean = {k: v for k, v in meta.items() if v not in (None, "", [])}
    if not clean:
        return ""
    return "---\n" + yaml.safe_dump(clean, allow_unicode=True, sort_keys=False) + "---\n"


def meta_str(meta: dict, key: str) -> str | None:
    v = meta.get(key)
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def meta_list(meta: dict, key: str) -> list[str]:
    v = meta.get(key)
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    if isinstance(v, list):
        return [str(x).strip() for x in v if isinstance(x, (str, int, float)) and str(x).strip()]
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [str(v)]
    return []


def normalize_date(value: str) -> str:
    return value.strip().replace(" ", "T", 1)[:16]


def _is_word(c: str) -> bool:
    return c.isalnum() or c == "_"


def mentions(line: str) -> list[str]:
    """Le `@persone` di una riga, senza `@`."""
    out, prev, i = [], "", 0
    while i < len(line):
        c = line[i]
        if c == "@" and not (prev and (_is_word(prev) or prev in ".@")) and i + 1 < len(line) and _is_word(line[i + 1]):
            end = i + 1
            while end < len(line) and (_is_word(line[end]) or line[end] in "-."):
                end += 1
            name = line[i + 1:end].rstrip("-.")
            out.append(name)
        prev = c
        i += 1
    return out


def tags(line: str) -> list[str]:
    """Le `#etichette` di una riga, senza `#`."""
    out, prev = [], ""
    for i, c in enumerate(line):
        if c == "#" and not (prev and (_is_word(prev) or prev in "/#&")):
            end = i + 1
            if end < len(line) and _is_word(line[end]) and not line[end].isnumeric():
                end += 1
                while end < len(line) and (_is_word(line[end]) or line[end] in "-/"):
                    end += 1
                out.append(line[i + 1:end])
        prev = c
    return out


def _indent(line: str) -> int:
    width = 0
    for c in line:
        if c == " ":
            width += 1
        elif c == "\t":
            width += 4
        else:
            break
    return width


def _is_fence(line: str) -> bool:
    t = line.lstrip()
    return t.startswith("```") or t.startswith("~~~")


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out


@dataclass
class Action:
    line_no: int
    text: str
    done: bool
    due: str | None
    parent_line: int | None


@dataclass
class Link:
    line_no: int
    target: str
    label: str | None
    line: str


@dataclass
class Extracted:
    people: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


def _scan_wiki(line: str, line_no: int, out: Extracted) -> None:
    pos = 0
    while True:
        start = line.find("[[", pos)
        if start < 0:
            return
        end = line.find("]]", start + 2)
        if end < 0:
            return
        inner = line[start + 2:end].strip()
        embed = start > 0 and line[start - 1] == "!"
        if inner and not embed:
            target, _, label = inner.partition("|")
            out.links.append(Link(line_no, target.strip(), label.strip() or None, line.strip()))
        pos = end + 2


def extract(body: str) -> Extracted:
    """Persone, etichette, azioni e collegamenti, ignorando i blocchi di codice."""
    result = Extracted()
    in_fence = False
    top: tuple[int, int] | None = None  # indice dell'ultima azione di primo livello e suo rientro
    for idx, line in enumerate(body.split("\n")):
        line_no = idx + 1
        if _is_fence(line):
            in_fence = not in_fence
            top = None
            continue
        if in_fence:
            continue
        scan = MD_LINK_TARGET_RE.sub("]", line)
        line_people = mentions(scan)
        line_tags = [t.lower() for t in tags(scan)]
        result.people.extend(line_people)
        result.tags.extend(line_tags)
        _scan_wiki(line, line_no, result)
        width = _indent(line)
        m = ACTION_RE.match(line)
        if m and m.group(3).strip():
            text = m.group(3).strip()
            parent = result.actions[top[0]].line_no if top and width > top[1] else None
            due = DUE_RE.search(text)
            result.actions.append(Action(line_no, text, m.group(2).lower() == "x", due.group(1) if due else None, parent))
            if parent is None:
                top = (len(result.actions) - 1, width)
        elif line.strip() and width == 0:
            top = None
    result.people = _dedupe(result.people)
    result.tags = _dedupe(result.tags)
    return result


def first_h1(body: str) -> str | None:
    in_fence = False
    for line in body.split("\n"):
        if _is_fence(line):
            in_fence = not in_fence
        elif not in_fence and line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return None


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    out, dash = "", False
    for c in ascii_text.strip().lower():
        if c.isalnum():
            if dash and out:
                out += "-"
            dash = False
            out += c
        elif c in "-_" or c.isspace():
            dash = True
        if len(out) >= 50:
            break
    return out.strip("-") or "nota"


def _date_from_id(note_id: str) -> str | None:
    if dates.parse_day(note_id) is None:
        return None
    day = note_id[:10]
    if len(note_id) >= 15 and note_id[10] == "-" and note_id[11:15].isdigit():
        return f"{day}T{note_id[11:13]}:{note_id[13:15]}"
    return day


# ------------------------------------------------------------------ nota


class Note:
    def __init__(self, path: Path, text: str, mtime: float | None = None):
        self.crlf = "\r\n" in text
        if self.crlf:
            text = text.replace("\r\n", "\n")
        self.front_raw, self.meta, self.body = split_frontmatter(text)
        self.meta_dirty = False
        self.path = path
        self.id = path.stem
        self.title = meta_str(self.meta, "title") or first_h1(self.body) or self.id
        d = meta_str(self.meta, "date")
        self.date = (normalize_date(d) if d else None) or _date_from_id(self.id) or (
            datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M") if mtime else "")

    @classmethod
    def new(cls, path: Path, meta: dict, body: str) -> Note:
        note = cls(path, render_frontmatter(meta) + body)
        note.meta = meta
        return note

    @property
    def note_type(self) -> str:
        return meta_str(self.meta, "type") or "note"

    @property
    def people(self) -> list[str]:
        return meta_list(self.meta, "people")

    @property
    def project(self) -> str:
        return meta_str(self.meta, "project") or ""

    def text(self) -> str:
        front = render_frontmatter(self.meta) if self.meta_dirty else self.front_raw
        text = front + self.body
        return text.replace("\n", "\r\n") if self.crlf else text


# ------------------------------------------------------------------ indice in memoria


@dataclass
class Entry:
    rel: str
    id: str
    title: str
    date: str
    type: str
    project: str
    people: list[str]
    tags: list[str]
    links: list[Link]
    actions: list[Action]
    haystack: str  # titolo e corpo in minuscolo, per la ricerca
    sig: tuple[int, int]


def _entry(rel: str, note: Note, sig: tuple[int, int]) -> Entry:
    ex = extract(note.body)
    return Entry(
        rel=rel, id=note.id, title=note.title, date=note.date, type=note.note_type, project=note.project,
        people=_dedupe(note.people + ex.people),
        tags=_dedupe([t.lower() for t in meta_list(note.meta, "tags")] + ex.tags),
        links=ex.links, actions=ex.actions,
        haystack=(note.title + "\n" + note.body).lower(), sig=sig,
    )


def summary(e: Entry, snippet: str | None = None) -> dict:
    out = {"id": e.id, "title": e.title, "type": e.type, "date": e.date,
           "project": e.project or None, "people": e.people, "path": e.rel}
    if snippet:
        out["snippet"] = snippet
    return out


class NoteStore:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.lock = threading.RLock()
        self.entries: dict[str, Entry] = {}
        self.by_id: dict[str, str] = {}

    # ---- allineamento ai file
    def _scan(self) -> dict[str, tuple[int, int]]:
        found = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.endswith(".md") and not name.startswith("."):
                    full = os.path.join(dirpath, name)
                    try:
                        st = os.stat(full)
                    except OSError:
                        continue
                    rel = os.path.relpath(full, self.root).replace("\\", "/")
                    found[rel] = (st.st_mtime_ns, st.st_size)
        return found

    def refresh(self) -> list[str]:
        """Allinea l'indice ai file. Restituisce gli id delle note cambiate o sparite."""
        on_disk = self._scan()
        with self.lock:
            changed_ids = []
            for rel in [r for r in self.entries if r not in on_disk]:
                e = self.entries.pop(rel)
                if self.by_id.get(e.id) == rel:
                    del self.by_id[e.id]
                changed_ids.append(e.id)
            for rel, sig in on_disk.items():
                old = self.entries.get(rel)
                if old and old.sig == sig:
                    continue
                path = self.root / rel
                try:
                    text = read_text(path)
                except (OSError, UnicodeDecodeError):
                    continue
                note = Note(path, text, sig[0] / 1e9)
                self.entries[rel] = _entry(rel, note, sig)
                self.by_id[note.id] = rel
                changed_ids.append(note.id)
            return changed_ids

    def _rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    # ---- lettura e scrittura
    def _path_for_id(self, note_id: str) -> Path | None:
        note_id = note_id.strip().removesuffix(".md")
        rel = self.by_id.get(note_id)
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
        return Note(path, read_text(path), path.stat().st_mtime)

    def save(self, note: Note) -> None:
        note.path.parent.mkdir(parents=True, exist_ok=True)
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
        rel = self._rel(note.path)
        with self.lock:
            # Si rilegge dal disco: l'indice vede esattamente ciò che è scritto.
            self.entries[rel] = _entry(rel, self._read_path(note.path), (st.st_mtime_ns, st.st_size))
            self.by_id[note.id] = rel

    def _unique_path(self, base: str, folder: Path) -> Path:
        candidate, n = base, 2
        while (folder / f"{candidate}.md").exists() or candidate in self.by_id:
            candidate = f"{base}-{n}"
            n += 1
        return folder / f"{candidate}.md"

    def create_note(self, title: str, note_type: str = "meeting", body: str = "",
                    when: datetime | None = None) -> Note:
        when = when or datetime.now()
        note_type = note_type or "meeting"
        title = title.strip() or ("Meeting" if note_type == "meeting" else "Nota")
        folder = self.root / when.strftime("%Y") / when.strftime("%m")
        path = self._unique_path(f"{when.strftime('%Y-%m-%d-%H%M')}-{slugify(title)}", folder)
        meta = {"type": note_type, "title": title, "date": when.strftime("%Y-%m-%dT%H:%M"),
                "people": [], "project": "", "tags": []}
        if body and not body.endswith("\n"):
            body += "\n"
        with self.lock:
            note = Note.new(path, meta, body)
            self.save(note)
        return note

    def daily(self, day: date, create: bool) -> Note | None:
        note_id = f"{day.isoformat()}-giornata"
        path = self.root / day.strftime("%Y") / day.strftime("%m") / f"{note_id}.md"
        if path.exists():
            return self._read_path(path)
        try:
            return self.read(note_id)
        except NoteNotFound:
            if not create:
                return None
        with self.lock:
            if path.exists():
                return self._read_path(path)
            meta = {"type": "daily", "title": dates.daily_file_title(day), "date": day.isoformat()}
            note = Note.new(path, meta, "")
            self.save(note)
            return note

    def save_if_unchanged(self, note_id: str, base: str, body: str) -> dict:
        """Salva solo se il file contiene ancora `base`; altrimenti restituisce il testo su disco."""
        with self.lock:
            note = self.read(note_id)
            if note.body == body:
                return {"status": "saved"}
            if note.body != base:
                return {"status": "conflict", "disk": note.body}
            note.body = body
            self.save(note)
            return {"status": "saved"}

    def save_conflict_copy(self, note_id: str, body: str) -> Note:
        note = self.read(note_id)
        now = datetime.now()
        return self.create_note(f"{note.title} (conflitto {now.strftime('%H:%M')})", "note", body, now)

    # ---- interrogazioni
    def _sorted(self) -> list[Entry]:
        return sorted(self.entries.values(), key=lambda e: (e.date, e.sig[0]), reverse=True)

    def list_notes(self, limit: int) -> list[dict]:
        with self.lock:
            return [summary(e) for e in self._sorted()[:limit]]

    def search(self, text: str, limit: int) -> list[dict]:
        words = [w for w in re.split(r"\s+", text.lower()) if w]
        if not words:
            return self.list_notes(limit)
        with self.lock:
            scored = []
            for e in self._sorted():
                if all(w in e.haystack for w in words):
                    title = e.title.lower()
                    scored.append((-sum(w in title for w in words), len(scored), e))
            scored.sort(key=lambda s: s[:2])
            return [summary(e) for *_, e in scored[:limit]]

    def _facets(self, pairs) -> list[dict]:
        acc: dict[str, dict] = {}
        for name, e in pairs:
            f = acc.setdefault(name.lower(), {"name": name, "paths": set(), "last_seen": None})
            f["name"] = max(f["name"], name)
            f["paths"].add(e.rel)
            f["last_seen"] = max(f["last_seen"] or "", e.date) or None
        out = [{"name": f["name"], "notes": len(f["paths"]), "last_seen": f["last_seen"]} for f in acc.values()]
        out.sort(key=lambda f: (-f["notes"], f["name"]))
        return out

    def people(self) -> list[dict]:
        with self.lock:
            return self._facets((p, e) for e in self.entries.values() for p in e.people)

    def projects(self) -> list[dict]:
        with self.lock:
            pairs = [(e.project, e) for e in self.entries.values() if e.project]
            pairs += [(t, e) for e in self.entries.values() for t in e.tags]
            return self._facets(pairs)

    def open_actions(self) -> list[Action]:
        with self.lock:
            return [a for e in self.entries.values() for a in e.actions if not a.done and a.parent_line is None]

    def backlinks(self, note_id: str, title: str) -> list[dict]:
        keys = {note_id.lower(), title.lower()}
        with self.lock:
            rows = [{"note_id": e.id, "note_title": e.title, "date": e.date, "line": l.line_no, "text": l.line}
                    for e in self.entries.values() if e.id != note_id
                    for l in e.links if l.target.lower() in keys]
        rows.sort(key=lambda r: r["line"])
        rows.sort(key=lambda r: r["date"], reverse=True)
        return rows

    def outgoing_links(self, note_id: str) -> list[dict]:
        with self.lock:
            rel = self.by_id.get(note_id)
            entry = self.entries.get(rel) if rel else None
            if not entry:
                return []
            titles = {e.title.lower(): e for e in self.entries.values()}
            out, seen = [], set()
            for l in entry.links:
                key = l.target.lower()
                if key in seen:
                    continue
                seen.add(key)
                target_rel = self.by_id.get(l.target)
                found = self.entries.get(target_rel) if target_rel else titles.get(key)
                out.append({"target": l.target, "label": l.label,
                            "note_id": found.id if found else None, "note_title": found.title if found else None})
            return out

    # ---- immagini
    def save_image(self, note_id: str, data: bytes) -> str:
        if len(data) > 50 * 1024 * 1024:
            raise ValueError(f"Immagine troppo grande: {len(data) // (1024 * 1024)} MB, il massimo è 50")
        kind = sniff(data)
        if not kind:
            raise ValueError("Non è un'immagine PNG, JPEG, GIF, WebP o BMP")
        note = self.read(note_id)
        folder = note.path.parent / "images"
        folder.mkdir(parents=True, exist_ok=True)
        stem = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        for n in range(1, 1000):
            name = f"{stem}.{kind[0]}" if n == 1 else f"{stem}-{n}.{kind[0]}"
            try:
                with open(folder / name, "xb") as f:
                    f.write(data)
                return f"images/{name}"
            except FileExistsError:
                continue
        raise ValueError("Troppe immagini con lo stesso nome")

    def resolve_image(self, rel: str) -> tuple[Path, str] | None:
        """Un'immagine vera dentro la cartella delle note, oppure None."""
        parts = rel.split("/")
        if any(p in ("", ".", "..") or ":" in p for p in parts):
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


def read_text(path: Path) -> str:
    """Il testo così com'è: `read_text` convertirebbe gli a capo di Windows e il file cambierebbe forma."""
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


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
