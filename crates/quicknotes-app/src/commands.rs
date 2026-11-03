//! Comandi chiamati dalla pagina. Girano fuori dal thread principale: il disco non blocca mai la finestra.

use chrono::{Duration, Local};
use quicknotes_core::index::{ActionQuery, Facet, Filter, NoteSummary, SearchQuery};
use quicknotes_core::store::{ActionPatch, NewNote, SaveOutcome};
use quicknotes_core::{dates, parser, views};
use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State};

use crate::AppState;

type CmdResult<T> = Result<T, String>;

fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}

#[tauri::command(async)]
pub fn save_ui(state: State<'_, AppState>, ui: Value) -> CmdResult<()> {
    let mut config = state.config.lock().map_err(err)?;
    config.set_ui(ui);
    config.save().map_err(err)
}

#[tauri::command(async)]
pub fn sidebar(state: State<'_, AppState>) -> CmdResult<Value> {
    let store = &state.store;
    let today = Local::now().date_naive();
    let today_iso = today.format("%Y-%m-%d").to_string();
    let open = store.actions(&ActionQuery { limit: 100_000, ..Default::default() }).map_err(err)?;
    let top_level: Vec<_> = open.iter().filter(|a| a.parent_line.is_none()).collect();
    let late = top_level.iter().filter(|a| a.due.as_deref().is_some_and(|d| d < today_iso.as_str())).count();
    let daily = store.daily(today, false).map_err(err)?;
    let (mut done, mut total) = (0, 0);
    if let Some(note) = daily {
        for a in parser::extract(&note.body).actions.iter().filter(|a| a.parent_line.is_none()) {
            total += 1;
            done += usize::from(a.done);
        }
    }
    Ok(json!({
        "todayDone": done,
        "todayTotal": total,
        "open": top_level.len(),
        "late": late,
        "people": store.people().map_err(err)?.len(),
    }))
}

#[tauri::command(async)]
pub fn recent_notes(state: State<'_, AppState>, limit: usize) -> CmdResult<Vec<NoteSummary>> {
    state.store.list_notes(&Filter::default(), limit).map_err(err)
}

#[tauri::command(async)]
pub fn top_people(state: State<'_, AppState>, limit: usize) -> CmdResult<Vec<Facet>> {
    let mut people = state.store.people().map_err(err)?;
    people.truncate(limit);
    Ok(people)
}

#[tauri::command(async)]
pub fn all_tags(state: State<'_, AppState>) -> CmdResult<Vec<String>> {
    Ok(state.store.projects().map_err(err)?.into_iter().map(|f| f.name).collect())
}

#[tauri::command(async)]
pub fn search_titles(state: State<'_, AppState>, query: String, limit: usize) -> CmdResult<Vec<NoteSummary>> {
    state.store.search(&SearchQuery { text: query, limit, ..Default::default() }).map_err(err)
}

/// Risolve il bersaglio di un `[[link]]`: id oppure titolo.
#[tauri::command(async)]
pub fn resolve_link(state: State<'_, AppState>, target: String) -> CmdResult<Option<Value>> {
    let store = &state.store;
    if let Ok(note) = store.read(&target) {
        return Ok(Some(json!({"id": note.id, "title": note.title()})));
    }
    let found = store.search(&SearchQuery { text: target.clone(), limit: 20, ..Default::default() }).map_err(err)?;
    Ok(found
        .into_iter()
        .find(|n| n.title.eq_ignore_ascii_case(&target))
        .map(|n| json!({"id": n.id, "title": n.title})))
}

#[tauri::command(async)]
pub fn save_note(state: State<'_, AppState>, id: String, base: String, body: String) -> CmdResult<SaveOutcome> {
    state.store.save_if_unchanged(&id, &base, &body).map_err(err)
}

#[tauri::command(async)]
pub fn save_conflict(state: State<'_, AppState>, id: String, body: String) -> CmdResult<Value> {
    let copy = state.store.save_conflict_copy(&id, &body, Local::now().naive_local()).map_err(err)?;
    Ok(json!({"id": copy.id, "title": copy.title()}))
}

/// La nota del giorno a `delta` giorni da `date`, creata se manca.
#[tauri::command(async)]
pub fn daily_note(state: State<'_, AppState>, date: String, delta: i64) -> CmdResult<Value> {
    let day = dates::parse_day(&date).ok_or("Data non valida")? + Duration::days(delta);
    let note = state.store.daily(day, true).map_err(err)?.ok_or("Nota del giorno non disponibile")?;
    Ok(json!({"id": note.id, "title": dates::daily_title(day)}))
}

/// La data di oggi: l'app resta aperta anche per giorni.
#[tauri::command(async)]
pub fn today_info(state: State<'_, AppState>) -> CmdResult<Value> {
    let today = Local::now().date_naive();
    let daily = state.store.daily(today, true).map_err(err)?.ok_or("Nota del giorno non disponibile")?;
    let (_, _) = (dates::daily_title(today), ());
    Ok(json!({"id": daily.id, "title": dates::daily_title(today), "short": today.format("%d/%m").to_string()}))
}

/// Salva una nota rapida nella nota del giorno, nella sezione scelta.
#[tauri::command(async)]
pub fn capture_save(app: AppHandle, state: State<'_, AppState>, text: String, section: String, open: bool) -> CmdResult<()> {
    let today = Local::now().date_naive();
    let daily = state.store.daily(today, true).map_err(err)?.ok_or("Nota del giorno non disponibile")?;
    let note = state.store.add_to_section(&daily.id, Some(&section), &text).map_err(err)?;
    let _ = app.emit("note-changed", [&note.id]);
    let _ = app.emit("index-updated", 1);
    if open {
        let _ = app.emit("open-page", json!({"page": format!("note:{}", note.id), "title": format!("Oggi · {}", dates::short_day(today))}));
        crate::show_main(&app);
    }
    Ok(())
}

#[tauri::command]
pub fn hide_capture(app: AppHandle) {
    if let Some(window) = app.get_webview_window("capture") {
        let _ = window.hide();
    }
}

#[tauri::command]
pub fn quit(app: tauri::AppHandle) {
    app.exit(0);
}

#[derive(Serialize)]
pub struct NotePayload {
    id: String,
    title: String,
    tab_title: String,
    is_daily: bool,
    date: String,
    date_label: String,
    path: String,
    body: String,
    people: Vec<String>,
    actions_done: usize,
    actions_total: usize,
    links_in: Vec<quicknotes_core::index::Backlink>,
}

#[tauri::command(async)]
pub fn read_note(state: State<'_, AppState>, id: String) -> CmdResult<NotePayload> {
    let store = &state.store;
    let note = store.read(&id).map_err(err)?;
    let is_daily = note.note_type() == "daily" || note.id.ends_with("-giornata");
    let day = is_daily.then(|| dates::parse_day(note.date())).flatten();
    let title = day.map(dates::daily_title).unwrap_or_else(|| note.title().to_string());
    let tab_title = match day {
        Some(d) if d == Local::now().date_naive() => format!("Oggi · {}", dates::short_day(d)),
        _ => title.clone(),
    };
    let ex = parser::extract(&note.body);
    let mut people = note.people();
    for p in ex.people {
        if !people.iter().any(|x| x.eq_ignore_ascii_case(&p)) {
            people.push(p);
        }
    }
    let top: Vec<_> = ex.actions.iter().filter(|a| a.parent_line.is_none()).collect();
    let path = note.path.strip_prefix(store.root()).unwrap_or(&note.path).to_string_lossy().replace('\\', "/");
    Ok(NotePayload {
        title,
        tab_title,
        is_daily,
        date: note.date().to_string(),
        date_label: dates::parse_day(note.date()).map(dates::short_day).unwrap_or_default(),
        path,
        people,
        actions_done: top.iter().filter(|a| a.done).count(),
        actions_total: top.len(),
        links_in: store.backlinks(&note.id).map_err(err)?,
        id: note.id,
        body: note.body,
    })
}

#[tauri::command(async)]
pub fn action_board(state: State<'_, AppState>) -> CmdResult<views::Board> {
    views::action_board(&state.store, Local::now().date_naive()).map_err(err)
}

#[tauri::command(async)]
pub fn set_action_done(state: State<'_, AppState>, note_id: String, line: usize, text: String, done: bool) -> CmdResult<()> {
    let today = Local::now().date_naive();
    state.store.set_action_done(&note_id, line, Some(&text), done.then_some(today)).map(|_| ()).map_err(err)
}

#[tauri::command(async)]
pub fn complete_action(state: State<'_, AppState>, note_id: String, line: usize, text: String) -> CmdResult<()> {
    state.store.complete_with_children(&note_id, line, Some(&text), Local::now().date_naive()).map(|_| ()).map_err(err)
}

/// Cambia un solo dettaglio. `field`: due, person, tag, description.
#[tauri::command(async)]
pub fn set_action_field(
    state: State<'_, AppState>,
    note_id: String,
    line: usize,
    text: String,
    field: String,
    index: Option<usize>,
    value: Option<String>,
) -> CmdResult<()> {
    let value = value.filter(|v| !v.trim().is_empty());
    let mut patch = ActionPatch::default();
    match field.as_str() {
        "due" => patch.due = Some(value),
        "person" => patch.person = Some((index.unwrap_or(0), value)),
        "tag" => patch.tag = Some(value),
        "description" => patch.description = Some(value.unwrap_or_default()),
        other => return Err(format!("Campo sconosciuto: {other}")),
    }
    state.store.set_action_details(&note_id, line, Some(&text), patch).map(|_| ()).map_err(err)
}

/// Una nuova azione finisce nella nota di oggi, sezione "Priorità". Restituisce l'id della nota.
#[tauri::command(async)]
pub fn add_action(state: State<'_, AppState>, text: String) -> CmdResult<String> {
    let today = Local::now().date_naive();
    let daily = state.store.daily(today, true).map_err(err)?.ok_or("Nota del giorno non disponibile")?;
    let note = state.store.add_to_section(&daily.id, Some("Priorità"), &format!("- [ ] {}", text.trim())).map_err(err)?;
    Ok(note.id)
}

#[tauri::command(async)]
pub fn person_page(state: State<'_, AppState>, name: String) -> CmdResult<views::PersonPage> {
    views::person_page(&state.store, &name, Local::now().date_naive()).map_err(err)
}

#[tauri::command(async)]
pub fn people_list(state: State<'_, AppState>) -> CmdResult<Vec<views::PersonRow>> {
    views::people_list(&state.store, Local::now().date_naive()).map_err(err)
}

#[tauri::command(async)]
pub fn tag_page(state: State<'_, AppState>, tag: String) -> CmdResult<views::TagPage> {
    views::tag_page(&state.store, &tag, Local::now().date_naive()).map_err(err)
}

#[tauri::command(async)]
pub fn calendar_data(state: State<'_, AppState>, from: String, to: String) -> CmdResult<std::collections::HashMap<String, views::CalendarDay>> {
    views::calendar_data(&state.store, &from, &to, Local::now().date_naive()).map_err(err)
}

#[tauri::command(async)]
pub fn graph_data(state: State<'_, AppState>, id: String) -> CmdResult<views::Graph> {
    views::graph_data(&state.store, &id).map_err(err)
}

#[tauri::command(async)]
pub fn search_all(state: State<'_, AppState>, query: String) -> CmdResult<Vec<views::SearchHit>> {
    views::search_all(&state.store, &query).map_err(err)
}

#[tauri::command(async)]
pub fn new_note(state: State<'_, AppState>, title: String, note_type: String) -> CmdResult<Value> {
    let note = state.store.create_note(NewNote { title, note_type, ..Default::default() }).map_err(err)?;
    Ok(json!({"id": note.id, "title": note.title()}))
}

/// Apre un link della nota nel browser. Solo `http` e `https`: niente file, niente altri protocolli.
#[tauri::command]
pub fn open_url(app: AppHandle, url: String) -> CmdResult<()> {
    use tauri_plugin_opener::OpenerExt;
    let parsed = tauri::Url::parse(&url).map_err(|_| format!("Link non valido: {url}"))?;
    if !matches!(parsed.scheme(), "http" | "https") || parsed.host_str().is_none() {
        return Err(format!("Si aprono solo i link http e https: {url}"));
    }
    app.opener().open_url(parsed.as_str(), None::<&str>).map_err(err)
}

/// Il blocco da copiare in Claude: percorso reale del server MCP accanto all'app.
#[tauri::command]
pub fn claude_config() -> CmdResult<Value> {
    let exe = std::env::current_exe().map_err(err)?;
    let name = if cfg!(windows) { "quicknotes-mcp.exe" } else { "quicknotes-mcp" };
    let mcp = exe.with_file_name(name);
    let path = mcp.to_string_lossy().into_owned();
    Ok(json!({
        "exists": mcp.exists(),
        "desktop": serde_json::to_string_pretty(&json!({"mcpServers": {"quicknotes": {"command": path}}})).map_err(err)?,
        "code": format!("claude mcp add --transport stdio --scope user quicknotes -- \"{path}\""),
    }))
}
