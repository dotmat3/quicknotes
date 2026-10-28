"""Formato delle note e convenzioni di scrittura rapida.

Una nota e' un file Markdown con frontmatter YAML:

    ---
    type: meeting
    title: Kickoff cliente X
    date: 2026-10-27T10:00
    people: [Marco, Laura]
    project: clientex
    ---
    - Budget confermato a 50k !decisione
    - [ ] @Marco invia preventivo due:2026-10-31

Convenzioni nel testo:
    @nome            persona citata
    #tag             tag (anche il nome di un progetto)
    - [ ] testo      azione da fare   (- [x] = fatta)
    due:AAAA-MM-GG   scadenza di un'azione (anche "entro:")
    !decisione       la riga e' una decisione presa
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field

import yaml

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
MENTION_RE = re.compile(r"(?<![\w.@])@([\w][\w\-.]*\w|\w)", re.U)
TAG_RE = re.compile(r"(?<![\w/#&])#([^\W\d][\w\-/]*)", re.U)
ACTION_RE = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]\s*(.*)$")
DUE_RE = re.compile(r"(?:due|entro|scadenza)\s*:\s*(\d{4}-\d{2}-\d{2})", re.I)
DECISION_RE = re.compile(r"!(?:decisione|decision|dec)\b", re.I)
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Action:
    line_no: int  # 1-based, riferito al corpo della nota
    text: str
    done: bool
    owner: str | None = None
    due: str | None = None


@dataclass
class Decision:
    line_no: int
    text: str


@dataclass
class Extracted:
    people: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Separa il frontmatter YAML dal corpo. Un frontmatter non valido viene ignorato."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(meta, dict):
        return {}, text
    return meta, text[match.end():]


def render(meta: dict, body: str) -> str:
    clean = {k: v for k, v in meta.items() if v not in (None, "", [])}
    front = yaml.safe_dump(clean, sort_keys=False, allow_unicode=True, default_flow_style=None, width=1000)
    return f"---\n{front}---\n{body}"


def normalize_date(value) -> str:
    """Restituisce una data ISO 'AAAA-MM-GG' o 'AAAA-MM-GGTHH:MM' (stringa vuota se assente)."""
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    if isinstance(value, dt.date):
        return value.isoformat()
    if value is None:
        return ""
    text = str(value).strip().replace(" ", "T", 1)
    return text[:16]


def as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    if isinstance(value, (list, tuple)):
        return [str(p).strip() for p in value if str(p).strip()]
    return [str(value)]


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _clean_line(line: str) -> str:
    return BULLET_RE.sub("", line).strip()


def extract(body: str) -> Extracted:
    """Estrae persone, tag, azioni e decisioni dal corpo (ignorando i blocchi di codice)."""
    result = Extracted()
    in_fence = False
    for idx, line in enumerate(body.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # le parentesi dei link Markdown non devono generare tag (es. file#ancora)
        scan = re.sub(r"\]\([^)]*\)", "]", line)
        mentions = MENTION_RE.findall(scan)
        result.people.extend(mentions)
        result.tags.extend(t.lower() for t in TAG_RE.findall(scan))

        action = ACTION_RE.match(line)
        if action:
            text = action.group(2).strip()
            if text:
                due = DUE_RE.search(text)
                result.actions.append(Action(
                    line_no=idx,
                    text=text,
                    done=action.group(1).lower() == "x",
                    owner=mentions[0] if mentions else None,
                    due=due.group(1) if due else None,
                ))
        if DECISION_RE.search(line):
            text = DECISION_RE.sub("", _clean_line(line)).strip(" -–:")
            if text:
                result.decisions.append(Decision(line_no=idx, text=text))
    result.people = _dedupe(result.people)
    result.tags = _dedupe(result.tags)
    return result


def slugify(text: str, max_len: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:max_len].strip("-") or "nota"
