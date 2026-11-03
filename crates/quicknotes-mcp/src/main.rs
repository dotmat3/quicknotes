//! Server MCP su stdio: messaggi JSON-RPC, uno per riga.
//!
//! È un eseguibile a parte, senza runtime asincrono né SDK: lo avvia Claude a ogni sessione
//! e deve rispondere subito. Serve solo la parte stabile del protocollo: strumenti e prompt.

use std::io::{BufRead, Write};

use chrono::{Datelike, Duration, Local, NaiveDate};
use quicknotes_core::index::{ActionQuery, Filter, SearchQuery, Status};
use quicknotes_core::store::NewNote;
use quicknotes_core::{Config, NoteStore};
use serde_json::{json, Value};

const SUPPORTED_VERSIONS: [&str; 4] = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];

fn instructions() -> String {
    format!(
        "Archivio personale di note di lavoro dell'utente (meeting, diario giornaliero, appunti).\n\
         Le note sono Markdown con convenzioni: @persona, #progetto/tag, \"- [ ]\" azione aperta,\n\
         \"- [x]\" azione fatta, \"due:AAAA-MM-GG\" scadenza, \"done:AAAA-MM-GG\" completamento,\n\
         \"!decisione\" decisione presa, \"[[id|Titolo]]\" collegamento a un'altra nota.\n\
         Strategia consigliata: usa search_notes o list_notes per trovare le note pertinenti,\n\
         poi read_note per leggerle per intero prima di rispondere, citando titolo e data.\n\
         Per azioni e decisioni usa list_action_items e list_decisions. Le date sono ISO.\n\
         Oggi: {}. Scrivi nelle note solo se l'utente lo chiede.",
        Local::now().format("%Y-%m-%d")
    )
}

fn tools() -> Value {
    let text = |d: &str| json!({"type": "string", "description": d});
    let filter_props = json!({
        "date_from": text("Data iniziale inclusa, AAAA-MM-GG"),
        "date_to": text("Data finale inclusa, AAAA-MM-GG"),
        "person": text("Nome o parte del nome di una persona"),
        "project": text("Progetto o etichetta, senza #"),
        "note_type": {"type": "string", "enum": ["meeting", "daily", "note"]},
    });
    let with = |extra: Value| -> Value {
        let mut props = filter_props.as_object().cloned().unwrap_or_default();
        props.extend(extra.as_object().cloned().unwrap_or_default());
        json!({"type": "object", "properties": props})
    };
    let schema = |props: Value, required: &[&str]| json!({"type": "object", "properties": props, "required": required});
    json!([
        {"name": "search_notes",
         "description": "Cerca nelle note per parole chiave, anche parziali, con filtri opzionali. Prima cerca note con tutte le parole; se non ne trova, restituisce quelle con almeno una. Con query vuota applica solo i filtri. Restituisce id, titolo, data, persone ed estratto.",
         "inputSchema": with(json!({"query": text("Parole da cercare"), "limit": {"type": "integer", "default": 20}}))},
        {"name": "list_notes",
         "description": "Elenca le note dalla più recente, con filtri opzionali.",
         "inputSchema": with(json!({"limit": {"type": "integer", "default": 50}}))},
        {"name": "read_note",
         "description": "Legge il contenuto completo di una nota dato il suo id (es. 2026-10-27-1000-kickoff), con i collegamenti in uscita e in entrata.",
         "inputSchema": schema(json!({"note_id": text("Id della nota")}), &["note_id"])},
        {"name": "read_daily_note",
         "description": "Legge la nota del giorno per la data indicata, di default oggi.",
         "inputSchema": schema(json!({"date": text("Data AAAA-MM-GG")}), &[])},
        {"name": "get_backlinks",
         "description": "Note che citano questa nota con un [[link]], con la riga in cui lo fanno.",
         "inputSchema": schema(json!({"note_id": text("Id della nota")}), &["note_id"])},
        {"name": "list_action_items",
         "description": "Elenca le azioni (righe \"- [ ]\") di tutte le note: prima quelle con scadenza più vicina. parent_line indica l'azione madre di una sotto-attività.",
         "inputSchema": schema(json!({
            "status": {"type": "string", "enum": ["open", "done", "all"], "default": "open"},
            "owner": text("Persona assegnata: prima @menzione della riga"),
            "project": text("Progetto o etichetta, senza #"),
            "due_before": text("Scadenza entro questa data, AAAA-MM-GG"),
            "date_from": text("Data iniziale della nota, AAAA-MM-GG"),
            "date_to": text("Data finale della nota, AAAA-MM-GG"),
         }), &[])},
        {"name": "list_decisions",
         "description": "Elenca le decisioni registrate (righe con !decisione), dalla più recente.",
         "inputSchema": with(json!({"query": text("Parole contenute nella decisione")}))},
        {"name": "list_people_and_projects",
         "description": "Persone e progetti o etichette presenti nelle note, con numero di note e ultima data.",
         "inputSchema": schema(json!({}), &[])},
        {"name": "create_note",
         "description": "Crea una nuova nota, per esempio un riepilogo richiesto dall'utente. Usa le convenzioni Markdown.",
         "inputSchema": schema(json!({
            "title": text("Titolo"), "content": text("Testo Markdown"),
            "note_type": {"type": "string", "enum": ["meeting", "note"], "default": "note"},
            "people": {"type": "array", "items": {"type": "string"}},
            "project": text("Progetto"),
            "tags": {"type": "array", "items": {"type": "string"}},
         }), &["title", "content"])},
        {"name": "append_to_note",
         "description": "Aggiunge testo in fondo a una nota esistente, opzionalmente sotto un titoletto.",
         "inputSchema": schema(json!({"note_id": text("Id della nota"), "text": text("Testo"), "heading": text("Titoletto")}), &["note_id", "text"])},
        {"name": "append_to_daily_note",
         "description": "Aggiunge una voce con orario alla nota del giorno, creandola se manca.",
         "inputSchema": schema(json!({"text": text("Testo")}), &["text"])},
        {"name": "set_action_status",
         "description": "Segna come fatta o riapre un'azione. action_text è il testo o una sua parte. Scrive o toglie anche la data done:.",
         "inputSchema": schema(json!({"note_id": text("Id della nota"), "action_text": text("Testo dell'azione"), "done": {"type": "boolean", "default": true}}), &["note_id", "action_text"])},
    ])
}

fn prompts() -> Value {
    json!([
        {"name": "riepilogo_settimanale",
         "description": "Riepilogo della settimana: meeting, decisioni, azioni aperte.",
         "arguments": [{"name": "settimana_che_inizia", "description": "Primo giorno, AAAA-MM-GG. Di default questa settimana.", "required": false}]},
        {"name": "briefing_meeting",
         "description": "Briefing prima di un meeting con una persona o su un progetto.",
         "arguments": [{"name": "persona_o_progetto", "description": "Persona o progetto", "required": true}]},
    ])
}

fn get_prompt(name: &str, args: &Value) -> Result<String, String> {
    match name {
        "riepilogo_settimanale" => {
            let today = Local::now().date_naive();
            let start = opt_str(args, "settimana_che_inizia")
                .and_then(|d| NaiveDate::parse_from_str(&d, "%Y-%m-%d").ok())
                .unwrap_or_else(|| today - Duration::days(i64::from(today.weekday().num_days_from_monday())));
            let end = start + Duration::days(6);
            Ok(format!(
                "Prepara un riepilogo della mia settimana dal {start} al {end} usando le mie note. \
                 Leggi tutte le note del periodo, poi elenca: meeting principali con l'esito, \
                 decisioni prese, azioni aperte (con responsabile e scadenza) e punti che \
                 sembrano rimasti in sospeso. Cita titolo e data di ogni nota usata."
            ))
        }
        "briefing_meeting" => {
            let topic = opt_str(args, "persona_o_progetto").ok_or("Manca persona_o_progetto")?;
            Ok(format!(
                "Devo fare un meeting su/con «{topic}». Cerca nelle mie note tutto ciò che riguarda \
                 questo argomento (prova sia come persona sia come progetto), leggi le note più \
                 rilevanti e preparami un briefing: contesto, decisioni già prese, azioni aperte \
                 che lo riguardano e domande da porre."
            ))
        }
        other => Err(format!("Prompt sconosciuto: {other}")),
    }
}

fn opt_str(args: &Value, key: &str) -> Option<String> {
    args.get(key).and_then(Value::as_str).map(str::trim).filter(|s| !s.is_empty()).map(String::from)
}

fn req_str(args: &Value, key: &str) -> Result<String, String> {
    opt_str(args, key).ok_or_else(|| format!("Manca il parametro {key}"))
}

fn str_list(args: &Value, key: &str) -> Vec<String> {
    args.get(key)
        .and_then(Value::as_array)
        .map(|a| a.iter().filter_map(Value::as_str).map(String::from).collect())
        .unwrap_or_default()
}

fn limit(args: &Value, default: usize, max: usize) -> usize {
    args.get("limit").and_then(Value::as_u64).map(|l| l as usize).unwrap_or(default).clamp(1, max)
}

fn filter(args: &Value) -> Filter {
    Filter {
        date_from: opt_str(args, "date_from"),
        date_to: opt_str(args, "date_to"),
        person: opt_str(args, "person"),
        project: opt_str(args, "project"),
        note_type: opt_str(args, "note_type"),
    }
}

fn note_payload(store: &NoteStore, note: &quicknotes_core::Note) -> Result<Value, String> {
    Ok(json!({
        "id": note.id, "title": note.title(), "type": note.note_type(), "date": note.date(),
        "people": note.people(), "project": Some(note.project()).filter(|p| !p.is_empty()), "tags": note.tags(),
        "content": note.body,
        "links_out": store.outgoing_links(&note.id).map_err(|e| e.to_string())?,
        "links_in": store.backlinks(&note.id).map_err(|e| e.to_string())?,
    }))
}

fn call_tool(store: &NoteStore, name: &str, args: &Value) -> Result<Value, String> {
    let e = |err: quicknotes_core::Error| err.to_string();
    // I file possono cambiare tra una chiamata e l'altra: l'allineamento senza modifiche costa pochi ms.
    store.refresh().map_err(e)?;
    let v = |r: serde_json::Result<Value>| r.map_err(|err| err.to_string());
    let today = || Local::now().date_naive();
    match name {
        "search_notes" => {
            let q = SearchQuery { text: opt_str(args, "query").unwrap_or_default(), filter: filter(args), limit: limit(args, 20, 100) };
            v(serde_json::to_value(store.search(&q).map_err(e)?))
        }
        "list_notes" => v(serde_json::to_value(store.list_notes(&filter(args), limit(args, 50, 200)).map_err(e)?)),
        "read_note" => {
            let note = store.read(&req_str(args, "note_id")?).map_err(e)?;
            note_payload(store, &note)
        }
        "read_daily_note" => {
            let date = opt_str(args, "date");
            let day = match &date {
                Some(d) => NaiveDate::parse_from_str(d, "%Y-%m-%d").map_err(|_| format!("Data non valida: {d}"))?,
                None => today(),
            };
            match store.daily(day, false).map_err(e)? {
                Some(note) => {
                    let mut out = note_payload(store, &note)?;
                    out["exists"] = json!(true);
                    Ok(out)
                }
                None => Ok(json!({"date": day.format("%Y-%m-%d").to_string(), "exists": false})),
            }
        }
        "get_backlinks" => v(serde_json::to_value(store.backlinks(&req_str(args, "note_id")?).map_err(e)?)),
        "list_action_items" => {
            let status = match opt_str(args, "status").as_deref() {
                None | Some("open") => Status::Open,
                Some("done") => Status::Done,
                Some("all") => Status::All,
                Some(other) => return Err(format!("Stato non valido: {other}")),
            };
            let q = ActionQuery {
                status,
                owner: opt_str(args, "owner"),
                project: opt_str(args, "project"),
                due_before: opt_str(args, "due_before"),
                date_from: opt_str(args, "date_from"),
                date_to: opt_str(args, "date_to"),
                text: None,
                limit: 200,
            };
            v(serde_json::to_value(store.actions(&q).map_err(e)?))
        }
        "list_decisions" => {
            let query = opt_str(args, "query").unwrap_or_default();
            v(serde_json::to_value(store.decisions(&filter(args), &query, 100).map_err(e)?))
        }
        "list_people_and_projects" => Ok(json!({"people": store.people().map_err(e)?, "projects": store.projects().map_err(e)?})),
        "create_note" => {
            let note = store
                .create_note(NewNote {
                    title: req_str(args, "title")?,
                    body: args.get("content").and_then(Value::as_str).unwrap_or_default().to_string(),
                    note_type: opt_str(args, "note_type").unwrap_or_else(|| "note".into()),
                    people: str_list(args, "people"),
                    project: opt_str(args, "project"),
                    tags: str_list(args, "tags"),
                    source: Some("claude".into()),
                    when: None,
                })
                .map_err(e)?;
            Ok(json!({"id": note.id, "title": note.title(), "path": note.path}))
        }
        "append_to_note" => {
            let text = req_str(args, "text")?;
            let note = store.append(&req_str(args, "note_id")?, &text, opt_str(args, "heading").as_deref()).map_err(e)?;
            Ok(json!({"id": note.id, "title": note.title()}))
        }
        "append_to_daily_note" => {
            let note = store.append_to_daily(&req_str(args, "text")?, Local::now().naive_local(), true).map_err(e)?;
            Ok(json!({"id": note.id, "title": note.title()}))
        }
        "set_action_status" => {
            let done = args.get("done").and_then(Value::as_bool).unwrap_or(true);
            let change = store
                .set_action_status(&req_str(args, "note_id")?, &req_str(args, "action_text")?, done.then(today))
                .map_err(e)?;
            v(serde_json::to_value(change))
        }
        other => Err(format!("Strumento sconosciuto: {other}")),
    }
}

/// La risposta a un messaggio; `None` per le notifiche.
fn handle(store: &mut Option<NoteStore>, msg: &Value) -> Option<Value> {
    let id = msg.get("id")?.clone();
    let method = msg.get("method").and_then(Value::as_str).unwrap_or_default();
    let params = msg.get("params").cloned().unwrap_or(Value::Null);
    let ok = |result: Value| Some(json!({"jsonrpc": "2.0", "id": id, "result": result}));
    let fail = |code: i64, message: String| Some(json!({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}));
    match method {
        "initialize" => {
            let asked = params.get("protocolVersion").and_then(Value::as_str).unwrap_or_default();
            let version = SUPPORTED_VERSIONS.iter().find(|v| **v == asked).copied().unwrap_or(SUPPORTED_VERSIONS[0]);
            ok(json!({
                "protocolVersion": version,
                "capabilities": {"tools": {}, "prompts": {}},
                "serverInfo": {"name": "quicknotes", "version": env!("CARGO_PKG_VERSION")},
                "instructions": instructions(),
            }))
        }
        "ping" => ok(json!({})),
        "tools/list" => ok(json!({"tools": tools()})),
        "prompts/list" => ok(json!({"prompts": prompts()})),
        "prompts/get" => {
            let name = params.get("name").and_then(Value::as_str).unwrap_or_default();
            match get_prompt(name, params.get("arguments").unwrap_or(&Value::Null)) {
                Ok(text) => ok(json!({"messages": [{"role": "user", "content": {"type": "text", "text": text}}]})),
                Err(e) => fail(-32602, e),
            }
        }
        "tools/call" => {
            let name = params.get("name").and_then(Value::as_str).unwrap_or_default();
            if !tools().as_array().is_some_and(|t| t.iter().any(|x| x["name"] == name)) {
                return fail(-32602, format!("Strumento sconosciuto: {name}"));
            }
            if store.is_none() {
                match NoteStore::open(Config::load().notes_path()) {
                    Ok(s) => *store = Some(s),
                    Err(e) => return ok(tool_error(e.to_string())),
                }
            }
            let args = params.get("arguments").cloned().unwrap_or_else(|| json!({}));
            let result = call_tool(store.as_ref().expect("aperto qui sopra"), name, &args);
            match result {
                Ok(value) => {
                    let text = serde_json::to_string_pretty(&value).unwrap_or_default();
                    ok(json!({"content": [{"type": "text", "text": text}], "isError": false}))
                }
                Err(e) => ok(tool_error(e)),
            }
        }
        other => fail(-32601, format!("Metodo non supportato: {other}")),
    }
}

fn tool_error(message: String) -> Value {
    json!({"content": [{"type": "text", "text": message}], "isError": true})
}

fn main() {
    // L'archivio si apre alla prima chiamata a uno strumento: rispondere a initialize deve essere immediato.
    let mut store: Option<NoteStore> = None;
    let stdin = std::io::stdin();
    let mut out = std::io::stdout().lock();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let response = match serde_json::from_str::<Value>(&line) {
            Ok(msg) => handle(&mut store, &msg),
            Err(e) => Some(json!({"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": e.to_string()}})),
        };
        if let Some(response) = response {
            if writeln!(out, "{response}").and_then(|_| out.flush()).is_err() {
                break;
            }
        }
    }
}
