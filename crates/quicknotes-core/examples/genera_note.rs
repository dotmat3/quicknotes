//! Genera note finte per misurare i tempi, poi misura indicizzazione e ricerca.
//! Uso: cargo run --release -p quicknotes-core --example genera_note -- <cartella> [numero]

use std::fs;
use std::path::PathBuf;
use std::time::Instant;

use quicknotes_core::index::{ActionQuery, SearchQuery};
use quicknotes_core::NoteStore;

const WORDS: [&str; 20] = [
    "budget", "preventivo", "cucina", "riunione", "fornitori", "scadenza", "ricerca", "embedding", "cliente",
    "contratto", "revisione", "trimestre", "obiettivi", "bozza", "misure", "lavello", "trascrizione", "modello",
    "architettura", "requisiti",
];

fn main() {
    let mut args = std::env::args().skip(1);
    let root = PathBuf::from(args.next().expect("indica una cartella di prova"));
    let count: usize = args.next().and_then(|n| n.parse().ok()).unwrap_or(1000);
    assert!(
        !root.join(".quicknotes/index.db").exists(),
        "la cartella contiene già note della versione precedente: usane una vuota"
    );
    for i in 0..count {
        let month = i % 12 + 1;
        let dom = i % 28 + 1;
        let dir = root.join(format!("2026/{month:02}"));
        fs::create_dir_all(&dir).unwrap();
        let mut body = format!(
            "---\ntype: meeting\ntitle: Riunione {i}\ndate: 2026-{month:02}-{dom:02}T10:00\npeople: [Giulia, Marco]\n---\n"
        );
        for p in 0..40 {
            let w = |k: usize| WORDS[(i * 7 + p * 13 + k) % WORDS.len()];
            body += &format!("{} {} {} {} con @Persona{} #tag{}\n", w(0), w(1), w(2), w(3), p % 9, i % 12);
            if p % 8 == 0 {
                body += &format!("- [ ] {} {} due:2026-{month:02}-{dom:02}\n", w(4), w(5));
            }
            if p % 19 == 0 {
                body += &format!("{} {} !decisione\n", w(6), w(7));
            }
        }
        fs::write(dir.join(format!("2026-{month:02}-{dom:02}-1000-riunione-{i}.md")), body).unwrap();
    }

    let t = Instant::now();
    let store = NoteStore::open(&root).unwrap();
    println!("apertura indice: {:?}", t.elapsed());
    let t = Instant::now();
    let n = store.refresh().unwrap();
    println!("indicizzazione completa di {n} note: {:?}", t.elapsed());
    let t = Instant::now();
    store.refresh().unwrap();
    println!("allineamento senza modifiche: {:?}", t.elapsed());
    for q in ["bud", "preventivo cucina", "lavello trascrizione modello"] {
        let t = Instant::now();
        let found = store.search(&SearchQuery { text: q.into(), limit: 20, ..Default::default() }).unwrap();
        println!("ricerca '{q}': {} risultati in {:?}", found.len(), t.elapsed());
    }
    let t = Instant::now();
    let a = store.actions(&ActionQuery { limit: 500, ..Default::default() }).unwrap();
    println!("{} azioni aperte: {:?}", a.len(), t.elapsed());
}
