//! Integrazione col sistema: area di notifica, tasti globali, finestra della nota rapida.

use std::sync::Mutex;
use std::time::Duration;

use chrono::Local;
use serde_json::json;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutEvent, ShortcutState};

use crate::{show_main, AppState};

/// Azione associata a ogni tasto globale registrato.
static BINDINGS: Mutex<Vec<(Shortcut, String)>> = Mutex::new(Vec::new());

pub fn show_capture(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("capture") {
        let _ = window.center();
        let _ = window.show();
        let _ = window.set_focus();
        let _ = window.emit("capture-open", ());
    } else {
        // Se non è ancora pronta (subito dopo l'avvio) si apre la finestra principale: nessun testo va perso.
        show_main(app);
    }
}

fn open_today(app: &AppHandle) {
    let state = app.state::<AppState>();
    let today = Local::now().date_naive();
    if let Ok(Some(note)) = state.store.daily(today, true) {
        let _ = app.emit("open-page", json!({"page": format!("note:{}", note.id)}));
    }
    show_main(app);
}

/// Salva il lavoro in sospeso, poi chiude. Se la pagina non risponde, chiude comunque.
fn quit(app: &AppHandle) {
    let _ = app.emit("flush-and-close", ());
    let app = app.clone();
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_secs(2));
        app.exit(0);
    });
}

pub fn setup_tray(app: &AppHandle) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Apri QuickNotes", true, None::<&str>)?;
    let quick = MenuItem::with_id(app, "quick", "Nota rapida", true, Some("Ctrl+Alt+N"))?;
    let daily = MenuItem::with_id(app, "daily", "Nota del giorno", true, Some("Ctrl+Alt+D"))?;
    let exit = MenuItem::with_id(app, "exit", "Esci", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &quick, &daily, &exit])?;
    let mut builder = TrayIconBuilder::with_id("main")
        .tooltip("QuickNotes")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "open" => show_main(app),
            "quick" => show_capture(app),
            "daily" => open_today(app),
            "exit" => quit(app),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                show_main(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

pub fn register_hotkeys(app: &AppHandle, hotkeys: &[(String, String)]) {
    let mut taken = Vec::new();
    for (action, combo) in hotkeys {
        match combo.parse::<Shortcut>() {
            Ok(shortcut) => {
                if app.global_shortcut().register(shortcut).is_ok() {
                    if let Ok(mut b) = BINDINGS.lock() {
                        b.push((shortcut, action.clone()));
                    }
                } else {
                    taken.push(combo.clone());
                }
            }
            Err(_) => taken.push(combo.clone()),
        }
    }
    if !taken.is_empty() {
        let _ = app.emit("toast", format!("Tasti globali non disponibili: {}", taken.join(", ")));
    }
}

pub fn on_shortcut(app: &AppHandle, shortcut: &Shortcut, event: ShortcutEvent) {
    if event.state() != ShortcutState::Pressed {
        return;
    }
    let action = BINDINGS.lock().ok().and_then(|b| b.iter().find(|(s, _)| s == shortcut).map(|(_, a)| a.clone()));
    match action.as_deref() {
        Some("quick_note") => show_capture(app),
        Some("daily") => open_today(app),
        Some("toggle_recording") => {
            show_main(app);
            let _ = app.emit("toast", "La registrazione arriva con la tappa dell'audio");
        }
        _ => {}
    }
}

pub fn create_capture(app: &AppHandle, init: &str) {
    let url = WebviewUrl::App("index.html#capture".into());
    let built = WebviewWindowBuilder::new(app, "capture", url)
        .title("Nota rapida")
        .inner_size(520.0, 460.0)
        .resizable(false)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible(false)
        .initialization_script(init)
        .build();
    if let Ok(window) = built {
        let handle = window.clone();
        // Perdere il focus non chiude: il testo scritto resta finché non si salva o si preme Esc.
        window.on_window_event(move |event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = handle.hide();
            }
        });
    }
}
