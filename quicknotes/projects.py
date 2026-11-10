"""Progetti e aree: a quale progetto appartiene un'azione, una decisione o una riga di log.

Un progetto è una nota con `type: project`. La sua chiave è il campo `project`, altrimenti lo slug del titolo;
`aliases` sono gli altri nomi con cui compare (per esempio nelle intestazioni dei daily), `areas` le sue aree.
Le regole, nell'ordine, sono quelle della guida: etichetta gerarchica sulla riga, etichetta che è un
progetto, intestazione sopra la riga, progetto dell'azione madre, progetto della nota.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import parser

PROJECT_STATUSES = ("attivo", "pausa", "chiuso")
# Gli stati con cui un progetto non compare in Agenda e nelle liste, a meno di chiederlo.
HIDDEN_STATUSES = ("pausa", "chiuso")


def key_of(name: str) -> str:
    """Il nome confrontabile: `LLM Training`, `llm-training` e `#llm-training` danno lo stesso valore."""
    name = name.strip().lstrip("#").strip()
    if not name:
        return ""
    slug = parser.slugify(name)
    return name.lower() if slug == "nota" and name.lower() != "nota" else slug


@dataclass
class Project:
    key: str
    title: str
    status: str = "attivo"
    aliases: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)
    path: str = ""
    note_id: str = ""


def project_status(value: str | None) -> str:
    v = (value or "").strip().lower()
    names = {"active": "attivo", "paused": "pausa", "in pausa": "pausa", "closed": "chiuso", "chiusa": "chiuso",
             "attiva": "attivo"}
    v = names.get(v, v)
    return v if v in PROJECT_STATUSES else "attivo"


def from_note(note) -> Project | None:
    """Il progetto descritto da una nota, se è una nota di progetto."""
    if note.note_type != "project":
        return None
    title = parser.meta_str(note.meta, "title") or note.title
    key = key_of(parser.meta_str(note.meta, "project") or title or note.id)
    if not key:
        return None
    return Project(
        key=key, title=title, status=project_status(parser.meta_str(note.meta, "status")),
        aliases=parser.meta_list(note.meta, "aliases"),
        areas=[a for a in (key_of(x) for x in parser.meta_list(note.meta, "areas")) if a],
        note_id=note.id,
    )


class Registry:
    """I progetti conosciuti, con tutti i nomi con cui si possono riconoscere."""

    def __init__(self, projects: list[Project] = ()):
        self.projects = {p.key: p for p in projects}
        self.names: dict[str, str] = {}
        for p in projects:
            for name in (p.key, p.title, *p.aliases):
                k = key_of(name)
                if k:
                    self.names.setdefault(k, p.key)

    def match(self, name: str | None) -> str | None:
        """La chiave del progetto con quel nome o alias, oppure None."""
        if not name:
            return None
        return self.names.get(key_of(name))

    def signature(self) -> tuple:
        """Cambia quando cambia qualcosa che conta per l'assegnazione dei progetti."""
        return tuple(sorted((p.key, key_of(p.title), tuple(sorted(key_of(a) for a in p.aliases)), tuple(p.areas))
                            for p in self.projects.values()))


def resolve(registry: Registry, tags: list[str], headings: list[str], inherited: list[str] = (),
            parent_project: str | None = None, note_project: str | None = None) -> tuple[str | None, list[str]]:
    """(progetto, aree) di una riga. Le aree sono le altre etichette della riga e di quella madre, più le
    intestazioni che sono aree del progetto; la prima è quella dichiarata nel progetto, se c'è."""
    project = None
    from_tag = set()
    hier_areas: list[str] = []
    for t in tags:
        if "/" in t:
            head, _, rest = t.partition("/")
            if head and project is None:
                project = registry.match(head) or key_of(head)
            if head and rest and (registry.match(head) or key_of(head)) == project:
                hier_areas.append(rest.strip("/"))
            from_tag.add(t)
    if project is None:
        for t in tags:
            k = registry.match(t)
            if k:
                project = k
                break
    if project is None:
        for h in reversed(headings):
            k = registry.match(h)
            if k:
                project = k
                break
    if project is None:
        project = parent_project
    if project is None and note_project:
        project = registry.match(note_project) or key_of(note_project)

    topics: list[str] = list(hier_areas)
    for t in [*tags, *inherited]:
        if "/" in t:
            head, _, rest = t.partition("/")
            if (registry.match(head) or key_of(head)) == project:
                if rest and t not in from_tag:
                    topics.append(rest.strip("/"))
                continue
            topics.append(t)
            continue
        if project and registry.match(t) == project:
            continue
        if project and key_of(t) == project:
            continue
        topics.append(t)
    declared = registry.projects[project].areas if project in registry.projects else []
    for h in headings:
        k = key_of(h)
        if k in declared:
            topics.append(k)
    topics = [t for t in dict.fromkeys(x.lower() for x in topics if x)]
    first = next((t for t in topics if t in declared), None)
    if first:
        topics.remove(first)
        topics.insert(0, first)
    return project, topics
