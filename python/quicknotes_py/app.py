"""Finestra pywebview (WebView2 su Windows) con l'interfaccia compilata in webui/.

- La pagina e le immagini delle note arrivano da un piccolo server su 127.0.0.1, con un prefisso casuale:
  così Python inietta i dati d'avvio (`window.__QN__`) prima che parta qualsiasi script.
- I comandi passano da `window.pywebview.api.invoke(nome, argomenti)`; gli eventi tornano con
  `window.__qnEmit(nome, dati)`.
- Tasti globali con RegisterHotKey, come Tauri: niente hook sulla tastiera.
- Una sola istanza: la seconda chiede alla prima di mostrarsi e termina.
"""

from __future__ import annotations

import ctypes
import getpass
import json
import logging
import mimetypes
import secrets
import sys
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing.connection import Client, Listener
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import dates
from .commands import Commands
from .config import Config, config_dir
from .notes import NoteStore

PACKAGE = Path(__file__).parent
WEB_DIR = PACKAGE / "webui"
ICON = PACKAGE / "icon.ico"
PIPE = rf"\\.\pipe\quicknotes-py-{getpass.getuser()}"
AUTHKEY = b"quicknotes-py"

# Sfondo della pagina (--chrome) e tema scuro, da frontend/src/theme/themes.js: la finestra nasce già
# del colore giusto, senza lampi.
THEMES = {"grafite": ("#17181B", True), "mezzanotte": ("#141A25", True), "salvia": ("#161C18", True),
          "lavanda": ("#EEE8F6", False), "carta": ("#EFECE5", False), "nebbia": ("#EDF0F3", False)}

# Il registro di Windows a volte associa .js a text/plain: i moduli ES verrebbero rifiutati.
for ext, mime in {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
                  ".woff2": "font/woff2", ".woff": "font/woff", ".json": "application/json"}.items():
    mimetypes.add_type(mime, ext)


def setup_logging() -> logging.Logger:
    log_dir = config_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(log_dir / "quicknotes-py.log", encoding="utf-8")]
    if sys.stdout is not None:  # con pythonw non c'è console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers, force=True)
    return logging.getLogger("quicknotes")


def message_box(text: str, title: str = "QuickNotes") -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    else:
        print(text, file=sys.stderr)


# ------------------------------------------------------------------ istanza singola
def send_to_running_instance(command: str) -> bool:
    try:
        with Client(PIPE, authkey=AUTHKEY) as conn:
            conn.send(command)
        return True
    except Exception:  # noqa: BLE001 - nessuna istanza in ascolto
        return False


# ------------------------------------------------------------------ tasti globali
MODIFIERS = {"ctrl": 0x2, "alt": 0x1, "shift": 0x4, "super": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312


def parse_hotkey(combo: str) -> tuple[int, int] | None:
    """"Ctrl+Alt+D" → (modificatori, codice del tasto) per RegisterHotKey."""
    mods, key = 0, None
    for part in combo.split("+"):
        p = part.strip().lower()
        if p in MODIFIERS:
            mods |= MODIFIERS[p]
        elif len(p) == 1 and p.isalnum():
            key = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 24:
            key = 0x6F + int(p[1:])
        else:
            return None
    return (mods, key) if key and mods else None


# ------------------------------------------------------------------ server della pagina
class PageServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, shell: Shell):
        self.shell = shell
        self.token = secrets.token_urlsafe(16)
        super().__init__(("127.0.0.1", 0), PageHandler)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/{self.token}/"


class PageHandler(BaseHTTPRequestHandler):
    server: PageServer

    def log_message(self, format, *args):  # noqa: A002 - firma di http.server
        pass

    def _rest(self) -> tuple[str | None, dict]:
        url = urlsplit(self.path)
        prefix = f"/{self.server.token}/"
        if not url.path.startswith(prefix):
            return None, {}
        return unquote(url.path[len(prefix):]), parse_qs(url.query)

    def _send(self, status: int, body: bytes, mime: str = "text/plain; charset=utf-8") -> None:
        if status >= 400:
            self.server.shell.log.warning("pagina: %d %s %s", status, self.command, self.path.split("?")[0])
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - nome deciso da http.server
        rest, _ = self._rest()
        if self.path == "/favicon.ico" and ICON.exists():  # chiesta da WebView2, senza prefisso
            return self._send(200, ICON.read_bytes(), "image/x-icon")
        if rest is None:
            return self._send(404, b"")
        if rest in ("", "index.html"):
            return self._send(200, self.server.shell.index_html().encode(), "text/html; charset=utf-8")
        if rest.startswith("qnfile/"):
            found = self.server.shell.store.resolve_image(rest[len("qnfile/"):])
            if not found:
                return self._send(404, b"")
            return self._send(200, found[0].read_bytes(), found[1])
        try:
            file = (WEB_DIR / rest).resolve()
            file.relative_to(WEB_DIR.resolve())
            data = file.read_bytes()
        except (OSError, ValueError):
            return self._send(404, b"")
        self._send(200, data, mimetypes.guess_type(file.name)[0] or "application/octet-stream")

    def do_POST(self):  # noqa: N802
        rest, query = self._rest()
        if rest != "qnfile/" or "note" not in query:
            return self._send(404, b"")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length)
            rel = self.server.shell.store.save_image(query["note"][0], data)
        except Exception as e:  # noqa: BLE001 - l'errore va mostrato nella pagina
            return self._send(400, str(e).encode())
        self._send(200, rel.encode())


# ------------------------------------------------------------------ ponte con la pagina
class Bridge:
    """L'unico oggetto visibile dal JavaScript: pywebview espone solo i metodi senza `_`."""

    def __init__(self, shell: Shell):
        self._shell = shell

    def invoke(self, command: str, args: dict | None = None) -> dict:
        return self._shell.commands.dispatch(command, args)


# ------------------------------------------------------------------ app
class Shell:
    def __init__(self, debug: bool = False, hidden: bool = False):
        self.log = setup_logging()
        self.debug = debug
        self.start_hidden = hidden
        self.config = Config.load()
        self.config_lock = threading.Lock()
        self.store = NoteStore(self.config.notes_path())
        self.commands = Commands(self)
        self.window = None
        self.hwnd = None
        self.quitting = False
        self.started = time.perf_counter()
        self.hotkey_errors: list[str] = []

    # ---- dati per la pagina
    def today_info(self) -> dict:
        today = date.today()
        note = self.store.daily(today, True)
        return {"id": note.id, "title": dates.daily_title(today), "short": today.strftime("%d/%m")}

    def index_html(self) -> str:
        boot = {"theme": self.config.theme(), "ui": self.config.ui(), "today": self.today_info(),
                "backend": "py", "fileOrigin": self.server.base + "qnfile/"}
        script = "<script>window.__QN__ = " + json.dumps(boot, ensure_ascii=False).replace("</", "<\\/") + ";</script>"
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        return html.replace("<head>", "<head>" + script, 1)

    def emit(self, event: str, payload=None) -> None:
        if self.window is None or self.quitting:
            return
        js = f"window.__qnEmit && window.__qnEmit({json.dumps(event)}, {json.dumps(payload, ensure_ascii=False)})"
        try:
            self.window.run_js(js)
        except Exception:  # noqa: BLE001 - finestra in chiusura
            self.log.debug("evento %s non consegnato", event, exc_info=True)

    def window_theme(self) -> tuple[str, bool]:
        """(colore di sfondo, scuro) del tema scelto, come resolveTheme nella pagina."""
        ui = self.config.ui()
        theme = ui.get("theme") or self.config.theme()
        if theme == "custom":
            custom = ui.get("custom") if isinstance(ui.get("custom"), dict) else {}
            bg, dark = THEMES["carta" if custom.get("base") == "chiaro" else "grafite"]
            return custom.get("chrome") or bg, dark
        theme = {"light": "carta", "dark": "grafite"}.get(theme, theme)
        if theme not in THEMES:
            theme = "grafite" if system_is_dark() else "carta"
        return THEMES[theme]

    # ---- finestra
    def page_ready(self) -> None:
        """La pagina è disegnata. La finestra è visibile da subito: in pywebview WebView2 non carica
        nulla finché la finestra resta nascosta, quindi non si può aspettare la pagina per mostrarla."""
        self.log.info("pagina disegnata in %.2f s", time.perf_counter() - self.started)

    def show(self) -> None:
        if self.window is None:
            return
        self.window.show()
        if self.hwnd and sys.platform == "win32":
            user32 = ctypes.windll.user32
            if user32.IsIconic(self.hwnd):
                user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE: solo se ridotta a icona, non se ingrandita
            user32.SetForegroundWindow(self.hwnd)
        self.emit("window-shown")

    def set_title(self, title: str) -> None:
        if self.window is not None:
            self.window.set_title(title)

    def open_today(self) -> None:
        t = self.today_info()
        self.emit("open-page", {"page": f"note:{t['id']}", "title": f"Oggi · {dates.short_day(date.today())}"})
        self.show()

    def request_close(self) -> None:
        """La pagina salva tutto, poi chiama `quit`. Se non risponde entro 3 secondi si chiude comunque."""
        self.emit("flush-and-close")
        timer = threading.Timer(3, self.quit)
        timer.daemon = True
        timer.start()

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        if self.window is not None:
            self.window.destroy()

    def _on_closing(self):
        """La X della finestra. Gira sul thread della finestra: qui `run_js` aspetterebbe una risposta che
        solo questo thread può dare, e l'app si bloccherebbe. Si annulla la chiusura e si chiede alla pagina
        di salvare da un altro thread; la pagina poi chiama `quit`."""
        if self.quitting:
            return True
        threading.Thread(target=self.request_close, daemon=True).start()
        return False

    def _on_shown(self):
        try:
            self.hwnd = self.window.native.Handle.ToInt64()
        except Exception:  # noqa: BLE001
            return
        if sys.platform == "win32" and self.window_theme()[1]:
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(self.hwnd), 20, ctypes.byref(value), 4)

    def _on_initialized(self, renderer: str):
        self.log.info("motore della pagina: %s", renderer)
        if renderer != "edgechromium":
            message_box("QuickNotes richiede Microsoft Edge WebView2, che su questo PC non risulta installato.\n"
                        f"Motore trovato: {renderer}. Esegui la verifica per i dettagli.")
            return False
        return True

    # ---- servizi in sottofondo
    def _listen_commands(self) -> None:
        try:
            listener = Listener(PIPE, authkey=AUTHKEY)
        except OSError:
            self.log.warning("istanza singola non disponibile", exc_info=True)
            return
        while True:
            try:
                with listener.accept() as conn:
                    command = conn.recv()
            except Exception:  # noqa: BLE001 - connessione non valida
                continue
            self.open_today() if command == "daily" else self.show()

    def _hotkeys(self) -> None:
        if sys.platform != "win32":
            return
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        actions = {}
        for i, (action, combo) in enumerate(self.config.hotkeys().items(), start=1):
            parsed = parse_hotkey(combo)
            if parsed and user32.RegisterHotKey(None, i, parsed[0] | MOD_NOREPEAT, parsed[1]):
                actions[i] = action
                self.log.info("tasto globale %s → %s", combo, action)
            else:
                self.hotkey_errors.append(combo)
                self.log.warning("tasto globale %s non registrato (già usato da un'altra app?)", combo)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in actions:
                threading.Thread(target=self._on_hotkey, args=(actions[msg.wParam],), daemon=True).start()

    def _on_hotkey(self, action: str) -> None:
        if action == "daily":
            self.open_today()
            return
        self.show()
        name = "La nota rapida" if action == "quick_note" else "La registrazione"
        self.emit("toast", f"{name} non fa parte della prova Python")

    def _watch(self) -> None:
        """Le modifiche fatte fuori dall'app (Obsidian, Claude, sincronizzazione): controllo ogni 2 secondi."""
        first = True
        while not self.quitting:
            try:
                changed = self.store.refresh()
            except Exception:  # noqa: BLE001
                self.log.exception("allineamento dell'indice")
                changed = []
            if first:
                self.log.info("indice pronto: %d note", len(self.store.entries))
            if changed or first:
                self.emit("note-changed", changed if not first else [])
                self.emit("index-updated", len(changed))
            first = False
            time.sleep(2)

    def _started(self) -> None:
        threading.Thread(target=self._watch, daemon=True).start()
        threading.Thread(target=self._hotkeys, daemon=True).start()
        threading.Thread(target=self._listen_commands, daemon=True).start()

    # ---- avvio
    def run(self) -> None:
        import webview

        if not (WEB_DIR / "index.html").exists():
            message_box(f"Manca l'interfaccia compilata in {WEB_DIR}.\nCompila con: cd frontend && npm run build:py")
            return
        self.server = PageServer(self)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.log.info("avvio: note in %s, pagina su porta %d", self.store.root, self.server.server_address[1])

        self.window = webview.create_window(
            "QuickNotes", self.server.base, js_api=Bridge(self),
            width=1440, height=900, min_size=(640, 420), hidden=self.start_hidden,
            background_color=self.window_theme()[0], text_select=True,
        )
        self.window.events.initialized += self._on_initialized
        self.window.events.closing += self._on_closing
        self.window.events.shown += self._on_shown
        storage = config_dir() / "webview-py"
        webview.start(self._started, gui="edgechromium", debug=self.debug, private_mode=False,
                      storage_path=str(storage), icon=str(ICON) if ICON.exists() else None)
        self.server.shutdown()
        self.log.info("chiusura")


def system_is_dark() -> bool:
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def main(debug: bool = False, hidden: bool = False) -> None:
    if send_to_running_instance("show"):
        return
    shell = Shell(debug=debug, hidden=hidden)
    try:
        shell.run()
    except Exception as e:  # noqa: BLE001 - con pythonw nessuno vedrebbe l'errore
        shell.log.exception("avvio della finestra")
        message_box(f"QuickNotes non riesce ad aprire la finestra:\n{type(e).__name__}: {e}\n\n"
                    "Apri Verifica.cmd per capire cosa manca su questo PC.")
