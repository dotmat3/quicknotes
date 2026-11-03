//! Indice SQLite: si può cancellare in ogni momento, perché si ricostruisce dai file.

use std::collections::HashMap;
use std::path::Path;
use std::time::Duration;

use rusqlite::{params, params_from_iter, types::Value as SqlValue, Connection, Row};
use serde::Serialize;

use crate::parser;
use crate::store::{Note, Result};

const SCHEMA_VERSION: i32 = 3;
const SCHEMA: &str = "
CREATE TABLE IF NOT EXISTS notes(
    path TEXT PRIMARY KEY, id TEXT, type TEXT, title TEXT, date TEXT,
    project TEXT, mtime INTEGER, size INTEGER);
CREATE INDEX IF NOT EXISTS notes_id ON notes(id);
CREATE INDEX IF NOT EXISTS notes_date ON notes(date);
CREATE TABLE IF NOT EXISTS note_people(path TEXT, person TEXT, key TEXT);
CREATE INDEX IF NOT EXISTS note_people_path ON note_people(path);
CREATE INDEX IF NOT EXISTS note_people_key ON note_people(key);
CREATE TABLE IF NOT EXISTS note_tags(path TEXT, tag TEXT);
CREATE INDEX IF NOT EXISTS note_tags_path ON note_tags(path);
CREATE INDEX IF NOT EXISTS note_tags_tag ON note_tags(tag);
CREATE TABLE IF NOT EXISTS actions(
    path TEXT, line_no INTEGER, text TEXT, done INTEGER, owner TEXT, due TEXT,
    done_on TEXT, parent_line INTEGER, people TEXT, tags TEXT, description TEXT);
CREATE INDEX IF NOT EXISTS actions_path ON actions(path);
CREATE INDEX IF NOT EXISTS actions_done ON actions(done, due);
CREATE TABLE IF NOT EXISTS decisions(path TEXT, line_no INTEGER, text TEXT);
CREATE INDEX IF NOT EXISTS decisions_path ON decisions(path);
CREATE TABLE IF NOT EXISTS links(path TEXT, line_no INTEGER, target TEXT, key TEXT, label TEXT, line TEXT);
CREATE INDEX IF NOT EXISTS links_path ON links(path);
CREATE INDEX IF NOT EXISTS links_key ON links(key);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    path UNINDEXED, title, body, people, tags, tokenize='unicode61 remove_diacritics 2');
";
const TABLES: [&str; 7] = ["notes", "note_people", "note_tags", "actions", "decisions", "links", "notes_fts"];

pub(crate) fn open(path: &Path) -> rusqlite::Result<Connection> {
    let db = Connection::open(path)?;
    db.busy_timeout(Duration::from_secs(10))?;
    db.pragma_update(None, "journal_mode", "WAL")?;
    db.pragma_update(None, "synchronous", "NORMAL")?;
    db.pragma_update(None, "temp_store", "MEMORY")?;
    Ok(db)
}

pub(crate) fn init_schema(db: &Connection) -> rusqlite::Result<()> {
    let version: i32 = db.query_row("PRAGMA user_version", [], |r| r.get(0))?;
    if version != SCHEMA_VERSION {
        clear(db)?;
    }
    db.execute_batch(SCHEMA)?;
    db.pragma_update(None, "user_version", SCHEMA_VERSION)
}

pub(crate) fn clear(db: &Connection) -> rusqlite::Result<()> {
    for table in TABLES {
        db.execute_batch(&format!("DROP TABLE IF EXISTS {table};"))?;
    }
    db.execute_batch(SCHEMA)
}

pub(crate) fn signatures(db: &Connection) -> rusqlite::Result<HashMap<String, (i64, i64)>> {
    let mut stmt = db.prepare("SELECT path, mtime, size FROM notes")?;
    let rows = stmt.query_map([], |r| Ok((r.get(0)?, (r.get(1)?, r.get(2)?))))?;
    rows.collect()
}

pub(crate) fn delete_rows(db: &Connection, rel: &str) -> rusqlite::Result<()> {
    for table in TABLES {
        db.prepare_cached(&format!("DELETE FROM {table} WHERE path=?1"))?.execute([rel])?;
    }
    Ok(())
}

pub(crate) fn path_for_id(db: &Connection, id: &str) -> rusqlite::Result<Option<String>> {
    let mut stmt = db.prepare_cached("SELECT path FROM notes WHERE id=?1 OR path=?2 ORDER BY mtime DESC LIMIT 1")?;
    let mut rows = stmt.query(params![id, format!("{id}.md")])?;
    rows.next()?.map(|r| r.get(0)).transpose()
}

fn dedupe_ci(items: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    items.into_iter().filter(|i| seen.insert(i.to_lowercase())).collect()
}

pub(crate) fn index_note(db: &Connection, rel: &str, note: &Note, mtime: i64, size: i64) -> rusqlite::Result<()> {
    let ex = parser::extract(&note.body);
    let people = dedupe_ci(note.people().into_iter().chain(ex.people.iter().cloned()));
    let tags = dedupe_ci(
        note.tags()
            .into_iter()
            .map(|t| t.trim_start_matches('#').to_lowercase())
            .chain(ex.tags.iter().cloned()),
    );
    delete_rows(db, rel)?;
    db.prepare_cached("INSERT INTO notes(path,id,type,title,date,project,mtime,size) VALUES(?1,?2,?3,?4,?5,?6,?7,?8)")?
        .execute(params![rel, note.id, note.note_type(), note.title(), note.date(), note.project().to_lowercase(), mtime, size])?;
    {
        let mut stmt = db.prepare_cached("INSERT INTO note_people VALUES(?1,?2,?3)")?;
        for p in &people {
            stmt.execute(params![rel, p, p.to_lowercase()])?;
        }
    }
    {
        let mut stmt = db.prepare_cached("INSERT INTO note_tags VALUES(?1,?2)")?;
        for t in &tags {
            stmt.execute(params![rel, t])?;
        }
    }
    {
        let mut stmt = db.prepare_cached("INSERT INTO actions VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)")?;
        for a in &ex.actions {
            stmt.execute(params![
                rel, a.line_no as i64, a.text, a.done, a.owner, a.due, a.done_on,
                a.parent_line.map(|l| l as i64), a.people.join(" "), a.tags.join(" "), a.description
            ])?;
        }
    }
    {
        let mut stmt = db.prepare_cached("INSERT INTO decisions VALUES(?1,?2,?3)")?;
        for d in &ex.decisions {
            stmt.execute(params![rel, d.line_no as i64, d.text])?;
        }
    }
    {
        let mut stmt = db.prepare_cached("INSERT INTO links VALUES(?1,?2,?3,?4,?5,?6)")?;
        for l in &ex.links {
            stmt.execute(params![rel, l.line_no as i64, l.target, l.target.to_lowercase(), l.label, l.line])?;
        }
    }
    db.prepare_cached("INSERT INTO notes_fts(path,title,body,people,tags) VALUES(?1,?2,?3,?4,?5)")?
        .execute(params![rel, note.title(), note.body, people.join(" "), tags.join(" ")])?;
    Ok(())
}

/// Filtri comuni. Le date sono `AAAA-MM-GG`, incluse.
#[derive(Debug, Clone, Default)]
pub struct Filter {
    pub date_from: Option<String>,
    pub date_to: Option<String>,
    pub person: Option<String>,
    pub project: Option<String>,
    pub note_type: Option<String>,
}

impl Filter {
    fn sql(&self, out: &mut Vec<String>, args: &mut Vec<SqlValue>) {
        if let Some(d) = &self.date_from {
            out.push("substr(n.date,1,10) >= ?".into());
            args.push(day(d).into());
        }
        if let Some(d) = &self.date_to {
            out.push("substr(n.date,1,10) <= ?".into());
            args.push(day(d).into());
        }
        if let Some(p) = &self.person {
            out.push("n.path IN (SELECT path FROM note_people WHERE key LIKE ?)".into());
            args.push(format!("%{}%", p.to_lowercase().trim_start_matches('@')).into());
        }
        if let Some(p) = &self.project {
            let p = p.to_lowercase();
            let p = p.trim_start_matches('#').to_string();
            out.push("(n.project = ? OR n.path IN (SELECT path FROM note_tags WHERE tag = ?))".into());
            args.push(p.clone().into());
            args.push(p.into());
        }
        if let Some(t) = &self.note_type {
            out.push("n.type = ?".into());
            args.push(t.clone().into());
        }
    }
}

fn day(value: &str) -> String {
    value.chars().take(10).collect()
}

fn where_clause(parts: &[String]) -> String {
    if parts.is_empty() {
        String::new()
    } else {
        format!("WHERE {}", parts.join(" AND "))
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct NoteSummary {
    pub id: String,
    pub title: String,
    #[serde(rename = "type")]
    pub note_type: String,
    pub date: String,
    pub project: Option<String>,
    pub people: Vec<String>,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub snippet: Option<String>,
}

fn people_of(db: &Connection, rel: &str) -> rusqlite::Result<Vec<String>> {
    let mut stmt = db.prepare_cached("SELECT person FROM note_people WHERE path=?1")?;
    let rows = stmt.query_map([rel], |r| r.get(0))?;
    rows.collect()
}

fn summary(db: &Connection, r: &Row, snippet: Option<String>) -> rusqlite::Result<NoteSummary> {
    let path: String = r.get("path")?;
    let project: String = r.get("project")?;
    Ok(NoteSummary {
        people: people_of(db, &path)?,
        id: r.get("id")?,
        title: r.get("title")?,
        note_type: r.get("type")?,
        date: r.get("date")?,
        project: Some(project).filter(|p| !p.is_empty()),
        path,
        snippet,
    })
}

pub fn fts_query(query: &str, op: &str) -> String {
    let mut terms = Vec::new();
    let mut cur = String::new();
    for c in query.chars() {
        let word = c.is_alphanumeric() || c == '_';
        let inner = !cur.is_empty() && matches!(c, '\'' | '’' | '.' | '-');
        if word || inner {
            cur.push(c);
        } else if !cur.is_empty() {
            terms.push(std::mem::take(&mut cur));
        }
    }
    if !cur.is_empty() {
        terms.push(cur);
    }
    terms.iter().map(|t| format!("\"{t}\"*")).collect::<Vec<_>>().join(&format!(" {op} "))
}

#[derive(Debug, Clone, Default)]
pub struct SearchQuery {
    pub text: String,
    pub filter: Filter,
    pub limit: usize,
}

/// Ricerca testuale: prima tutte le parole, poi almeno una. Senza parole applica solo i filtri.
pub fn search(db: &Connection, q: &SearchQuery) -> Result<Vec<NoteSummary>> {
    if fts_query(&q.text, "AND").is_empty() {
        return list_notes(db, &q.filter, q.limit);
    }
    let mut where_parts = Vec::new();
    let mut filter_args = Vec::new();
    q.filter.sql(&mut where_parts, &mut filter_args);
    let extra: String = where_parts.iter().map(|w| format!("AND {w} ")).collect();
    let sql = format!(
        "SELECT n.*, snippet(notes_fts, 2, '«', '»', ' … ', 16) AS snip \
         FROM notes_fts JOIN notes n ON n.path = notes_fts.path \
         WHERE notes_fts MATCH ? {extra} ORDER BY bm25(notes_fts, 0, 6.0, 1.0, 3.0, 3.0) LIMIT ?"
    );
    for op in ["AND", "OR"] {
        let mut args: Vec<SqlValue> = vec![fts_query(&q.text, op).into()];
        args.extend(filter_args.iter().cloned());
        args.push((q.limit as i64).into());
        let mut stmt = db.prepare_cached(&sql)?;
        let rows = stmt.query_map(params_from_iter(args), |r| {
            let snip: Option<String> = r.get("snip")?;
            summary(db, r, snip)
        })?;
        let found: Vec<NoteSummary> = rows.collect::<rusqlite::Result<_>>()?;
        if !found.is_empty() {
            return Ok(found);
        }
    }
    Ok(Vec::new())
}

pub fn list_notes(db: &Connection, f: &Filter, limit: usize) -> Result<Vec<NoteSummary>> {
    let mut parts = Vec::new();
    let mut args = Vec::new();
    f.sql(&mut parts, &mut args);
    args.push((limit as i64).into());
    let sql = format!("SELECT n.* FROM notes n {} ORDER BY n.date DESC, n.mtime DESC LIMIT ?", where_clause(&parts));
    let mut stmt = db.prepare_cached(&sql)?;
    let rows = stmt.query_map(params_from_iter(args), |r| summary(db, r, None))?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Status {
    #[default]
    Open,
    Done,
    All,
}

#[derive(Debug, Clone, Default)]
pub struct ActionQuery {
    pub status: Status,
    pub owner: Option<String>,
    pub project: Option<String>,
    pub due_before: Option<String>,
    pub date_from: Option<String>,
    pub date_to: Option<String>,
    /// Parole che il testo dell'azione deve contenere tutte.
    pub text: Option<String>,
    pub limit: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct ActionRow {
    pub text: String,
    pub done: bool,
    pub owner: Option<String>,
    pub due: Option<String>,
    pub done_on: Option<String>,
    pub note_id: String,
    pub note_title: String,
    pub note_date: String,
    pub line: i64,
    pub parent_line: Option<i64>,
    pub description: String,
    pub people: Vec<String>,
    pub tags: Vec<String>,
    pub project: Option<String>,
}

fn split_words(value: String) -> Vec<String> {
    value.split_whitespace().map(String::from).collect()
}

pub fn actions(db: &Connection, q: &ActionQuery) -> Result<Vec<ActionRow>> {
    let filter = Filter {
        date_from: q.date_from.clone(),
        date_to: q.date_to.clone(),
        project: q.project.clone(),
        ..Filter::default()
    };
    let mut parts = Vec::new();
    let mut args = Vec::new();
    filter.sql(&mut parts, &mut args);
    match q.status {
        Status::Open => parts.push("a.done = 0".into()),
        Status::Done => parts.push("a.done = 1".into()),
        Status::All => {}
    }
    if let Some(owner) = &q.owner {
        parts.push("lower(coalesce(a.owner,'')) LIKE ?".into());
        args.push(format!("%{}%", owner.to_lowercase().trim_start_matches('@')).into());
    }
    if let Some(d) = &q.due_before {
        parts.push("a.due IS NOT NULL AND a.due <= ?".into());
        args.push(day(d).into());
    }
    for term in q.text.as_deref().unwrap_or_default().split(|c: char| !(c.is_alphanumeric() || c == '_')).filter(|t| !t.is_empty()) {
        parts.push("lower(a.text) LIKE ?".into());
        args.push(format!("%{}%", term.to_lowercase()).into());
    }
    args.push((q.limit as i64).into());
    let sql = format!(
        "SELECT a.*, n.id, n.title, n.date, n.project FROM actions a JOIN notes n ON n.path = a.path {} \
         ORDER BY a.due IS NULL, a.due, n.date DESC, a.line_no LIMIT ?",
        where_clause(&parts)
    );
    let mut stmt = db.prepare_cached(&sql)?;
    let rows = stmt.query_map(params_from_iter(args), |r| {
        let project: String = r.get("project")?;
        Ok(ActionRow {
            text: r.get("text")?,
            done: r.get("done")?,
            owner: r.get("owner")?,
            due: r.get("due")?,
            done_on: r.get("done_on")?,
            note_id: r.get("id")?,
            note_title: r.get("title")?,
            note_date: r.get("date")?,
            line: r.get("line_no")?,
            parent_line: r.get("parent_line")?,
            description: r.get("description")?,
            people: split_words(r.get("people")?),
            tags: split_words(r.get("tags")?),
            project: Some(project).filter(|p| !p.is_empty()),
        })
    })?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

#[derive(Debug, Clone, Serialize)]
pub struct DecisionRow {
    pub text: String,
    pub line: i64,
    pub note_id: String,
    pub note_title: String,
    pub date: String,
    pub project: Option<String>,
}

pub fn decisions(db: &Connection, f: &Filter, query: &str, limit: usize) -> Result<Vec<DecisionRow>> {
    let mut parts = Vec::new();
    let mut args = Vec::new();
    f.sql(&mut parts, &mut args);
    for term in query.split(|c: char| !(c.is_alphanumeric() || c == '_')).filter(|t| !t.is_empty()) {
        parts.push("lower(d.text) LIKE ?".into());
        args.push(format!("%{}%", term.to_lowercase()).into());
    }
    args.push((limit as i64).into());
    let sql = format!(
        "SELECT d.*, n.id, n.title, n.date, n.project FROM decisions d JOIN notes n ON n.path = d.path {} \
         ORDER BY n.date DESC LIMIT ?",
        where_clause(&parts)
    );
    let mut stmt = db.prepare_cached(&sql)?;
    let rows = stmt.query_map(params_from_iter(args), |r| {
        let project: String = r.get("project")?;
        Ok(DecisionRow {
            text: r.get("text")?,
            line: r.get("line_no")?,
            note_id: r.get("id")?,
            note_title: r.get("title")?,
            date: r.get("date")?,
            project: Some(project).filter(|p| !p.is_empty()),
        })
    })?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

#[derive(Debug, Clone, Serialize)]
pub struct Facet {
    pub name: String,
    pub notes: i64,
    pub last_seen: Option<String>,
}

fn facets(db: &Connection, sql: &str) -> Result<Vec<Facet>> {
    let mut stmt = db.prepare_cached(sql)?;
    let rows = stmt.query_map([], |r| Ok(Facet { name: r.get(0)?, notes: r.get(1)?, last_seen: r.get(2)? }))?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

pub fn people(db: &Connection) -> Result<Vec<Facet>> {
    facets(
        db,
        "SELECT max(p.person), count(DISTINCT p.path) AS c, max(n.date) FROM note_people p \
         JOIN notes n ON n.path = p.path GROUP BY p.key ORDER BY c DESC, 1",
    )
}

pub fn projects(db: &Connection) -> Result<Vec<Facet>> {
    facets(
        db,
        "SELECT name, count(DISTINCT path) AS c, max(date) FROM (\
           SELECT n.project AS name, n.path, n.date FROM notes n WHERE n.project <> '' \
           UNION ALL SELECT t.tag, t.path, n.date FROM note_tags t JOIN notes n ON n.path = t.path\
         ) GROUP BY name ORDER BY c DESC, name",
    )
}

#[derive(Debug, Clone, Serialize)]
pub struct Backlink {
    pub note_id: String,
    pub note_title: String,
    pub date: String,
    pub line: i64,
    pub text: String,
}

/// Le note che citano questa nota, per id o per titolo.
pub fn backlinks(db: &Connection, id: &str, title: &str) -> Result<Vec<Backlink>> {
    let mut stmt = db.prepare_cached(
        "SELECT n.id, n.title, n.date, l.line_no, l.line FROM links l JOIN notes n ON n.path = l.path \
         WHERE l.key IN (?1, ?2) AND n.id <> ?3 ORDER BY n.date DESC, l.line_no",
    )?;
    let rows = stmt.query_map(params![id.to_lowercase(), title.to_lowercase(), id], |r| {
        Ok(Backlink { note_id: r.get(0)?, note_title: r.get(1)?, date: r.get(2)?, line: r.get(3)?, text: r.get(4)? })
    })?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

#[derive(Debug, Clone, Serialize)]
pub struct OutLink {
    pub target: String,
    pub label: Option<String>,
    /// Id della nota collegata, se esiste.
    pub note_id: Option<String>,
    pub note_title: Option<String>,
}

pub fn outgoing_links(db: &Connection, rel: &str) -> Result<Vec<OutLink>> {
    let mut stmt = db.prepare_cached(
        "SELECT l.target, l.label, n.id, n.title FROM links l \
         LEFT JOIN notes n ON n.id = l.target OR lower(n.title) = l.key \
         WHERE l.path = ?1 GROUP BY l.key ORDER BY min(l.line_no)",
    )?;
    let rows = stmt.query_map([rel], |r| {
        Ok(OutLink { target: r.get(0)?, label: r.get(1)?, note_id: r.get(2)?, note_title: r.get(3)? })
    })?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

/// Tutto quello che serve al grafo completo, letto in una volta dall'indice.
#[derive(Debug, Default)]
pub struct GraphRows {
    /// path, id, titolo, tipo, data
    pub notes: Vec<(String, String, String, String, String)>,
    /// path della nota che contiene il link, chiave del link in minuscolo
    pub links: Vec<(String, String)>,
    /// path, persona
    pub people: Vec<(String, String)>,
    /// path, etichetta
    pub tags: Vec<(String, String)>,
}

pub fn graph_rows(db: &Connection) -> Result<GraphRows> {
    let text = |r: &Row, i: usize| r.get::<_, Option<String>>(i).map(Option::unwrap_or_default);
    let pairs = |sql: &str| -> Result<Vec<(String, String)>> {
        let mut stmt = db.prepare_cached(sql)?;
        let rows = stmt.query_map([], |r| Ok((text(r, 0)?, text(r, 1)?)))?;
        Ok(rows.collect::<rusqlite::Result<_>>()?)
    };
    let mut stmt = db.prepare_cached("SELECT path, id, title, type, date FROM notes")?;
    let notes = stmt
        .query_map([], |r| Ok((text(r, 0)?, text(r, 1)?, text(r, 2)?, text(r, 3)?, text(r, 4)?)))?
        .collect::<rusqlite::Result<_>>()?;
    Ok(GraphRows {
        notes,
        links: pairs("SELECT DISTINCT path, key FROM links")?,
        people: pairs("SELECT DISTINCT path, person FROM note_people")?,
        tags: pairs("SELECT DISTINCT path, tag FROM note_tags")?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn query_fts() {
        assert_eq!(fts_query("budget Q4", "AND"), "\"budget\"* AND \"Q4\"*");
        assert_eq!(fts_query("dell'anno -x \"y", "OR"), "\"dell'anno\"* OR \"x\"* OR \"y\"*");
        assert_eq!(fts_query(" -- ", "AND"), "");
    }
}
