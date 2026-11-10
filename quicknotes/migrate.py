"""Migrazione delle note scritte prima della 0.6.0: stati, note di progetto, etichette ripetute.

Funziona in due tempi, come la vista Migrazione dell'app e `scripts/migra_note.py`:

1. `plan(root)` legge le note e propone, senza scrivere nulla:
   - le modifiche alle righe, una per regola (vedi RULES), ognuna con il testo prima e dopo;
   - i progetti da creare, ricavati dalle intestazioni dei daily e dalle etichette usate fuori da un progetto,
     con le aree prese dalle etichette usate nelle loro azioni.
2. `apply(store, choices)` fa una copia della cartella, crea i progetti scelti e applica le righe scelte. Una
   riga cambiata dopo la proposta non si tocca: torna tra le "saltate".

Le regole cambiano solo la riga indicata e, nella riga, solo quello che serve: frontmatter, a capo e il resto
del file restano com'erano. Le scelte di contenuto (chiudere un task superato, spostarne un altro) restano alla
Revisione nell'app o a Claude via MCP.
"""

from __future__ import annotations

import os
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import dates, edit, parser
from . import projects as prj
from .store import Note, NoteStore, QuickNotesError, read_text


@dataclass(frozen=True)
class Rule:
    key: str
    title: str
    description: str
    default: bool


RULES = [
    Rule("cancelled", "Annullate", "Le azioni [x] con «Deprecato» nel testo o nella descrizione diventano [-] annullate.", True),
    Rule("question", "Domande", "Le azioni aperte [ ] il cui testo finisce con ? diventano [?] domande.", True),
    Rule("redundant_tag", "Etichette ripetute",
         "Sotto l’intestazione di un progetto l’etichetta del progetto sulla riga non serve: si toglie. "
         "La riga resta nello stesso progetto.", False),
]
RULE_KEYS = {r.key for r in RULES}

# Intestazioni che l'app scrive da sé o che non sono progetti.
NOT_PROJECTS = {"priorita", "note", "trascrizioni", "prossime-azioni", "obiettivo", "note-collegate", "decisioni",
                "azioni", "todo", "log", "varie", "altro", "appunti", "riunioni", "meeting", "oggi", "domani"}
TIME_HEADING = re.compile(r"^\d{1,2}[:.]\d{2}$")
# Sopra questa soglia un progetto proposto parte già scelto.
MIN_NOTES, MIN_ACTIONS = 2, 3
# Un progetto senza attività da più giorni di così si propone in pausa.
PAUSE_AFTER_DAYS = 30


@dataclass
class Edit:
    id: str
    rule: str
    rel: str
    line: int  # nel file, da 1, frontmatter compreso
    before: str
    after: str
    note_id: str
    note_title: str
    project: str | None = None  # per redundant_tag: vale solo se il progetto esiste o viene creato


@dataclass
class Candidate:
    key: str
    title: str
    sources: set[str] = field(default_factory=set)  # heading, tag
    notes: set[str] = field(default_factory=set)
    actions: int = 0
    open: int = 0
    lines: int = 0  # righe di log
    last: str = ""
    topics: Counter = field(default_factory=Counter)


# ------------------------------------------------------------------ regole sulle righe


def _set_mark(line: str, mark: str) -> str:
    m = parser.ACTION_RE.match(line)
    if not m:
        return line
    box = m.start(2) - 1
    return line[:box] + f"[{mark}]" + line[box + 3:]


_TRAILING = re.compile(r"(?:\s+[#@][\w\-/.]+)+\s*$")


def _asks(text: str) -> bool:
    """Il testo dell'azione finisce con ?, anche se dopo vengono etichette, persone o date."""
    return _TRAILING.sub("", parser.action_display_text(text)).rstrip().endswith("?")


def _drop_tag(line: str, project: str) -> str:
    """La riga senza le etichette `#progetto` (non quelle gerarchiche `#progetto/area`, che portano l'area)."""
    out = line
    for start, end in reversed(parser.tag_spans(line)):
        name = line[start + 1:end]
        if "/" not in name and prj.key_of(name) == project:
            out = out[:start] + out[end:]
    return edit._squeeze(out) if out != line else line  # noqa: SLF001 - stessa pulizia degli spazi delle modifiche


def transform(rule: str, line: str, project: str | None = None) -> str:
    """Una regola applicata a una riga."""
    if rule == "cancelled":
        return _set_mark(line, "-")
    if rule == "question":
        return _set_mark(line, "?")
    if rule == "redundant_tag":
        return _drop_tag(line, project or "")
    raise ValueError(f"Regola sconosciuta: {rule}")


# ------------------------------------------------------------------ lettura


def _scan(root: Path) -> dict[str, tuple[str, Note]]:
    """Testo e nota di ogni file .md, saltando file e cartelle nascosti come fa l'app."""
    out = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.startswith(".") or not name.endswith(".md"):
                continue
            path = Path(folder) / name
            try:
                text = read_text(path)
            except (OSError, UnicodeDecodeError):
                continue
            out[path.relative_to(root).as_posix()] = (text, Note(path, text))
    return out


def _is_daily(note: Note) -> bool:
    return note.note_type == "daily" or note.id.endswith("-giornata")


def _project_heading(text: str) -> bool:
    k = prj.key_of(text)
    return bool(k) and k not in NOT_PROJECTS and not TIME_HEADING.match(text.strip()) \
        and not text.lower().startswith("trascrizione")


def _resolve_all(notes: dict[str, Note], reg: prj.Registry):
    """Per ogni azione e riga di log: (rel, nota, elemento, progetto, aree)."""
    for rel, note in notes.items():
        own = prj.from_note(note)
        note_project = own.key if own else (reg.match(note.project) or note.project.lower() or None)
        ex = parser.extract(note.body)
        resolved: dict[int, str | None] = {}
        for a in ex.actions:
            project, topics = prj.resolve(reg, a.tags, a.headings, a.inherited_tags,
                                          resolved.get(a.parent_line) if a.parent_line else None, note_project)
            resolved[a.line_no] = project
            yield rel, note, a, project, topics
        if _is_daily(note):
            for line in ex.logs:
                project, topics = prj.resolve(reg, line.tags, line.headings, note_project=note_project)
                yield rel, note, line, project, topics


# ------------------------------------------------------------------ proposta


def plan(root: Path, today: date | None = None) -> dict:
    """Tutto quello che la migrazione propone, senza scrivere nulla. Il risultato va bene così com'è per la pagina."""
    today = today or date.today()
    files = _scan(root)
    notes = {rel: note for rel, (_, note) in files.items()}
    existing = [p for p in (prj.from_note(n) for n in notes.values()) if p]
    existing_keys = {p.key for p in existing}

    # 1. Progetti dalle intestazioni dei daily che hanno righe sotto.
    cands: dict[str, Candidate] = {}

    def cand(name: str, source: str) -> Candidate | None:
        k = prj.key_of(name)
        if not k or k in existing_keys or prj.Registry(existing).match(name):
            return None
        c = cands.setdefault(k, Candidate(k, name.strip().lstrip("#")))
        if source == "heading" and "heading" not in c.sources:
            c.title = name.strip()  # il nome scritto nell'intestazione è il più leggibile
        c.sources.add(source)
        return c

    for note in notes.values():
        if not _is_daily(note):
            continue
        ex = parser.extract(note.body)
        used = {h for a in ex.actions for h in a.headings[:1]} | {h for l in ex.logs for h in l.headings[:1]}
        for h in ex.headings:
            if h.level <= 2 and h.text in used and _project_heading(h.text):
                cand(h.text, "heading")

    # 2. Etichette usate dove nessuna intestazione o nota dice il progetto.
    reg = prj.Registry(existing + [prj.Project(c.key, c.title) for c in cands.values()])
    for _, _, item, project, _ in _resolve_all(notes, reg):
        if project is None:
            for t in item.tags:
                head = t.split("/")[0]
                if _project_heading(head):
                    cand(head, "tag")

    # 3. Con tutti i candidati: quante azioni, in quante note, quando l'ultima volta, quali aree.
    reg = prj.Registry(existing + [prj.Project(c.key, c.title) for c in cands.values()])
    for rel, note, item, project, topics in _resolve_all(notes, reg):
        c = cands.get(project)
        if c is None:
            continue
        c.notes.add(rel)
        c.last = max(c.last, (note.date or "")[:10])
        if isinstance(item, parser.Action):
            c.actions += 1
            c.open += not item.closed
        else:
            c.lines += 1
        c.topics.update(t for t in topics if "/" not in t and not reg.match(t))

    proposals = []
    for c in sorted(cands.values(), key=lambda c: (-len(c.notes), -c.actions, c.key)):
        if not c.actions and not c.lines:
            continue
        last = dates.parse_day(c.last)
        idle = (today - last).days if last else None
        strong = len(c.notes) >= MIN_NOTES or c.actions >= MIN_ACTIONS
        proposals.append({
            "key": c.key, "title": c.title, "sources": sorted(c.sources), "notes": len(c.notes),
            "actions": c.actions, "open": c.open, "lines": c.lines, "last": c.last or None, "idle_days": idle,
            "status": "pausa" if idle is not None and idle > PAUSE_AFTER_DAYS else "attivo",
            "areas": [{"name": t, "count": n, "selected": n >= 2} for t, n in c.topics.most_common()],
            "selected": strong,
        })

    # 4. Le righe, regola per regola, sul testo originale del file.
    edits: list[Edit] = []
    for rel, (raw, note) in files.items():
        lines = raw.splitlines(keepends=True)
        offset = note.front_raw.count("\n")  # le righe del frontmatter prima del corpo
        ex = parser.extract(note.body)

        def add(rule: str, body_line: int, project: str | None = None) -> None:
            i = offset + body_line - 1
            if i >= len(lines):
                return
            before = lines[i].rstrip("\r\n")
            after = transform(rule, before, project)
            if after != before:
                title = dates.daily_title(dates.parse_day(note.date)) if _is_daily(note) and dates.parse_day(note.date) else note.title
                edits.append(Edit(f"{rel}:{i + 1}:{rule}", rule, rel, i + 1, before, after, note.id, title, project))

        for a in ex.actions:
            if a.status == "done" and ("deprecat" in a.text.lower() or "deprecat" in a.description.lower()):
                add("cancelled", a.line_no)
            elif a.status == "todo" and _asks(a.text):
                add("question", a.line_no)
        # Etichetta del progetto ripetuta sotto la sua intestazione (azioni e righe di log).
        for item in [*ex.actions, *(ex.logs if _is_daily(note) else [])]:
            heading_project = next((reg.match(h) for h in reversed(item.headings) if reg.match(h)), None)
            if heading_project and any("/" not in t and reg.match(t) == heading_project for t in item.tags):
                add("redundant_tag", item.line_no, heading_project)

    edits.sort(key=lambda e: (e.rule, e.rel, e.line))
    counts = Counter(e.rule for e in edits)
    return {
        "root": str(root),
        "rules": [{"key": r.key, "title": r.title, "description": r.description, "default": r.default,
                   "count": counts[r.key]} for r in RULES],
        "edits": [e.__dict__ for e in edits],
        "projects": proposals,
        "existing": [{"key": p.key, "title": p.title, "status": p.status} for p in existing],
        "notes": len(notes),
    }


def default_choices(proposal: dict) -> dict:
    """Le scelte predefinite: le regole attive di default e i progetti proposti come scelti."""
    rules = {r["key"] for r in proposal["rules"] if r["default"]}
    projects = [{"title": p["title"], "from_key": p["key"], "status": p["status"],
                 "areas": [a["name"] for a in p["areas"] if a["selected"]]}
                for p in proposal["projects"] if p["selected"]]
    keys = {p["from_key"] for p in projects} | {p["key"] for p in proposal["existing"]}
    edits = [e for e in proposal["edits"] if e["rule"] in rules and (e["project"] is None or e["project"] in keys)]
    return {"projects": projects, "edits": [{"id": e["id"], "before": e["before"]} for e in edits]}


# ------------------------------------------------------------------ applicazione


def backup(root: Path, now: datetime | None = None) -> Path:
    """Una copia completa della cartella delle note, accanto a lei, senza l'indice (si ricostruisce)."""
    base = root.parent / f"{root.name}-copia-{(now or datetime.now()).strftime('%Y%m%d-%H%M')}"
    dest, n = base, 2
    while dest.exists():
        dest = base.with_name(f"{base.name}-{n}")
        n += 1
    shutil.copytree(root, dest, ignore=shutil.ignore_patterns(".quicknotes"))
    return dest


def apply(store: NoteStore, choices: dict, now: datetime | None = None, make_backup: bool = True) -> dict:
    """Applica le scelte: `projects` [{title, status, aliases?, areas}] e `edits` [{id, before}] presi da `plan`.
    Prima la copia della cartella, poi i progetti, poi le righe, file per file. Restituisce cosa è stato fatto."""
    root = store.root
    wanted = [e for e in choices.get("edits", []) if isinstance(e, dict) and e.get("id")]
    projects = [p for p in choices.get("projects", []) if isinstance(p, dict) and str(p.get("title", "")).strip()]
    if not wanted and not projects:
        raise QuickNotesError("Niente da applicare: scegli almeno un progetto o una riga")
    # Prima di scrivere qualsiasi cosa: nessun progetto deve esistere già, né comparire due volte.
    reg = store.registry()
    seen: set[str] = set()
    for p in projects:
        k = prj.key_of(str(p["title"]))
        if not k or reg.match(str(p["title"])) or k in seen:
            raise QuickNotesError(f"Il progetto {p['title']} esiste già o è scelto due volte")
        seen.add(k)
    fresh = {e["id"]: e for e in plan(root)["edits"]}
    copy = backup(root, now) if make_backup else None

    created = []
    for p in projects:
        note = store.create_project(str(p["title"]), [str(a) for a in p.get("aliases") or []],
                                    [str(a) for a in p.get("areas") or []], str(p.get("status") or "attivo"))
        created.append({"id": note.id, "title": note.title, "key": parser.meta_str(note.meta, "project")})
    # `from_key` è la chiave proposta: se il titolo è stato cambiato, le righe legate a lei valgono ancora.
    keys = ({c["key"] for c in created} | {str(p["from_key"]) for p in projects if p.get("from_key")}
            | set(store.registry().projects))

    # Le righe scelte, per file. Una riga che non è più quella proposta si salta.
    by_file: dict[str, list[dict]] = {}
    skipped = []
    for w in wanted:
        e = fresh.get(w["id"])
        if e is None or e["before"] != w.get("before") or e["rule"] not in RULE_KEYS:
            skipped.append(w["id"])
            continue
        if e["project"] is not None and e["project"] not in keys:
            skipped.append(w["id"])
            continue
        by_file.setdefault(e["rel"], []).append(e)

    changed_ids, applied = [], 0
    with store.edit_lock:
        for rel, items in by_file.items():
            path = root / rel
            raw = read_text(path)
            lines = raw.splitlines(keepends=True)
            # Più regole sulla stessa riga si applicano una dopo l'altra, partendo dal testo proposto.
            for line_no in sorted({e["line"] for e in items}):
                i = line_no - 1
                ending = lines[i][len(lines[i].rstrip("\r\n")):]
                current = lines[i].rstrip("\r\n")
                same = [e for e in items if e["line"] == line_no]
                if current != same[0]["before"]:
                    skipped.extend(e["id"] for e in same)
                    continue
                for e in sorted(same, key=lambda e: [r.key for r in RULES].index(e["rule"])):
                    current = transform(e["rule"], current, e["project"])
                    applied += 1
                lines[i] = current + ending
            text = "".join(lines)
            if text != raw:
                tmp = path.with_name(f".tmp-migra-{path.name}")
                with open(tmp, "w", encoding="utf-8", newline="") as f:
                    f.write(text)
                os.replace(tmp, path)
                changed_ids.append(path.stem)
    store.refresh()
    return {"backup": str(copy) if copy else None, "projects": created, "applied": applied, "skipped": skipped,
            "changed": changed_ids + [c["id"] for c in created]}
