// In release niente finestra di console.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod desktop;
mod trace;
mod watcher;

use std::sync::{Arc, Mutex};
use std::time::Duration;

use chrono::Local;
use quicknotes_core::{dates, Config, NoteStore};
use serde_json::json;
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};

pub struct AppState {
    pub store: Arc<NoteStore>,
    pub config: Mutex<Config>,
}

/// La pagina è disegnata: si può mostrare la finestra. La nota rapida resta nascosta finché non serve.
#[tauri::command]
fn app_ready(window: tauri::WebviewWindow) {
    if window.label() == "main" {
        trace::mark("prima pittura");
        let _ = window.show();
        let _ = window.set_focus();
    }
}

pub fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
        let _ = window.emit("window-shown", ());
    }
}

/// Dati iniettati in ogni pagina: la prima schermata non aspetta nessuna chiamata.
fn boot_script(config: &Config, store: &NoteStore) -> quicknotes_core::Result<String> {
    let today = Local::now().date_naive();
    let daily = store.daily(today, true)?;
    let boot = json!({
        "theme": config.theme(),
        "ui": config.ui(),
        "today": daily.map(|n| json!({
            "id": n.id,
            "title": dates::daily_title(today),
            "short": today.format("%d/%m").to_string(),
        })),
    });
    Ok(format!("window.__QN__ = {boot};"))
}

fn main() {
    trace::mark("main");
    tauri::Builder::default()
        // Va registrato per primo: una seconda istanza riapre questa e termina subito.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_main(app)))
        .plugin(tauri_plugin_global_shortcut::Builder::new().with_handler(desktop::on_shortcut).build())
        // Solo per `open_url`: la pagina non ha permessi sul plugin.
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            app_ready,
            commands::save_ui,
            commands::open_url,
            commands::sidebar,
            commands::recent_notes,
            commands::top_people,
            commands::read_note,
            commands::all_tags,
            commands::search_titles,
            commands::resolve_link,
            commands::save_note,
            commands::save_conflict,
            commands::daily_note,
            commands::today_info,
            commands::capture_save,
            commands::hide_capture,
            commands::quit,
            commands::action_board,
            commands::set_action_done,
            commands::complete_action,
            commands::set_action_field,
            commands::add_action,
            commands::person_page,
            commands::people_list,
            commands::tag_page,
            commands::calendar_data,
            commands::graph_data,
            commands::search_all,
            commands::new_note,
            commands::claude_config,
        ])
        .on_window_event(|window, event| {
            // Chiudere non termina l'app: la finestra si nasconde e riaprirla è immediato.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.emit("flush", ());
                let _ = window.hide();
            }
        })
        .setup(|app| {
            let config = Config::load();
            let store = Arc::new(NoteStore::open(config.notes_path())?);
            let init = boot_script(&config, &store)?;
            trace::mark("dati pronti");

            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                .title("QuickNotes")
                .inner_size(1440.0, 900.0)
                .min_inner_size(640.0, 420.0)
                .visible(false)
                .background_color(tauri::window::Color(0x17, 0x18, 0x1B, 0xFF))
                .initialization_script(init.clone())
                .build()?;
            trace::mark("finestra creata");

            // Se la pagina non risponde, la finestra deve comparire comunque.
            let fallback = window.clone();
            std::thread::spawn(move || {
                std::thread::sleep(Duration::from_secs(3));
                let _ = fallback.show();
            });

            desktop::setup_tray(app.handle())?;
            let hotkeys = config.hotkeys();
            app.manage(AppState { store: store.clone(), config: Mutex::new(config) });

            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let changed = store.refresh_changes().unwrap_or_default();
                trace::mark("indice allineato");
                let _ = handle.emit("note-changed", &changed);
                let _ = handle.emit("index-updated", changed.len());
                desktop::register_hotkeys(&handle, &hotkeys);
                // La nota rapida si prepara a riposo, così non pesa sull'avvio e Ctrl Alt N è immediato.
                std::thread::sleep(Duration::from_millis(1500));
                let main_thread = handle.clone();
                let _ = handle.run_on_main_thread(move || desktop::create_capture(&main_thread, &init));
                watcher::start(handle, store);
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("avvio dell'app");
}
