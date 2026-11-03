//! Immagini delle note: salvate in `images/` accanto alla nota e citate con il tag Markdown standard
//! `![](images/…)`. Il formato si riconosce dal contenuto, mai dal nome o da quello che dice la pagina.

use std::fs;
use std::io::Write;
use std::path::{Component, Path, PathBuf};

use chrono::NaiveDateTime;

use crate::store::{Error, NoteStore, Result};

/// Oltre questa dimensione un'immagine si rifiuta: la pagina chiede conferma già sopra i 10 MB.
pub const MAX_BYTES: usize = 50 * 1024 * 1024;

/// Estensione e tipo MIME dai primi byte del file. Solo formati che WebView2 mostra e che non eseguono nulla:
/// niente SVG, che può contenere script.
pub fn sniff(bytes: &[u8]) -> Option<(&'static str, &'static str)> {
    if bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        Some(("png", "image/png"))
    } else if bytes.starts_with(&[0xFF, 0xD8, 0xFF]) {
        Some(("jpg", "image/jpeg"))
    } else if bytes.starts_with(b"GIF87a") || bytes.starts_with(b"GIF89a") {
        Some(("gif", "image/gif"))
    } else if bytes.len() >= 12 && &bytes[..4] == b"RIFF" && &bytes[8..12] == b"WEBP" {
        Some(("webp", "image/webp"))
    } else if bytes.starts_with(b"BM") && bytes.len() > 26 {
        Some(("bmp", "image/bmp"))
    } else {
        None
    }
}

impl NoteStore {
    /// Salva un'immagine accanto alla nota, in `images/AAAA-MM-GG-HHMMSS.ext` (con `-2`, `-3`… se il nome
    /// c'è già), e restituisce il percorso da scrivere nel tag Markdown, relativo alla nota.
    pub fn save_image(&self, note_id: &str, bytes: &[u8], now: NaiveDateTime) -> Result<String> {
        if bytes.len() > MAX_BYTES {
            return Err(Error::Invalid(format!("Immagine troppo grande: {} MB, il massimo è 50", bytes.len() / (1024 * 1024))));
        }
        let (ext, _) = sniff(bytes).ok_or_else(|| Error::Invalid("Non è un'immagine PNG, JPEG, GIF, WebP o BMP".into()))?;
        let note = self.read(note_id)?;
        let dir = note.path.parent().unwrap_or(self.root()).join("images");
        fs::create_dir_all(&dir)?;
        let stem = now.format("%Y-%m-%d-%H%M%S").to_string();
        let mut n = 1;
        let (name, mut file) = loop {
            let name = if n == 1 { format!("{stem}.{ext}") } else { format!("{stem}-{n}.{ext}") };
            // `create_new` non sovrascrive mai: due immagini nello stesso secondo ricevono un numero.
            match fs::OpenOptions::new().write(true).create_new(true).open(dir.join(&name)) {
                Ok(f) => break (name, f),
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists && n < 1000 => n += 1,
                Err(e) => return Err(e.into()),
            }
        };
        if let Err(e) = file.write_all(bytes).and_then(|_| file.sync_all()) {
            drop(file);
            let _ = fs::remove_file(dir.join(&name));
            return Err(e.into());
        }
        Ok(format!("images/{name}"))
    }
}

/// Il file chiesto dalla pagina con il protocollo delle immagini: `path` è il percorso dell'indirizzo,
/// relativo alla cartella delle note e codificato. Restituisce il file e il suo tipo solo se è
/// un'immagine vera dentro la cartella delle note; per tutto il resto `None`.
pub fn resolve(root: &Path, path: &str) -> Option<(PathBuf, &'static str)> {
    let decoded = percent_decode(path.trim_start_matches('/'))?;
    let rel = Path::new(&decoded);
    if rel.components().any(|c| !matches!(c, Component::Normal(_))) {
        return None;
    }
    let root = root.canonicalize().ok()?;
    let file = root.join(rel).canonicalize().ok()?;
    if !file.starts_with(&root) || !file.is_file() {
        return None;
    }
    let mut head = [0u8; 32];
    let n = fs::File::open(&file).and_then(|mut f| std::io::Read::read(&mut f, &mut head)).ok()?;
    let (_, mime) = sniff(&head[..n])?;
    Some((file, mime))
}

/// Decodifica `%XX` (come `encodeURIComponent` nella pagina). `None` se il risultato non è UTF-8 valido.
pub fn percent_decode(s: &str) -> Option<String> {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' {
            let hex = std::str::from_utf8(bytes.get(i + 1..i + 3)?).ok()?;
            out.push(u8::from_str_radix(hex, 16).ok()?);
            i += 3;
        } else {
            out.push(bytes[i]);
            i += 1;
        }
    }
    String::from_utf8(out).ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::store::NewNote;

    const PNG: &[u8] = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR";

    fn at(s: &str) -> NaiveDateTime {
        NaiveDateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S").unwrap()
    }

    #[test]
    fn formato_dal_contenuto() {
        assert_eq!(sniff(PNG), Some(("png", "image/png")));
        assert_eq!(sniff(&[0xFF, 0xD8, 0xFF, 0xE0]).map(|s| s.0), Some("jpg"));
        assert_eq!(sniff(b"RIFF\0\0\0\0WEBPVP8 ").map(|s| s.0), Some("webp"));
        assert_eq!(sniff(b"<svg xmlns=\"http://www.w3.org/2000/svg\"><script/></svg>"), None, "niente SVG");
        assert_eq!(sniff(b"MZ\x90\0"), None, "un eseguibile non passa per immagine");
    }

    #[test]
    fn salvata_accanto_alla_nota_con_un_nome_libero() {
        let dir = tempfile::tempdir().unwrap();
        let store = NoteStore::open(dir.path()).unwrap();
        let note = store.create_note(NewNote { title: "Riunione".into(), note_type: "meeting".into(), ..Default::default() }).unwrap();
        let first = store.save_image(&note.id, PNG, at("2026-11-03 15:30:12")).unwrap();
        let second = store.save_image(&note.id, PNG, at("2026-11-03 15:30:12")).unwrap();
        assert_eq!(first, "images/2026-11-03-153012.png");
        assert_eq!(second, "images/2026-11-03-153012-2.png", "lo stesso secondo non sovrascrive");
        let folder = note.path.parent().unwrap();
        assert_eq!(fs::read(folder.join(&first)).unwrap(), PNG);
        assert!(store.save_image(&note.id, b"testo qualsiasi", at("2026-11-03 15:30:13")).is_err());
        assert!(!folder.join("images/2026-11-03-153013.png").exists(), "un file rifiutato non lascia tracce");
    }

    #[test]
    fn si_serve_solo_un_immagine_dentro_la_cartella_delle_note() {
        let base = tempfile::tempdir().unwrap();
        let root = base.path().join("note");
        fs::create_dir_all(root.join("2026/11/images")).unwrap();
        fs::write(root.join("2026/11/images/foto con spazi.png"), PNG).unwrap();
        fs::write(root.join("2026/11/nota.md"), "testo").unwrap();
        fs::write(base.path().join("fuori.png"), PNG).unwrap();
        let (file, mime) = resolve(&root, "/2026/11/images/foto%20con%20spazi.png").expect("l'immagine si serve");
        assert!(file.ends_with("foto con spazi.png"));
        assert_eq!(mime, "image/png");
        assert!(resolve(&root, "/2026/11/nota.md").is_none(), "una nota non è un'immagine");
        assert!(resolve(&root, "/../fuori.png").is_none(), "fuori dalla cartella delle note");
        assert!(resolve(&root, "/2026/%2E%2E/%2E%2E/../fuori.png").is_none(), "nemmeno con i punti codificati");
        assert!(resolve(&root, "/C:/Windows/win.ini").is_none(), "niente percorsi assoluti");
        assert!(resolve(&root, "/2026/11/images/manca.png").is_none());
    }
}
