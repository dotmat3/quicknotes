"""Formato delle note e convenzioni di scrittura rapida.

Una nota è un file Markdown con frontmatter YAML facoltativo. Nel testo: `@persona`, `#etichetta` (anche
gerarchica, `#progetto/area`), `- [ ] azione` con gli stati `[/]` in corso, `[w]` in attesa, `[?]` domanda,
`[-]` annullata, `[x]` fatta, `due:AAAA-MM-GG`, `scheduled:AAAA-MM-GG`, `done:AAAA-MM-GG`, `prio:alta|media|bassa`,
`!decisione`, `[[id|Titolo]]`, `![[schizzo.excalidraw]]`.

`@` e `#` si riconoscono con scanner scritti a mano: le regole guardano il carattere precedente.
Le posizioni restituite sono indici di carattere nella riga.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import yaml

DUE_RE = re.compile(r"\b(?:due|entro|scadenza)\s*:\s*(\d{4}-\d{2}-\d{2})", re.I)
DONE_RE = re.compile(r"\bdone\s*:\s*(\d{4}-\d{2}-\d{2})", re.I)
# `scheduled:` è il giorno in cui si pensa di farla; `due:` resta la scadenza.
SCHEDULED_RE = re.compile(r"\bscheduled\s*:\s*(\d{4}-\d{2}-\d{2})", re.I)
# `prio:alta`, anche `priorità:` e `priority:`; i valori inglesi valgono come quelli italiani.
PRIO_RE = re.compile(r"\b(?:prio|priorit[àa]|priority)\s*:\s*(alta|media|bassa|high|medium|low)\b", re.I)
PRIORITIES = ("alta", "media", "bassa")
_PRIO_NAMES = {"high": "alta", "medium": "media", "low": "bassa"}
DECISION_RE = re.compile(r"!(?:decisione|decision|dec)\b", re.I)
MD_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
ACTION_RE = re.compile(r"^(\s*)[-*+]\s+\[( |x|X|/|w|W|\?|-)\]\s*(.*)$")
# Il segno nella casella e lo stato che indica. `done` resta vero solo per `[x]`.
STATUS_OF_MARK = {" ": "todo", "/": "doing", "w": "waiting", "?": "question", "-": "cancelled", "x": "done"}
MARK_OF_STATUS = {v: k for k, v in STATUS_OF_MARK.items()}
STATUSES = ("todo", "doing", "waiting", "question", "cancelled", "done")
CLOSED = ("done", "cancelled")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
# `🎙️ [Registrazione 15:02 (12:30)](audio/nota-150200.wav)`, la riga scritta alla fine di una registrazione.
RECORDING_RE = re.compile(r"\[Registrazione (\d{1,2}:\d{2})(?: \((\d{1,2}(?::\d{2}){1,2})\))?\]\(([^)]*)\)")
# `### Trascrizione 15:02`, il titolo sopra il testo trascritto.
TRANSCRIPT_HEADING_RE = re.compile(r"^#{1,6}\s+Trascrizione\s+(\d{1,2}:\d{2})\s*$", re.I)
# `[mm:ss]` o `[h:mm:ss]` a inizio riga: il minutaggio di un paragrafo trascritto.
TIMESTAMP_RE = re.compile(r"^\s*(?:[-*+]\s+)?\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)$")


def lines_of(text: str) -> list[str]:
    """Le righe come le intende Rust `str::lines`: senza l'ultima vuota dopo l'a capo finale, senza `\\r`."""
    if not text:
        return []
    parts = text.split("\n")
    if text.endswith("\n"):
        parts.pop()
    return [p[:-1] if p.endswith("\r") else p for p in parts]


def is_fence(line: str) -> bool:
    t = line.lstrip()
    return t.startswith("```") or t.startswith("~~~")


def is_word(c: str) -> bool:
    return c.isalnum() or c == "_"


def indent_width(line: str) -> int:
    width = 0
    for c in line:
        if c == " ":
            width += 1
        elif c == "\t":
            width += 4
        else:
            break
    return width


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out


# ------------------------------------------------------------------ frontmatter


class _Loader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    """YAML senza conversione delle date: `date: 2026-10-27` resta testo. Usa libyaml quando c'è (dieci volte
    più veloce: conta quando si indicizzano migliaia di note)."""


class _Dumper(yaml.SafeDumper):
    """Le date si scrivono senza virgolette, come prima."""


for _cls in (_Loader, _Dumper):
    _cls.yaml_implicit_resolvers = {
        k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
        for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }


def _split_inclusive(text: str):
    start = 0
    while start < len(text):
        nl = text.find("\n", start)
        end = len(text) if nl < 0 else nl + 1
        yield text[start:end]
        start = end


def split_frontmatter(text: str) -> tuple[str, dict, str]:
    """(testo originale del frontmatter, metadati, corpo). Un frontmatter non valido resta nel corpo, così
    non si perde nulla."""
    if not text.startswith("---"):
        return "", {}, text
    nl = text.find("\n", 3)
    if nl < 0 or text[3:nl].strip(" \t\r"):
        return "", {}, text
    start = pos = nl + 1
    for line in _split_inclusive(text[start:]):
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
    """Riscrive il frontmatter dai metadati, togliendo i valori vuoti."""
    clean = {k: v for k, v in meta.items() if v is not None and v != "" and v != []}
    if not clean:
        return ""
    body = yaml.dump(clean, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=10**6)
    return f"---\n{body}---\n"


def meta_str(meta: dict, key: str) -> str | None:
    v = meta.get(key)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def meta_list(meta: dict, key: str) -> list[str]:
    """Un elenco nei metadati: lista YAML oppure testo separato da virgole."""
    v = meta.get(key)
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    if isinstance(v, list):
        return [str(x).strip() for x in v
                if isinstance(x, (str, int, float)) and not isinstance(x, bool) and str(x).strip()]
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [str(v)]
    return []


def normalize_date(value: str) -> str:
    """Una data ISO `AAAA-MM-GG` o `AAAA-MM-GGTHH:MM`."""
    return value.strip().replace(" ", "T", 1)[:16]


# ------------------------------------------------------------------ persone ed etichette


def mention_spans(line: str) -> list[tuple[int, int]]:
    """Posizioni delle `@persone` di una riga, `@` compresa. Si salta da una `@` all'altra: le righe sono
    tante e scorrerle carattere per carattere costerebbe."""
    out = []
    n = len(line)
    i = line.find("@")
    while i >= 0:
        prev = line[i - 1] if i else None
        if not (prev is not None and (is_word(prev) or prev in ".@")) and i + 1 < n and is_word(line[i + 1]):
            end = i + 1
            while end < n and (is_word(line[end]) or line[end] in "-."):
                end += 1
            while line[end - 1] in "-.":
                end -= 1
            out.append((i, end))
        i = line.find("@", i + 1)
    return out


def mentions(line: str) -> list[str]:
    return [line[s + 1:e] for s, e in mention_spans(line)]


def tag_spans(line: str) -> list[tuple[int, int]]:
    """Posizioni delle `#etichette` di una riga, `#` compreso."""
    out = []
    n = len(line)
    i = line.find("#")
    while i >= 0:
        prev = line[i - 1] if i else None
        first = line[i + 1] if i + 1 < n else ""
        if not (prev is not None and (is_word(prev) or prev in "/#&")) and first and is_word(first) and not first.isnumeric():
            end = i + 2
            while end < n and (is_word(line[end]) or line[end] in "-/"):
                end += 1
            out.append((i, end))
        i = line.find("#", i + 1)
    return out


def tags(line: str) -> list[str]:
    return [line[s + 1:e] for s, e in tag_spans(line)]


# ------------------------------------------------------------------ estrazione


@dataclass
class Action:
    line_no: int
    text: str
    done: bool = False
    owner: str | None = None
    people: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    due: str | None = None
    done_on: str | None = None
    priority: str | None = None  # alta, media, bassa
    parent_line: int | None = None  # riga dell'azione madre; None per quelle di primo livello
    description: str = ""
    status: str = "todo"  # todo, doing, waiting, question, cancelled, done
    scheduled: str | None = None  # `scheduled:`
    headings: list[str] = field(default_factory=list)  # le intestazioni sopra la riga, dalla più esterna
    inherited_tags: list[str] = field(default_factory=list)  # le etichette dell'azione madre

    @property
    def closed(self) -> bool:
        return self.status in CLOSED


@dataclass
class Decision:
    line_no: int
    text: str
    tags: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)


@dataclass
class LogLine:
    """Una riga puntata che non è un'azione: nei daily diventa il log di un progetto."""
    line_no: int
    text: str
    tags: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)


@dataclass
class WikiLink:
    line_no: int
    target: str
    label: str | None
    line: str  # la riga in cui compare, per i collegamenti in entrata


@dataclass
class Embed:
    line_no: int
    target: str


@dataclass
class Heading:
    line_no: int
    level: int
    text: str


@dataclass
class Extracted:
    people: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    links: list[WikiLink] = field(default_factory=list)
    embeds: list[Embed] = field(default_factory=list)
    headings: list[Heading] = field(default_factory=list)
    logs: list[LogLine] = field(default_factory=list)


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
        if inner:
            target, sep, label = inner.partition("|")
            target = target.strip() if sep else inner
            label = label.strip() or None if sep else None
            if embed:
                out.embeds.append(Embed(line_no, target))
            else:
                out.links.append(WikiLink(line_no, target, label, line.strip()))
        pos = end + 2


def extract(body: str) -> Extracted:
    """Persone, etichette, azioni, decisioni e collegamenti, ignorando i blocchi di codice."""
    result = Extracted()
    lines = lines_of(body)
    in_fence = False
    top: tuple[int, int] | None = None  # indice e rientro dell'ultima azione di primo livello
    describing: int | None = None  # indice dell'azione che può ancora ricevere righe di descrizione
    stack: list[tuple[int, str]] = []  # intestazioni aperte: (livello, testo)

    for idx, line in enumerate(lines):
        line_no = idx + 1
        if is_fence(line):
            in_fence = not in_fence
            top = describing = None
            continue
        if in_fence:
            continue
        h = HEADING_RE.match(line)
        if h:
            level = len(h.group(1))
            result.headings.append(Heading(line_no, level, h.group(2)))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, h.group(2)))
        context = [t for _, t in stack]
        # Le destinazioni dei link Markdown non devono generare etichette (`file#ancora`).
        scan = MD_LINK_TARGET_RE.sub("]", line)
        line_people = mentions(scan)
        line_tags = [t.lower() for t in tags(scan)]
        result.people.extend(line_people)
        result.tags.extend(line_tags)
        _scan_wiki(line, line_no, result)

        width = indent_width(line)
        described = False
        m = ACTION_RE.match(line)
        if m:
            text = m.group(3).strip()
            if text:
                mother = result.actions[top[0]] if top is not None and width > top[1] else None
                parent = mother.line_no if mother else None
                due = DUE_RE.search(text)
                done_on = DONE_RE.search(text)
                prio = PRIO_RE.search(text)
                scheduled = SCHEDULED_RE.search(text)
                status = STATUS_OF_MARK[m.group(2).lower()]
                result.actions.append(Action(
                    line_no=line_no, text=text, done=status == "done", status=status,
                    owner=line_people[0] if line_people else None,
                    people=_dedupe(line_people), tags=_dedupe(line_tags),
                    due=due.group(1) if due else None, done_on=done_on.group(1) if done_on else None,
                    scheduled=scheduled.group(1) if scheduled else None,
                    parent_line=parent, priority=priority_name(prio.group(1)) if prio else None,
                    headings=context,
                    inherited_tags=_dedupe(mother.tags + mother.inherited_tags) if mother else [],
                ))
                i = len(result.actions) - 1
                if parent is None:
                    top = (i, width)
                describing = i
                described = True
        elif line.strip():
            if describing is not None:
                owner_width = indent_width(lines[result.actions[describing].line_no - 1])
                if width > owner_width and not BULLET_RE.match(line):
                    a = result.actions[describing]
                    a.description = f"{a.description}\n{line.strip()}" if a.description else line.strip()
                    described = True
            # Una riga non rientrata chiude l'azione madre corrente.
            if width == 0:
                top = None
            if not described and BULLET_RE.match(line) and not DECISION_RE.search(line):
                bare = BULLET_RE.sub("", line, count=1).strip()
                if bare and not bare.startswith("↗"):
                    result.logs.append(LogLine(line_no, bare, _dedupe(line_tags), context))
        if not described:
            describing = None

        if DECISION_RE.search(line):
            cleaned = BULLET_RE.sub("", line, count=1)
            text = DECISION_RE.sub("", cleaned.strip()).strip(" -–:")
            if text:
                result.decisions.append(Decision(line_no, text, _dedupe(line_tags), context))
    result.people = _dedupe(result.people)
    result.tags = _dedupe(result.tags)
    return result


def first_h1(body: str) -> str | None:
    """Il primo titolo di livello 1, usato quando il frontmatter non ha `title`."""
    in_fence = False
    for line in lines_of(body):
        if is_fence(line):
            in_fence = not in_fence
        elif not in_fence and line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return None


def action_display_text(text: str) -> str:
    """Il testo di un'azione senza `due:`, `scheduled:`, `done:` e `prio:`, mostrati a parte nell'interfaccia."""
    return " ".join(PRIO_RE.sub("", DONE_RE.sub("", SCHEDULED_RE.sub("", DUE_RE.sub("", text)))).split())


def priority_name(value: str | None) -> str | None:
    """`alta`, `media` o `bassa`, qualunque sia la forma scritta; None se non è una priorità."""
    v = (value or "").strip().lower()
    v = _PRIO_NAMES.get(v, v)
    return v if v in PRIORITIES else None


# ------------------------------------------------------------------ registrazioni e trascrizioni


@dataclass
class Recording:
    line_no: int
    time: str  # ora d'inizio, HH:MM
    duration: str | None
    file: str | None  # manca quando resta solo il titolo della trascrizione
    transcribed: bool


def _pad_time(t: str) -> str:
    return f"0{t}" if len(t) == 4 else t


def recordings(body: str) -> list[Recording]:
    """Le righe `🎙️ [Registrazione …](…)` e i titoli `Trascrizione HH:MM`, uniti per ora."""
    out: list[Recording] = []
    in_fence = False
    for idx, line in enumerate(lines_of(body)):
        if is_fence(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        c = RECORDING_RE.search(line)
        if c:
            time = _pad_time(c.group(1))
            same = next((r for r in out if r.time == time and r.file is None), None)
            if same:
                same.file, same.duration = c.group(3), c.group(2)
            else:
                out.append(Recording(idx + 1, time, c.group(2), c.group(3), False))
            continue
        c = TRANSCRIPT_HEADING_RE.match(line)
        if c:
            time = _pad_time(c.group(1))
            same = next((r for r in out if r.time == time and not r.transcribed), None)
            if same:
                same.transcribed = True
            else:
                out.append(Recording(idx + 1, time, None, None, True))
    return out


@dataclass
class TranscriptLine:
    line_no: int
    time: str | None  # l'ora della trascrizione a cui appartiene la riga
    stamp: str  # il minutaggio, mm:ss
    text: str


def transcript_lines(body: str) -> list[TranscriptLine]:
    out = []
    time = None
    in_fence = False
    for idx, line in enumerate(lines_of(body)):
        if is_fence(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        c = TRANSCRIPT_HEADING_RE.match(line)
        if c:
            time = _pad_time(c.group(1))
        elif HEADING_RE.match(line):
            time = None
        else:
            c = TIMESTAMP_RE.match(line)
            if c and c.group(2).strip():
                out.append(TranscriptLine(idx + 1, time, c.group(1), c.group(2).strip()))
    return out


def slugify(text: str) -> str:
    ascii_text = "".join(c for c in unicodedata.normalize("NFKD", text) if c.isascii())
    out, dash = "", False
    for c in ascii_text.strip().lower():
        if c.isascii() and c.isalnum():
            if dash and out:
                out += "-"
            dash = False
            out += c
        elif c in "-_" or c.isspace():
            dash = True
        if len(out) >= 50:
            break
    return out.strip("-") or "nota"
