//! Note, indice e regole di QuickNotes. I file Markdown sono la fonte di verità;
//! l'indice SQLite si può sempre ricostruire.

pub mod config;
pub mod dates;
pub mod edit;
pub mod images;
pub mod index;
pub mod parser;
pub mod store;
pub mod views;

pub use config::Config;
pub use store::{Error, Note, NoteStore, Result};
