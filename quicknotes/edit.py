"""Modifiche al testo delle note: funzioni pure, usate da app e server MCP."""

from __future__ import annotations

import re

from .parser import ACTION_RE, DONE_RE, DUE_RE, indent_width, is_fence, lines_of, mention_spans, tag_spans

_NUMBERED = re.compile(r"^\d+[.)] ")


def _squeeze(line: str) -> str:
    """Toglie gli spazi rimasti doppi dopo aver levato un elemento, senza toccare il rientro."""
    indent = line[:len(line) - len(line.lstrip())]
    out, prev_space = [indent], False
    for c in line.strip():
        if c in " \t":
            if not prev_space:
                out.append(" ")
            prev_space = True
        else:
            out.append(c)
            prev_space = False
    return "".join(out)


def with_done(line: str, day: str | None) -> str:
    """La riga con la data di completamento indicata; None la toglie."""
    bare = _squeeze(DONE_RE.sub("", line))
    return f"{bare} done:{day}" if day else bare


def with_due(line: str, day: str | None) -> str:
    """La riga con la scadenza indicata, prima di un eventuale `done:`; None la toglie."""
    done = DONE_RE.search(line)
    out = _squeeze(DUE_RE.sub("", DONE_RE.sub("", line)))
    if day:
        out += f" due:{day}"
    if done:
        out += f" done:{done.group(1)}"
    return out


def with_checked(line: str, done_on: str | None) -> str:
    """La riga spuntata o riaperta: la casella e `done:` cambiano insieme."""
    mark = "[x]" if done_on else "[ ]"
    m = ACTION_RE.match(line)
    if m:
        box = m.start(2) - 1
        line = line[:box] + mark + line[box + 3:]
    return with_done(line, done_on)


def _insert_before_dates(line: str, item: str) -> str:
    """Inserisce un elemento dopo il testo, prima di `due:` e `done:`."""
    found = [m.start() for m in (DUE_RE.search(line), DONE_RE.search(line)) if m]
    if found:
        pos = min(found)
        return _squeeze(f"{line[:pos].rstrip()} {item} {line[pos:]}")
    return f"{line.rstrip()} {item}"


def _normalized(prefix: str, name: str) -> str:
    bare = name.strip().lstrip(prefix)
    return prefix + ("-" if prefix == "#" else "").join(bare.split())


def with_person(line: str, index: int, name: str | None) -> str:
    """Cambia la persona in posizione `index`, al suo posto, così la frase resta corretta. Se in quella
    posizione non c'è nessuno la aggiunge; None la toglie."""
    spans = mention_spans(line)
    if index < len(spans):
        start, end = spans[index]
        if name:
            return line[:start] + _normalized("@", name) + line[end:]
        return _squeeze(line[:start] + line[end:])
    return _insert_before_dates(line, _normalized("@", name)) if name else line


def with_tag(line: str, name: str | None) -> str:
    """Cambia la prima etichetta e lascia invariate le altre; None la toglie."""
    spans = tag_spans(line)
    if spans:
        start, end = spans[0]
        if name:
            return line[:start] + _normalized("#", name) + line[end:]
        return _squeeze(line[:start] + line[end:])
    return _insert_before_dates(line, _normalized("#", name)) if name else line


def with_description(body: str, line_no: int, text: str) -> str:
    """Il corpo con la descrizione dell'azione alla riga `line_no` sostituita da `text`."""
    lines = lines_of(body)
    if line_no == 0 or line_no > len(lines):
        return body
    action = lines[line_no - 1]
    width = indent_width(action)
    indent = action[:len(action) - len(action.lstrip())] + "    "
    end = line_no
    while end < len(lines):
        l = lines[end]
        t = l.lstrip()
        bullet = t.startswith(("- ", "* ", "+ ")) or bool(_NUMBERED.match(t))
        if not l.strip() or indent_width(l) <= width or bullet:
            break
        end += 1
    new = [indent + l.strip() for l in lines_of(text) if l.strip()]
    lines[line_no:end] = new
    out = "\n".join(lines)
    return out + "\n" if body.endswith("\n") else out


def _heading_of(line: str) -> tuple[int, str] | None:
    hashes = len(line) - len(line.lstrip("#"))
    if not 1 <= hashes <= 6:
        return None
    rest = line[hashes:]
    if not rest.startswith((" ", "\t")):
        return None
    return hashes, rest.strip()


def add_to_section(body: str, section: str | None, block: str) -> str:
    """Il corpo con `block` in fondo alla sezione indicata, creata alla fine della nota se manca.
    Senza sezione il blocco va in fondo alla nota, separato da una riga vuota."""
    block = block.strip("\n")
    lines = [] if not body.strip() else body.rstrip("\n").split("\n")

    found = None
    if section is not None:
        wanted = section.strip().lower()
        in_fence = False
        for i, line in enumerate(lines):
            if is_fence(line):
                in_fence = not in_fence
            elif not in_fence:
                h = _heading_of(line)
                if h and h[1].lower() == wanted:
                    found = (i, h[0])
                    break

    if found is None:
        tail = [""] if lines else []
        if section is not None:
            tail.append(f"## {section.strip()}")
        tail.append(block)
        return "\n".join(lines + tail) + "\n"

    start, level = found
    end = len(lines)
    in_fence = False
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if is_fence(line):
            in_fence = not in_fence
        elif not in_fence:
            h = _heading_of(line)
            if h and h[0] <= level:
                end = i
                break
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
    lines.insert(end, block)
    return "\n".join(lines) + "\n"
