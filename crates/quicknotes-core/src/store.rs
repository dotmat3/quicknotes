//! Archivio delle note: i file Markdown sono la fonte di verità.
//!
//! Un salvataggio non riscrive ciò che non è cambiato: il frontmatter resta il testo originale
//! finché i metadati non vengono modificati, e gli a capo restano quelli del file.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use chrono::{DateTime, Local, NaiveDate, NaiveDateTime};
use rusqlite::Connection;
use serde::Serialize;
use serde_yaml_ng::{Mapping, Value};

use crate::{dates, edit, index, parser};

pub const NOTE_TYPES: [&str; 3] = ["meeting", "daily", "note"];

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("Nota non trovata: {0}")]
    NotFound(String),
    #[error("La riga è cambiata nel frattempo: ricarica la nota")]
    Stale,
    #[error("{0}")]
    Invalid(String),
    #[error("Errore di file: {0}")]
    Io(#[from] std::io::Error),
    #[error("Errore dell'indice: {0}")]
    Sql(#[from] rusqlite::Error),
}

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Clone)]
pub struct Note {
    pub id: String,
    pub path: PathBuf,
    pub meta: Mapping,
    pub body: String,
    /// Testo originale del frontmatter, valido finché `meta` non cambia.
    front_raw: String,
    meta_dirty: bool,
    crlf: bool,
    title: String,
    date: String,
}

impl Note {
    fn from_text(path: &Path, text: &str, mtime: Option<DateTime<Local>>) -> Self {
        let crlf = text.contains("\r\n");
        let normalized;
        let text = if crlf {
            normalized = text.replace("\r\n", "\n");
            normalized.as_str()
        } else {
            text
        };
        let (front, body) = parser::split_frontmatter(text);
        let id = path.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
        let title = parser::meta_str(&front.meta, "title")
            .or_else(|| parser::first_h1(body))
            .unwrap_or_else(|| id.clone());
        let date = parser::meta_str(&front.meta, "date")
            .map(|d| parser::normalize_date(&d))
            .or_else(|| date_from_id(&id))
            .or_else(|| mtime.map(|m| m.format("%Y-%m-%dT%H:%M").to_string()))
            .unwrap_or_default();
        Self {
            id,
            path: path.to_path_buf(),
            meta: front.meta,
            body: body.to_string(),
            front_raw: front.raw,
            meta_dirty: false,
            crlf,
            title,
            date,
        }
    }

    fn new(path: PathBuf, meta: Mapping, body: String) -> Self {
        let text = parser::render_frontmatter(&meta) + &body;
        let mut note = Self::from_text(&path, &text, None);
        note.meta = meta;
        note
    }

    pub fn note_type(&self) -> String {
        parser::meta_str(&self.meta, "type").unwrap_or_else(|| "note".to_string())
    }

    pub fn title(&self) -> &str {
        &self.title
    }

    pub fn date(&self) -> &str {
        &self.date
    }

    pub fn people(&self) -> Vec<String> {
        parser::meta_list(&self.meta, "people")
    }

    pub fn project(&self) -> String {
        parser::meta_str(&self.meta, "project").unwrap_or_default()
    }

    pub fn tags(&self) -> Vec<String> {
        parser::meta_list(&self.meta, "tags")
    }

    pub fn set_meta(&mut self, key: &str, value: Value) {
        self.meta.insert(Value::String(key.to_string()), value);
        self.meta_dirty = true;
        if key == "title" {
            self.title = parser::meta_str(&self.meta, "title").unwrap_or_else(|| self.id.clone());
        }
        if key == "date" {
            if let Some(d) = parser::meta_str(&self.meta, "date") {
                self.date = parser::normalize_date(&d);
            }
        }
    }

    /// Il contenuto completo del file.
    pub fn text(&self) -> String {
        let front = if self.meta_dirty { parser::render_frontmatter(&self.meta) } else { self.front_raw.clone() };
        let text = front + &self.body;
        if self.crlf {
            text.replace('\n', "\r\n")
        } else {
            text
        }
    }
}

fn date_from_id(id: &str) -> Option<String> {
    let day = id.get(..10)?;
    NaiveDate::parse_from_str(day, "%Y-%m-%d").ok()?;
    let b = id.as_bytes();
    let time = (b.len() >= 15 && b[10] == b'-' && b[11..15].iter().all(u8::is_ascii_digit))
        .then(|| format!("T{}:{}", &id[11..13], &id[13..15]));
    Some(format!("{day}{}", time.unwrap_or_default()))
}

/// Una nuova nota da creare.
#[derive(Debug, Clone, Default)]
pub struct NewNote {
    pub title: String,
    pub body: String,
    pub note_type: String,
    pub people: Vec<String>,
    pub project: Option<String>,
    pub tags: Vec<String>,
    pub when: Option<NaiveDateTime>,
    pub source: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(tag = "status", rename_all = "lowercase")]
pub enum SaveOutcome {
    Saved,
    Conflict { disk: String },
}

/// Il risultato di una modifica a una riga.
#[derive(Debug, Clone, Serialize)]
pub struct LineChange {
    pub note_id: String,
    pub line: usize,
    pub text: String,
    pub done: bool,
}

/// I dettagli di un'azione da modificare. Ogni campo assente resta com'è.
#[derive(Debug, Clone, Default)]
pub struct ActionPatch {
    /// `Some(None)` toglie la scadenza.
    pub due: Option<Option<String>>,
    /// Posizione della persona e nuovo nome; `None` la toglie.
    pub person: Option<(usize, Option<String>)>,
    /// `Some(None)` toglie l'etichetta.
    pub tag: Option<Option<String>>,
    pub description: Option<String>,
}

pub struct NoteStore {
    root: PathBuf,
    writer: Mutex<Connection>,
    reader: Mutex<Connection>,
}

fn lock<T>(m: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

impl NoteStore {
    /// Apre l'archivio senza leggere le note: `refresh` allinea l'indice quando conviene.
    pub fn open(root: impl AsRef<Path>) -> Result<Self> {
        let root = root.as_ref();
        fs::create_dir_all(root)?;
        let root = root.canonicalize().map(dunce)?;
        let dir = root.join(".quicknotes");
        fs::create_dir_all(&dir)?;
        let db = dir.join("index-v3.db");
        let writer = index::open(&db)?;
        index::init_schema(&writer)?;
        let reader = index::open(&db)?;
        Ok(Self { root, writer: Mutex::new(writer), reader: Mutex::new(reader) })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    fn rel(&self, path: &Path) -> Result<String> {
        let rel = path.strip_prefix(&self.root).map_err(|_| {
            Error::Invalid(format!("Percorso fuori dalla cartella delle note: {}", path.display()))
        })?;
        Ok(rel.components().map(|c| c.as_os_str().to_string_lossy()).collect::<Vec<_>>().join("/"))
    }

    fn scan(&self) -> Vec<(String, i64, i64)> {
        let mut found = Vec::new();
        let mut stack = vec![self.root.clone()];
        while let Some(dir) = stack.pop() {
            let Ok(entries) = fs::read_dir(&dir) else { continue };
            for entry in entries.flatten() {
                let name = entry.file_name();
                let name = name.to_string_lossy();
                if name.starts_with('.') {
                    continue;
                }
                let Ok(meta) = entry.metadata() else { continue };
                if meta.is_dir() {
                    stack.push(entry.path());
                } else if name.ends_with(".md") {
                    if let Ok(rel) = self.rel(&entry.path()) {
                        found.push((rel, mtime_ms(&meta), meta.len() as i64));
                    }
                }
            }
        }
        found
    }

    /// Allinea l'indice ai file su disco e restituisce il numero di file reindicizzati.
    pub fn refresh(&self) -> Result<usize> {
        Ok(self.refresh_changes()?.len())
    }

    /// Come `refresh`, ma restituisce gli id delle note cambiate o sparite. Un salvataggio dell'app
    /// aggiorna già l'indice, quindi qui compaiono solo le modifiche esterne.
    pub fn refresh_changes(&self) -> Result<Vec<String>> {
        let on_disk = self.scan();
        let mut db = lock(&self.writer);
        let known = index::signatures(&db)?;
        let changed: Vec<_> = on_disk.iter().filter(|(p, m, s)| known.get(p) != Some(&(*m, *s))).collect();
        let present: std::collections::HashSet<&str> = on_disk.iter().map(|(p, _, _)| p.as_str()).collect();
        let removed: Vec<&String> = known.keys().filter(|p| !present.contains(p.as_str())).collect();
        if changed.is_empty() && removed.is_empty() {
            return Ok(Vec::new());
        }
        let tx = db.transaction()?;
        let id_of = |rel: &str| Path::new(rel).file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
        let mut ids: Vec<String> = removed.iter().map(|r| id_of(r)).collect();
        for rel in removed {
            index::delete_rows(&tx, rel)?;
        }
        for (rel, mtime, size) in &changed {
            let path = self.root.join(rel);
            // Un file illeggibile o non UTF-8 non deve fermare gli altri.
            if let Ok(text) = fs::read_to_string(&path) {
                let note = Note::from_text(&path, &text, Some(local_time(*mtime)));
                index::index_note(&tx, rel, &note, *mtime, *size)?;
                ids.push(note.id);
            }
        }
        tx.commit()?;
        Ok(ids)
    }

    /// Cancella l'indice e lo ricostruisce dai file.
    pub fn reindex(&self) -> Result<usize> {
        index::clear(&lock(&self.writer))?;
        self.refresh()
    }

    fn path_for_id(&self, id: &str) -> Result<Option<PathBuf>> {
        let id = id.trim();
        let id = id.strip_suffix(".md").unwrap_or(id);
        let rel = index::path_for_id(&lock(&self.reader), id)?;
        Ok(rel.map(|r| self.root.join(r)))
    }

    pub fn read(&self, id: &str) -> Result<Note> {
        let mut path = self.path_for_id(id)?.filter(|p| p.exists());
        if path.is_none() {
            self.refresh()?;
            path = self.path_for_id(id)?.filter(|p| p.exists());
        }
        let path = path.ok_or_else(|| Error::NotFound(id.to_string()))?;
        self.read_path(&path)
    }

    fn read_path(&self, path: &Path) -> Result<Note> {
        let text = fs::read_to_string(path)?;
        let mtime = fs::metadata(path).ok().map(|m| local_time(mtime_ms(&m)));
        Ok(Note::from_text(path, &text, mtime))
    }

    /// Scrive la nota su disco in modo atomico e aggiorna l'indice.
    pub fn save(&self, note: &Note) -> Result<()> {
        let dir = note.path.parent().ok_or_else(|| Error::Invalid("Percorso non valido".into()))?;
        fs::create_dir_all(dir)?;
        let rel = self.rel(&note.path)?;
        let tmp = dir.join(format!(".tmp-{}-{}.md", std::process::id(), note.id));
        let write = || -> std::io::Result<()> {
            let mut file = fs::File::create(&tmp)?;
            file.write_all(note.text().as_bytes())?;
            file.sync_all()?;
            drop(file);
            fs::rename(&tmp, &note.path)
        };
        if let Err(e) = write() {
            let _ = fs::remove_file(&tmp);
            return Err(e.into());
        }
        let meta = fs::metadata(&note.path)?;
        let mut db = lock(&self.writer);
        let tx = db.transaction()?;
        index::index_note(&tx, &rel, note, mtime_ms(&meta), meta.len() as i64)?;
        tx.commit()?;
        Ok(())
    }

    fn unique_path(&self, base: &str, folder: &Path) -> Result<(String, PathBuf)> {
        let mut candidate = base.to_string();
        let mut n = 2;
        while folder.join(format!("{candidate}.md")).exists() || self.path_for_id(&candidate)?.is_some() {
            candidate = format!("{base}-{n}");
            n += 1;
        }
        let path = folder.join(format!("{candidate}.md"));
        Ok((candidate, path))
    }

    pub fn create_note(&self, new: NewNote) -> Result<Note> {
        let when = new.when.unwrap_or_else(|| Local::now().naive_local());
        let note_type = if new.note_type.is_empty() { "meeting".to_string() } else { new.note_type };
        let title = match new.title.trim() {
            "" if note_type == "meeting" => "Meeting".to_string(),
            "" => "Nota".to_string(),
            t => t.to_string(),
        };
        let folder = self.root.join(when.format("%Y").to_string()).join(when.format("%m").to_string());
        let base = format!("{}-{}", when.format("%Y-%m-%d-%H%M"), parser::slugify(&title));
        let (_, path) = self.unique_path(&base, &folder)?;
        let mut meta = Mapping::new();
        let list = |v: Vec<String>| Value::Sequence(v.into_iter().map(Value::String).collect());
        meta.insert("type".into(), note_type.into());
        meta.insert("title".into(), title.into());
        meta.insert("date".into(), when.format("%Y-%m-%dT%H:%M").to_string().into());
        meta.insert("people".into(), list(new.people));
        meta.insert("project".into(), new.project.unwrap_or_default().into());
        meta.insert("tags".into(), list(new.tags));
        if let Some(source) = new.source {
            meta.insert("source".into(), source.into());
        }
        let mut body = new.body;
        if !body.is_empty() && !body.ends_with('\n') {
            body.push('\n');
        }
        let note = Note::new(path, meta, body);
        self.save(&note)?;
        Ok(note)
    }

    /// La nota del giorno, creata se manca e se richiesto.
    pub fn daily(&self, day: NaiveDate, create: bool) -> Result<Option<Note>> {
        let id = format!("{}-giornata", day.format("%Y-%m-%d"));
        let path = self
            .root
            .join(day.format("%Y").to_string())
            .join(day.format("%m").to_string())
            .join(format!("{id}.md"));
        if path.exists() {
            return self.read_path(&path).map(Some);
        }
        match self.read(&id) {
            Ok(note) => return Ok(Some(note)),
            Err(Error::NotFound(_)) if !create => return Ok(None),
            Err(Error::NotFound(_)) => {}
            Err(e) => return Err(e),
        }
        let mut meta = Mapping::new();
        meta.insert("type".into(), "daily".into());
        meta.insert("title".into(), dates::daily_file_title(day).into());
        meta.insert("date".into(), day.format("%Y-%m-%d").to_string().into());
        let note = Note::new(path, meta, String::new());
        self.save(&note)?;
        Ok(Some(note))
    }

    /// Sostituisce il corpo di una nota.
    pub fn update_body(&self, id: &str, body: &str) -> Result<Note> {
        let mut note = self.read(id)?;
        note.body = body.to_string();
        self.save(&note)?;
        Ok(note)
    }

    /// Salva il testo solo se il file contiene ancora `base`, il testo da cui è partita la modifica.
    /// Altrimenti non scrive nulla: il file è cambiato fuori dall'app e restituisce il suo contenuto.
    pub fn save_if_unchanged(&self, id: &str, base: &str, body: &str) -> Result<SaveOutcome> {
        let mut note = self.read(id)?;
        if note.body == body {
            return Ok(SaveOutcome::Saved);
        }
        if note.body != base {
            return Ok(SaveOutcome::Conflict { disk: note.body });
        }
        note.body = body.to_string();
        self.save(&note)?;
        Ok(SaveOutcome::Saved)
    }

    /// Conserva un testo in conflitto come nota a parte, così non si perde nulla.
    pub fn save_conflict_copy(&self, id: &str, body: &str, now: NaiveDateTime) -> Result<Note> {
        let note = self.read(id)?;
        self.create_note(NewNote {
            title: format!("{} (conflitto {})", note.title(), now.format("%H:%M")),
            body: body.to_string(),
            note_type: "note".to_string(),
            when: Some(now),
            ..NewNote::default()
        })
    }

    pub fn append(&self, id: &str, text: &str, heading: Option<&str>) -> Result<Note> {
        let mut note = self.read(id)?;
        let block = text.trim_matches('\n');
        let block = match heading {
            Some(h) => format!("### {h}\n{block}"),
            None => block.to_string(),
        };
        let base = note.body.trim_end_matches('\n');
        note.body = if base.is_empty() { format!("{block}\n") } else { format!("{base}\n\n{block}\n") };
        self.save(&note)?;
        Ok(note)
    }

    /// Aggiunge una voce alla nota del giorno, con l'orario se richiesto.
    pub fn append_to_daily(&self, text: &str, now: NaiveDateTime, timestamp: bool) -> Result<Note> {
        let note = self
            .daily(now.date(), true)?
            .ok_or_else(|| Error::Invalid("Nota del giorno non disponibile".into()))?;
        let text = text.trim();
        let time = now.format("%H:%M").to_string();
        if timestamp && !text.contains('\n') && !text.starts_with(['-', '*', '#']) {
            return self.append(&note.id, &format!("- {time} {text}"), None);
        }
        self.append(&note.id, text, timestamp.then_some(time.as_str()))
    }

    pub fn add_to_section(&self, id: &str, section: Option<&str>, block: &str) -> Result<Note> {
        let mut note = self.read(id)?;
        note.body = edit::add_to_section(&note.body, section, block);
        self.save(&note)?;
        Ok(note)
    }

    /// Una nuova azione nella nota del giorno, sezione "Priorità". Scadenza ed etichetta si aggiungono
    /// solo se il testo non ne ha già una: vale quello che l'utente ha scritto.
    pub fn add_action(&self, today: NaiveDate, text: &str, due: Option<NaiveDate>, tag: Option<&str>) -> Result<Note> {
        let daily = self.daily(today, true)?.ok_or_else(|| Error::Invalid("Nota del giorno non disponibile".into()))?;
        let mut line = format!("- [ ] {}", text.trim());
        let written = parser::extract(&line).actions.into_iter().next();
        if let Some(d) = due.filter(|_| written.as_ref().is_none_or(|a| a.due.is_none())) {
            line = edit::with_due(&line, Some(&d.format("%Y-%m-%d").to_string()));
        }
        if let Some(t) = tag.filter(|_| written.as_ref().is_none_or(|a| a.tags.is_empty())) {
            line = edit::with_tag(&line, Some(t));
        }
        self.add_to_section(&daily.id, Some("Priorità"), &line)
    }

    /// Sposta a domani le azioni di primo livello in ritardo. Una riga cambiata nel frattempo resta com'è.
    /// Restituisce quante azioni sono state spostate e le note toccate.
    pub fn postpone_late(&self, today: NaiveDate) -> Result<(usize, Vec<String>)> {
        let rows = self.actions(&index::ActionQuery { limit: 100_000, ..Default::default() })?;
        let tomorrow = (today + chrono::Duration::days(1)).format("%Y-%m-%d").to_string();
        let mut moved = 0;
        let mut ids: Vec<String> = Vec::new();
        for row in rows.iter().filter(|r| r.parent_line.is_none()) {
            let due = row.due.as_deref().and_then(dates::parse_day);
            if dates::due_group(due, today) != dates::DueGroup::Late {
                continue;
            }
            let patch = ActionPatch { due: Some(Some(tomorrow.clone())), ..Default::default() };
            match self.set_action_details(&row.note_id, row.line as usize, Some(&row.text), patch) {
                Ok(_) => moved += 1,
                Err(Error::Stale) => continue,
                Err(e) => return Err(e),
            }
            if !ids.contains(&row.note_id) {
                ids.push(row.note_id.clone());
            }
        }
        Ok((moved, ids))
    }

    /// Il file della nota seguito dalle sue registrazioni audio.
    pub fn note_files(&self, id: &str) -> Result<Vec<PathBuf>> {
        let note = self.read(id)?;
        let mut audio = Vec::new();
        if let Some(entries) = note.path.parent().and_then(|d| fs::read_dir(d.join("audio")).ok()) {
            for entry in entries.flatten() {
                let name = entry.file_name();
                let name = name.to_string_lossy();
                let is_recording = name
                    .strip_prefix(&format!("{}-", note.id))
                    .and_then(|r| r.strip_suffix(".wav"))
                    .is_some_and(|t| t.len() == 6 && t.bytes().all(|b| b.is_ascii_digit()));
                if is_recording {
                    audio.push(entry.path());
                }
            }
        }
        audio.sort();
        let mut files = vec![note.path];
        files.extend(audio);
        Ok(files)
    }

    /// Elimina una nota e le sue registrazioni. `discard` decide come rimuovere ogni file:
    /// l'app li sposta nel Cestino. Se fallisce sulla nota, non si tocca nient'altro.
    pub fn delete(&self, id: &str, discard: impl Fn(&Path) -> std::io::Result<()>) -> Result<Vec<PathBuf>> {
        let files = self.note_files(id)?;
        let rel = self.rel(&files[0])?;
        discard(&files[0])?;
        index::delete_rows(&lock(&self.writer), &rel)?;
        for path in &files[1..] {
            // Un audio rimasto non deve bloccare l'eliminazione della nota.
            let _ = discard(path);
        }
        Ok(files)
    }

    fn change_line(note: &mut Note, line_no: usize, f: impl FnOnce(&str) -> String) -> Result<String> {
        let ends_nl = note.body.ends_with('\n');
        let mut lines: Vec<String> = note.body.lines().map(String::from).collect();
        let line = lines
            .get_mut(line_no.wrapping_sub(1))
            .ok_or_else(|| Error::Invalid(format!("Riga {line_no} inesistente")))?;
        *line = f(line);
        let new = line.clone();
        note.body = lines.join("\n");
        if ends_nl {
            note.body.push('\n');
        }
        Ok(new)
    }

    /// Spunta o riapre l'azione alla riga indicata, se è ancora quella attesa. Vale una sola riga.
    pub fn set_action_done(&self, id: &str, line_no: usize, expected: Option<&str>, done_on: Option<NaiveDate>) -> Result<LineChange> {
        let mut note = self.read(id)?;
        check_line(&note, line_no, expected)?;
        let day = done_on.map(|d| d.format("%Y-%m-%d").to_string());
        let text = Self::change_line(&mut note, line_no, |l| edit::with_checked(l, day.as_deref()))?;
        self.save(&note)?;
        Ok(LineChange { note_id: note.id, line: line_no, text: text.trim().to_string(), done: done_on.is_some() })
    }

    /// Spunta o riapre un'azione cercandola per testo dentro la nota. Lo usa il server MCP.
    pub fn set_action_status(&self, id: &str, action_text: &str, done_on: Option<NaiveDate>) -> Result<LineChange> {
        let note = self.read(id)?;
        let wanted = action_text.trim().to_lowercase();
        let mut best: Option<(u8, usize)> = None;
        for (i, line) in note.body.lines().enumerate() {
            if let Some(c) = parser::ACTION_RE.captures(line) {
                let text = c[3].trim().to_lowercase();
                let score = if text == wanted {
                    2
                } else if !wanted.is_empty() && text.contains(&wanted) {
                    1
                } else {
                    0
                };
                if score > 0 && best.is_none_or(|(s, _)| score >= s) {
                    best = Some((score, i + 1));
                }
            }
        }
        let (_, line) = best.ok_or_else(|| {
            Error::NotFound(format!("nessuna azione che contenga '{action_text}' in {id}"))
        })?;
        self.set_action_done(id, line, None, done_on)
    }

    /// Chiude l'azione madre e le figlie aperte con una sola scrittura. Le figlie già chiuse
    /// conservano la loro data.
    pub fn complete_with_children(&self, id: &str, line_no: usize, expected: Option<&str>, today: NaiveDate) -> Result<usize> {
        let mut note = self.read(id)?;
        check_line(&note, line_no, expected)?;
        let actions = parser::extract(&note.body).actions;
        let day = today.format("%Y-%m-%d").to_string();
        let targets: Vec<usize> = actions
            .iter()
            .filter(|a| !a.done && (a.line_no == line_no || a.parent_line == Some(line_no)))
            .map(|a| a.line_no)
            .collect();
        for line in &targets {
            Self::change_line(&mut note, *line, |l| edit::with_checked(l, Some(&day)))?;
        }
        self.save(&note)?;
        Ok(targets.len())
    }

    /// Modifica i dettagli di un'azione. Se la riga è cambiata nel frattempo non scrive.
    pub fn set_action_details(&self, id: &str, line_no: usize, expected: Option<&str>, patch: ActionPatch) -> Result<Note> {
        let mut note = self.read(id)?;
        check_line(&note, line_no, expected)?;
        Self::change_line(&mut note, line_no, |line| {
            let mut l = line.to_string();
            if let Some(due) = &patch.due {
                l = edit::with_due(&l, due.as_deref());
            }
            if let Some((index, name)) = &patch.person {
                l = edit::with_person(&l, *index, name.as_deref());
            }
            if let Some(tag) = &patch.tag {
                l = edit::with_tag(&l, tag.as_deref());
            }
            l
        })?;
        if let Some(text) = &patch.description {
            note.body = edit::with_description(&note.body, line_no, text);
        }
        self.save(&note)?;
        Ok(note)
    }

    pub fn search(&self, q: &index::SearchQuery) -> Result<Vec<index::NoteSummary>> {
        index::search(&lock(&self.reader), q)
    }

    pub fn list_notes(&self, f: &index::Filter, limit: usize) -> Result<Vec<index::NoteSummary>> {
        index::list_notes(&lock(&self.reader), f, limit)
    }

    pub fn actions(&self, q: &index::ActionQuery) -> Result<Vec<index::ActionRow>> {
        index::actions(&lock(&self.reader), q)
    }

    pub fn decisions(&self, f: &index::Filter, query: &str, limit: usize) -> Result<Vec<index::DecisionRow>> {
        index::decisions(&lock(&self.reader), f, query, limit)
    }

    pub fn people(&self) -> Result<Vec<index::Facet>> {
        index::people(&lock(&self.reader))
    }

    pub fn projects(&self) -> Result<Vec<index::Facet>> {
        index::projects(&lock(&self.reader))
    }

    pub fn backlinks(&self, id: &str) -> Result<Vec<index::Backlink>> {
        let note = self.read(id)?;
        index::backlinks(&lock(&self.reader), &note.id, note.title())
    }

    pub fn outgoing_links(&self, id: &str) -> Result<Vec<index::OutLink>> {
        let note = self.read(id)?;
        index::outgoing_links(&lock(&self.reader), &self.rel(&note.path)?)
    }
}

fn check_line(note: &Note, line_no: usize, expected: Option<&str>) -> Result<()> {
    let Some(expected) = expected else { return Ok(()) };
    let line = note.body.lines().nth(line_no.wrapping_sub(1)).unwrap_or_default();
    let text = parser::ACTION_RE.captures(line).map(|c| c[3].trim().to_string());
    if line == expected || text.as_deref() == Some(expected) {
        Ok(())
    } else {
        Err(Error::Stale)
    }
}

fn mtime_ms(meta: &fs::Metadata) -> i64 {
    meta.modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn local_time(ms: i64) -> DateTime<Local> {
    DateTime::from_timestamp_millis(ms).unwrap_or_default().with_timezone(&Local)
}

/// Toglie il prefisso `\\?\` che `canonicalize` aggiunge su Windows.
fn dunce(path: PathBuf) -> PathBuf {
    let text = path.to_string_lossy();
    match text.strip_prefix(r"\\?\") {
        Some(rest) if !rest.starts_with("UNC\\") => PathBuf::from(rest),
        _ => path,
    }
}
