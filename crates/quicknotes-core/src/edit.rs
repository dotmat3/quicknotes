//! Modifiche al testo delle note: funzioni pure, usate da app e server MCP.

use crate::parser::{self, is_fence, DONE_RE, DUE_RE};

/// Toglie gli spazi rimasti doppi dopo aver levato un'etichetta, senza toccare il rientro.
fn squeeze(line: &str) -> String {
    let indent = &line[..line.len() - line.trim_start().len()];
    let mut out = indent.to_string();
    let mut prev_space = false;
    for c in line.trim() .chars() {
        if c == ' ' || c == '\t' {
            if !prev_space {
                out.push(' ');
            }
            prev_space = true;
        } else {
            out.push(c);
            prev_space = false;
        }
    }
    out
}

/// La riga con la data di completamento indicata; `None` la toglie.
pub fn with_done(line: &str, day: Option<&str>) -> String {
    let bare = squeeze(&DONE_RE.replace_all(line, ""));
    match day {
        Some(d) => format!("{bare} done:{d}"),
        None => bare,
    }
}

/// La riga con la scadenza indicata, prima di un eventuale `done:`; `None` la toglie.
pub fn with_due(line: &str, day: Option<&str>) -> String {
    let done = DONE_RE.captures(line).map(|c| c[1].to_string());
    let no_done = DONE_RE.replace_all(line, "");
    let mut out = squeeze(&DUE_RE.replace_all(&no_done, ""));
    if let Some(d) = day {
        out.push_str(&format!(" due:{d}"));
    }
    if let Some(d) = done {
        out.push_str(&format!(" done:{d}"));
    }
    out
}

/// La riga spuntata o riaperta: la casella e `done:` cambiano insieme.
pub fn with_checked(line: &str, done_on: Option<&str>) -> String {
    let mark = if done_on.is_some() { "[x]" } else { "[ ]" };
    let replaced = match parser::ACTION_RE.captures(line) {
        Some(c) => {
            let box_pos = c.get(2).expect("gruppo presente").start() - 1;
            format!("{}{}{}", &line[..box_pos], mark, &line[box_pos + 3..])
        }
        None => line.to_string(),
    };
    with_done(&replaced, done_on)
}

/// Inserisce un elemento dopo il testo, prima di `due:` e `done:`.
fn insert_before_dates(line: &str, item: &str) -> String {
    let first = [DUE_RE.find(line), DONE_RE.find(line)]
        .into_iter()
        .flatten()
        .map(|m| m.start())
        .min();
    match first {
        Some(pos) => squeeze(&format!("{} {item} {}", line[..pos].trim_end(), &line[pos..])),
        None => format!("{} {item}", line.trim_end()),
    }
}

fn normalized(prefix: char, name: &str) -> String {
    let bare = name.trim().trim_start_matches(prefix);
    let bare: String = bare.split_whitespace().collect::<Vec<_>>().join(if prefix == '#' { "-" } else { "" });
    format!("{prefix}{bare}")
}

/// Cambia la persona in posizione `index`, al suo posto, così la frase resta corretta.
/// Se in quella posizione non c'è nessuno la aggiunge; `None` la toglie.
pub fn with_person(line: &str, index: usize, name: Option<&str>) -> String {
    let spans = parser::mention_spans(line);
    match (spans.get(index), name) {
        (Some(&(start, end)), Some(n)) => {
            format!("{}{}{}", &line[..start], normalized('@', n), &line[end..])
        }
        (Some(&(start, end)), None) => squeeze(&format!("{}{}", &line[..start], &line[end..])),
        (None, Some(n)) => insert_before_dates(line, &normalized('@', n)),
        (None, None) => line.to_string(),
    }
}

/// Cambia la prima etichetta e lascia invariate le altre; `None` la toglie.
pub fn with_tag(line: &str, name: Option<&str>) -> String {
    let spans = parser::tag_spans(line);
    match (spans.first(), name) {
        (Some(&(start, end)), Some(n)) => {
            format!("{}{}{}", &line[..start], normalized('#', n), &line[end..])
        }
        (Some(&(start, end)), None) => squeeze(&format!("{}{}", &line[..start], &line[end..])),
        (None, Some(n)) => insert_before_dates(line, &normalized('#', n)),
        (None, None) => line.to_string(),
    }
}

/// Il corpo con la descrizione dell'azione alla riga `line_no` sostituita da `text`.
pub fn with_description(body: &str, line_no: usize, text: &str) -> String {
    let ends_nl = body.ends_with('\n');
    let mut lines: Vec<String> = body.lines().map(String::from).collect();
    if line_no == 0 || line_no > lines.len() {
        return body.to_string();
    }
    let width = parser::indent_width(&lines[line_no - 1]);
    let raw_indent = &lines[line_no - 1][..lines[line_no - 1].len() - lines[line_no - 1].trim_start().len()];
    let indent = format!("{raw_indent}    ");
    let mut end = line_no;
    while end < lines.len() {
        let l = &lines[end];
        let bullet = {
            let t = l.trim_start();
            t.starts_with("- ") || t.starts_with("* ") || t.starts_with("+ ")
                || t.split_once(['.', ')']).is_some_and(|(n, r)| {
                    !n.is_empty() && n.bytes().all(|b| b.is_ascii_digit()) && r.starts_with(' ')
                })
        };
        if l.trim().is_empty() || parser::indent_width(l) <= width || bullet {
            break;
        }
        end += 1;
    }
    let new: Vec<String> = text
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .map(|l| format!("{indent}{l}"))
        .collect();
    lines.splice(line_no..end, new);
    let mut out = lines.join("\n");
    if ends_nl {
        out.push('\n');
    }
    out
}

/// Il corpo con `block` in fondo alla sezione indicata, creata alla fine della nota se manca.
/// Senza sezione il blocco va in fondo alla nota, separato da una riga vuota.
pub fn add_to_section(body: &str, section: Option<&str>, block: &str) -> String {
    let block = block.trim_matches('\n');
    let trimmed = body.trim_end_matches('\n');
    let mut lines: Vec<&str> = if body.trim().is_empty() { Vec::new() } else { trimmed.split('\n').collect() };

    let heading_of = |line: &str| -> Option<(usize, String)> {
        let hashes = line.bytes().take_while(|b| *b == b'#').count();
        if !(1..=6).contains(&hashes) {
            return None;
        }
        let rest = &line[hashes..];
        if !rest.starts_with([' ', '\t']) {
            return None;
        }
        Some((hashes, rest.trim().to_string()))
    };

    let mut found: Option<(usize, usize)> = None;
    if let Some(wanted) = section {
        let wanted = wanted.trim().to_lowercase();
        let mut in_fence = false;
        for (i, line) in lines.iter().enumerate() {
            if is_fence(line) {
                in_fence = !in_fence;
            } else if !in_fence {
                if let Some((level, text)) = heading_of(line) {
                    if text.to_lowercase() == wanted {
                        found = Some((i, level));
                        break;
                    }
                }
            }
        }
    }

    let Some((start, level)) = found else {
        let heading;
        let mut tail: Vec<&str> = Vec::new();
        if !lines.is_empty() {
            tail.push("");
        }
        if let Some(s) = section {
            heading = format!("## {}", s.trim());
            tail.push(&heading);
            tail.push(block);
            lines.extend(tail);
            return lines.join("\n") + "\n";
        }
        tail.push(block);
        lines.extend(tail);
        return lines.join("\n") + "\n";
    };

    let mut end = lines.len();
    let mut in_fence = false;
    for (i, line) in lines.iter().enumerate().skip(start + 1) {
        if is_fence(line) {
            in_fence = !in_fence;
        } else if !in_fence && heading_of(line).is_some_and(|(l, _)| l <= level) {
            end = i;
            break;
        }
    }
    while end - 1 > start && lines[end - 1].trim().is_empty() {
        end -= 1;
    }
    lines.insert(end, block);
    lines.join("\n") + "\n"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn done_conserva_il_rientro_e_gli_spazi() {
        assert_eq!(with_done("    - [x] Fatta", Some("2026-11-01")), "    - [x] Fatta done:2026-11-01");
        assert_eq!(with_done("    - [ ] Fatta done:2026-11-01 ora", None), "    - [ ] Fatta ora");
        assert_eq!(with_done("- [x] A done:2026-01-01", Some("2026-02-02")), "- [x] A done:2026-02-02");
    }

    #[test]
    fn due_sta_prima_di_done() {
        assert_eq!(with_due("- [x] A done:2026-01-01", Some("2026-02-02")), "- [x] A due:2026-02-02 done:2026-01-01");
        assert_eq!(with_due("- [ ] A due:2026-01-01 #x", Some("2026-02-02")), "- [ ] A #x due:2026-02-02");
        assert_eq!(with_due("- [ ] A entro: 2026-01-01", None), "- [ ] A");
    }

    #[test]
    fn spunta_e_riapertura() {
        assert_eq!(with_checked("  - [ ] A due:2026-01-01", Some("2026-11-03")), "  - [x] A due:2026-01-01 done:2026-11-03");
        assert_eq!(with_checked("* [X] A done:2026-11-03", None), "* [ ] A");
        assert_eq!(with_checked("testo senza casella", None), "testo senza casella");
    }

    #[test]
    fn persona_sostituita_al_suo_posto() {
        let l = "- [ ] Mandare a @Giulia la bozza #casa due:2026-11-02";
        assert_eq!(with_person(l, 0, Some("@Marco")), "- [ ] Mandare a @Marco la bozza #casa due:2026-11-02");
        assert_eq!(with_person(l, 1, Some("Elena")), "- [ ] Mandare a @Giulia la bozza #casa @Elena due:2026-11-02");
        assert_eq!(with_person(l, 0, None), "- [ ] Mandare a la bozza #casa due:2026-11-02");
        assert_eq!(with_person("- [ ] A", 0, Some("B")), "- [ ] A @B");
        assert_eq!(with_person("- [ ] A @x @y", 1, None), "- [ ] A @x");
        assert_eq!(with_person("- [ ] A", 3, None), "- [ ] A");
    }

    #[test]
    fn etichetta_lascia_invariate_le_altre() {
        assert_eq!(with_tag("- [ ] A #a #b", Some("c")), "- [ ] A #c #b");
        assert_eq!(with_tag("- [ ] A #a #b", None), "- [ ] A #b");
        assert_eq!(with_tag("- [ ] A done:2026-01-01", Some("#Nuova etichetta")), "- [ ] A #Nuova-etichetta done:2026-01-01");
    }

    #[test]
    fn descrizione_scritta_prima_delle_figlie() {
        let b = "- [ ] A\n    vecchia\n    riga\n    - [ ] figlia\n- [ ] B\n";
        assert_eq!(with_description(b, 1, "nuova\n\naltra"), "- [ ] A\n    nuova\n    altra\n    - [ ] figlia\n- [ ] B\n");
        assert_eq!(with_description(b, 1, ""), "- [ ] A\n    - [ ] figlia\n- [ ] B\n");
        assert_eq!(with_description("  - [ ] A", 1, "x"), "  - [ ] A\n      x");
        assert_eq!(with_description(b, 99, "x"), b);
    }

    #[test]
    fn sezione_assente_o_nota_vuota() {
        assert_eq!(add_to_section("", Some("Note"), "x"), "## Note\nx\n");
        assert_eq!(add_to_section("testo\n", Some("Note"), "x\n"), "testo\n\n## Note\nx\n");
        assert_eq!(add_to_section("", None, "x"), "x\n");
        assert_eq!(add_to_section("testo\n\n", None, "x"), "testo\n\nx\n");
    }

    #[test]
    fn sezione_esistente() {
        let b = "## Note\na\n\n## Altro\nb\n";
        assert_eq!(add_to_section(b, Some("note"), "x"), "## Note\na\nx\n\n## Altro\nb\n");
        assert_eq!(add_to_section("## Note\n\n\n", Some("NOTE"), "x"), "## Note\nx\n");
        assert_eq!(add_to_section("## N\n### sotto\na\n# Dopo\n", Some("N"), "x"), "## N\n### sotto\na\nx\n# Dopo\n");
    }

    #[test]
    fn titoli_nei_blocchi_di_codice_ignorati() {
        let b = "```\n## Note\n```\n## Note\n```\n# no\n```\n";
        assert_eq!(add_to_section(b, Some("Note"), "x"), "```\n## Note\n```\n## Note\n```\n# no\n```\nx\n");
    }
}
