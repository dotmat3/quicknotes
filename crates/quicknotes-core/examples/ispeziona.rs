//! Mostra come il nucleo legge una cartella di note. Uso: ispeziona <cartella>
use quicknotes_core::index::{ActionQuery, Filter, Status};
use quicknotes_core::NoteStore;

fn main() {
    let root = std::env::args().nth(1).expect("indica una cartella");
    let store = NoteStore::open(&root).unwrap();
    println!("indicizzate: {}", store.refresh().unwrap());
    for n in store.list_notes(&Filter::default(), 50).unwrap() {
        println!("{} | {} | {} | {} | {:?}", n.id, n.note_type, n.title, n.date, n.people);
        let note = store.read(&n.id).unwrap();
        store.save(&note).unwrap();
    }
    for a in store.actions(&ActionQuery { status: Status::All, limit: 50, ..Default::default() }).unwrap() {
        println!("azione: {} done={} due={:?} in {}", a.text, a.done, a.due, a.note_id);
    }
    println!("decisioni: {}", store.decisions(&Filter::default(), "", 50).unwrap().len());
    println!("persone: {:?}", store.people().unwrap().iter().map(|p| &p.name).collect::<Vec<_>>());
    println!("etichette: {:?}", store.projects().unwrap().iter().map(|p| &p.name).collect::<Vec<_>>());
}
