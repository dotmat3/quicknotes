"""App desktop: finestra pywebview (WebView2) con l'interfaccia compilata in webui/.

- La pagina e le immagini delle note arrivano da un piccolo server su 127.0.0.1, con un prefisso casuale:
  così Python inietta i dati d'avvio (`window.__QN__`) prima che parta qualsiasi script.
- I comandi passano da `window.pywebview.api.invoke(nome, argomenti)`; gli eventi tornano con
  `window.__qnEmit(nome, dati)`.
- Chiudere la finestra la nasconde nell'area di notifica; si esce dal menu dell'icona.
- Nota rapida in una seconda finestra, sempre in primo piano. Tasti globali con RegisterHotKey.
- Una sola istanza: la seconda chiede alla prima di mostrarsi e termina.
"""

from __future__ import annotations

import ctypes
import getpass
import json
import logging
import mimetypes
import os
import secrets
import sys
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing.connection import Client, Listener
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import dates, system
from .commands import Commands
from .config import Config, config_dir
from .store import NoteStore

PACKAGE = Path(__file__).parent
WEB_DIR = PACKAGE / "webui"
ICON = PACKAGE / "icon.ico"
PIPE = rf"\\.\pipe\quicknotes-app-{getpass.getuser()}"
AUTHKEY = b"quicknotes-app"
CAPTURE_SIZE = (520, 460)
TRAY_TITLE = "QuickNotes · area di notifica"

# Sfondo della pagina (--chrome) e tema scuro, da frontend/src/theme/themes.js: la finestra nasce già
# del colore giusto, senza lampi.
THEMES = {"grafite": ("#17181B", True), "mezzanotte": ("#141A25", True), "salvia": ("#161C18", True),
          "lavanda": ("#EEE8F6", False), "carta": ("#EFECE5", False), "nebbia": ("#EDF0F3", False)}

# La pagina esegue solo i propri script e i dati d'avvio (con il nonce di quella risposta), non carica nulla da
# fuori e non incorpora altre pagine: un HTML malevolo dentro una nota non può fare danni neanche se sfuggisse
# alla sanificazione. Il ponte di pywebview arriva da WebView2, non dalla pagina, quindi non è toccato.
CSP = ("default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; font-src 'self'; "
       "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; "
       "base-uri 'none'; form-action 'none'; frame-src 'none'")

# Il registro di Windows a volte associa .js a text/plain: i moduli ES verrebbero rifiutati.
for _ext, _mime in {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
                    ".svg": "image/svg+xml", ".woff2": "font/woff2", ".woff": "font/woff",
                    ".json": "application/json"}.items():
    mimetypes.add_type(_mime, _ext)


def setup_logging() -> logging.Logger:
    log_dir = config_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(log_dir / "quicknotes.log", encoding="utf-8")]
    if sys.stdout is not None:  # con pythonw non c'è console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers, force=True)
    return logging.getLogger("quicknotes")


def _process_ms() -> float:
    """Millisecondi dalla creazione del processo: comprende anche l'avvio di Python."""
    if sys.platform == "win32":
        from ctypes import wintypes
        created, ignored, now = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        if kernel32.GetProcessTimes(ctypes.c_void_p(kernel32.GetCurrentProcess()), ctypes.byref(created),
                                    ctypes.byref(ignored), ctypes.byref(ignored), ctypes.byref(ignored)):
            kernel32.GetSystemTimeAsFileTime(ctypes.byref(now))

            def ticks(ft):
                return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
            return (ticks(now) - ticks(created)) / 10_000
    return time.perf_counter() * 1000


def trace(phase: str) -> None:
    """Tappe dell'avvio per scripts/misura-avvio.mjs, solo se QUICKNOTES_TRACE indica un file."""
    path = os.environ.get("QUICKNOTES_TRACE")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{_process_ms():8.1f} ms  {phase}\n")


def message_box(text: str, title: str = "QuickNotes") -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    else:
        print(text, file=sys.stderr)


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
    # Connessioni riusate: con HTTP/1.0 ogni file della pagina aprirebbe una porta nuova, e dopo molti avvii
    # Windows finisce le porte temporanee (ERR_NO_BUFFER_SPACE).
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - firma di http.server
        pass

    def _rest(self) -> tuple[str | None, dict]:
        url = urlsplit(self.path)
        prefix = f"/{self.server.token}/"
        if not url.path.startswith(prefix):
            return None, {}
        return unquote(url.path[len(prefix):]), parse_qs(url.query)

    def _send(self, status: int, body: bytes, mime: str = "text/plain; charset=utf-8", csp: str | None = None) -> None:
        if status >= 400:
            self.server.shell.log.warning("pagina: %d %s %s", status, self.command, self.path.split("?")[0])
        self.send_response(status)
        if csp:
            self.send_header("Content-Security-Policy", csp)
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
            nonce = secrets.token_urlsafe(16)
            return self._send(200, self.server.shell.index_html(nonce).encode(), "text/html; charset=utf-8",
                              CSP.format(nonce=nonce))
        if rest.startswith("qnfile/"):
            # Solo immagini vere dentro la cartella delle note.
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
        """Un'immagine incollata: i byte così come sono, la nota nell'indirizzo."""
        rest, query = self._rest()
        if rest != "qnfile/" or "note" not in query:
            return self._send(404, b"")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            rel = self.server.shell.store.save_image(query["note"][0], self.rfile.read(length))
        except Exception as e:  # noqa: BLE001 - l'errore va mostrato nella pagina
            return self._send(400, str(e).encode())
        self._send(200, rel.encode())


class Bridge:
    """L'unico oggetto visibile dal JavaScript: pywebview espone solo i metodi senza `_`."""

    def __init__(self, shell: Shell):
        self._shell = shell

    def invoke(self, command: str, args: dict | None = None) -> dict:
        return self._shell.commands.dispatch(command, args)


def _hwnd(window) -> int | None:
    try:
        return int(window.native.Handle.ToInt64())
    except Exception:  # noqa: BLE001 - finestra non ancora creata o già chiusa
        return None


def _bring_to_front(window) -> None:
    hwnd = _hwnd(window)
    if hwnd and sys.platform == "win32":
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE: solo se ridotta a icona, non se ingrandita
        user32.SetForegroundWindow(hwnd)


class Shell:
    def __init__(self, debug: bool = False, hidden: bool = False):
        self.log = setup_logging()
        self.debug = debug
        self.start_hidden = hidden
        self.config = Config.load()
        self.config_lock = threading.Lock()
        self.store = NoteStore(self.config.notes_path())
        self.commands = Commands(self)
        self.bridge = Bridge(self)
        self.window = None
        self.capture = None
        self.capture_lock = threading.Lock()
        self.tray = None
        self.quitting = False
        self.started = time.perf_counter()
        self.hotkey_errors: list[str] = []

    # ---- dati per la pagina
    def today_info(self) -> dict:
        today = date.today()
        note = self.store.daily(today, True)
        return {"id": note.id, "title": dates.daily_title(today), "short": today.strftime("%d/%m")}

    def index_html(self, nonce: str) -> str:
        """La pagina con i dati d'avvio già dentro: la prima schermata non aspetta nessuna chiamata."""
        boot = {"theme": self.config.theme(), "ui": self.config.ui(), "today": self.today_info(),
                "backend": "py", "fileOrigin": self.server.base + "qnfile/"}
        data = json.dumps(boot, ensure_ascii=False).replace("</", "<\\/")
        script = f'<script nonce="{nonce}">window.__QN__ = {data};</script>'
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        return html.replace("<head>", "<head>" + script, 1)

    def emit(self, event: str, payload=None, window=None) -> None:
        """Un evento alla pagina principale, o alla finestra indicata. Mai dal thread della finestra:
        `run_js` aspetta una risposta che solo quel thread può dare."""
        target = window or self.window
        if target is None or self.quitting:
            return
        js = f"window.__qnEmit && window.__qnEmit({json.dumps(event)}, {json.dumps(payload, ensure_ascii=False)})"
        try:
            target.run_js(js)
        except Exception:  # noqa: BLE001 - finestra in chiusura o non ancora caricata
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
            theme = "grafite" if system.system_is_dark() else "carta"
        return THEMES[theme]

    # ---- finestra principale
    def page_ready(self) -> None:
        """La pagina principale è disegnata."""
        self.log.info("pagina disegnata in %.2f s", time.perf_counter() - self.started)
        trace("prima pittura")
        if self.hotkey_errors:
            self.emit("toast", f"Tasti globali non disponibili: {', '.join(self.hotkey_errors)}")

    def show_main(self) -> None:
        if self.window is None:
            return
        self.window.show()
        _bring_to_front(self.window)
        self.emit("window-shown")

    def hide_main(self) -> None:
        """Il pulsante Chiudi e la X: si salva, poi la finestra va nell'area di notifica."""
        self.emit("flush")
        if self.window is not None:
            self.window.hide()

    def set_title(self, title: str) -> None:
        if self.window is not None:
            self.window.set_title(title)

    def open_today(self) -> None:
        t = self.today_info()
        self.emit("open-page", {"page": f"note:{t['id']}", "title": f"Oggi · {dates.short_day(date.today())}"})
        self.show_main()

    def request_quit(self) -> None:
        """Esci: la pagina salva tutto, poi chiama `quit`. Se non risponde entro 3 secondi si chiude comunque."""
        self.emit("flush-and-close")
        timer = threading.Timer(3, self.quit)
        timer.daemon = True
        timer.start()

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        self._remove_tray()
        for w in (self.capture, self.window):
            if w is not None:
                try:
                    w.destroy()
                except Exception:  # noqa: BLE001 - già chiusa
                    pass

    def _on_closing(self):
        """La X o Alt F4. Gira sul thread della finestra, quindi niente `run_js` qui: si annulla la chiusura
        e il resto parte da un altro thread."""
        if self.quitting:
            return True
        threading.Thread(target=self.hide_main if self.tray else self.request_quit, daemon=True).start()
        return False

    def _on_shown(self):
        hwnd = _hwnd(self.window)
        if hwnd and sys.platform == "win32" and self.window_theme()[1]:
            value = ctypes.c_int(1)  # barra del titolo scura, come la pagina
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 20, ctypes.byref(value), 4)

    def _on_initialized(self, renderer: str):
        self.log.info("motore della pagina: %s", renderer)
        if renderer != "edgechromium":
            message_box("QuickNotes richiede Microsoft Edge WebView2, che su questo PC non risulta installato.\n"
                        f"Motore trovato: {renderer}. Apri Verifica.cmd per i dettagli.")
            return False
        return True

    # ---- nota rapida
    def _create_capture(self):
        import webview
        bg, _ = self.window_theme()
        w = webview.create_window(
            "Nota rapida", self.server.base + "index.html#capture", js_api=self.bridge,
            width=CAPTURE_SIZE[0], height=CAPTURE_SIZE[1], resizable=False, frameless=True, easy_drag=False,
            on_top=True, hidden=True, background_color=bg, text_select=True,
        )

        def before_show():
            # Non deve comparire nella barra delle applicazioni. Qui siamo già sul thread della finestra.
            try:
                w.native.ShowInTaskbar = False
            except Exception:  # noqa: BLE001
                self.log.debug("ShowInTaskbar non impostato", exc_info=True)

        def closing():
            if self.quitting:
                return True
            threading.Thread(target=self.hide_capture, daemon=True).start()
            return False

        w.events.before_show += before_show
        w.events.closing += closing
        w.events.loaded += lambda: self.log.info("nota rapida pronta")
        return w

    def show_capture(self) -> None:
        with self.capture_lock:
            if self.capture is None:
                self.capture = self._create_capture()
        w = self.capture
        try:
            import webview
            screen = webview.screens[0]
            w.move(screen.x + (screen.width - CAPTURE_SIZE[0]) // 2, screen.y + (screen.height - CAPTURE_SIZE[1]) // 3)
        except Exception:  # noqa: BLE001 - resta dov'era
            pass
        w.show()
        _bring_to_front(w)
        self.emit("capture-open", window=w)

    def hide_capture(self) -> None:
        if self.capture is not None:
            self.capture.hide()

    # ---- area di notifica
    def _create_tray(self) -> None:
        """L'icona accanto all'orologio, con il suo menu. È un NotifyIcon di .NET: pythonnet è già caricato da
        pywebview, e deve vivere sul thread della finestra."""
        if sys.platform != "win32" or self.window is None:
            return
        for _ in range(100):
            if self.window.native is not None:
                break
            time.sleep(0.05)
        else:
            self.log.warning("area di notifica non disponibile: finestra non pronta")
            return
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        from System import Action
        from System.Drawing import Icon
        from System.Reflection import BindingFlags
        from System.Windows.Forms import ContextMenu, MenuItem, MouseButtons, NotifyIcon

        hotkeys = self.config.hotkeys()

        def later(func):
            # I clic arrivano sul thread della finestra: il lavoro va fatto altrove.
            return lambda *_: threading.Thread(target=func, daemon=True).start()

        def build():
            icon = NotifyIcon()
            icon.Icon = Icon(str(ICON))
            icon.Text = "QuickNotes"
            # Menu nativo di Windows, come quello delle altre icone accanto all'orologio.
            menu = ContextMenu()
            for label, func, keys in (("Apri QuickNotes", self.show_main, ""),
                                      ("Nota rapida", self.show_capture, hotkeys.get("quick_note", "")),
                                      ("Nota del giorno", self.open_today, hotkeys.get("daily", "")),
                                      ("Esci", self.request_quit, "")):
                item = MenuItem(f"{label}\t{keys}" if keys else label)
                item.Click += later(func)
                menu.MenuItems.Add(item)
            icon.ContextMenu = menu

            def clicked(_sender, args):
                if args.Button == MouseButtons.Left:
                    later(self.show_main)()
            icon.MouseClick += clicked
            icon.Visible = True
            self.tray = icon
            # La finestra nascosta che riceve i clic sull'icona prende un nome: le prove la cercano così.
            try:
                field = icon.GetType().GetField("window", BindingFlags.NonPublic | BindingFlags.Instance)
                hwnd = int(field.GetValue(icon).Handle.ToInt64())
                ctypes.windll.user32.SetWindowTextW(ctypes.c_void_p(hwnd), TRAY_TITLE)
            except Exception:  # noqa: BLE001 - solo per le prove
                self.log.debug("finestra dell'icona senza nome", exc_info=True)

        try:
            self.window.native.Invoke(Action(build))
            self.log.info("icona nell'area di notifica pronta")
        except Exception:  # noqa: BLE001 - senza icona chiudere la finestra fa uscire
            self.log.exception("area di notifica")

    def _remove_tray(self) -> None:
        """Senza questo l'icona resterebbe accanto all'orologio finché non ci passa sopra il mouse."""
        tray, self.tray = self.tray, None
        if tray is None or self.window is None or self.window.native is None:
            return
        try:
            from System import Action

            def remove():
                tray.Visible = False
                tray.Dispose()
            self.window.native.Invoke(Action(remove))
        except Exception:  # noqa: BLE001
            self.log.debug("icona non rimossa", exc_info=True)

    # ---- servizi in sottofondo
    def _listen_commands(self) -> None:
        try:
            listener = Listener(PIPE, authkey=AUTHKEY)
        except OSError:
            self.log.warning("istanza singola non disponibile", exc_info=True)
            return
        while not self.quitting:
            try:
                with listener.accept() as conn:
                    command = conn.recv()
            except Exception:  # noqa: BLE001 - connessione non valida
                continue
            self.open_today() if command == "daily" else self.show_main()

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
        if action == "quick_note":
            self.show_capture()
        elif action == "daily":
            self.open_today()
        else:
            self.show_main()
            self.emit("toast", "La registrazione arriva con la tappa dell'audio")

    def _refresh(self) -> list[str]:
        try:
            changed = self.store.refresh_changes()
        except Exception:  # noqa: BLE001
            self.log.exception("allineamento dell'indice")
            return []
        if changed:
            self.emit("note-changed", changed)
            self.emit("index-updated", len(changed))
        return changed

    def _watch(self) -> None:
        """Le modifiche fatte fuori dall'app (Obsidian, Claude, una sincronizzazione). Windows avvisa quando
        qualcosa cambia nella cartella delle note; si aspetta che la raffica finisca e si allinea una volta sola.
        Le scritture dell'app aggiornano già l'indice, quindi lì l'allineamento non trova nulla."""
        changed = self._refresh()
        self.log.info("indice allineato in %.2f s: %d note cambiate", time.perf_counter() - self.started, len(changed))
        trace("indice allineato")
        handle = None
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.FindFirstChangeNotificationW.restype = ctypes.c_void_p
            # Nomi di file e cartelle, dimensione, ultima scrittura; in tutte le sottocartelle.
            handle = kernel32.FindFirstChangeNotificationW(str(self.store.root), True, 0x1 | 0x2 | 0x8 | 0x10)
            if handle in (None, ctypes.c_void_p(-1).value):
                self.log.warning("avvisi di modifica non disponibili: controllo ogni 10 secondi")
                handle = None
        while not self.quitting:
            if handle is None:
                time.sleep(10)
            elif kernel32.WaitForSingleObject(ctypes.c_void_p(handle), 10_000) == 0:
                # Una modifica: si aspetta che per 200 ms non ne arrivino altre.
                while True:
                    kernel32.FindNextChangeNotification(ctypes.c_void_p(handle))
                    if kernel32.WaitForSingleObject(ctypes.c_void_p(handle), 200) != 0:
                        break
            # Anche senza avvisi, ogni 10 secondi: alcune cartelle di rete non li mandano.
            self._refresh()
        if handle is not None:
            kernel32.FindCloseChangeNotification(ctypes.c_void_p(handle))

    def _warm_hidden(self) -> None:
        """Avvio con Windows: la finestra resta nascosta, ma WebView2 carica la pagina solo in una finestra
        mostrata. Si mostra trasparente finché la pagina non è pronta, poi si nasconde: il primo clic
        sull'icona è immediato."""
        from System import Action

        for _ in range(100):
            if self.window.native is not None:
                break
            time.sleep(0.05)
        form = self.window.native

        def show():
            form.Opacity = 0
            form.Show()

        def hide():
            form.Hide()
            form.Opacity = 1
        try:
            form.Invoke(Action(show))
            self.window.events.loaded.wait(15)
            form.Invoke(Action(hide))
            self.log.info("pagina preparata in sottofondo")
        except Exception:  # noqa: BLE001 - si caricherà alla prima apertura
            self.log.warning("pagina non preparata in sottofondo", exc_info=True)

    def _started(self) -> None:
        if self.start_hidden:
            self._warm_hidden()
        threading.Thread(target=self._watch, daemon=True).start()
        threading.Thread(target=self._hotkeys, daemon=True).start()
        threading.Thread(target=self._listen_commands, daemon=True).start()
        self._create_tray()
        # La nota rapida si prepara a riposo, così non pesa sull'avvio e Ctrl Alt N è immediato.
        time.sleep(1.5)
        with self.capture_lock:
            if self.capture is None and not self.quitting:
                self.capture = self._create_capture()

    # ---- avvio
    def run(self) -> None:
        import webview

        if not (WEB_DIR / "index.html").exists():
            message_box(f"Manca l'interfaccia compilata in {WEB_DIR}.\nCompila con: cd frontend && npm run build")
            return
        self.server = PageServer(self)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.log.info("avvio: note in %s, pagina su porta %d", self.store.root, self.server.server_address[1])
        trace("dati pronti")

        self.window = webview.create_window(
            "QuickNotes", self.server.base, js_api=self.bridge,
            width=1440, height=900, min_size=(640, 420), hidden=self.start_hidden,
            background_color=self.window_theme()[0], text_select=True,
        )
        self.window.events.initialized += self._on_initialized
        self.window.events.closing += self._on_closing
        self.window.events.shown += self._on_shown
        webview.start(self._started, gui="edgechromium", debug=self.debug, private_mode=False,
                      storage_path=str(config_dir() / "webview"), icon=str(ICON) if ICON.exists() else None)
        self.quitting = True
        self._remove_tray()
        self.server.shutdown()
        self.store.close()
        self.log.info("chiusura")


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
