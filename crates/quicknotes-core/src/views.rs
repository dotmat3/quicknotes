//! Dati pronti per le viste dell'interfaccia.

use std::collections::HashMap;

use chrono::{Datelike, Duration, NaiveDate};
use serde::Serialize;

use crate::dates::{self, DueGroup, DueLevel};
use crate::index::{ActionQuery, ActionRow, Filter, NoteSummary, SearchQuery, Status};
use crate::parser;
use crate::store::{NoteStore, Result};

/// Le azioni fatte senza data di completamento possono diventare centinaia: se ne mostrano poche.
const UNDATED_DONE_LIMIT: usize = 30;

#[derive(Debug, Clone, Serialize)]
pub struct SubItem {
    pub line: i64,
    /// Testo grezzo della riga, per controllare che non sia cambiata prima di scrivere.
    pub raw: String,
    pub text: String,
    pub done: bool,
    pub due_label: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct BoardItem {
    pub note_id: String,
    pub note_title: String,
    pub line: i64,
    pub raw: String,
    pub text: String,
    pub done: bool,
    pub done_on: Option<String>,
    pub due: Option<String>,
    pub due_label: Option<String>,
    pub due_level: Option<DueLevel>,
    pub group: DueGroup,
    pub people: Vec<String>,
    pub tag: Option<String>,
    pub description: String,
    pub subs: Vec<SubItem>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Board {
    pub items: Vec<BoardItem>,
    pub open: usize,
    pub late: usize,
    pub done_this_week: usize,
    pub week_number: u32,
    /// Scadenza di un'azione aggiunta con il "+" della colonna: `soon`, `week`, `later`. Manca se la colonna
    /// oggi non può ricevere date.
    pub column_due: HashMap<DueGroup, String>,
}

fn clean_text(raw: &str, tag: Option<&str>) -> String {
    let display = parser::action_display_text(raw);
    // L'etichetta è mostrata dalla pillola: nel testo resta solo se è dentro la frase.
    let Some(tag) = tag else { return display };
    let marker = format!("#{tag}");
    match display.to_lowercase().strip_suffix(&marker) {
        Some(_) => display[..display.len() - marker.len()].trim_end().to_string(),
        None => display,
    }
}

type Children<'a> = HashMap<(String, i64), Vec<&'a ActionRow>>;

/// Le figlie di ogni madre, per nota e riga della madre.
fn children_of(rows: &[ActionRow]) -> Children<'_> {
    let mut children: Children = HashMap::new();
    for row in rows {
        if let Some(parent) = row.parent_line {
            children.entry((row.note_id.clone(), parent)).or_default().push(row);
        }
    }
    children
}

/// Una scheda della bacheca: la stessa in bacheca, in elenco e nella pagina etichetta.
fn board_item(row: &ActionRow, children: &Children, today: NaiveDate) -> BoardItem {
    let due = row.due.as_deref().and_then(dates::parse_day);
    let label = due.map(|d| dates::due_label(d, today));
    let mut subs: Vec<SubItem> = children
        .get(&(row.note_id.clone(), row.line))
        .map(|c| {
            c.iter()
                .map(|s| SubItem {
                    line: s.line,
                    raw: s.text.clone(),
                    text: parser::action_display_text(&s.text),
                    done: s.done,
                    due_label: s.due.as_deref().and_then(dates::parse_day).map(|d| dates::due_label(d, today).0),
                })
                .collect()
        })
        .unwrap_or_default();
    subs.sort_by_key(|s| s.line);
    BoardItem {
        note_id: row.note_id.clone(),
        note_title: row.note_title.clone(),
        line: row.line,
        raw: row.text.clone(),
        text: clean_text(&row.text, row.tags.first().map(String::as_str)),
        done: row.done,
        done_on: row.done_on.clone(),
        due: row.due.clone(),
        due_label: label.as_ref().map(|l| l.0.clone()),
        due_level: label.map(|l| l.1),
        group: dates::due_group(due, today),
        people: row.people.clone(),
        tag: row.tags.first().cloned().or_else(|| row.project.clone()),
        description: row.description.clone(),
        subs,
    }
}

/// Tutte le azioni di primo livello con le loro figlie. Le figlie ereditano etichetta e persone.
pub fn action_board(store: &NoteStore, today: NaiveDate) -> Result<Board> {
    let rows = store.actions(&ActionQuery { status: Status::All, limit: 100_000, ..Default::default() })?;
    let children = children_of(&rows);
    let monday = today - Duration::days(i64::from(today.weekday().num_days_from_monday()));
    let sunday = monday + Duration::days(6);
    let (mut open, mut late, mut done_week, mut undated) = (0, 0, 0, 0);
    let mut items = Vec::new();

    for row in rows.iter().filter(|r| r.parent_line.is_none()) {
        let done_on = row.done_on.as_deref().and_then(dates::parse_day);
        if row.done {
            if done_on.is_some_and(|d| d >= monday && d <= sunday) {
                done_week += 1;
            }
            if done_on.is_none() {
                undated += 1;
                if undated > UNDATED_DONE_LIMIT {
                    continue;
                }
            }
        }
        let item = board_item(row, &children, today);
        if !row.done {
            open += 1;
            late += usize::from(item.group == DueGroup::Late);
        }
        items.push(item);
    }
    let column_due = [DueGroup::Soon, DueGroup::Week, DueGroup::Later]
        .into_iter()
        .filter_map(|g| dates::first_day_in(g, today).map(|d| (g, d.format("%Y-%m-%d").to_string())))
        .collect();
    Ok(Board { items, open, late, done_this_week: done_week, week_number: today.iso_week().week(), column_due })
}

#[derive(Debug, Clone, Serialize)]
pub struct NoteRef {
    pub id: String,
    pub title: String,
    pub date: String,
    pub is_daily: bool,
}

fn note_ref(n: &NoteSummary) -> NoteRef {
    NoteRef { id: n.id.clone(), title: n.title.clone(), date: n.date.clone(), is_daily: n.note_type == "daily" }
}

#[derive(Debug, Clone, Serialize)]
pub struct PageAction {
    pub note_id: String,
    pub note_title: String,
    pub text: String,
    pub due_label: Option<String>,
    pub due_level: Option<DueLevel>,
    /// Titolo della madre, se è una sotto-attività.
    pub parent: Option<String>,
}

fn page_action(row: &ActionRow, today: NaiveDate, parent: Option<String>) -> PageAction {
    let label = row.due.as_deref().and_then(dates::parse_day).map(|d| dates::due_label(d, today));
    PageAction {
        note_id: row.note_id.clone(),
        note_title: row.note_title.clone(),
        text: parser::action_display_text(&row.text),
        due_label: label.as_ref().map(|l| l.0.clone()),
        due_level: label.map(|l| l.1),
        parent,
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct DecisionRef {
    pub text: String,
    pub note_id: String,
    pub date: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PersonPage {
    pub name: String,
    pub notes_count: usize,
    pub first_seen: Option<String>,
    pub actions: Vec<PageAction>,
    pub notes: Vec<NoteRef>,
    pub decisions: Vec<DecisionRef>,
}

fn is_person(n: &NoteSummary, name: &str) -> bool {
    n.people.iter().any(|p| p.eq_ignore_ascii_case(name))
}

/// Solo i nomi `@` grezzi: `@Giulia` e `@G.Ferri` restano due persone.
pub fn person_page(store: &NoteStore, name: &str, today: NaiveDate) -> Result<PersonPage> {
    let filter = Filter { person: Some(name.to_string()), ..Default::default() };
    let notes: Vec<NoteSummary> = store.list_notes(&filter, 500)?.into_iter().filter(|n| is_person(n, name)).collect();
    let rows = store.actions(&ActionQuery { limit: 100_000, ..Default::default() })?;
    let titles: HashMap<(String, i64), String> = rows.iter().map(|r| ((r.note_id.clone(), r.line), parser::action_display_text(&r.text))).collect();
    let actions = rows
        .iter()
        .filter(|r| r.people.iter().any(|p| p.eq_ignore_ascii_case(name)))
        .map(|r| page_action(r, today, r.parent_line.and_then(|l| titles.get(&(r.note_id.clone(), l)).cloned())))
        .collect();
    let ids: std::collections::HashSet<&str> = notes.iter().map(|n| n.id.as_str()).collect();
    let decisions = store
        .decisions(&filter, "", 200)?
        .into_iter()
        .filter(|d| ids.contains(d.note_id.as_str()))
        .map(|d| DecisionRef { text: d.text, note_id: d.note_id, date: d.date })
        .collect();
    Ok(PersonPage {
        name: notes.iter().flat_map(|n| n.people.iter()).find(|p| p.eq_ignore_ascii_case(name)).cloned().unwrap_or_else(|| name.to_string()),
        notes_count: notes.len(),
        first_seen: notes.last().map(|n| n.date.clone()),
        actions,
        decisions,
        notes: notes.iter().take(30).map(note_ref).collect(),
    })
}

#[derive(Debug, Clone, Serialize)]
pub struct PersonRow {
    pub name: String,
    pub notes: i64,
    pub last_seen: Option<String>,
    pub open: usize,
    pub late: usize,
}

pub fn people_list(store: &NoteStore, today: NaiveDate) -> Result<Vec<PersonRow>> {
    let today_iso = today.format("%Y-%m-%d").to_string();
    let rows = store.actions(&ActionQuery { limit: 100_000, ..Default::default() })?;
    Ok(store
        .people()?
        .into_iter()
        .map(|p| {
            let mine: Vec<_> = rows.iter().filter(|r| r.people.iter().any(|x| x.eq_ignore_ascii_case(&p.name))).collect();
            PersonRow {
                late: mine.iter().filter(|r| r.due.as_deref().is_some_and(|d| d < today_iso.as_str())).count(),
                open: mine.len(),
                name: p.name,
                notes: p.notes,
                last_seen: p.last_seen,
            }
        })
        .collect())
}

#[derive(Debug, Clone, Serialize)]
pub struct TagPage {
    pub tag: String,
    pub notes_count: usize,
    /// Azioni aperte di primo livello, come in bacheca: si modificano con le pillole.
    pub actions: Vec<BoardItem>,
    pub notes: Vec<NoteRef>,
    pub decisions: Vec<DecisionRef>,
    pub people: Vec<String>,
}

pub fn tag_page(store: &NoteStore, tag: &str, today: NaiveDate) -> Result<TagPage> {
    let filter = Filter { project: Some(tag.to_string()), ..Default::default() };
    let notes = store.list_notes(&filter, 500)?;
    let lower = tag.to_lowercase();
    let rows = store.actions(&ActionQuery { status: Status::All, limit: 100_000, ..Default::default() })?;
    let children = children_of(&rows);
    let actions = rows
        .iter()
        .filter(|r| !r.done && r.parent_line.is_none() && (r.tags.iter().any(|t| *t == lower) || r.project.as_deref() == Some(lower.as_str())))
        .map(|r| board_item(r, &children, today))
        .collect();
    let mut people: Vec<String> = Vec::new();
    for p in notes.iter().flat_map(|n| n.people.iter()) {
        if !people.iter().any(|x| x.eq_ignore_ascii_case(p)) {
            people.push(p.clone());
        }
    }
    Ok(TagPage {
        tag: lower,
        notes_count: notes.len(),
        actions,
        decisions: store.decisions(&filter, "", 100)?.into_iter().map(|d| DecisionRef { text: d.text, note_id: d.note_id, date: d.date }).collect(),
        people,
        notes: notes.iter().take(30).map(note_ref).collect(),
    })
}

#[derive(Debug, Clone, Serialize)]
pub struct CalendarEvent {
    pub kind: &'static str,
    pub text: String,
    pub note_id: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct CalendarDay {
    pub daily: Option<String>,
    pub events: Vec<CalendarEvent>,
}

/// Note, scadenze, completamenti e decisioni per giorno, da `from` a `to` inclusi.
pub fn calendar_data(store: &NoteStore, from: &str, to: &str, today: NaiveDate) -> Result<HashMap<String, CalendarDay>> {
    let mut days: HashMap<String, CalendarDay> = HashMap::new();
    let filter = Filter { date_from: Some(from.to_string()), date_to: Some(to.to_string()), ..Default::default() };
    for n in store.list_notes(&filter, 5000)? {
        let Some(day) = n.date.get(..10) else { continue };
        let entry = days.entry(day.to_string()).or_default();
        if n.note_type == "daily" {
            entry.daily = Some(n.id);
        } else {
            entry.events.push(CalendarEvent { kind: "note", text: n.title, note_id: Some(n.id) });
        }
    }
    for d in store.decisions(&filter, "", 5000)? {
        let Some(day) = d.date.get(..10) else { continue };
        days.entry(day.to_string()).or_default().events.push(CalendarEvent { kind: "dec", text: d.text, note_id: Some(d.note_id) });
    }
    let today_iso = today.format("%Y-%m-%d").to_string();
    for a in store.actions(&ActionQuery { status: Status::All, limit: 100_000, ..Default::default() })? {
        let text = parser::action_display_text(&a.text);
        if let Some(day) = a.done_on.as_deref().filter(|d| *d >= from && *d <= to) {
            days.entry(day.to_string()).or_default().events.push(CalendarEvent { kind: "done", text: text.clone(), note_id: Some(a.note_id.clone()) });
        }
        if !a.done {
            if let Some(day) = a.due.as_deref().filter(|d| *d >= from && *d <= to) {
                let kind = if day < today_iso.as_str() { "late" } else { "due" };
                days.entry(day.to_string()).or_default().events.push(CalendarEvent { kind, text, note_id: Some(a.note_id.clone()) });
            }
        }
    }
    Ok(days)
}

#[derive(Debug, Clone, Serialize)]
pub struct GraphNode {
    pub id: String,
    pub label: String,
    pub kind: &'static str,
    pub page: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct Graph {
    pub nodes: Vec<GraphNode>,
    pub edges: Vec<(usize, usize)>,
}

/// Collegamenti attorno a una nota: persone, etichette, note citate e note che la citano.
pub fn graph_data(store: &NoteStore, id: &str) -> Result<Graph> {
    let note = store.read(id)?;
    let ex = parser::extract(&note.body);
    let mut nodes = vec![GraphNode { id: note.id.clone(), label: note.title().to_string(), kind: "center", page: format!("note:{}", note.id) }];
    let mut edges = Vec::new();
    let mut add = |nodes: &mut Vec<GraphNode>, n: GraphNode| {
        if !nodes.iter().any(|x| x.page == n.page) {
            nodes.push(n);
            edges.push((0, nodes.len() - 1));
        }
    };
    for p in note.people().into_iter().chain(ex.people) {
        add(&mut nodes, GraphNode { id: p.clone(), label: format!("@{p}"), kind: "person", page: format!("person:{p}") });
    }
    for t in note.tags().into_iter().map(|t| t.to_lowercase()).chain(ex.tags) {
        add(&mut nodes, GraphNode { id: t.clone(), label: format!("#{t}"), kind: "tag", page: format!("tag:{t}") });
    }
    for l in store.outgoing_links(&note.id)? {
        if let (Some(nid), Some(title)) = (l.note_id, l.note_title) {
            add(&mut nodes, GraphNode { id: nid.clone(), label: title, kind: "note", page: format!("note:{nid}") });
        }
    }
    for b in store.backlinks(&note.id)? {
        add(&mut nodes, GraphNode { id: b.note_id.clone(), label: b.note_title, kind: "note", page: format!("note:{}", b.note_id) });
    }
    Ok(Graph { nodes, edges })
}

#[derive(Debug, Clone, Serialize)]
pub struct SearchHit {
    pub kind: &'static str,
    pub label: String,
    pub hint: String,
    pub page: String,
    pub snippet: Option<String>,
}

/// La ricerca di Ctrl K. `@nome`, `#etichetta` filtrano; `!parole` cerca tra le decisioni.
pub fn search_all(store: &NoteStore, query: &str) -> Result<Vec<SearchHit>> {
    let mut filter = Filter::default();
    let mut words = Vec::new();
    let mut decisions = false;
    for w in query.split_whitespace() {
        if let Some(p) = w.strip_prefix('@').filter(|p| !p.is_empty()) {
            filter.person = Some(p.to_string());
        } else if let Some(t) = w.strip_prefix('#').filter(|t| !t.is_empty()) {
            filter.project = Some(t.to_string());
        } else if w == "!" || w.eq_ignore_ascii_case("!decisione") {
            decisions = true;
        } else if let Some(d) = w.strip_prefix('!') {
            decisions = true;
            words.push(d.to_string());
        } else {
            words.push(w.to_string());
        }
    }
    let text = words.join(" ");
    let mut hits = Vec::new();
    if decisions {
        for d in store.decisions(&filter, &text, 15)? {
            hits.push(SearchHit { kind: "decision", label: d.text, hint: d.date.chars().take(10).collect(), page: format!("note:{}", d.note_id), snippet: None });
        }
        return Ok(hits);
    }
    if text.is_empty() {
        if let Some(p) = &filter.person {
            let lower = p.to_lowercase();
            for f in store.people()?.into_iter().filter(|f| f.name.to_lowercase().contains(&lower)).take(5) {
                hits.push(SearchHit { kind: "person", label: format!("@{}", f.name), hint: format!("{} note", f.notes), page: format!("person:{}", f.name), snippet: None });
            }
        }
        if let Some(t) = &filter.project {
            let lower = t.to_lowercase();
            for f in store.projects()?.into_iter().filter(|f| f.name.contains(&lower)).take(5) {
                hits.push(SearchHit { kind: "tag", label: format!("#{}", f.name), hint: format!("{} note", f.notes), page: format!("tag:{}", f.name), snippet: None });
            }
        }
    }
    for n in store.search(&SearchQuery { text, filter, limit: 15 })? {
        hits.push(SearchHit {
            kind: "note",
            hint: n.date.chars().take(10).collect(),
            page: format!("note:{}", n.id),
            label: n.title,
            snippet: n.snippet,
        });
    }
    Ok(hits)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn day(s: &str) -> NaiveDate {
        dates::parse_day(s).unwrap()
    }

    #[test]
    fn bacheca_con_gruppi_figlie_e_conteggi() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(
            dir.path().join("a.md"),
            "---\ntitle: Nota A\ndate: 2026-11-02\nproject: clientex\n---\n\
             - [ ] Madre #casa due:2026-11-01\n    Descrizione\n    - [x] Figlia done:2026-11-02\n    - [ ] Altra due:2026-11-03\n\
             - [ ] Domani @Marco due:2026-11-04\n\
             - [ ] Senza scadenza\n\
             - [x] Fatta #casa done:2026-11-03\n\
             - [x] Vecchia done:2026-01-01\n",
        )
        .unwrap();
        let store = NoteStore::open(dir.path()).unwrap();
        store.refresh().unwrap();
        let board = action_board(&store, day("2026-11-03")).unwrap();
        assert_eq!(board.open, 3, "le figlie non contano");
        assert_eq!(board.late, 1);
        assert_eq!(board.done_this_week, 1);
        assert_eq!(board.items.len(), 5);
        let madre = board.items.iter().find(|i| i.text == "Madre").unwrap();
        assert_eq!(madre.group, DueGroup::Late);
        assert_eq!(madre.tag.as_deref(), Some("casa"));
        assert_eq!(madre.description, "Descrizione");
        assert_eq!(madre.subs.len(), 2);
        assert_eq!(madre.subs[0].text, "Figlia");
        assert_eq!(madre.subs[1].due_label.as_deref(), Some("oggi"));
        let domani = board.items.iter().find(|i| i.text.starts_with("Domani")).unwrap();
        assert_eq!(domani.group, DueGroup::Soon);
        assert_eq!(domani.people, ["Marco"]);
        assert_eq!(domani.tag.as_deref(), Some("clientex"), "senza etichetta vale il progetto della nota");
        assert_eq!(board.column_due.get(&DueGroup::Week).map(String::as_str), Some("2026-11-05"));
        let json = serde_json::to_value(&board).unwrap();
        assert_eq!(json["column_due"]["soon"], "2026-11-03", "le chiavi sono i nomi delle colonne");
    }

    fn demo() -> (tempfile::TempDir, NoteStore) {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join("2026-11-02-giornata.md"), "---\ntype: daily\ntitle: G\ndate: 2026-11-02\n---\n- [ ] Madre @Giulia #casa due:2026-11-01\n    - [ ] Figlia @Marco due:2026-11-05\nTop in quarzo !decisione con @Marco\nVedi [[riunione]]\n").unwrap();
        fs::write(dir.path().join("riunione.md"), "---\ntype: meeting\ntitle: Riunione budget\ndate: 2026-11-03T10:00\npeople: [Giulia]\ntags: [casa]\n---\n- [x] Fatta done:2026-11-03\n").unwrap();
        let store = NoteStore::open(dir.path()).unwrap();
        store.refresh().unwrap();
        (dir, store)
    }

    #[test]
    fn pagina_persona_con_figlie_e_madre() {
        let (_d, store) = demo();
        let p = person_page(&store, "marco", day("2026-11-03")).unwrap();
        assert_eq!(p.name, "Marco");
        assert_eq!(p.actions.len(), 1);
        assert_eq!(p.actions[0].parent.as_deref(), Some("Madre @Giulia #casa"));
        assert_eq!(p.decisions[0].text, "Top in quarzo  con @Marco");
        let list = people_list(&store, day("2026-11-03")).unwrap();
        let giulia = list.iter().find(|r| r.name == "Giulia").unwrap();
        assert_eq!((giulia.notes, giulia.open, giulia.late), (2, 1, 1));
    }

    #[test]
    fn pagina_etichetta() {
        let (_d, store) = demo();
        let t = tag_page(&store, "#Casa".trim_start_matches('#'), day("2026-11-03")).unwrap();
        assert_eq!(t.tag, "casa");
        assert_eq!(t.notes_count, 2);
        assert_eq!(t.actions.len(), 1);
        assert_eq!(t.actions[0].raw, "Madre @Giulia #casa due:2026-11-01", "il testo grezzo serve alle pillole per controllare la riga");
        assert_eq!(t.actions[0].subs.len(), 1, "come in bacheca, con le figlie");
        assert!(t.people.contains(&"Giulia".to_string()));
    }

    #[test]
    fn calendario_per_giorno() {
        let (_d, store) = demo();
        let c = calendar_data(&store, "2026-11-01", "2026-11-30", day("2026-11-03")).unwrap();
        assert_eq!(c["2026-11-02"].daily.as_deref(), Some("2026-11-02-giornata"));
        assert_eq!(c["2026-11-01"].events[0].kind, "late");
        assert_eq!(c["2026-11-05"].events[0].kind, "due");
        let kinds: Vec<_> = c["2026-11-03"].events.iter().map(|e| e.kind).collect();
        assert!(kinds.contains(&"note") && kinds.contains(&"done"));
    }

    #[test]
    fn grafo_attorno_alla_nota() {
        let (_d, store) = demo();
        let g = graph_data(&store, "2026-11-02-giornata").unwrap();
        let pages: Vec<_> = g.nodes.iter().map(|n| n.page.as_str()).collect();
        assert!(pages.contains(&"person:Marco") && pages.contains(&"tag:casa") && pages.contains(&"note:riunione"));
        assert_eq!(g.edges.len(), g.nodes.len() - 1);
    }

    #[test]
    fn ricerca_con_filtri() {
        let (_d, store) = demo();
        let labels = |q: &str| search_all(&store, q).unwrap().into_iter().map(|h| h.label).collect::<Vec<_>>();
        assert_eq!(labels("riunion")[0], "Riunione budget", "prima il titolo, poi chi la cita");
        assert_eq!(labels("!quarzo"), ["Top in quarzo  con @Marco"]);
        assert!(labels("@gi").contains(&"@Giulia".to_string()));
        assert!(labels("#ca").contains(&"#casa".to_string()));
        assert_eq!(labels("riunione @Giulia #casa")[0], "Riunione budget");
    }
}
