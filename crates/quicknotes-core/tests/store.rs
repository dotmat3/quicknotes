use std::fs;

use chrono::NaiveDate;
use quicknotes_core::index::{ActionQuery, Filter, SearchQuery, Status};
use quicknotes_core::store::{ActionPatch, Error, NewNote, NoteStore, SaveOutcome};

fn day(s: &str) -> NaiveDate {
    NaiveDate::parse_from_str(s, "%Y-%m-%d").unwrap()
}

fn store() -> (tempfile::TempDir, NoteStore) {
    let dir = tempfile::tempdir().unwrap();
    let store = NoteStore::open(dir.path()).unwrap();
    (dir, store)
}

fn write(dir: &tempfile::TempDir, rel: &str, text: &str) {
    let path = dir.path().join(rel);
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, text).unwrap();
}

const OLD_MEETING: &str = "---\ntype: meeting\ntitle: Kickoff cliente X\ndate: 2026-10-27T10:00\npeople: [Marco, Laura]\nproject: clientex\nextra: da conservare   # commento\n---\n- Budget confermato !decisione\n- [ ] @Marco invia preventivo due:2026-10-31\nVedi [[2026-10-28-giornata|Giornata]]\n";

#[test]
fn un_salvataggio_non_cambia_il_frontmatter_di_una_nota_esistente() {
    let (dir, store) = store();
    write(&dir, "2026/10/2026-10-27-1000-kickoff.md", OLD_MEETING);
    assert_eq!(store.refresh().unwrap(), 1);
    let note = store.read("2026-10-27-1000-kickoff").unwrap();
    assert_eq!(note.title(), "Kickoff cliente X");
    assert_eq!(note.date(), "2026-10-27T10:00");
    assert_eq!(note.people(), ["Marco", "Laura"]);
    let new_body = format!("{}altro\n", note.body);
    store.update_body(&note.id, &new_body).unwrap();
    let text = fs::read_to_string(dir.path().join("2026/10/2026-10-27-1000-kickoff.md")).unwrap();
    assert!(text.contains("extra: da conservare   # commento"));
    assert!(text.ends_with("altro\n"));
}

#[test]
fn gli_a_capo_windows_restano_tali() {
    let (dir, store) = store();
    let crlf = OLD_MEETING.replace('\n', "\r\n");
    write(&dir, "2026/10/n.md", &crlf);
    store.refresh().unwrap();
    let note = store.read("n").unwrap();
    assert!(!note.body.contains('\r'));
    store.save(&note).unwrap();
    assert_eq!(fs::read_to_string(dir.path().join("2026/10/n.md")).unwrap(), crlf);
}

#[test]
fn titolo_e_data_dedotti_senza_frontmatter() {
    let (dir, store) = store();
    write(&dir, "x/2026-10-28-1530-prova.md", "# Titolo dal testo\ncorpo\n");
    write(&dir, "x/semplice.md", "solo testo\n");
    store.refresh().unwrap();
    let a = store.read("2026-10-28-1530-prova").unwrap();
    assert_eq!((a.title(), a.date()), ("Titolo dal testo", "2026-10-28T15:30"));
    assert_eq!(store.read("semplice").unwrap().title(), "semplice");
    // Nessuna scrittura implicita.
    assert_eq!(fs::read_to_string(dir.path().join("x/semplice.md")).unwrap(), "solo testo\n");
}

#[test]
fn nota_del_giorno_con_il_nome_di_sempre() {
    let (dir, store) = store();
    assert!(store.daily(day("2026-11-01"), false).unwrap().is_none());
    let note = store.daily(day("2026-11-01"), true).unwrap().unwrap();
    assert_eq!(note.id, "2026-11-01-giornata");
    assert_eq!(note.title(), "Giornata di domenica 01/11/2026");
    assert!(dir.path().join("2026/11/2026-11-01-giornata.md").exists());
    assert_eq!(store.daily(day("2026-11-01"), false).unwrap().unwrap().id, note.id);
}

#[test]
fn nuove_note_con_id_unico() {
    let (_dir, store) = store();
    let when = day("2026-11-03").and_hms_opt(9, 5, 0);
    let make = || NewNote { title: "Più idee".into(), note_type: "note".into(), when, body: "x".into(), ..Default::default() };
    let a = store.create_note(make()).unwrap();
    let b = store.create_note(make()).unwrap();
    assert_eq!(a.id, "2026-11-03-0905-piu-idee");
    assert_eq!(b.id, "2026-11-03-0905-piu-idee-2");
    let read = store.read(&a.id).unwrap();
    assert_eq!(read.body, "x\n");
    assert_eq!(read.note_type(), "note");
}

#[test]
fn ricerca_e_filtri() {
    let (dir, store) = store();
    write(&dir, "2026/10/2026-10-27-1000-kickoff.md", OLD_MEETING);
    write(&dir, "2026/10/2026-10-28-giornata.md", "---\ntype: daily\ntitle: Giornata\ndate: 2026-10-28\n---\nPreventivo cucina con @Giulia #casa\n");
    store.refresh().unwrap();
    let find = |text: &str, filter: Filter| {
        let found = store.search(&SearchQuery { text: text.into(), filter, limit: 10 }).unwrap();
        found.into_iter().map(|n| n.id).collect::<Vec<_>>()
    };
    assert_eq!(find("preventiv", Filter::default()).len(), 2, "parole parziali");
    assert_eq!(find("preventivo budget", Filter::default()), ["2026-10-27-1000-kickoff"], "prima tutte le parole");
    assert_eq!(find("cucina inesistente", Filter::default()), ["2026-10-28-giornata"], "poi almeno una");
    let by_person = Filter { person: Some("@giul".into()), ..Default::default() };
    assert_eq!(find("preventivo", by_person), ["2026-10-28-giornata"]);
    let by_project = Filter { project: Some("clientex".into()), ..Default::default() };
    assert_eq!(find("", by_project), ["2026-10-27-1000-kickoff"]);
    let by_date = Filter { date_from: Some("2026-10-28".into()), date_to: Some("2026-10-28".into()), ..Default::default() };
    assert_eq!(find("", by_date), ["2026-10-28-giornata"]);
    let hit = store.search(&SearchQuery { text: "cucina".into(), limit: 1, ..Default::default() }).unwrap();
    assert!(hit[0].snippet.as_ref().unwrap().contains("«cucina»"));
}

#[test]
fn le_modifiche_esterne_si_vedono_con_refresh() {
    let (dir, store) = store();
    write(&dir, "a.md", "- [ ] uno\n");
    store.refresh().unwrap();
    assert_eq!(store.refresh().unwrap(), 0, "senza modifiche non si reindicizza nulla");
    std::thread::sleep(std::time::Duration::from_millis(20));
    write(&dir, "a.md", "- [ ] uno\n- [ ] due\n");
    assert_eq!(store.refresh().unwrap(), 1);
    assert_eq!(store.actions(&ActionQuery { limit: 10, ..Default::default() }).unwrap().len(), 2);
    fs::remove_file(dir.path().join("a.md")).unwrap();
    store.refresh().unwrap();
    assert!(store.actions(&ActionQuery { limit: 10, ..Default::default() }).unwrap().is_empty());
}

#[test]
fn azioni_decisioni_persone_e_collegamenti() {
    let (dir, store) = store();
    write(&dir, "2026/10/2026-10-27-1000-kickoff.md", OLD_MEETING);
    write(&dir, "2026/10/2026-10-28-giornata.md", "---\ntype: daily\ntitle: Giornata\ndate: 2026-10-28\n---\n- [ ] Madre #casa\n    Una descrizione\n    - [x] Figlia done:2026-10-28\n");
    store.refresh().unwrap();
    let open = store.actions(&ActionQuery { limit: 10, ..Default::default() }).unwrap();
    assert_eq!(open.len(), 2);
    assert_eq!(open[0].due.as_deref(), Some("2026-10-31"), "prima le azioni con scadenza");
    assert_eq!(open[1].description, "Una descrizione");
    let all = store.actions(&ActionQuery { status: Status::All, limit: 10, ..Default::default() }).unwrap();
    let child = all.iter().find(|a| a.done).unwrap();
    assert_eq!(child.parent_line, Some(open[1].line));
    assert_eq!(child.done_on.as_deref(), Some("2026-10-28"));
    let by_owner = store.actions(&ActionQuery { owner: Some("marco".into()), limit: 10, ..Default::default() }).unwrap();
    assert_eq!(by_owner.len(), 1);
    assert_eq!(store.decisions(&Filter::default(), "budget", 10).unwrap()[0].text, "Budget confermato");
    let people: Vec<_> = store.people().unwrap().into_iter().map(|p| p.name).collect();
    assert!(people.contains(&"Laura".to_string()));
    assert!(store.projects().unwrap().iter().any(|p| p.name == "clientex"));
    let back = store.backlinks("2026-10-28-giornata").unwrap();
    assert_eq!(back[0].note_id, "2026-10-27-1000-kickoff");
    let out = store.outgoing_links("2026-10-27-1000-kickoff").unwrap();
    assert_eq!(out[0].note_id.as_deref(), Some("2026-10-28-giornata"));
}

#[test]
fn spunta_scrive_e_toglie_done() {
    let (dir, store) = store();
    write(&dir, "a.md", "- [ ] Rivedere il budget due:2026-11-02\n");
    store.refresh().unwrap();
    let change = store.set_action_status("a", "budget", Some(day("2026-11-03"))).unwrap();
    assert!(change.done);
    assert_eq!(fs::read_to_string(dir.path().join("a.md")).unwrap(), "- [x] Rivedere il budget due:2026-11-02 done:2026-11-03\n");
    store.set_action_status("a", "budget", None).unwrap();
    assert_eq!(fs::read_to_string(dir.path().join("a.md")).unwrap(), "- [ ] Rivedere il budget due:2026-11-02\n");
    assert!(matches!(store.set_action_status("a", "niente", None), Err(Error::NotFound(_))));
}

#[test]
fn chiudere_la_madre_conserva_le_date_delle_figlie() {
    let (dir, store) = store();
    write(&dir, "a.md", "- [ ] Madre\n    - [x] Già fatta done:2026-10-01\n    - [ ] Aperta\n- [ ] Altra\n");
    store.refresh().unwrap();
    assert_eq!(store.complete_with_children("a", 1, Some("- [ ] Madre"), day("2026-11-03")).unwrap(), 2);
    assert_eq!(
        fs::read_to_string(dir.path().join("a.md")).unwrap(),
        "- [x] Madre done:2026-11-03\n    - [x] Già fatta done:2026-10-01\n    - [x] Aperta done:2026-11-03\n- [ ] Altra\n"
    );
}

#[test]
fn dettagli_di_un_azione() {
    let (dir, store) = store();
    let line = "- [ ] Mandare a @Giulia la bozza #casa";
    write(&dir, "a.md", &format!("{line}\n"));
    store.refresh().unwrap();
    let patch = ActionPatch {
        due: Some(Some("2026-11-06".into())),
        person: Some((0, Some("Marco".into()))),
        tag: Some(Some("lavoro".into())),
        description: Some("Allegare il foglio".into()),
    };
    store.set_action_details("a", 1, Some(line), patch).unwrap();
    assert_eq!(
        fs::read_to_string(dir.path().join("a.md")).unwrap(),
        "- [ ] Mandare a @Marco la bozza #lavoro due:2026-11-06\n    Allegare il foglio\n"
    );
    let stale = store.set_action_details("a", 1, Some(line), ActionPatch::default());
    assert!(matches!(stale, Err(Error::Stale)), "se la riga è cambiata non si scrive");
}

#[test]
fn aggiunte_alla_nota_e_alla_giornata() {
    let (_dir, store) = store();
    let now = day("2026-11-03").and_hms_opt(14, 30, 0).unwrap();
    let note = store.append_to_daily("Telefonata", now, true).unwrap();
    assert_eq!(note.body, "- 14:30 Telefonata\n");
    let note = store.append_to_daily("riga uno\nriga due", now, true).unwrap();
    assert_eq!(note.body, "- 14:30 Telefonata\n\n### 14:30\nriga uno\nriga due\n");
    let note = store.add_to_section(&note.id, Some("Priorità"), "- [ ] Nuova").unwrap();
    assert!(note.body.ends_with("## Priorità\n- [ ] Nuova\n"));
}

#[test]
fn eliminazione_con_le_registrazioni() {
    let (dir, store) = store();
    write(&dir, "2026/n.md", "x\n");
    write(&dir, "2026/audio/n-101500.wav", "a");
    write(&dir, "2026/audio/n-altra.wav", "b");
    store.refresh().unwrap();
    let removed = store.delete("n", |p| fs::remove_file(p)).unwrap();
    assert_eq!(removed.len(), 2);
    assert!(dir.path().join("2026/audio/n-altra.wav").exists());
    assert!(matches!(store.read("n"), Err(Error::NotFound(_))));
}

#[test]
fn un_file_non_utf8_non_ferma_gli_altri_e_reindex_ricostruisce() {
    let (dir, store) = store();
    fs::write(dir.path().join("rotto.md"), [0xff, 0xfe, 0x00]).unwrap();
    write(&dir, "ok.md", "#casa\n");
    assert_eq!(store.refresh().unwrap(), 1);
    assert_eq!(store.reindex().unwrap(), 1);
    assert_eq!(store.projects().unwrap()[0].name, "casa");
}

#[test]
fn file_nascosti_e_temporanei_ignorati() {
    let (dir, store) = store();
    write(&dir, ".obsidian/x.md", "a");
    write(&dir, ".tmp-1-n.md", "a");
    write(&dir, "note.txt", "a");
    assert_eq!(store.refresh().unwrap(), 0);
}

#[test]
fn non_tocca_il_vecchio_indice() {
    let (dir, _) = {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir_all(dir.path().join(".quicknotes")).unwrap();
        fs::write(dir.path().join(".quicknotes/index.db"), "vecchio").unwrap();
        let s = NoteStore::open(dir.path()).unwrap();
        (dir, s)
    };
    assert_eq!(fs::read_to_string(dir.path().join(".quicknotes/index.db")).unwrap(), "vecchio");
    assert!(dir.path().join(".quicknotes/index-v3.db").exists());
}

#[test]
fn salvataggio_con_conflitto_non_sovrascrive_le_modifiche_esterne() {
    let (dir, store) = store();
    write(&dir, "a.md", "uno
");
    store.refresh().unwrap();
    assert_eq!(store.save_if_unchanged("a", "uno
", "due
").unwrap(), SaveOutcome::Saved);
    assert_eq!(store.save_if_unchanged("a", "due
", "due
").unwrap(), SaveOutcome::Saved);
    write(&dir, "a.md", "esterno
");
    let outcome = store.save_if_unchanged("a", "due
", "mio
").unwrap();
    assert_eq!(outcome, SaveOutcome::Conflict { disk: "esterno
".into() });
    assert_eq!(fs::read_to_string(dir.path().join("a.md")).unwrap(), "esterno
");
    let now = day("2026-11-03").and_hms_opt(10, 0, 0).unwrap();
    let copy = store.save_conflict_copy("a", "mio
", now).unwrap();
    assert_eq!(store.read(&copy.id).unwrap().body, "mio
");
}

#[test]
fn refresh_elenca_solo_le_modifiche_esterne() {
    let (dir, store) = store();
    write(&dir, "a.md", "uno
");
    assert_eq!(store.refresh_changes().unwrap(), ["a"]);
    store.update_body("a", "due
").unwrap();
    assert!(store.refresh_changes().unwrap().is_empty(), "le scritture dell'app non contano");
    std::thread::sleep(std::time::Duration::from_millis(20));
    write(&dir, "a.md", "tre
");
    assert_eq!(store.refresh_changes().unwrap(), ["a"]);
    fs::remove_file(dir.path().join("a.md")).unwrap();
    assert_eq!(store.refresh_changes().unwrap(), ["a"]);
}
