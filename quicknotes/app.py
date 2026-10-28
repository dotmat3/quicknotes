"""App desktop: finestra pywebview (WebView2 su Windows) col frontend compilato in webui/, icona
nell'area di notifica, tasti globali e un'unica istanza (i comandi successivi arrivano a quella aperta).

Il frontend (cartella frontend/, Svelte + CodeMirror) chiama i metodi pubblici di `Api` come
`window.pywebview.api.<metodo>(...)`; Python gli manda eventi con `window.qnEvent(nome, dati)`.
Node serve solo per compilare il frontend, non per usare l'app.

Scorciatoie nell'editor:
    Ctrl+T          trasforma la riga in azione "- [ ]"   (di nuovo: la spunta)
    Ctrl+D          marca la riga come !decisione
    Ctrl+Shift+H    inserisce l'ora corrente
    Invio           continua l'elenco puntato / di azioni; Invio su voce vuota la chiude
Nella finestra:
    Ctrl+N nuovo meeting, Ctrl+Shift+N nuova nota, Ctrl+F cerca, Ctrl+S salva
Scorciatoie globali (configurabili in ~/.quicknotes/config.json):
    Ctrl+Alt+N nuovo meeting, Ctrl+Alt+D nota del giorno, Ctrl+Alt+R avvia/ferma registrazione
"""

from __future__ import annotations

import ctypes
import getpass
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
from multiprocessing.connection import Client, Listener
from pathlib import Path
from typing import Callable

from . import service
from .config import CONFIG_DIR, Config, load_config, save_config
from .icons import app_icon, write_ico
from .recording import Recordings
from .store import NoteNotFound, NoteStore

log = logging.getLogger(__name__)

WEB_DIR = Path(__file__).with_name("webui")
DEV_URL = "http://localhost:5173"
COMMANDS = ("show", "new", "daily", "record")
THEMES = ("auto", "light", "dark")
BACKGROUND = {False: "#FFFFFF", True: "#1F1F1E"}  # colore della finestra prima che la pagina sia pronta
GEOMETRY_FILE = CONFIG_DIR / "window.json"
DEFAULT_SIZE = (1320, 820)
MIN_SIZE = (960, 580)

_user = getpass.getuser()
ADDRESS = (rf"\\.\pipe\quicknotes-{_user}" if sys.platform == "win32"
           else str(Path(tempfile.gettempdir()) / f"quicknotes-{_user}.sock"))
AUTHKEY = b"quicknotes"


# ------------------------------------------------------------------ Windows
def system_is_dark() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def is_dark(cfg: Config) -> bool:
    return cfg.theme == "dark" or (cfg.theme not in ("light", "dark") and system_is_dark())


def on_gui_thread(window, func: Callable[[], None]) -> None:
    """Esegue `func` sul thread della finestra (WinForms non accetta modifiche da altri thread)."""
    from System import Action  # pythonnet, caricato da pywebview
    window.native.Invoke(Action(func))


def set_dark_titlebar(window, dark: bool) -> None:
    """Barra del titolo scura o chiara come la pagina (Windows 10 20H1+ e 11)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.c_void_p(window.native.Handle.ToInt64())
        value = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:  # noqa: BLE001 - solo estetica: senza, resta la barra di sistema
        pass


def set_window_icon(window, ico: Path) -> None:
    if sys.platform != "win32":
        return
    try:
        import clr
        clr.AddReference("System.Drawing")
        from System.Drawing import Icon

        def apply():
            window.native.Icon = Icon(str(ico))
        on_gui_thread(window, apply)
    except Exception:  # noqa: BLE001 - resta l'icona di Python
        log.debug("icona della finestra non impostata", exc_info=True)


# ------------------------------------------------------------------ istanza singola
def send_to_running_instance(cmd: str) -> bool:
    try:
        with Client(ADDRESS, authkey=AUTHKEY) as conn:
            conn.send(cmd)
        return True
    except Exception:  # noqa: BLE001 - nessuna istanza in ascolto (o socket rimasto da un crash)
        return False


def listen_for_commands(handle: Callable[[str], None]) -> Listener | None:
    if sys.platform != "win32" and os.path.exists(ADDRESS):
        os.unlink(ADDRESS)  # socket rimasto da un'istanza chiusa male
    try:
        listener = Listener(ADDRESS, authkey=AUTHKEY)
    except OSError:
        return None

    def loop():
        while True:
            try:
                with listener.accept() as conn:
                    cmd = conn.recv()
            except OSError:
                return  # listener chiuso
            except Exception:  # noqa: BLE001 - connessione non valida: si ignora
                continue
            handle(cmd if cmd in COMMANDS else "show")

    threading.Thread(target=loop, daemon=True).start()
    return listener


def start_global_hotkeys(cfg: Config, handle: Callable[[str], None]):
    """Tasti globali via pynput (Windows, macOS con permesso Accessibilita', Linux X11)."""
    if not cfg.hotkeys:
        return None
    try:
        from pynput import keyboard
    except Exception:  # noqa: BLE001 - pynput assente o display non supportato (es. Wayland)
        return None
    names = {"new_meeting": "new", "daily": "daily", "toggle_recording": "record"}
    mapping = {combo: (lambda c=names[key]: handle(c)) for key, combo in cfg.hotkeys.items() if key in names and combo}
    try:
        listener = keyboard.GlobalHotKeys(mapping)
        listener.daemon = True
        listener.start()
        return listener
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ posizione della finestra
def load_geometry() -> dict:
    try:
        geo = json.loads(GEOMETRY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(geo, dict):
        return {}
    out = {"width": max(int(geo.get("width") or DEFAULT_SIZE[0]), MIN_SIZE[0]),
           "height": max(int(geo.get("height") or DEFAULT_SIZE[1]), MIN_SIZE[1]),
           "maximized": bool(geo.get("maximized"))}
    x, y = geo.get("x"), geo.get("y")
    if isinstance(x, int) and isinstance(y, int) and _on_screen(x, y):
        out.update(x=x, y=y)
    return out


def _on_screen(x: int, y: int) -> bool:
    """Il bordo in alto a sinistra e' su uno schermo collegato (un monitor puo' essere stato scollegato)."""
    try:
        import webview
        return any(s.x - 50 <= x <= s.x + s.width - 100 and s.y - 10 <= y <= s.y + s.height - 100
                   for s in webview.screens)
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------ API per la pagina
class Api:
    """Metodi chiamabili dal JavaScript. Ogni chiamata gira in un thread di pywebview: lo store ha il suo lock."""

    def __init__(self, shell: Shell):
        self._shell = shell

    @property
    def _store(self) -> NoteStore:
        return self._shell.store

    def bootstrap(self) -> dict:
        shell = self._shell
        command, shell.initial_command = shell.initial_command, "show"
        return {"theme": shell.cfg.theme, "animations": shell.cfg.animations, "hasTray": shell.tray is not None,
                "nav": service.nav_items(self._store), "note": service.note_payload(self._store.daily()),
                "command": command, "notice": shell.notice, "recording": shell.recordings.status()}

    # ---- elenchi e note
    def nav(self) -> list[dict]:
        return service.nav_items(self._store)

    def notes(self, view: str, search: str = "") -> list[dict]:
        return service.note_items(self._store, view, search)

    def actions(self, search: str = "") -> list[dict]:
        return service.action_items(self._store, search)

    def suggestions(self) -> dict:
        """Persone e progetti gia' usati, per il completamento di @ e # nell'editor."""
        return {"people": [p["name"] for p in self._store.people()],
                "projects": [p["name"] for p in self._store.projects()]}

    def open(self, note_id: str) -> dict | None:
        try:
            return service.note_payload(self._store.read(note_id))
        except NoteNotFound:
            return None

    def daily(self) -> dict:
        return service.note_payload(self._store.daily())

    def draft(self, note_type: str) -> dict:
        return service.draft_payload(note_type)

    def save(self, data: dict, force: bool = False) -> dict:
        return service.save_note(self._store, data, force)

    def poll(self, note_id: str, mtime: float) -> dict | None:
        return service.changed_on_disk(self._store, note_id, mtime)

    def append(self, note_id: str, text: str, heading: str | None = None) -> bool:
        """Aggiunge testo a una nota che non e' aperta nell'editor."""
        try:
            self._store.append(note_id, text, heading)
            return True
        except NoteNotFound:
            return False

    def complete_action(self, note_id: str, raw: str) -> dict:
        try:
            return service.complete_action(self._store, note_id, raw)
        except NoteNotFound as exc:
            return {"error": str(exc)}

    def delete_info(self, note_id: str) -> dict | None:
        try:
            return service.delete_info(self._store, note_id)
        except NoteNotFound:
            return None

    def delete_note(self, note_id: str, permanent: bool = False) -> dict:
        return service.delete_note(self._store, note_id, permanent)

    # ---- registrazione
    def start_recording(self, note_id: str) -> dict:
        try:
            return self._shell.recordings.start(note_id)
        except NoteNotFound as exc:
            return {"error": str(exc)}

    def stop_recording(self) -> dict | None:
        return self._shell.recordings.stop()

    def recording_status(self) -> dict:
        return self._shell.recordings.status()

    # ---- finestra e sistema
    def reveal_note(self, note_id: str) -> None:
        try:
            path = self._store.read(note_id).path
        except NoteNotFound:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            open_path(path.parent)

    def open_folder(self) -> None:
        open_path(self._store.root)

    def set_theme(self, mode: str) -> None:
        if mode in THEMES:
            self._shell.cfg.theme = mode
            save_config(self._shell.cfg)

    def titlebar(self, dark: bool) -> None:
        if self._shell.window is not None:
            set_dark_titlebar(self._shell.window, bool(dark))

    def quit(self) -> None:
        self._shell.quit()


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - cartella delle note dell'utente
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


# ------------------------------------------------------------------ guscio
class Shell:
    """Finestra, area di notifica, comandi esterni e chiusura (con salvataggio di cio' che e' in sospeso)."""

    def __init__(self, cfg: Config, store: NoteStore, command: str = "show"):
        self.cfg, self.store = cfg, store
        self.initial_command = command
        self.notice = ""
        self.window = None
        self.tray = None
        self.quitting = False
        self.maximized = self.minimized = False
        self._tray_hint_shown = False
        self.recordings = Recordings(cfg, store, self.emit, self.set_recording_look)
        self.api = Api(self)
        icons = CONFIG_DIR / "icons"
        self.ico = {on: write_ico(icons / f"quicknotes{'-rec' if on else ''}.ico", on) for on in (False, True)}

    # ---- verso la pagina
    def emit(self, event: str, data=None) -> None:
        if self.window is None:
            return
        try:
            self.window.run_js(f"window.qnEvent && window.qnEvent({json.dumps(event)}, {json.dumps(data)})")
        except Exception:  # noqa: BLE001 - finestra in chiusura
            log.debug("evento %s non consegnato", event, exc_info=True)

    def handle_command(self, cmd: str) -> None:
        """Comandi da tasti globali, area di notifica o da un secondo avvio dell'app."""
        if cmd == "record":
            self.emit("command", "record")
            return
        self.show()
        if cmd in ("new", "daily"):
            self.emit("command", cmd)

    def show(self) -> None:
        w = self.window
        if w is None:
            return
        w.show()
        if self.minimized:
            w.restore()
        try:  # in primo piano: Windows lo concede solo con un piccolo aiuto
            w.on_top = True
            w.on_top = False
            if sys.platform == "win32":
                on_gui_thread(w, lambda: w.native.Activate())
        except Exception:  # noqa: BLE001
            pass

    # ---- area di notifica
    def build_tray(self):
        try:
            import pystray
        except Exception:  # noqa: BLE001 - nessuna area di notifica: chiudere la finestra chiude l'app
            return None
        item = pystray.MenuItem
        menu = pystray.Menu(
            item("Mostra QuickNotes", lambda: self.handle_command("show"), default=True),
            item("Nuovo meeting", lambda: self.handle_command("new")),
            item("Nota del giorno", lambda: self.handle_command("daily")),
            item(lambda _item: "Ferma registrazione" if self.recordings.recording else "Avvia registrazione",
                 lambda: self.handle_command("record")),
            pystray.Menu.SEPARATOR,
            item("Esci", lambda: self.quit()),
        )
        tray = pystray.Icon("QuickNotes", app_icon(False, 64), "QuickNotes", menu)
        try:
            tray.run_detached()
        except Exception:  # noqa: BLE001
            return None
        return tray

    def set_recording_look(self, on: bool) -> None:
        if self.tray is not None:
            self.tray.icon = app_icon(on, 64)
            self.tray.title = "QuickNotes · registrazione in corso" if on else "QuickNotes"
            self.tray.update_menu()
        if self.window is not None:
            set_window_icon(self.window, self.ico[on])

    # ---- chiusura
    def on_shown(self) -> None:
        set_dark_titlebar(self.window, is_dark(self.cfg))
        set_window_icon(self.window, self.ico[self.recordings.recording])

    def on_closing(self) -> bool:
        if self.quitting:
            return True
        if self.tray is not None:
            threading.Thread(target=self.hide_to_tray, daemon=True).start()
        else:
            self.quit()
        return False

    def hide_to_tray(self) -> None:
        self.save_geometry()
        self.emit("command", "flush")
        self.window.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            try:
                self.tray.notify("L'app resta attiva qui. Ctrl+Alt+N per un nuovo meeting.", "QuickNotes")
            except Exception:  # noqa: BLE001
                pass

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        threading.Thread(target=self._quit, daemon=True).start()

    def _quit(self) -> None:
        """Salva il testo non ancora salvato e ferma la registrazione, poi chiude davvero."""
        try:
            self.save_geometry()
            pending = self.window.evaluate_js("window.qnPending ? window.qnPending() : null")
            if pending:
                # chi stava scrivendo vince: meglio sovrascrivere che perdere le ultime parole
                service.save_note(self.store, pending, force=True)
            stopped = self.recordings.stop(transcribe=False)
            if stopped:
                self.store.append(stopped["noteId"], stopped["text"])
        except Exception:  # noqa: BLE001 - la finestra si chiude comunque
            log.exception("Salvataggio alla chiusura non riuscito")
        finally:
            self.window.destroy()

    def save_geometry(self) -> None:
        w = self.window
        try:
            geo = {"maximized": self.maximized}
            if not self.maximized:
                geo.update(width=w.width, height=w.height, x=w.x, y=w.y)
            else:
                old = json.loads(GEOMETRY_FILE.read_text(encoding="utf-8")) if GEOMETRY_FILE.exists() else {}
                geo = {**old, **geo}
            GEOMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            GEOMETRY_FILE.write_text(json.dumps(geo), encoding="utf-8")
        except Exception:  # noqa: BLE001 - la posizione e' solo una comodita'
            log.debug("posizione della finestra non salvata", exc_info=True)

    def on_state(self, state: str) -> None:
        self.minimized = state == "minimized"
        if state != "minimized":
            self.maximized = state == "maximized"


def run(command: str = "show", dev: bool = False) -> int:
    if send_to_running_instance(command):
        return 0  # l'app era gia' aperta: le abbiamo passato il comando
    if not dev and not (WEB_DIR / "index.html").exists():
        print("Interfaccia non compilata: esegui `npm install` e `npm run build` in frontend/", file=sys.stderr)
        return 1
    import webview

    if sys.platform == "win32":  # icona e raggruppamento propri nella barra delle applicazioni
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QuickNotes.App")
        except Exception:  # noqa: BLE001
            pass
    cfg = load_config()
    store = NoteStore(cfg.notes_path)
    shell = Shell(cfg, store, command)
    listener = listen_for_commands(shell.handle_command)
    hotkeys = start_global_hotkeys(cfg, shell.handle_command)
    if hotkeys is None and cfg.hotkeys:
        shell.notice = "Tasti globali non attivi: usa il menu nell'area di notifica"
    shell.tray = shell.build_tray()

    geo = load_geometry()
    window = webview.create_window(
        "QuickNotes", DEV_URL if dev else str(WEB_DIR / "index.html"), js_api=shell.api,
        width=geo.get("width", DEFAULT_SIZE[0]), height=geo.get("height", DEFAULT_SIZE[1]),
        x=geo.get("x"), y=geo.get("y"), maximized=geo.get("maximized", False),
        min_size=MIN_SIZE, background_color=BACKGROUND[is_dark(cfg)])
    shell.window = window
    shell.maximized = geo.get("maximized", False)
    window.events.shown += shell.on_shown
    window.events.closing += shell.on_closing
    window.events.maximized += lambda: shell.on_state("maximized")
    window.events.minimized += lambda: shell.on_state("minimized")
    window.events.restored += lambda: shell.on_state("restored")
    try:
        webview.start(gui="edgechromium" if sys.platform == "win32" else None, debug=dev, http_server=True,
                      private_mode=False, storage_path=str(CONFIG_DIR / "webview"))
    finally:
        if shell.tray is not None:
            shell.tray.stop()
        if hotkeys is not None:
            hotkeys.stop()
        if listener is not None:
            listener.close()
        store.close()
    return 0
