"""Dati pronti per le viste dell'interfaccia."""

from __future__ import annotations

import re
from datetime import date, timedelta

from . import dates, parser
from .index import Filter
from .projects import HIDDEN_STATUSES
from .store import NoteStore

# Le azioni fatte senza data di completamento possono diventare centinaia: se ne mostrano poche.
UNDATED_DONE_LIMIT = 30


def _children_of(rows: list[dict]) -> dict[tuple[str, int], list[dict]]:
    children: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        if row["parent_line"] is not None:
            children.setdefault((row["note_id"], row["parent_line"]), []).append(row)
    return children


def _label(due: str | None, today: date) -> tuple[str, str] | None:
    d = dates.parse_day(due)
    return dates.due_label(d, today) if d else None


def _closed(row: dict) -> bool:
    return row["status"] in parser.CLOSED


def _board_item(row: dict, children: dict, today: date) -> dict:
    """Una scheda della bacheca: la stessa in bacheca, in elenco, in Agenda e nelle pagine etichetta e progetto."""
    label = _label(row["due"], today)
    planned = _label(row["scheduled"], today)
    subs = sorted(({
        "line": s["line"], "raw": s["text"], "text": parser.action_display_text(s["text"]), "done": s["done"],
        "status": s["status"], "closed": _closed(s), "due_label": (_label(s["due"], today) or (None,))[0],
    } for s in children.get((row["note_id"], row["line"]), [])), key=lambda s: s["line"])
    tag = row["tags"][0] if row["tags"] else None
    return {
        "note_id": row["note_id"], "note_title": row["note_title"], "line": row["line"], "raw": row["text"],
        # Le #etichette restano dove sono scritte: l'interfaccia le mostra come mini pillole dentro il testo.
        "text": parser.action_display_text(row["text"]), "done": row["done"], "done_on": row["done_on"], "due": row["due"],
        "due_label": label[0] if label else None, "due_level": label[1] if label else None,
        "group": dates.due_group(dates.parse_day(row["due"]), today), "people": row["people"],
        "priority": row["priority"], "status": row["status"], "closed": _closed(row),
        "scheduled": row["scheduled"], "scheduled_label": planned[0] if planned else None,
        "project": row["project"], "project_in_text": row.get("project_in_text", False),
        "topics": row["topics"], "area": row["area"],
        "project_status": row["project_status"], "is_daily": _is_daily(row), "note_type": row["note_type"],
        "inbox": _is_inbox(row, today),
        "tag": tag or row["project"], "description": row["description"], "subs": subs,
    }


def action_board(store: NoteStore, today: date) -> dict:
    """Tutte le azioni di primo livello con le loro figlie."""
    rows = store.actions(status="all")
    children = _children_of(rows)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    open_, late, done_week, undated = 0, 0, 0, 0
    items = []
    for row in rows:
        if row["parent_line"] is not None:
            continue
        done_on = dates.parse_day(row["done_on"])
        if _closed(row):
            if row["done"] and done_on and monday <= done_on <= sunday:
                done_week += 1
            if done_on is None:
                undated += 1
                if undated > UNDATED_DONE_LIMIT:
                    continue
        item = _board_item(row, children, today)
        if not _closed(row):
            open_ += 1
            late += item["group"] == "late"
        items.append(item)
    column_due = {}
    for g in ("soon", "week", "later"):
        d = dates.first_day_in(g, today)
        if d:
            column_due[g] = dates.iso(d)
    return {"items": items, "open": open_, "late": late, "done_this_week": done_week,
            "week_number": today.isocalendar()[1], "column_due": column_due}


def _note_ref(n: dict) -> dict:
    return {"id": n["id"], "title": n["title"], "date": n["date"], "is_daily": n["type"] == "daily"}


def _page_action(row: dict, today: date, parent: str | None) -> dict:
    label = _label(row["due"], today)
    return {"note_id": row["note_id"], "note_title": row["note_title"], "text": parser.action_display_text(row["text"]),
            "due_label": label[0] if label else None, "due_level": label[1] if label else None, "parent": parent,
            "priority": row["priority"]}


def _decision_ref(d: dict) -> dict:
    return {"text": d["text"], "note_id": d["note_id"], "date": d["date"]}


def person_page(store: NoteStore, name: str, today: date) -> dict:
    """Solo i nomi `@` grezzi: `@Giulia` e `@G.Ferri` restano due persone."""
    lower = name.lower()
    flt = Filter(person=name)
    notes = [n for n in store.list_notes(flt, 500) if any(p.lower() == lower for p in n["people"])]
    rows = store.actions()
    titles = {(r["note_id"], r["line"]): parser.action_display_text(r["text"]) for r in rows}
    actions = [_page_action(r, today, titles.get((r["note_id"], r["parent_line"])) if r["parent_line"] else None)
               for r in rows if any(p.lower() == lower for p in r["people"])]
    ids = {n["id"] for n in notes}
    decisions = [_decision_ref(d) for d in store.decisions(flt, "", 200) if d["note_id"] in ids]
    shown = next((p for n in notes for p in n["people"] if p.lower() == lower), name)
    return {"name": shown, "notes_count": len(notes), "first_seen": notes[-1]["date"] if notes else None,
            "actions": actions, "notes": [_note_ref(n) for n in notes[:30]], "decisions": decisions}


def people_list(store: NoteStore, today: date) -> list[dict]:
    today_iso = dates.iso(today)
    rows = store.actions()
    out = []
    for p in store.people():
        lower = p["name"].lower()
        mine = [r for r in rows if any(x.lower() == lower for x in r["people"])]
        out.append({"name": p["name"], "notes": p["notes"], "last_seen": p["last_seen"], "open": len(mine),
                    "late": sum(1 for r in mine if r["due"] and r["due"] < today_iso)})
    return out


def tag_page(store: NoteStore, tag: str, today: date) -> dict:
    """Un'etichetta. Se è un progetto lo dice (`project`), così la pagina apre la vista Progetto; un'area è
    raggruppata per progetto."""
    lower = tag.lower().lstrip("#")
    project = store.registry().match(lower)
    flt = Filter(project=lower)
    notes = store.list_notes(flt, 500)
    rows = store.actions(status="all")
    children = _children_of(rows)

    def has_tag(r: dict) -> bool:
        return (lower in r["tags"] or lower in r["topics"] or r["project"] == lower
                or any(t.endswith(f"/{lower}") or t.startswith(f"{lower}/") for t in r["tags"]))
    actions = [_board_item(r, children, today) for r in rows
               if not _closed(r) and r["parent_line"] is None and has_tag(r)]
    groups: dict[str, list[dict]] = {}
    for a in actions:
        groups.setdefault(a["project"] or "", []).append(a)
    people: list[str] = []
    for p in (p for n in notes for p in n["people"]):
        if not any(x.lower() == p.lower() for x in people):
            people.append(p)
    return {"tag": lower, "project": project, "notes_count": len(notes), "actions": actions,
            "groups": [{"project": k or None, "items": v} for k, v in sorted(groups.items(), key=lambda g: (g[0] == "", g[0]))],
            "notes": [_note_ref(n) for n in notes[:30]],
            "decisions": [_decision_ref(d) for d in store.decisions(flt, "", 100)], "people": people}


def _event(kind: str, text: str, note_id: str, line: int | None = None) -> dict:
    out = {"kind": kind, "text": text, "note_id": note_id}
    if line is not None:
        out["line"] = line
    return out


def calendar_data(store: NoteStore, start: str, end: str, today: date, project: str | None = None) -> dict[str, dict]:
    """Note, registrazioni, scadenze, giorni pianificati (`scheduled:`), completamenti e decisioni per giorno, da
    `start` a `end` inclusi. Una registrazione cade nel giorno della nota che la contiene; le azioni in ritardo
    compaiono anche oggi. Con `project` restano solo note, decisioni e azioni di quel progetto."""
    days: dict[str, dict] = {}

    def day(key: str) -> dict:
        return days.setdefault(key, {"daily": None, "events": []})

    flt = Filter(date_from=start, date_to=end, project=project)
    notes = store.list_notes(flt, 5000)
    day_of = {}
    for n in notes:
        if len(n["date"]) < 10:
            continue
        key = n["date"][:10]
        day_of[n["path"]] = (key, n["id"])
        if n["type"] == "daily":
            day(key)["daily"] = n["id"]
        else:
            day(key)["events"].append(_event("note", n["title"], n["id"]))
    for path, body in store.bodies([n["path"] for n in notes], ["[Registrazione ", "Trascrizione "]):
        if path not in day_of:
            continue
        key, note_id = day_of[path]
        for r in parser.recordings(body):
            if r.file and r.duration:
                text = f"Registrazione {r.time} ({r.duration})"
            elif r.file:
                text = f"Registrazione {r.time}"
            else:
                text = f"Trascrizione {r.time}"
            day(key)["events"].append(_event("rec", text, note_id, r.line_no))
    for d in store.decisions(flt, "", 5000):
        if len(d["date"]) >= 10:
            day(d["date"][:10])["events"].append(_event("dec", d["text"], d["note_id"]))
    today_iso = dates.iso(today)
    for a in store.actions(status="all", project=project):
        text = parser.action_display_text(a["text"])
        line = a["line"]
        if a["done"] and a["done_on"] and start <= a["done_on"] <= end:
            day(a["done_on"])["events"].append(_event("done", text, a["note_id"], line))
        if _closed(a):
            continue
        if a["due"] and start <= a["due"] <= end:
            day(a["due"])["events"].append(_event("late" if a["due"] < today_iso else "due", text, a["note_id"], line))
        if a["scheduled"] and start <= a["scheduled"] <= end and a["scheduled"] != a["due"]:
            day(a["scheduled"])["events"].append(_event("plan", text, a["note_id"], line))
        late = (a["due"] and a["due"] < today_iso) or (a["scheduled"] and a["scheduled"] < today_iso)
        if late and start <= today_iso <= end and a["due"] != today_iso:
            day(today_iso)["events"].append(_event("late", text, a["note_id"], line))
    return days


# ------------------------------------------------------------------ Agenda, Progetto, Revisione

# Soglie in giorni: da regolare dopo una settimana d'uso.
INBOX_DAYS = 2  # un'azione di un daily passato senza progetto o senza data va smistata dopo 2 giorni
WAITING_DAYS = 7  # un'attesa più lunga è evidenziata
STALE_DAYS = 14  # un'azione senza data ferma da più di 14 giorni torna in Revisione
REVIEW_DAYS = 7  # dopo una settimana la barra laterale ricorda la Revisione


def _age(row: dict, today: date, key: str = "first_seen") -> int:
    """I giorni da quando l'azione esiste (o, con `status_since`, da quando ha il suo stato)."""
    d = dates.parse_day(row.get(key)) or dates.parse_day(row["note_date"]) or today
    return (today - d).days


def _is_daily(row: dict) -> bool:
    return row["note_type"] == "daily" or row["note_id"].endswith("-giornata")


def _is_inbox(row: dict, today: date) -> bool:
    """Un'azione senza progetto o senza data nella nota "Da smistare", oppure nata in un daily passato e aperta
    da più di INBOX_DAYS giorni."""
    if row["parent_line"] is not None or _closed(row):
        return False
    if row["note_type"] == "inbox":
        return not row["project"] or not (row["due"] or row["scheduled"])
    if not _is_daily(row):
        return False
    born = dates.parse_day(row["note_date"])
    if born is None or born >= today or (today - born).days <= INBOX_DAYS:
        return False
    return not row["project"] or not (row["due"] or row["scheduled"])


def _agenda_item(row: dict, children: dict, today: date, titles: dict) -> dict:
    item = _board_item(row, children, today)
    planned = dates.parse_day(row["scheduled"])
    item["since_days"] = (today - planned).days if planned and planned < today else 0
    item["waiting_days"] = _age(row, today, "status_since") if row["status"] == "waiting" else 0
    item["age_days"] = _age(row, today)
    item["parent"] = titles.get((row["note_id"], row["parent_line"])) if row["parent_line"] else None
    return item


def _first_date(item: dict) -> str:
    return min(d for d in (item["due"], item["scheduled"], "9999-99-99") if d)


def _grouped(items: list[dict], key, empty: str) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for i in items:
        groups.setdefault(key(i) or "", []).append(i)
    return [{"name": k or None, "label": k or empty, "items": v}
            for k, v in sorted(groups.items(), key=lambda g: (g[0] == "", g[0].lower()))]


def _section(key: str, title: str, items: list[dict], groups: list[dict] | None = None) -> dict:
    return {"key": key, "title": title, "count": len(items),
            "groups": groups if groups is not None else [{"name": None, "label": None, "items": items}]}


def agenda(store: NoteStore, today: date, project: str | None = None, include_paused: bool = False) -> dict:
    """Cosa fare adesso: in ritardo, oggi, in corso, in attesa per persona, domande per progetto, prossimi 7
    giorni, da smistare. Ogni azione compare nella prima sezione in cui rientra. I progetti in pausa restano
    fuori, a meno di sceglierne uno o di chiederli."""
    if project:
        project = store.project(project).key
    rows = store.actions(status="all", project=project, include_paused=include_paused or bool(project))
    children = _children_of(rows)
    titles = {(r["note_id"], r["line"]): parser.action_display_text(r["text"]) for r in rows}
    week = today + timedelta(days=7)
    buckets: dict[str, list[dict]] = {k: [] for k in ("late", "today", "doing", "waiting", "question", "next", "inbox")}
    for r in rows:
        if _closed(r):
            continue
        due, planned = dates.parse_day(r["due"]), dates.parse_day(r["scheduled"])
        if due and due < today:
            bucket = "late"
        elif due == today or (planned and planned <= today):
            bucket = "today"
        elif r["status"] in ("doing", "waiting", "question"):
            bucket = r["status"]
        elif (due and due <= week) or (planned and planned <= week):
            bucket = "next"
        elif _is_inbox(r, today):
            bucket = "inbox"
        else:
            continue
        buckets[bucket].append(_agenda_item(r, children, today, titles))

    from .parser import PRIORITIES
    rank = {p: i for i, p in enumerate(PRIORITIES)}
    by_prio = lambda i: (rank.get(i["priority"], 3), _first_date(i))  # noqa: E731
    buckets["late"].sort(key=lambda i: (i["due"], rank.get(i["priority"], 3)))
    for k in ("today", "doing", "waiting", "question", "inbox"):
        buckets[k].sort(key=by_prio)
    buckets["next"].sort(key=lambda i: (_first_date(i), rank.get(i["priority"], 3)))
    for i in buckets["waiting"]:
        i["stale"] = i["waiting_days"] > WAITING_DAYS
    sections = [
        _section("late", "In ritardo", buckets["late"]),
        _section("today", "Oggi", buckets["today"]),
        _section("doing", "In corso", buckets["doing"]),
        _section("waiting", "In attesa", buckets["waiting"],
                 _grouped(buckets["waiting"], lambda i: i["people"][0] if i["people"] else None, "Senza persona")),
        _section("question", "Domande", buckets["question"],
                 _grouped(buckets["question"], lambda i: i["project"], "Senza progetto")),
        _section("next", "Prossimi 7 giorni", buckets["next"]),
        _section("inbox", "Da smistare", buckets["inbox"]),
    ]
    chips = [{"key": p["key"], "title": p["title"], "open": p["open"]}
             for p in store.project_rows() if p["status"] not in HIDDEN_STATUSES]
    return {"date": dates.iso(today), "title": dates.daily_title(today), "project": project,
            "sections": sections, "projects": chips, "open": sum(len(v) for v in buckets.values())}


def _archive_id(store: NoteStore, note_id: str) -> str | None:
    hub = store._path_for_id(note_id)  # noqa: SLF001 - serve solo il percorso, per l'archivio accanto
    if hub is None:
        return None
    path = hub.with_name(f"{note_id}.archivio.md")
    return path.stem if path.exists() else None


def project_page(store: NoteStore, slug: str, today: date) -> dict:
    """Un progetto: stato e nota, azioni aperte per area, attese, domande, decisioni recenti, note collegate e
    log dei daily degli ultimi 14 giorni."""
    p = store.project(slug)
    rows = store.actions(status="all", project=p.key)
    children = _children_of(rows)
    titles = {(r["note_id"], r["line"]): parser.action_display_text(r["text"]) for r in rows}
    keys = {(r["note_id"], r["line"]) for r in rows}
    shown = [r for r in rows if not _closed(r)
             and (r["parent_line"] is None or (r["note_id"], r["parent_line"]) not in keys)]
    items = [_agenda_item(r, children, today, titles) for r in shown]
    waiting = [i for i in items if i["status"] == "waiting"]
    questions = [i for i in items if i["status"] == "question"]
    rest = [i for i in items if i["status"] not in ("waiting", "question")]
    order = {a: n for n, a in enumerate(p.areas)}
    by_area: dict[str, list[dict]] = {}
    for i in rest:
        by_area.setdefault(i["area"] or "", []).append(i)
    areas = [{"area": a or None, "items": sorted(v, key=lambda i: (i["status"] != "doing", _first_date(i)))}
             for a, v in sorted(by_area.items(), key=lambda g: (g[0] == "", order.get(g[0], len(order)), g[0]))]
    for i in waiting:
        i["stale"] = i["waiting_days"] > WAITING_DAYS
    archive = _archive_id(store, p.note_id)
    notes = [n for n in store.list_notes(Filter(project=p.key), 60) if n["id"] not in (p.note_id, archive)]
    decisions = store.decisions(Filter(project=p.key), "", 10)
    done_recent = sum(1 for r in rows if r["done"] and r["done_on"] and r["done_on"] >= dates.iso(today - timedelta(days=6)))
    return {
        "key": p.key, "title": p.title, "status": p.status, "aliases": p.aliases, "areas": p.areas,
        "hub_id": p.note_id, "archive_id": archive, "open": len(items),
        "closed_in_hub": sum(1 for r in rows if _closed(r) and r["note_id"] == p.note_id and r["parent_line"] is None),
        "done_week": done_recent, "groups": areas, "waiting": waiting, "questions": questions,
        "decisions": [_decision_ref(d) for d in decisions],
        "notes": [_note_ref(n) for n in notes[:30]],
        "log": store.logs(p.key, dates.iso(today - timedelta(days=14))),
    }


def _dup_key(text: str) -> str:
    bare = re.sub(r"[#@][\w\-/.]+", "", parser.action_display_text(text).lower())
    return " ".join(re.sub(r"[^\w\s]", " ", bare).split())


def weekly_review(store: NoteStore, today: date, last_review: str | None = None) -> dict:
    """I passi della Revisione settimanale. Ogni azione compare nel primo passo in cui rientra."""
    rows = store.actions(status="all")
    children = _children_of(rows)
    titles = {(r["note_id"], r["line"]): parser.action_display_text(r["text"]) for r in rows}
    projects = store.project_rows()
    hidden = {p["key"] for p in projects if p["status"] in HIDDEN_STATUSES}
    open_rows = [r for r in rows if not _closed(r)]
    active = [r for r in open_rows if r["project"] not in hidden]
    used: set[tuple[str, int]] = set()

    def take(selected: list[dict]) -> list[dict]:
        out = []
        for r in selected:
            k = (r["note_id"], r["line"])
            if k not in used:
                used.add(k)
                out.append(_agenda_item(r, children, today, titles))
        return out

    # Le madri prima di "da smistare": chiuderle è la cosa da fare, anche se stanno in un daily vecchio.
    parents = take([r for r in active if r["parent_line"] is None and children.get((r["note_id"], r["line"]))
                    and all(_closed(c) for c in children[(r["note_id"], r["line"])])])
    inbox = take([r for r in active if _is_inbox(r, today)])
    stale = take([r for r in active if r["parent_line"] is None and r["status"] in ("todo", "doing")
                  and not r["due"] and not r["scheduled"] and _age(r, today) > STALE_DAYS])
    waiting = take([r for r in active if r["status"] == "waiting" and _age(r, today, "status_since") > WAITING_DAYS])
    for i in waiting:
        i["stale"] = True

    same: dict[str, list[dict]] = {}
    for r in active:
        if r["parent_line"] is None:
            same.setdefault(_dup_key(r["text"]), []).append(r)
    dups = [{"name": v[0]["text"], "label": parser.action_display_text(v[0]["text"]),
             "items": [_agenda_item(r, children, today, titles) for r in v]}
            for k, v in same.items() if k and len(v) > 1]

    has_next = {r["project"] for r in open_rows if r["status"] in ("todo", "doing") and r["project"]}
    no_next = [{"key": p["key"], "title": p["title"], "status": p["status"], "open": p["open"], "note_id": p["note_id"]}
               for p in projects if p["status"] == "attivo" and p["key"] not in has_next]
    paused = [{"key": p["key"], "title": p["title"], "status": p["status"], "open": p["open"], "note_id": p["note_id"]}
              for p in projects if p["status"] in HIDDEN_STATUSES and p["open"]]

    since = dates.iso(today - timedelta(days=6))
    week_rows = [r for r in rows if r["done_on"] and since <= r["done_on"] <= dates.iso(today)]
    decisions = [_decision_ref(d) for d in store.decisions(Filter(date_from=since, date_to=dates.iso(today)), "", 100)]
    summary = {"from": since, "to": dates.iso(today), "done": sum(1 for r in week_rows if r["status"] == "done"),
               "cancelled": sum(1 for r in week_rows if r["status"] == "cancelled"), "decisions": decisions,
               "done_items": [parser.action_display_text(r["text"]) for r in week_rows if r["status"] == "done"][:50]}

    last = dates.parse_day(last_review)
    days = (today - last).days if last else None
    steps = [
        {"key": "inbox", "title": "Da smistare", "hint": "Sposta nel progetto, pianifica o chiudi.", "kind": "actions", "items": inbox},
        {"key": "parents", "title": "Madri con tutte le figlie chiuse", "hint": "Chiudile o aggiungi il passo successivo.", "kind": "actions", "items": parents},
        {"key": "stale", "title": f"Ferme da più di {STALE_DAYS} giorni, senza data", "hint": "Pianifica, annulla o lascia.", "kind": "actions", "items": stale},
        {"key": "waiting", "title": f"In attesa da più di {WAITING_DAYS} giorni", "hint": "Sollecita o cambia stato.", "kind": "actions", "items": waiting},
        {"key": "duplicates", "title": "Possibili duplicati", "hint": "Tieni una sola copia.", "kind": "groups", "groups": dups},
        {"key": "no_next", "title": "Progetti attivi senza prossima azione", "hint": "Aggiungi un'azione o metti in pausa.", "kind": "projects", "projects": no_next},
        {"key": "paused", "title": "Progetti in pausa con task aperti", "hint": "Riattiva, annulla o archivia.", "kind": "projects", "projects": paused},
        {"key": "summary", "title": "La settimana", "hint": f"Dal {since} a oggi.", "kind": "summary", "summary": summary},
    ]
    for st in steps:
        st["count"] = (len(st.get("items", [])) + len(st.get("groups", [])) + len(st.get("projects", []))
                       if st["kind"] != "summary" else summary["done"] + summary["cancelled"])
    return {"date": dates.iso(today), "week_number": today.isocalendar()[1], "last_review": last_review,
            "days_since": days, "due": days is None or days > REVIEW_DAYS, "steps": steps}


def review_note_body(review: dict) -> str:
    """Il testo della nota "Revisione settimana NN": il riepilogo e cosa resta da guardare."""
    s = next(st for st in review["steps"] if st["key"] == "summary")["summary"]
    out = ["## Riepilogo", f"- Fatte: {s['done']}", f"- Annullate: {s['cancelled']}",
           f"- Decisioni: {len(s['decisions'])}"]
    for d in s["decisions"]:
        out.append(f"    - {d['text']} ([[{d['note_id']}]])")
    left = []
    for st in review["steps"]:
        if st["kind"] == "actions" and st["items"]:
            left.append(f"- {st['title']}: {len(st['items'])}")
        elif st["kind"] == "groups" and st["groups"]:
            left.append(f"- {st['title']}: {len(st['groups'])}")
        elif st["kind"] == "projects" and st["projects"]:
            left.append(f"- {st['title']}: " + ", ".join(f"[[{p['note_id']}|{p['title']}]]" for p in st["projects"]))
    if left:
        out += ["", "## Ancora da guardare", *left]
    out += ["", "## Note", ""]
    return "\n".join(out) + "\n"


def _node(node_id: str, label: str, kind: str, page: str) -> dict:
    return {"id": node_id, "label": label, "kind": kind, "page": page}


def full_graph(store: NoteStore) -> dict:
    """Il grafo di tutte le note, come in Obsidian: note collegate con `[[link]]`, più persone ed etichette.
    I link verso note che non esistono non diventano nodi."""
    rows = store.graph_rows()
    nodes: list[dict] = []
    by_path: dict[str, int] = {}
    by_key: dict[str, int] = {}
    for i, (path, note_id, title, kind, when) in enumerate(rows["notes"]):
        daily = kind == "daily" or note_id.endswith("-giornata")
        d = dates.parse_day(when) if daily else None
        label = dates.daily_title(d) if d else (title or note_id)
        nodes.append(_node(note_id, label, "daily" if daily else "note", f"note:{note_id}"))
        by_path[path] = i
        by_key[note_id.lower()] = i
        by_key.setdefault(title.lower(), i)
    edges: set[tuple[int, int]] = set()

    def link(a: int, b: int) -> None:
        if a != b:
            edges.add((min(a, b), max(a, b)))

    for path, key in rows["links"]:
        if path in by_path and key in by_key:
            link(by_path[path], by_key[key])
    extra: dict[str, int] = {}
    for pairs, kind in ((rows["people"], "person"), (rows["tags"], "tag")):
        for path, name in pairs:
            if path not in by_path:
                continue
            lower = name.lower()
            key = f"{kind}:{lower}"
            if key not in extra:
                node_id, label = (name, f"@{name}") if kind == "person" else (lower, f"#{lower}")
                nodes.append(_node(node_id, label, kind, f"{kind}:{node_id}"))
                extra[key] = len(nodes) - 1
            link(by_path[path], extra[key])
    return {"nodes": nodes, "edges": [list(e) for e in sorted(edges)]}


# ------------------------------------------------------------------ Ctrl K


def _hit(kind: str, label: str, hint: str, page: str, snippet: str | None = None, line: int | None = None,
         level: str | None = None) -> dict:
    out = {"kind": kind, "label": label, "hint": hint, "page": page, "snippet": snippet}
    if line is not None:
        out["line"] = line
    if level is not None:
        out["level"] = level
    return out


def _note_label(note_id: str, title: str, note_type: str, when: str) -> str:
    """Il nome di una nota nei risultati: le note del giorno si chiamano con la data, come nelle schede."""
    d = dates.parse_day(when) if note_type == "daily" or note_id.endswith("-giornata") else None
    return dates.daily_title(d) if d else title


def _terms(text: str) -> list[str]:
    return [t.lower() for t in re.split(r"[^\w]+", text) if t]


def excerpt(line: str, word: str, width: int) -> str:
    """Un pezzo di riga attorno alla prima parola trovata, al massimo `width` caratteri, senza parole tagliate."""
    if len(line) <= width:
        return line
    at = line.lower().find(word) if word else 0
    at = max(at, 0)
    start = min(max(at - width // 3, 0), len(line) - width)
    end = start + width
    if start > 0 and not line[start - 1].isspace():
        space = next((i for i, c in enumerate(line[start:end]) if c.isspace()), 0)
        start += space
    if end < len(line) and not line[end].isspace():
        space = next((i for i in range(end - 1, start - 1, -1) if line[i].isspace()), None)
        end = space if space is not None else end
    body = line[start:end].strip()
    return ("…" if start > 0 else "") + body + ("…" if end < len(line) else "")


def search_all(store: NoteStore, query: str, today: date) -> list[dict]:
    """La ricerca di Ctrl K: note, azioni aperte, decisioni e righe delle trascrizioni.
    `@nome`, `#etichetta` filtrano; `!parole` cerca solo tra le decisioni."""
    flt = Filter()
    words: list[str] = []
    only_decisions = False
    for w in query.split():
        if w.startswith("@") and len(w) > 1:
            flt.person = w[1:]
        elif w.startswith("#") and len(w) > 1:
            flt.project = w[1:]
        elif w == "!" or w.lower() == "!decisione":
            only_decisions = True
        elif w.startswith("!"):
            only_decisions = True
            words.append(w[1:])
        else:
            words.append(w)
    text = " ".join(words)

    def day_hint(when: str) -> str:
        d = dates.parse_day(when)
        return dates.short_day(d) if d else ""

    def decision_hit(d: dict) -> dict:
        return _hit("decision", d["text"], day_hint(d["date"]), f"note:{d['note_id']}",
                    snippet=_note_label(d["note_id"], d["note_title"], "", d["date"]), line=d["line"])

    hits: list[dict] = []
    if only_decisions:
        return [decision_hit(d) for d in store.decisions(flt, text, 15)]
    if not text:
        if flt.person:
            lower = flt.person.lower()
            for f in [f for f in store.people() if lower in f["name"].lower()][:5]:
                hits.append(_hit("person", f"@{f['name']}", f"{f['notes']} note", f"person:{f['name']}"))
        if flt.project:
            lower = flt.project.lower()
            for f in [f for f in store.projects() if lower in f["name"]][:5]:
                hits.append(_hit("tag", f"#{f['name']}", f"{f['notes']} note", f"tag:{f['name']}"))
    notes = store.search(text, flt, 15)
    for n in notes:
        hits.append(_hit("note", _note_label(n["id"], n["title"], n["type"], n["date"]), day_hint(n["date"]),
                         f"note:{n['id']}", snippet=n.get("snippet")))
    # Azioni, decisioni e trascrizioni da tre lettere in su: con una o due troverebbero quasi tutto.
    terms = _terms(text)
    if not any(len(w) >= 3 for w in terms):
        return hits

    person = flt.person.lower() if flt.person else None
    found = [a for a in store.actions(text=text, project=flt.project, limit=30)
             if person is None or any(person in x.lower() for x in a["people"])]
    for a in found[:5]:
        label = _label(a["due"], today)
        hits.append(_hit("action", parser.action_display_text(a["text"]), label[0] if label else "",
                         f"note:{a['note_id']}", snippet=_note_label(a["note_id"], a["note_title"], "", a["note_date"]),
                         line=a["line"], level=label[1] if label else None))
    hits.extend(decision_hit(d) for d in store.decisions(flt, text, 5))

    # Trascrizioni: le righe con il minutaggio, nelle note già trovate dalla ricerca a testo pieno.
    count = 0
    by_path = {n["path"]: n for n in notes}
    for path, body in store.bodies(list(by_path)):
        n = by_path[path]
        for t in parser.transcript_lines(body):
            lower = t.text.lower()
            if not all(w in lower for w in terms):
                continue
            when = f" · Trascrizione {t.time}" if t.time else ""
            hits.append(_hit("transcript", excerpt(t.text, terms[0], 110), t.stamp, f"note:{n['id']}",
                             snippet=_note_label(n["id"], n["title"], n["type"], n["date"]) + when, line=t.line_no))
            count += 1
            if count == 5:
                return hits
    return hits
