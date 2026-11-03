//! Configurazione: `~/.quicknotes/config.json`, lo stesso file della versione precedente.
//!
//! `QUICKNOTES_CONFIG_DIR` e `QUICKNOTES_DIR` spostano configurazione e note: li usano
//! i test, le prove di sviluppo e il server MCP. Le chiavi sconosciute si conservano.

use std::fs;
use std::path::{Path, PathBuf};

use serde_json::{json, Map, Value};

fn home() -> PathBuf {
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

pub fn config_dir() -> PathBuf {
    std::env::var_os("QUICKNOTES_CONFIG_DIR").map(PathBuf::from).unwrap_or_else(|| home().join(".quicknotes"))
}

#[derive(Debug, Clone)]
pub struct Config {
    path: PathBuf,
    data: Map<String, Value>,
}

impl Config {
    /// Legge la configurazione. Un file assente o illeggibile vale come configurazione predefinita.
    pub fn load() -> Self {
        Self::load_from(&config_dir().join("config.json"))
    }

    pub fn load_from(path: &Path) -> Self {
        let data = fs::read_to_string(path)
            .ok()
            .and_then(|t| serde_json::from_str::<Value>(t.trim_start_matches('\u{feff}')).ok())
            .and_then(|v| v.as_object().cloned())
            .unwrap_or_default();
        Self { path: path.to_path_buf(), data }
    }

    pub fn save(&self) -> std::io::Result<()> {
        if let Some(dir) = self.path.parent() {
            fs::create_dir_all(dir)?;
        }
        let text = serde_json::to_string_pretty(&self.data).map_err(std::io::Error::other)?;
        let tmp = self.path.with_extension("json.tmp");
        fs::write(&tmp, text)?;
        fs::rename(tmp, &self.path)
    }

    fn str_or(&self, key: &str, default: &str) -> String {
        self.data.get(key).and_then(Value::as_str).unwrap_or(default).to_string()
    }

    pub fn notes_path(&self) -> PathBuf {
        if let Some(dir) = std::env::var_os("QUICKNOTES_DIR") {
            return PathBuf::from(dir);
        }
        match self.data.get("notes_dir").and_then(Value::as_str) {
            Some(d) if !d.trim().is_empty() => {
                let d = d.trim();
                match d.strip_prefix("~/").or_else(|| d.strip_prefix("~\\")) {
                    Some(rest) => home().join(rest),
                    None => PathBuf::from(d),
                }
            }
            _ => home().join("QuickNotes"),
        }
    }

    pub fn whisper_model(&self) -> String {
        self.str_or("whisper_model", "small")
    }

    pub fn language(&self) -> String {
        self.str_or("language", "it")
    }

    pub fn theme(&self) -> String {
        self.str_or("theme", "auto")
    }

    pub fn animations(&self) -> bool {
        self.data.get("animations").and_then(Value::as_bool).unwrap_or(true)
    }

    /// Le preferenze dell'interfaccia, chiave `ui`.
    pub fn ui(&self) -> Value {
        self.data.get("ui").cloned().unwrap_or_else(|| json!({}))
    }

    pub fn set_ui(&mut self, ui: Value) {
        self.data.insert("ui".to_string(), ui);
    }

    /// I tasti globali, azione → combinazione in formato Tauri (`Ctrl+Alt+N`).
    /// `new_meeting` della versione precedente diventa la nota rapida.
    pub fn hotkeys(&self) -> Vec<(String, String)> {
        let mut map = vec![
            ("quick_note".to_string(), "Ctrl+Alt+N".to_string()),
            ("daily".to_string(), "Ctrl+Alt+D".to_string()),
            ("toggle_recording".to_string(), "Ctrl+Alt+R".to_string()),
        ];
        if let Some(obj) = self.data.get("hotkeys").and_then(Value::as_object) {
            for (key, value) in obj {
                let action = if key == "new_meeting" { "quick_note" } else { key.as_str() };
                if let (Some(slot), Some(combo)) = (map.iter_mut().find(|(a, _)| a == action), value.as_str()) {
                    slot.1 = convert_hotkey(combo);
                }
            }
        }
        map
    }
}

/// Converte il formato pynput (`<ctrl>+<alt>+n`) in quello di Tauri (`Ctrl+Alt+N`).
pub fn convert_hotkey(combo: &str) -> String {
    combo
        .split('+')
        .map(|part| {
            let bare = part.trim().trim_start_matches('<').trim_end_matches('>');
            match bare.to_lowercase().as_str() {
                "ctrl" | "control" => "Ctrl".to_string(),
                "alt" => "Alt".to_string(),
                "shift" => "Shift".to_string(),
                "cmd" | "win" | "super" | "meta" => "Super".to_string(),
                _ => {
                    let mut c = bare.chars();
                    match c.next() {
                        Some(first) => first.to_uppercase().chain(c).collect(),
                        None => String::new(),
                    }
                }
            }
        })
        .collect::<Vec<_>>()
        .join("+")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn conversione_dei_tasti() {
        assert_eq!(convert_hotkey("<ctrl>+<alt>+n"), "Ctrl+Alt+N");
        assert_eq!(convert_hotkey("<cmd>+<shift>+n"), "Super+Shift+N");
        assert_eq!(convert_hotkey("Ctrl+Alt+R"), "Ctrl+Alt+R");
    }

    #[test]
    fn file_della_versione_precedente_e_chiavi_sconosciute() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        fs::write(&path, r#"{"notes_dir":"D:\\Note","whisper_model":"base","altro":1,
            "hotkeys":{"new_meeting":"<ctrl>+<alt>+m","daily":"<ctrl>+<alt>+d","toggle_recording":"<ctrl>+<alt>+r"}}"#).unwrap();
        let mut cfg = Config::load_from(&path);
        assert_eq!(cfg.whisper_model(), "base");
        assert_eq!(cfg.hotkeys()[0], ("quick_note".to_string(), "Ctrl+Alt+M".to_string()));
        cfg.set_ui(json!({"side": "open"}));
        cfg.save().unwrap();
        let again: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(again["altro"], 1);
        assert_eq!(again["ui"]["side"], "open");
    }

    #[test]
    fn file_assente_o_rovinato_vale_i_predefiniti() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        assert_eq!(Config::load_from(&path).theme(), "auto");
        fs::write(&path, "{ non valido").unwrap();
        assert_eq!(Config::load_from(&path).language(), "it");
    }
}
