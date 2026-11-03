"""Server MCP su stdio: messaggi JSON-RPC, uno per riga.

Lo avvia Claude a ogni sessione (`python -m quicknotes mcp`) e deve rispondere subito: nessun SDK, solo la
parte stabile del protocollo, cioè strumenti e prompt. L'archivio si apre alla prima chiamata a uno strumento.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta

from . import __version__
from .config import Config
from .index import Filter
from .store import NoteStore, QuickNotesError

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]


def instructions() -> str:
    return (
        "Archivio personale di note di lavoro dell'utente (meeting, diario giornaliero, appunti).\n"
        "Le note sono Markdown con convenzioni: @persona, #progetto/tag, \"- [ ]\" azione aperta,\n"
        "\"- [x]\" azione fatta, \"due:AAAA-MM-GG\" scadenza, \"done:AAAA-MM-GG\" completamento,\n"
        "\"!decisione\" decisione presa, \"[[id|Titolo]]\" collegamento a un'altra nota.\n"
        "Strategia consigliata: usa search_notes o list_notes per trovare le note pertinenti,\n"
        "poi read_note per leggerle per intero prima di rispondere, citando titolo e data.\n"
        "Per azioni e decisioni usa list_action_items e list_decisions. Le date sono ISO.\n"
        f"Oggi: {date.today().isoformat()}. Scrivi nelle note solo se l'utente lo chiede."
    )


def _text(description: str) -> dict:
    return {"type": "string", "description": description}


FILTER_PROPS = {
    "date_from": _text("Data iniziale inclusa, AAAA-MM-GG"),
    "date_to": _text("Data finale inclusa, AAAA-MM-GG"),
    "person": _text("Nome o parte del nome di una persona"),
    "project": _text("Progetto o etichetta, senza #"),
    "note_type": {"type": "string", "enum": ["meeting", "daily", "note"]},
}


def _with_filters(extra: dict) -> dict:
    return {"type": "object", "properties": {**FILTER_PROPS, **extra}}


def _schema(props: dict, required: list[str] = ()) -> dict:
    return {"type": "object", "properties": props, "required": list(required)}


TOOLS = [
    {"name": "search_notes",
     "description": "Cerca nelle note per parole chiave, anche parziali, con filtri opzionali. Prima cerca note con tutte le parole; se non ne trova, restituisce quelle con almeno una. Con query vuota applica solo i filtri. Restituisce id, titolo, data, persone ed estratto.",
     "inputSchema": _with_filters({"query": _text("Parole da cercare"), "limit": {"type": "integer", "default": 20}})},
    {"name": "list_notes",
     "description": "Elenca le note dalla più recente, con filtri opzionali.",
     "inputSchema": _with_filters({"limit": {"type": "integer", "default": 50}})},
    {"name": "read_note",
     "description": "Legge il contenuto completo di una nota dato il suo id (es. 2026-10-27-1000-kickoff), con i collegamenti in uscita e in entrata.",
     "inputSchema": _schema({"note_id": _text("Id della nota")}, ["note_id"])},
    {"name": "read_daily_note",
     "description": "Legge la nota del giorno per la data indicata, di default oggi.",
     "inputSchema": _schema({"date": _text("Data AAAA-MM-GG")})},
    {"name": "get_backlinks",
     "description": "Note che citano questa nota con un [[link]], con la riga in cui lo fanno.",
     "inputSchema": _schema({"note_id": _text("Id della nota")}, ["note_id"])},
    {"name": "list_action_items",
     "description": "Elenca le azioni (righe \"- [ ]\") di tutte le note: prima quelle con scadenza più vicina. parent_line indica l'azione madre di una sotto-attività.",
     "inputSchema": _schema({
         "status": {"type": "string", "enum": ["open", "done", "all"], "default": "open"},
         "owner": _text("Persona assegnata: prima @menzione della riga"),
         "project": _text("Progetto o etichetta, senza #"),
         "due_before": _text("Scadenza entro questa data, AAAA-MM-GG"),
         "date_from": _text("Data iniziale della nota, AAAA-MM-GG"),
         "date_to": _text("Data finale della nota, AAAA-MM-GG"),
     })},
    {"name": "list_decisions",
     "description": "Elenca le decisioni registrate (righe con !decisione), dalla più recente.",
     "inputSchema": _with_filters({"query": _text("Parole contenute nella decisione")})},
    {"name": "list_people_and_projects",
     "description": "Persone e progetti o etichette presenti nelle note, con numero di note e ultima data.",
     "inputSchema": _schema({})},
    {"name": "create_note",
     "description": "Crea una nuova nota, per esempio un riepilogo richiesto dall'utente. Usa le convenzioni Markdown.",
     "inputSchema": _schema({
         "title": _text("Titolo"), "content": _text("Testo Markdown"),
         "note_type": {"type": "string", "enum": ["meeting", "note"], "default": "note"},
         "people": {"type": "array", "items": {"type": "string"}},
         "project": _text("Progetto"),
         "tags": {"type": "array", "items": {"type": "string"}},
     }, ["title", "content"])},
    {"name": "append_to_note",
     "description": "Aggiunge testo in fondo a una nota esistente, opzionalmente sotto un titoletto.",
     "inputSchema": _schema({"note_id": _text("Id della nota"), "text": _text("Testo"), "heading": _text("Titoletto")},
                            ["note_id", "text"])},
    {"name": "append_to_daily_note",
     "description": "Aggiunge una voce con orario alla nota del giorno, creandola se manca.",
     "inputSchema": _schema({"text": _text("Testo")}, ["text"])},
    {"name": "set_action_status",
     "description": "Segna come fatta o riapre un'azione. action_text è il testo o una sua parte. Scrive o toglie anche la data done:.",
     "inputSchema": _schema({"note_id": _text("Id della nota"), "action_text": _text("Testo dell'azione"),
                             "done": {"type": "boolean", "default": True}}, ["note_id", "action_text"])},
]

PROMPTS = [
    {"name": "riepilogo_settimanale",
     "description": "Riepilogo della settimana: meeting, decisioni, azioni aperte.",
     "arguments": [{"name": "settimana_che_inizia", "description": "Primo giorno, AAAA-MM-GG. Di default questa settimana.",
                    "required": False}]},
    {"name": "briefing_meeting",
     "description": "Briefing prima di un meeting con una persona o su un progetto.",
     "arguments": [{"name": "persona_o_progetto", "description": "Persona o progetto", "required": True}]},
]


class ToolError(Exception):
    pass


def _opt(args: dict, key: str) -> str | None:
    v = args.get(key)
    return v.strip() or None if isinstance(v, str) else None


def _req(args: dict, key: str) -> str:
    v = _opt(args, key)
    if v is None:
        raise ToolError(f"Manca il parametro {key}")
    return v


def _str_list(args: dict, key: str) -> list[str]:
    v = args.get(key)
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _limit(args: dict, default: int, maximum: int) -> int:
    v = args.get("limit")
    v = v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else default
    return max(1, min(v, maximum))


def _filter(args: dict) -> Filter:
    return Filter(date_from=_opt(args, "date_from"), date_to=_opt(args, "date_to"), person=_opt(args, "person"),
                  project=_opt(args, "project"), note_type=_opt(args, "note_type"))


def _parse_day(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ToolError(f"Data non valida: {value}") from None


def get_prompt(name: str, args: dict) -> str:
    if name == "riepilogo_settimanale":
        today = date.today()
        start = None
        given = _opt(args, "settimana_che_inizia")
        if given:
            try:
                start = datetime.strptime(given, "%Y-%m-%d").date()
            except ValueError:
                start = None
        start = start or today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return (f"Prepara un riepilogo della mia settimana dal {start} al {end} usando le mie note. "
                "Leggi tutte le note del periodo, poi elenca: meeting principali con l'esito, "
                "decisioni prese, azioni aperte (con responsabile e scadenza) e punti che "
                "sembrano rimasti in sospeso. Cita titolo e data di ogni nota usata.")
    if name == "briefing_meeting":
        topic = _opt(args, "persona_o_progetto")
        if topic is None:
            raise ToolError("Manca persona_o_progetto")
        return (f"Devo fare un meeting su/con «{topic}». Cerca nelle mie note tutto ciò che riguarda "
                "questo argomento (prova sia come persona sia come progetto), leggi le note più "
                "rilevanti e preparami un briefing: contesto, decisioni già prese, azioni aperte "
                "che lo riguardano e domande da porre.")
    raise ToolError(f"Prompt sconosciuto: {name}")


def _note_payload(store: NoteStore, note) -> dict:
    return {"id": note.id, "title": note.title, "type": note.note_type, "date": note.date, "people": note.people,
            "project": note.project or None, "tags": note.tags, "content": note.body,
            "links_out": store.outgoing_links(note.id), "links_in": store.backlinks(note.id)}


def call_tool(store: NoteStore, name: str, args: dict):
    # I file possono cambiare tra una chiamata e l'altra: l'allineamento senza modifiche costa pochi ms.
    store.refresh()
    if name == "search_notes":
        return store.search(_opt(args, "query") or "", _filter(args), _limit(args, 20, 100))
    if name == "list_notes":
        return store.list_notes(_filter(args), _limit(args, 50, 200))
    if name == "read_note":
        return _note_payload(store, store.read(_req(args, "note_id")))
    if name == "read_daily_note":
        given = _opt(args, "date")
        day = _parse_day(given) if given else date.today()
        note = store.daily(day, False)
        if note is None:
            return {"date": day.isoformat(), "exists": False}
        return {**_note_payload(store, note), "exists": True}
    if name == "get_backlinks":
        return store.backlinks(_req(args, "note_id"))
    if name == "list_action_items":
        status = _opt(args, "status") or "open"
        if status not in ("open", "done", "all"):
            raise ToolError(f"Stato non valido: {status}")
        return store.actions(status=status, owner=_opt(args, "owner"), project=_opt(args, "project"),
                             due_before=_opt(args, "due_before"), date_from=_opt(args, "date_from"),
                             date_to=_opt(args, "date_to"), limit=200)
    if name == "list_decisions":
        return store.decisions(_filter(args), _opt(args, "query") or "", 100)
    if name == "list_people_and_projects":
        return {"people": store.people(), "projects": store.projects()}
    if name == "create_note":
        content = args.get("content") if isinstance(args.get("content"), str) else ""
        note = store.create_note(_req(args, "title"), content, _opt(args, "note_type") or "note",
                                 _str_list(args, "people"), _opt(args, "project"), _str_list(args, "tags"),
                                 source="claude")
        return {"id": note.id, "title": note.title, "path": str(note.path)}
    if name == "append_to_note":
        text = _req(args, "text")
        note = store.append(_req(args, "note_id"), text, _opt(args, "heading"))
        return {"id": note.id, "title": note.title}
    if name == "append_to_daily_note":
        note = store.append_to_daily(_req(args, "text"), datetime.now(), True)
        return {"id": note.id, "title": note.title}
    if name == "set_action_status":
        done = args.get("done")
        done = done if isinstance(done, bool) else True
        return store.set_action_status(_req(args, "note_id"), _req(args, "action_text"),
                                       date.today() if done else None)
    raise ToolError(f"Strumento sconosciuto: {name}")


def _tool_error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


class Server:
    def __init__(self):
        self.store: NoteStore | None = None

    def handle(self, msg: dict) -> dict | None:
        """La risposta a un messaggio; None per le notifiche."""
        if not isinstance(msg, dict) or "id" not in msg:
            return None
        msg_id = msg["id"]
        method = msg.get("method") if isinstance(msg.get("method"), str) else ""
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

        def ok(result):
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}

        def fail(code: int, message: str):
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

        if method == "initialize":
            asked = params.get("protocolVersion")
            version = asked if asked in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            return ok({"protocolVersion": version, "capabilities": {"tools": {}, "prompts": {}},
                       "serverInfo": {"name": "quicknotes", "version": __version__}, "instructions": instructions()})
        if method == "ping":
            return ok({})
        if method == "tools/list":
            return ok({"tools": TOOLS})
        if method == "prompts/list":
            return ok({"prompts": PROMPTS})
        if method == "prompts/get":
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            try:
                text = get_prompt(params.get("name") or "", arguments)
            except ToolError as e:
                return fail(-32602, str(e))
            return ok({"messages": [{"role": "user", "content": {"type": "text", "text": text}}]})
        if method == "tools/call":
            name = params.get("name") or ""
            if not any(t["name"] == name for t in TOOLS):
                return fail(-32602, f"Strumento sconosciuto: {name}")
            if self.store is None:
                try:
                    self.store = NoteStore(Config.load().notes_path())
                except Exception as e:  # noqa: BLE001 - l'errore va a Claude, il server resta vivo
                    return ok(_tool_error(str(e)))
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            try:
                value = call_tool(self.store, name, arguments)
            except (ToolError, QuickNotesError) as e:
                return ok(_tool_error(str(e)))
            except Exception as e:  # noqa: BLE001
                return ok(_tool_error(f"{type(e).__name__}: {e}"))
            text = json.dumps(value, ensure_ascii=False, indent=2)
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        return fail(-32601, f"Metodo non supportato: {method}")


def main() -> None:
    server = Server()
    out = sys.stdout.buffer
    for raw in sys.stdin.buffer:
        # Alcuni client (PowerShell, per esempio) mettono un BOM in testa al primo messaggio.
        line = raw.decode("utf-8", errors="replace").lstrip("﻿").strip()
        if not line:
            continue
        try:
            response = server.handle(json.loads(line))
        except ValueError as e:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
        if response is not None:
            try:
                out.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
                out.flush()
            except OSError:
                break
