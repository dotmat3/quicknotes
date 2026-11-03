//! Formato delle note e convenzioni di scrittura rapida.
//!
//! Una nota è un file Markdown con frontmatter YAML facoltativo. Nel testo:
//! `@persona`, `#etichetta`, `- [ ] azione`, `due:AAAA-MM-GG`, `done:AAAA-MM-GG`,
//! `!decisione`, `[[id|Titolo]]`, `![[schizzo.excalidraw]]`.
//!
//! `@` e `#` si riconoscono con scanner scritti a mano: le regole originali guardano il
//! carattere precedente, cosa che la libreria `regex` non supporta.

use std::sync::LazyLock;

use regex::Regex;
use serde::Serialize;
use serde_yaml_ng::{Mapping, Value};
use unicode_normalization::UnicodeNormalization;

pub(crate) static DUE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:due|entro|scadenza)\s*:\s*(\d{4}-\d{2}-\d{2})").expect("regex valida")
});
pub(crate) static DONE_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)\bdone\s*:\s*(\d{4}-\d{2}-\d{2})").expect("regex valida"));
static DECISION_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)!(?:decisione|decision|dec)\b").expect("regex valida"));
static MD_LINK_TARGET_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\]\([^)]*\)").expect("regex valida"));
static BULLET_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*(?:[-*+]|\d+[.)])\s+").expect("regex valida"));
pub(crate) static ACTION_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^(\s*)[-*+]\s+\[( |x|X)\]\s*(.*)$").expect("regex valida"));
static HEADING_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^(#{1,6})\s+(.*?)\s*$").expect("regex valida"));

pub(crate) fn is_fence(line: &str) -> bool {
    let t = line.trim_start();
    t.starts_with("```") || t.starts_with("~~~")
}

fn is_word(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// Frontmatter separato dal corpo. `raw` è il testo originale, delimitatori compresi:
/// scrivendo la nota si riusa così com'è se i metadati non cambiano.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Frontmatter {
    pub raw: String,
    pub meta: Mapping,
}

/// Separa il frontmatter YAML dal corpo. Un frontmatter non valido viene ignorato
/// e il testo resta tutto nel corpo, così non si perde nulla.
pub fn split_frontmatter(text: &str) -> (Frontmatter, &str) {
    let none = (Frontmatter::default(), text);
    let Some(rest) = text.strip_prefix("---") else { return none };
    let Some(nl) = rest.find('\n') else { return none };
    if !rest[..nl].trim_end_matches(['\r', ' ', '\t']).is_empty() {
        return none;
    }
    let start = 3 + nl + 1;
    let mut pos = start;
    for line in text[start..].split_inclusive('\n') {
        let end = pos + line.len();
        if line.trim_end_matches(['\r', '\n', ' ', '\t']) == "---" {
            let yaml = &text[start..pos];
            return match serde_yaml_ng::from_str::<Value>(yaml) {
                Ok(Value::Mapping(meta)) => {
                    (Frontmatter { raw: text[..end].to_string(), meta }, &text[end..])
                }
                Ok(Value::Null) => {
                    (Frontmatter { raw: text[..end].to_string(), meta: Mapping::new() }, &text[end..])
                }
                _ => none,
            };
        }
        pos = end;
    }
    none
}

/// Riscrive il frontmatter dai metadati, togliendo i valori vuoti.
pub fn render_frontmatter(meta: &Mapping) -> String {
    let mut clean = Mapping::new();
    for (k, v) in meta {
        let empty = match v {
            Value::Null => true,
            Value::String(s) => s.is_empty(),
            Value::Sequence(s) => s.is_empty(),
            _ => false,
        };
        if !empty {
            clean.insert(k.clone(), v.clone());
        }
    }
    if clean.is_empty() {
        return String::new();
    }
    let yaml = serde_yaml_ng::to_string(&clean).unwrap_or_default();
    format!("---\n{yaml}---\n")
}

pub fn meta_str(meta: &Mapping, key: &str) -> Option<String> {
    match meta.get(key)? {
        Value::String(s) => Some(s.trim().to_string()).filter(|s| !s.is_empty()),
        Value::Number(n) => Some(n.to_string()),
        Value::Bool(b) => Some(b.to_string()),
        _ => None,
    }
}

/// Un elenco nei metadati: lista YAML oppure testo separato da virgole.
pub fn meta_list(meta: &Mapping, key: &str) -> Vec<String> {
    match meta.get(key) {
        Some(Value::String(s)) => {
            s.split(',').map(str::trim).filter(|p| !p.is_empty()).map(String::from).collect()
        }
        Some(Value::Sequence(seq)) => seq
            .iter()
            .filter_map(|v| match v {
                Value::String(s) => Some(s.trim().to_string()),
                Value::Number(n) => Some(n.to_string()),
                _ => None,
            })
            .filter(|s| !s.is_empty())
            .collect(),
        Some(Value::Number(n)) => vec![n.to_string()],
        _ => Vec::new(),
    }
}

/// Una data ISO `AAAA-MM-GG` o `AAAA-MM-GGTHH:MM`.
pub fn normalize_date(value: &str) -> String {
    let text = value.trim().replacen(' ', "T", 1);
    text.chars().take(16).collect()
}

/// Le `@persone` di una riga, senza `@`.
pub fn mentions(line: &str) -> Vec<&str> {
    mention_spans(line).into_iter().map(|(start, end)| &line[start + 1..end]).collect()
}

/// Posizioni in byte delle `@persone` di una riga, `@` compresa.
pub(crate) fn mention_spans(line: &str) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut prev: Option<char> = None;
    let mut chars = line.char_indices().peekable();
    while let Some((i, c)) = chars.next() {
        if c == '@' && !prev.is_some_and(|p| is_word(p) || p == '.' || p == '@') {
            let body = i + 1;
            let mut end = body;
            let mut valid_first = false;
            for (off, ch) in line[body..].char_indices() {
                if off == 0 {
                    valid_first = is_word(ch);
                    if !valid_first {
                        break;
                    }
                }
                if is_word(ch) || ch == '-' || ch == '.' {
                    end = body + off + ch.len_utf8();
                } else {
                    break;
                }
            }
            if valid_first {
                while line[..end].ends_with(['-', '.']) {
                    end -= 1;
                }
                out.push((i, end));
            }
        }
        prev = Some(c);
    }
    out
}

/// Le `#etichette` di una riga, senza `#`, come sono scritte.
pub fn tags(line: &str) -> Vec<&str> {
    tag_spans(line).into_iter().map(|(start, end)| &line[start + 1..end]).collect()
}

/// Posizioni in byte delle `#etichette` di una riga, `#` compreso.
pub(crate) fn tag_spans(line: &str) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut prev: Option<char> = None;
    for (i, c) in line.char_indices() {
        if c == '#' && !prev.is_some_and(|p| is_word(p) || p == '/' || p == '#' || p == '&') {
            let body = i + 1;
            let mut end = body;
            for (off, ch) in line[body..].char_indices() {
                let ok = if off == 0 {
                    is_word(ch) && !ch.is_numeric()
                } else {
                    is_word(ch) || ch == '-' || ch == '/'
                };
                if !ok {
                    break;
                }
                end = body + off + ch.len_utf8();
            }
            if end > body {
                out.push((i, end));
            }
        }
        prev = Some(c);
    }
    out
}

/// Azione: una riga `- [ ]`, con la sua eventuale madre e descrizione.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Action {
    /// 1-based, riferito al corpo della nota.
    pub line_no: usize,
    pub text: String,
    pub done: bool,
    pub owner: Option<String>,
    pub people: Vec<String>,
    pub tags: Vec<String>,
    pub due: Option<String>,
    pub done_on: Option<String>,
    /// Riga dell'azione madre; `None` per le azioni di primo livello.
    pub parent_line: Option<usize>,
    pub description: String,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Decision {
    pub line_no: usize,
    pub text: String,
}

/// `[[id|Titolo]]` oppure `[[Titolo]]`.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct WikiLink {
    pub line_no: usize,
    pub target: String,
    pub label: Option<String>,
    /// La riga in cui compare, per mostrarla tra i collegamenti in entrata.
    pub line: String,
}

/// `![[nome]]`.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Embed {
    pub line_no: usize,
    pub target: String,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Heading {
    pub line_no: usize,
    pub level: usize,
    pub text: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Extracted {
    pub people: Vec<String>,
    pub tags: Vec<String>,
    pub actions: Vec<Action>,
    pub decisions: Vec<Decision>,
    pub links: Vec<WikiLink>,
    pub embeds: Vec<Embed>,
    pub headings: Vec<Heading>,
}

fn dedupe(items: Vec<String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    items.into_iter().filter(|i| seen.insert(i.to_lowercase())).collect()
}

pub(crate) fn indent_width(line: &str) -> usize {
    let mut width = 0;
    for c in line.chars() {
        match c {
            ' ' => width += 1,
            '\t' => width += 4,
            _ => break,
        }
    }
    width
}

fn scan_wiki(line: &str, line_no: usize, out: &mut Extracted) {
    let mut rest = line;
    let mut offset = 0;
    while let Some(start) = rest.find("[[") {
        let after = &rest[start + 2..];
        let Some(len) = after.find("]]") else { break };
        let inner = after[..len].trim();
        let embed = offset + start > 0 && line.as_bytes()[offset + start - 1] == b'!';
        if !inner.is_empty() {
            let (target, label) = match inner.split_once('|') {
                Some((t, l)) => (t.trim(), Some(l.trim().to_string()).filter(|l| !l.is_empty())),
                None => (inner, None),
            };
            if embed {
                out.embeds.push(Embed { line_no, target: target.to_string() });
            } else {
                out.links.push(WikiLink {
                    line_no,
                    target: target.to_string(),
                    label,
                    line: line.trim().to_string(),
                });
            }
        }
        let advance = start + 2 + len + 2;
        offset += advance;
        rest = &rest[advance..];
    }
}

/// Estrae persone, etichette, azioni, decisioni e collegamenti, ignorando i blocchi di codice.
pub fn extract(body: &str) -> Extracted {
    let mut result = Extracted::default();
    let mut in_fence = false;
    // Indice in `actions` e rientro dell'ultima azione di primo livello.
    let mut top: Option<(usize, usize)> = None;
    // Indice dell'azione che può ancora ricevere righe di descrizione.
    let mut describing: Option<usize> = None;

    for (idx, line) in body.lines().enumerate() {
        let line_no = idx + 1;
        if is_fence(line) {
            in_fence = !in_fence;
            top = None;
            describing = None;
            continue;
        }
        if in_fence {
            continue;
        }
        if let Some(c) = HEADING_RE.captures(line) {
            result.headings.push(Heading {
                line_no,
                level: c[1].len(),
                text: c[2].to_string(),
            });
        }
        // Le destinazioni dei link Markdown non devono generare etichette (`file#ancora`).
        let scan = MD_LINK_TARGET_RE.replace_all(line, "]");
        let line_people: Vec<String> = mentions(&scan).into_iter().map(String::from).collect();
        let line_tags: Vec<String> = tags(&scan).into_iter().map(str::to_lowercase).collect();
        result.people.extend(line_people.iter().cloned());
        result.tags.extend(line_tags.iter().cloned());
        scan_wiki(line, line_no, &mut result);

        let width = indent_width(line);
        let mut described = false;
        if let Some(c) = ACTION_RE.captures(line) {
            let text = c[3].trim().to_string();
            if !text.is_empty() {
                let parent = top.filter(|&(_, w)| width > w).map(|(i, _)| {
                    result.actions[i].line_no
                });
                let action = Action {
                    line_no,
                    due: DUE_RE.captures(&text).map(|m| m[1].to_string()),
                    done_on: DONE_RE.captures(&text).map(|m| m[1].to_string()),
                    done: c[2].eq_ignore_ascii_case("x"),
                    owner: line_people.first().cloned(),
                    people: dedupe(line_people.clone()),
                    tags: dedupe(line_tags.clone()),
                    parent_line: parent,
                    description: String::new(),
                    text,
                };
                result.actions.push(action);
                let i = result.actions.len() - 1;
                if parent.is_none() {
                    top = Some((i, width));
                }
                describing = Some(i);
                described = true;
            }
        } else if !line.trim().is_empty() {
            if let Some(i) = describing {
                let owner_width = indent_of_action(body, result.actions[i].line_no);
                if width > owner_width && !BULLET_RE.is_match(line) {
                    let desc = &mut result.actions[i].description;
                    if !desc.is_empty() {
                        desc.push('\n');
                    }
                    desc.push_str(line.trim());
                    described = true;
                }
            }
            // Una riga non rientrata chiude l'azione madre corrente.
            if width == 0 {
                top = None;
            }
        }
        if !described {
            describing = None;
        }

        if DECISION_RE.is_match(line) {
            let cleaned = BULLET_RE.replace(line, "");
            let text = DECISION_RE
                .replace_all(cleaned.trim(), "")
                .trim_matches([' ', '-', '–', ':'])
                .to_string();
            if !text.is_empty() {
                result.decisions.push(Decision { line_no, text });
            }
        }
    }
    result.people = dedupe(std::mem::take(&mut result.people));
    result.tags = dedupe(std::mem::take(&mut result.tags));
    result
}

fn indent_of_action(body: &str, line_no: usize) -> usize {
    body.lines().nth(line_no - 1).map(indent_width).unwrap_or(0)
}

/// Il primo titolo di livello 1, usato quando il frontmatter non ha `title`.
pub fn first_h1(body: &str) -> Option<String> {
    let mut in_fence = false;
    for line in body.lines() {
        if is_fence(line) {
            in_fence = !in_fence;
        } else if !in_fence {
            if let Some(rest) = line.strip_prefix("# ") {
                let t = rest.trim();
                if !t.is_empty() {
                    return Some(t.to_string());
                }
            }
        }
    }
    None
}

/// Il testo di un'azione senza `due:` e `done:`, mostrati a parte nell'interfaccia.
pub fn action_display_text(text: &str) -> String {
    let t = DUE_RE.replace_all(text, "");
    let t = DONE_RE.replace_all(&t, "");
    t.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// `🎙️ [Registrazione 15:02 (12:30)](audio/nota-150200.wav)`, la riga scritta alla fine di una registrazione.
static RECORDING_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\[Registrazione (\d{1,2}:\d{2})(?: \((\d{1,2}(?::\d{2}){1,2})\))?\]\(([^)]*)\)").expect("regex valida")
});
/// `### Trascrizione 15:02`, il titolo sopra il testo trascritto.
static TRANSCRIPT_HEADING_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)^#{1,6}\s+Trascrizione\s+(\d{1,2}:\d{2})\s*$").expect("regex valida"));
/// `[mm:ss]` o `[h:mm:ss]` a inizio riga: il minutaggio di un paragrafo trascritto.
static TIMESTAMP_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*(?:[-*+]\s+)?\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)$").expect("regex valida"));

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Recording {
    pub line_no: usize,
    /// Ora d'inizio, `HH:MM`.
    pub time: String,
    pub duration: Option<String>,
    /// Il file audio, se la riga c'è; manca quando resta solo il titolo della trascrizione.
    pub file: Option<String>,
    pub transcribed: bool,
}

/// Registrazioni di una nota: le righe `🎙️ [Registrazione …](…)` e i titoli `Trascrizione HH:MM`, uniti per ora.
pub fn recordings(body: &str) -> Vec<Recording> {
    let mut out: Vec<Recording> = Vec::new();
    let mut in_fence = false;
    for (idx, line) in body.lines().enumerate() {
        if is_fence(line) {
            in_fence = !in_fence;
            continue;
        }
        if in_fence {
            continue;
        }
        if let Some(c) = RECORDING_RE.captures(line) {
            let time = pad_time(&c[1]);
            match out.iter_mut().find(|r| r.time == time && r.file.is_none()) {
                Some(r) => {
                    r.file = Some(c[3].to_string());
                    r.duration = c.get(2).map(|m| m.as_str().to_string());
                }
                None => out.push(Recording {
                    line_no: idx + 1,
                    time,
                    duration: c.get(2).map(|m| m.as_str().to_string()),
                    file: Some(c[3].to_string()),
                    transcribed: false,
                }),
            }
        } else if let Some(c) = TRANSCRIPT_HEADING_RE.captures(line) {
            let time = pad_time(&c[1]);
            match out.iter_mut().find(|r| r.time == time && !r.transcribed) {
                Some(r) => r.transcribed = true,
                None => out.push(Recording { line_no: idx + 1, time, duration: None, file: None, transcribed: true }),
            }
        }
    }
    out
}

fn pad_time(t: &str) -> String {
    if t.len() == 4 {
        format!("0{t}")
    } else {
        t.to_string()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct TranscriptLine {
    pub line_no: usize,
    /// L'ora della trascrizione (`Trascrizione HH:MM` sopra la riga), se c'è.
    pub time: Option<String>,
    /// Il minutaggio della riga, `mm:ss`.
    pub stamp: String,
    pub text: String,
}

/// Le righe con il minutaggio a inizio riga, con l'ora della trascrizione a cui appartengono.
pub fn transcript_lines(body: &str) -> Vec<TranscriptLine> {
    let mut out = Vec::new();
    let mut time = None;
    let mut in_fence = false;
    for (idx, line) in body.lines().enumerate() {
        if is_fence(line) {
            in_fence = !in_fence;
            continue;
        }
        if in_fence {
            continue;
        }
        if let Some(c) = TRANSCRIPT_HEADING_RE.captures(line) {
            time = Some(pad_time(&c[1]));
        } else if HEADING_RE.is_match(line) {
            time = None;
        } else if let Some(c) = TIMESTAMP_RE.captures(line) {
            let text = c[2].trim();
            if !text.is_empty() {
                out.push(TranscriptLine { line_no: idx + 1, time: time.clone(), stamp: c[1].to_string(), text: text.to_string() });
            }
        }
    }
    out
}

pub fn slugify(text: &str) -> String {
    let ascii: String = text.nfkd().filter(char::is_ascii).collect();
    let mut out = String::new();
    let mut pending_dash = false;
    for c in ascii.trim().chars() {
        let c = c.to_ascii_lowercase();
        if c.is_ascii_alphanumeric() {
            if pending_dash && !out.is_empty() {
                out.push('-');
            }
            pending_dash = false;
            out.push(c);
        } else if c == '-' || c == '_' || c.is_whitespace() {
            pending_dash = true;
        }
        if out.len() >= 50 {
            break;
        }
    }
    let out = out.trim_matches('-').to_string();
    if out.is_empty() {
        "nota".to_string()
    } else {
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registrazioni_e_trascrizioni() {
        let body = "Intro\n🎙️ [Registrazione 9:42 (12:30)](audio/n-094200.wav)\n\n### Trascrizione 09:42\n[00:00] Allora, il budget.\n[01:12] Tre tranche mensili.\n\n## Note\n[02:00] Fuori dalla trascrizione\n\
                    ```\n[Registrazione 10:00](x.wav)\n```\n### Trascrizione 16:05\n[1:02:03] Lunga\n";
        let r = recordings(body);
        assert_eq!(r.len(), 2, "{r:?}");
        assert_eq!((r[0].time.as_str(), r[0].duration.as_deref(), r[0].file.as_deref(), r[0].transcribed), ("09:42", Some("12:30"), Some("audio/n-094200.wav"), true));
        assert_eq!((r[1].time.as_str(), r[1].file.as_deref(), r[1].transcribed), ("16:05", None, true), "resta solo il titolo");
        let t = transcript_lines(body);
        assert_eq!(t.len(), 4);
        assert_eq!((t[0].time.as_deref(), t[0].stamp.as_str(), t[0].text.as_str()), (Some("09:42"), "00:00", "Allora, il budget."));
        assert_eq!(t[2].time, None, "un altro titolo chiude la trascrizione");
        assert_eq!((t[3].time.as_deref(), t[3].stamp.as_str()), (Some("16:05"), "1:02:03"));
    }

    #[test]
    fn frontmatter_conservato_e_separato() {
        let text = "---\ntype: meeting\ntitle: Kickoff\npeople: [Marco, Laura]\n---\nCorpo\n";
        let (front, body) = split_frontmatter(text);
        assert_eq!(body, "Corpo\n");
        assert_eq!(front.raw, "---\ntype: meeting\ntitle: Kickoff\npeople: [Marco, Laura]\n---\n");
        assert_eq!(meta_str(&front.meta, "title").as_deref(), Some("Kickoff"));
        assert_eq!(meta_list(&front.meta, "people"), ["Marco", "Laura"]);
    }

    #[test]
    fn frontmatter_con_a_capo_windows() {
        let (front, body) = split_frontmatter("---\r\ntitle: A\r\n---\r\nCorpo\r\n");
        assert_eq!(body, "Corpo\r\n");
        assert_eq!(meta_str(&front.meta, "title").as_deref(), Some("A"));
    }

    #[test]
    fn frontmatter_non_valido_resta_nel_corpo() {
        for text in ["---\n: : [\n---\nx\n", "---\nnon chiuso\n", "--- no\ntitle: x\n---\n", "---\n- a\n---\nx"] {
            let (front, body) = split_frontmatter(text);
            assert_eq!(body, text);
            assert!(front.raw.is_empty());
        }
    }

    #[test]
    fn persone_riconosciute_come_prima() {
        assert_eq!(mentions("@Marco e @laura.b, @a @è-x"), ["Marco", "laura.b", "a", "è-x"]);
        assert_eq!(mentions("mail@example.com .@no @@no"), Vec::<&str>::new());
        assert_eq!(mentions("(@Marco.) @Giulia-"), ["Marco", "Giulia"]);
        assert_eq!(mentions("@ - @-x"), Vec::<&str>::new());
    }

    #[test]
    fn etichette_riconosciute_come_prima() {
        assert_eq!(tags("#casa #lavoro-q4 #a/b (#città)"), ["casa", "lavoro-q4", "a/b", "città"]);
        assert_eq!(tags("# titolo ## due #1 x#y a/#z &#39; ##w"), Vec::<&str>::new());
        assert_eq!(tags("#_ok"), ["_ok"]);
    }

    #[test]
    fn azioni_con_scadenza_e_completamento() {
        let ex = extract("- [ ] @Marco invia preventivo #Casa due:2026-10-31\n* [x] fatta done:2026-11-01 entro: 2026-10-01\n- [ ]   \n");
        assert_eq!(ex.actions.len(), 2);
        let a = &ex.actions[0];
        assert_eq!(a.line_no, 1);
        assert!(!a.done);
        assert_eq!(a.owner.as_deref(), Some("Marco"));
        assert_eq!(a.due.as_deref(), Some("2026-10-31"));
        assert_eq!(a.tags, ["casa"]);
        let b = &ex.actions[1];
        assert!(b.done);
        assert_eq!(b.done_on.as_deref(), Some("2026-11-01"));
        assert_eq!(b.due.as_deref(), Some("2026-10-01"));
    }

    #[test]
    fn sotto_attivita_e_descrizione() {
        let body = "- [ ] Madre #casa\n    Prima riga\n    Seconda riga\n    - [x] Figlia done:2026-11-01\n\t- [ ] Con tab\n        - [ ] Più interna\n- [ ] Altra\n";
        let ex = extract(body);
        let by = |n: usize| ex.actions.iter().find(|a| a.line_no == n).unwrap();
        assert_eq!(by(1).parent_line, None);
        assert_eq!(by(1).description, "Prima riga\nSeconda riga");
        assert_eq!(by(4).parent_line, Some(1));
        assert_eq!(by(5).parent_line, Some(1));
        assert_eq!(by(6).parent_line, Some(1), "i livelli più interni valgono come figlie della madre");
        assert_eq!(by(7).parent_line, None);
    }

    #[test]
    fn figlia_senza_madre_e_interruzioni() {
        let ex = extract("    - [ ] Senza madre\n- Punto normale\n    - [ ] Sotto un punto\nTesto\n- [ ] A\nTesto\n    - [ ] Dopo il testo\n");
        assert!(ex.actions.iter().all(|a| a.parent_line.is_none()));
    }

    #[test]
    fn la_descrizione_non_cambia_la_persona_dell_azione() {
        let ex = extract("- [ ] Azione\n    chiedere a @Elena #x\n\n    fuori dalla descrizione\n");
        assert_eq!(ex.actions[0].description, "chiedere a @Elena #x");
        assert!(ex.actions[0].people.is_empty());
        assert!(ex.actions[0].tags.is_empty());
        assert_eq!(ex.people, ["Elena"]);
    }

    #[test]
    fn blocchi_di_codice_ignorati() {
        let ex = extract("```\n- [ ] no @no #no !decisione [[no]]\n```\n- [ ] sì\n~~~\n# no\n~~~\n");
        assert_eq!(ex.actions.len(), 1);
        assert!(ex.people.is_empty() && ex.tags.is_empty() && ex.decisions.is_empty() && ex.links.is_empty());
        assert!(ex.headings.is_empty());
    }

    #[test]
    fn decisioni() {
        let ex = extract("- Budget confermato !decisione\n!Dec - Top in quarzo\n!decisionex no\n!decisione\n");
        let texts: Vec<_> = ex.decisions.iter().map(|d| d.text.as_str()).collect();
        assert_eq!(texts, ["Budget confermato", "Top in quarzo"]);
    }

    #[test]
    fn collegamenti_e_incorporamenti() {
        let ex = extract("Vedi [[2026-id|Titolo]] e [[Altra]] e [[]] ![[schizzo.excalidraw]] [[aperto\n");
        assert_eq!(ex.links.len(), 2);
        assert_eq!(ex.links[0].target, "2026-id");
        assert_eq!(ex.links[0].label.as_deref(), Some("Titolo"));
        assert_eq!(ex.links[1].target, "Altra");
        assert_eq!(ex.embeds, [Embed { line_no: 1, target: "schizzo.excalidraw".into() }]);
    }

    #[test]
    fn i_link_markdown_non_generano_etichette() {
        let ex = extract("[testo](file.md#ancora) [a](mailto:x@y.it)\n");
        assert!(ex.tags.is_empty() && ex.people.is_empty());
    }

    #[test]
    fn elementi_unici_senza_badare_alle_maiuscole() {
        let ex = extract("@Marco @marco #Casa #casa\n");
        assert_eq!(ex.people, ["Marco"]);
        assert_eq!(ex.tags, ["casa"]);
    }

    #[test]
    fn slug() {
        assert_eq!(slugify("Città & Più: Kickoff_cliente  X!"), "citta-piu-kickoff-cliente-x");
        assert_eq!(slugify("🎙️"), "nota");
        assert!(slugify(&"a".repeat(80)).len() <= 50);
    }

    #[test]
    fn testo_senza_scadenze() {
        assert_eq!(action_display_text("Chiamare @Marco  due:2026-01-01 done:2026-01-02 ora"), "Chiamare @Marco ora");
    }

    #[test]
    fn titolo_dal_primo_h1() {
        assert_eq!(first_h1("```\n# no\n```\n## no\n# Sì \n").as_deref(), Some("Sì"));
    }
}
