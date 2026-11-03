"""Verifica: controlla, uno per uno, ciò che serve a QuickNotes su questo PC e scrive un rapporto.

    python -m quicknotes verifica                 tutti i controlli, con una finestra di prova
    python -m quicknotes verifica --senza-finestra
"""

from __future__ import annotations

import ctypes
import getpass
import os
import platform
import struct
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .config import Config, config_dir

OK, WARN, FAIL = "OK", "ATTENZIONE", "ERRORE"
WEBVIEW2_KEY = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


class Report:
    def __init__(self):
        self.lines: list[str] = []
        self.problems: list[str] = []

    def add(self, status: str, what: str, detail: str = "") -> None:
        line = f"[{status:^10}] {what}" + (f": {detail}" if detail else "")
        self.lines.append(line)
        print(line, flush=True)
        if status != OK:
            self.problems.append(line)

    def info(self, text: str) -> None:
        self.lines.append(text)
        print(text, flush=True)


def _reg_value(root, path: str, name: str):
    import winreg
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def webview2_version() -> str | None:
    import winreg
    for root, path in ((winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\{WEBVIEW2_KEY}"),
                       (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\{WEBVIEW2_KEY}"),
                       (winreg.HKEY_CURRENT_USER, rf"Software\{WEBVIEW2_KEY}")):
        v = _reg_value(root, path, "pv")
        if v and v != "0.0.0.0":
            return v
    return None


def check_system(r: Report) -> None:
    r.info(f"QuickNotes {__version__} — verifica del {datetime.now():%d/%m/%Y %H:%M}")
    r.info(f"Sistema: {platform.platform()} · utente {getpass.getuser()}")
    r.info(f"Python: {sys.version.split()[0]} {struct.calcsize('P') * 8} bit · {sys.executable}")
    r.info("")


def check_runtime(r: Report) -> bool:
    if sys.platform != "win32":
        r.add(WARN, "Sistema non Windows", "i controlli di WebView2 e .NET valgono solo su Windows")
        return True
    import winreg
    v = webview2_version()
    if v:
        r.add(OK, "Microsoft Edge WebView2", v)
    else:
        r.add(FAIL, "Microsoft Edge WebView2", "non trovato nel registro: senza, la finestra non si apre")
    release = _reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full", "Release")
    if release and release >= 461808:
        r.add(OK, ".NET Framework 4.7.2 o successivo", f"release {release}")
    else:
        r.add(FAIL, ".NET Framework 4.7.2 o successivo", f"release {release}: serve a pywebview su Windows")
    return bool(v)


def check_packages(r: Report) -> bool:
    ok = True
    try:
        import webview
        from importlib.metadata import version
        r.add(OK, "pywebview", version("pywebview"))
    except Exception as e:  # noqa: BLE001
        r.add(FAIL, "pywebview", f"{type(e).__name__}: {e}")
        return False
    try:
        import yaml  # noqa: F401
        r.add(OK, "PyYAML", "con libyaml" if hasattr(yaml, "CSafeLoader") else "senza libyaml: indicizzazione più lenta")
    except Exception as e:  # noqa: BLE001
        r.add(FAIL, "PyYAML", str(e))
        ok = False
    try:
        import sqlite3
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(a)")
        r.add(OK, "SQLite con ricerca a testo pieno", sqlite3.sqlite_version)
    except Exception as e:  # noqa: BLE001
        r.add(FAIL, "SQLite con ricerca a testo pieno (FTS5)", f"{type(e).__name__}: {e}")
        ok = False
    if sys.platform == "win32":
        try:
            import clr  # noqa: F401 - pythonnet: carica .NET nel processo
            from System import Environment
            r.add(OK, "pythonnet e .NET caricati", f"CLR {Environment.Version}")
        except Exception as e:  # noqa: BLE001
            r.add(FAIL, "pythonnet (.NET dentro Python)", f"{type(e).__name__}: {e}")
            r.info("             " + pythonnet_hint())
            ok = False
    return ok


def _marked_from_internet(path: Path) -> bool:
    """Il file porta il marchio "scaricato da internet" (flusso NTFS Zone.Identifier)."""
    try:
        with open(f"{path}:Zone.Identifier", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    return "ZoneId=3" in text or "ZoneId=4" in text


def pythonnet_hint() -> str:
    """Perché pythonnet non parte, per quanto si può capire da qui."""
    import importlib.util
    spec = importlib.util.find_spec("pythonnet")
    dll = Path(spec.origin).parent / "runtime" / "Python.Runtime.dll" if spec and spec.origin else None
    if dll is None or not dll.exists():
        return ("Manca Python.Runtime.dll: probabilmente l'antivirus l'ha messo in quarantena. "
                "Controlla la cronologia delle protezioni di Windows Security.")
    config = Path(sys.executable).with_name(Path(sys.executable).name + ".config")
    if _marked_from_internet(dll):
        if not config.exists():
            return (f"I file sono marcati come scaricati da internet e manca {config.name}. "
                    "Estrai di nuovo lo zip dopo averlo sbloccato (tasto destro > Proprieta' > Sblocca).")
        return ("I file sono marcati come scaricati da internet. Estrai di nuovo lo zip dopo averlo sbloccato "
                "(tasto destro > Proprieta' > Sblocca); se il problema resta, le regole aziendali bloccano le DLL .NET.")
    return ("I file non sono marcati e la DLL c'e': probabilmente una regola aziendale (AppLocker, WDAC) "
            "o l'antivirus blocca le DLL non firmate. Serve un'eccezione dall'IT per la cartella dell'app.")


def _writable(path: Path) -> str | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".verifica-", delete=True) as f:
            f.write(b"ok")
        return None
    except OSError as e:
        return str(e)


def check_folders(r: Report) -> None:
    cfg = Config.load()
    notes = cfg.notes_path()
    for what, path in (("Cartella delle note", notes), ("Cartella della configurazione", config_dir())):
        err = _writable(path)
        r.add(FAIL if err else OK, what, f"{path}" + (f" — non scrivibile: {err}" if err else ""))
    if "onedrive" in str(notes).lower():
        r.add(WARN, "Note dentro OneDrive", "funziona, ma la sincronizzazione può creare copie in conflitto")


class _Ping(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"<!doctype html><title>prova</title><p id=x>QuickNotes: verifica in corso...</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def check_local_server(r: Report) -> ThreadingHTTPServer | None:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Ping)
    except OSError as e:
        r.add(FAIL, "Server locale su 127.0.0.1", str(e))
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        opener.open(url, timeout=5).read()
        r.add(OK, "Server locale su 127.0.0.1", f"porta {server.server_address[1]}")
    except Exception as e:  # noqa: BLE001
        r.add(FAIL, "Server locale su 127.0.0.1", f"{type(e).__name__}: {e}")
    return server


def check_hotkeys(r: Report) -> None:
    if sys.platform != "win32":
        return
    from .app import MOD_NOREPEAT, parse_hotkey
    user32 = ctypes.windll.user32
    for i, (action, combo) in enumerate(Config.load().hotkeys().items(), start=100):
        parsed = parse_hotkey(combo)
        if parsed and user32.RegisterHotKey(None, i, parsed[0] | MOD_NOREPEAT, parsed[1]):
            user32.UnregisterHotKey(None, i)
            r.add(OK, f"Tasto globale {combo}", action)
        else:
            r.add(WARN, f"Tasto globale {combo}", "già usato da un'altra app (anche QuickNotes stessa, se è aperta)")


class _TestApi:
    def __init__(self):
        self.received: dict | None = None
        self._done = threading.Event()

    def ping(self, info):
        self.received = info
        self._done.set()
        return "pong"


def check_window(r: Report, server: ThreadingHTTPServer | None) -> None:
    """Una finestra vera: WebView2 parte, carica da 127.0.0.1, il JavaScript chiama Python e riceve risposta."""
    import webview

    api = _TestApi()
    url = f"http://127.0.0.1:{server.server_address[1]}/" if server else None
    html = None if url else "<!doctype html><p>QuickNotes: verifica in corso...</p>"
    window = webview.create_window("QuickNotes — verifica", url=url, html=html, js_api=api, width=480, height=200)
    renderer = {}
    timings = {"start": time.perf_counter()}

    def on_init(name):
        renderer["name"] = name

    def on_loaded():
        timings["loaded"] = time.perf_counter()
        try:
            window.run_js(
                "(async () => {"
                " const r = await window.pywebview.api.ping({ua: navigator.userAgent, ls: (() => { try {"
                " localStorage.setItem('qn','1'); return localStorage.getItem('qn') === '1'; } catch { return false } })()});"
                " document.getElementById('x') && (document.getElementById('x').textContent = 'Risposta da Python: ' + r);"
                "})()")
        except Exception:  # noqa: BLE001
            pass

    window.events.initialized += on_init
    window.events.loaded += on_loaded

    def wait_and_close():
        ok = api._done.wait(20)
        if ok:
            time.sleep(0.8)
        window.destroy()

    webview.start(wait_and_close, gui="edgechromium", private_mode=False,
                  storage_path=str(config_dir() / "webview-verifica"))
    name = renderer.get("name", "?")
    if name != "edgechromium":
        r.add(FAIL, "Motore della finestra", f"{name} invece di WebView2 (edgechromium)")
    else:
        r.add(OK, "Motore della finestra", "WebView2 (edgechromium)")
    if api.received:
        load = timings.get("loaded", timings["start"]) - timings["start"]
        r.add(OK, "Finestra e ponte JavaScript ↔ Python", f"pagina caricata in {load:.1f} s")
        ua = api.received.get("ua", "")
        edg = next((p for p in ua.split() if p.startswith("Edg/")), "")
        if edg:
            r.info(f"             WebView2 in uso: {edg}")
        if not api.received.get("ls"):
            r.add(WARN, "Memoria locale della pagina", "localStorage non disponibile")
    else:
        r.add(FAIL, "Finestra e ponte JavaScript ↔ Python", "nessuna risposta dalla pagina in 20 secondi")


def run(with_window: bool = True) -> int:
    # Una console con codifica cp1252 non sa scrivere "↔": meglio un "?" che un errore.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    r = Report()
    check_system(r)
    runtime_ok = check_runtime(r)
    packages_ok = check_packages(r)
    check_folders(r)
    server = check_local_server(r)
    check_hotkeys(r)
    if with_window and runtime_ok and packages_ok:
        try:
            check_window(r, server)
        except Exception as e:  # noqa: BLE001
            r.add(FAIL, "Finestra di prova", f"{type(e).__name__}: {e}")
    elif with_window:
        r.add(WARN, "Finestra di prova", "saltata: mancano i requisiti sopra")
    r.info("")
    if not r.problems:
        r.info("Esito: tutto a posto, QuickNotes può girare su questo PC.")
    else:
        r.info(f"Esito: {len(r.problems)} punti da guardare:")
        for p in r.problems:
            r.info("  " + p)
    out = _report_path()
    try:
        out.write_text("\n".join(r.lines) + "\n", encoding="utf-8")
        print(f"\nRapporto salvato in {out}")
    except OSError as e:
        print(f"\nRapporto non salvato ({e})")
    return 0 if not any(FAIL in p for p in r.problems) else 1


def _report_path() -> Path:
    for folder in (Path.cwd(), config_dir()):
        if os.access(folder, os.W_OK):
            return folder / "verifica-quicknotes.txt"
    return config_dir() / "verifica-quicknotes.txt"
