"""Server MCP: espone le note a Claude (Claude Desktop, Claude Code, ...).

Avvio:  python -m quicknotes.mcp_server      (trasporto stdio)
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

try:  # SDK MCP 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # SDK MCP 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from .config import load_config
from .store import NoteNotFound, NoteStore

INSTRUCTIONS = """\
Archivio personale di note di lavoro dell'utente (meeting, diario giornaliero, appunti).
Le note sono Markdown con convenzioni: @persona, #progetto/tag, "- [ ]" azione aperta,
"- [x]" azione fatta, "due:AAAA-MM-GG" scadenza, "!decisione" decisione presa.
Strategia consigliata: usa search_notes o list_notes per trovare le note pertinenti,
poi read_note per leggerle per intero prima di rispondere, citando titolo e data.
Per azioni e decisioni usa list_action_items e list_decisions. Le date sono ISO.
Oggi: {today}. Scrivi nelle note solo se l'utente lo chiede.
"""

_store: NoteStore | None = None


def store() -> NoteStore:
    global _store
    if _store is None:
        _store = NoteStore(load_config().notes_path)
    return _store


server = _Server(name="quicknotes", instructions=INSTRUCTIONS.format(today=dt.date.today().isoformat()))


@server.tool()
def search_notes(query: str = "", date_from: str | None = None, date_to: str | None = None,
                 person: str | None = None, project: str | None = None,
                 note_type: Literal["meeting", "daily", "note"] | None = None,
                 limit: int = 20) -> list[dict]:
    """Cerca nelle note per parole chiave (anche parziali) con filtri opzionali.

    query: parole da cercare; vuota = solo filtri. Prima cerca note con tutte le parole,
      se non ne trova restituisce quelle con almeno una.
    date_from/date_to: AAAA-MM-GG inclusi. person: nome o parte del nome.
    project: progetto o tag (senza #). Restituisce id, titolo, data, persone ed estratto.
    """
    return store().search(query, date_from, date_to, person, project, note_type, max(1, min(limit, 100)))


@server.tool()
def list_notes(date_from: str | None = None, date_to: str | None = None, person: str | None = None,
               project: str | None = None, note_type: Literal["meeting", "daily", "note"] | None = None,
               limit: int = 50) -> list[dict]:
    """Elenca le note dalla piu' recente, con filtri opzionali (date AAAA-MM-GG incluse)."""
    return store().list_notes(date_from, date_to, person, project, note_type, max(1, min(limit, 200)))


@server.tool()
def read_note(note_id: str) -> dict:
    """Legge il contenuto completo di una nota dato il suo id (es. 2026-10-27-1000-kickoff)."""
    try:
        note = store().read(note_id)
    except NoteNotFound as exc:
        raise ValueError(str(exc)) from None
    return {"id": note.id, "title": note.title, "type": note.type, "date": note.date,
            "people": note.people, "project": note.project or None, "tags": note.tags,
            "content": note.body}


@server.tool()
def read_daily_note(date: str | None = None) -> dict:
    """Legge la nota del giorno (diario) per la data AAAA-MM-GG, di default oggi."""
    note = store().daily(date, create=False)
    if note is None:
        return {"date": date or dt.date.today().isoformat(), "exists": False}
    return {"id": note.id, "title": note.title, "date": note.date, "exists": True, "content": note.body}


@server.tool()
def list_action_items(status: Literal["open", "done", "all"] = "open", owner: str | None = None,
                      project: str | None = None, due_before: str | None = None,
                      date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """Elenca le azioni (righe "- [ ]") di tutte le note: prima quelle con scadenza piu' vicina.

    owner: persona assegnata (prima @menzione della riga). due_before: AAAA-MM-GG.
    date_from/date_to filtrano per data della nota che contiene l'azione.
    """
    return store().actions(status, owner, project, due_before, date_from, date_to)


@server.tool()
def list_decisions(query: str = "", date_from: str | None = None, date_to: str | None = None,
                   person: str | None = None, project: str | None = None) -> list[dict]:
    """Elenca le decisioni registrate (righe con !decisione), dalla piu' recente."""
    return store().decisions(date_from, date_to, person, project, query)


@server.tool()
def list_people_and_projects() -> dict:
    """Persone e progetti/tag presenti nelle note, con numero di note e ultima data."""
    return {"people": store().people(), "projects": store().projects()}


@server.tool()
def create_note(title: str, content: str, note_type: Literal["meeting", "note"] = "note",
                people: list[str] | None = None, project: str | None = None,
                tags: list[str] | None = None) -> dict:
    """Crea una nuova nota (es. un riepilogo richiesto dall'utente). Usa le convenzioni Markdown."""
    note = store().create_note(title, content, note_type, people, project, tags,
                               extra_meta={"source": "claude"})
    return {"id": note.id, "title": note.title, "path": str(note.path)}


@server.tool()
def append_to_note(note_id: str, text: str, heading: str | None = None) -> dict:
    """Aggiunge testo in fondo a una nota esistente, opzionalmente sotto un titoletto."""
    try:
        note = store().append(note_id, text, heading)
    except NoteNotFound as exc:
        raise ValueError(str(exc)) from None
    return {"id": note.id, "title": note.title}


@server.tool()
def append_to_daily_note(text: str, date: str | None = None) -> dict:
    """Aggiunge una voce con orario alla nota del giorno (creandola se manca)."""
    note = store().append_to_daily(text, date)
    return {"id": note.id, "title": note.title}


@server.tool()
def set_action_status(note_id: str, action_text: str, done: bool = True) -> dict:
    """Segna come fatta (o riapre) un'azione; action_text e' il testo o una sua parte."""
    try:
        return store().set_action_status(note_id, action_text, done)
    except NoteNotFound as exc:
        raise ValueError(str(exc)) from None


@server.prompt()
def riepilogo_settimanale(settimana_che_inizia: str | None = None) -> str:
    """Riepilogo della settimana: meeting, decisioni, azioni aperte."""
    start = dt.date.fromisoformat(settimana_che_inizia) if settimana_che_inizia else \
        dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
    end = start + dt.timedelta(days=6)
    return (f"Prepara un riepilogo della mia settimana dal {start} al {end} usando le mie note. "
            "Leggi tutte le note del periodo, poi elenca: meeting principali con l'esito, "
            "decisioni prese, azioni aperte (con responsabile e scadenza) e punti che "
            "sembrano rimasti in sospeso. Cita titolo e data di ogni nota usata.")


@server.prompt()
def briefing_meeting(persona_o_progetto: str) -> str:
    """Briefing prima di un meeting con una persona o su un progetto."""
    return (f"Devo fare un meeting su/con «{persona_o_progetto}». Cerca nelle mie note tutto "
            "cio' che riguarda questo argomento (prova sia come persona sia come progetto), "
            "leggi le note piu' rilevanti e preparami un briefing: contesto, decisioni gia' "
            "prese, azioni aperte che lo riguardano e domande da porre.")


def main() -> None:
    store()  # costruisce l'indice prima di accettare richieste
    server.run()


if __name__ == "__main__":
    main()
