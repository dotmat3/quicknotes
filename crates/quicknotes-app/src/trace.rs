//! Tempi di avvio: con `QUICKNOTES_TRACE=<file>` ogni fase aggiunge una riga al file.

use std::io::Write;
use std::sync::OnceLock;
use std::time::Instant;

static START: OnceLock<Instant> = OnceLock::new();

pub fn mark(phase: &str) {
    let start = *START.get_or_init(Instant::now);
    let Some(path) = std::env::var_os("QUICKNOTES_TRACE") else { return };
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{:>7.1} ms  {phase}", start.elapsed().as_secs_f64() * 1000.0);
    }
}
