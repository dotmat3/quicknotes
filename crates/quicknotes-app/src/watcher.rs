//! Modifiche esterne: Obsidian, Claude, una sincronizzazione. Gli eventi arrivano raggruppati.

use std::sync::mpsc::{channel, RecvTimeoutError};
use std::sync::Arc;
use std::time::Duration;

use notify::{RecursiveMode, Watcher};
use quicknotes_core::NoteStore;
use tauri::{AppHandle, Emitter};

const QUIET: Duration = Duration::from_millis(200);

pub fn start(app: AppHandle, store: Arc<NoteStore>) {
    std::thread::spawn(move || {
        let (tx, rx) = channel();
        let Ok(mut watcher) = notify::recommended_watcher(tx) else { return };
        if watcher.watch(store.root(), RecursiveMode::Recursive).is_err() {
            return;
        }
        loop {
            let relevant = |e: &notify::Result<notify::Event>| {
                e.as_ref().is_ok_and(|ev| {
                    ev.paths.iter().any(|p| {
                        p.extension().is_some_and(|x| x == "md")
                            && !p.components().any(|c| c.as_os_str().to_string_lossy().starts_with('.'))
                    })
                })
            };
            match rx.recv() {
                Ok(event) if relevant(&event) => {}
                Ok(_) => continue,
                Err(_) => return,
            }
            // Si aspetta che la raffica finisca, poi si allinea una volta sola.
            loop {
                match rx.recv_timeout(QUIET) {
                    Ok(_) => continue,
                    Err(RecvTimeoutError::Timeout) => break,
                    Err(RecvTimeoutError::Disconnected) => return,
                }
            }
            if let Ok(ids) = store.refresh_changes() {
                if !ids.is_empty() {
                    let _ = app.emit("note-changed", &ids);
                    let _ = app.emit("index-updated", ids.len());
                }
            }
        }
    });
}
