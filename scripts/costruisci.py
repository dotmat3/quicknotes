"""Costruisce la cartella portatile di QuickNotes e il suo zip: si estrae e si usa, senza installare nulla.

    .venv/Scripts/python scripts/costruisci.py

Dentro c'è il Python "embeddable" ufficiale di python.org (python.exe firmato dalla Python Software Foundation),
le librerie già scaricate e l'app. Sul PC di destinazione non servono né Python, né pip, né accesso a PyPI.

    dist/QuickNotes/
      QuickNotes.cmd        avvia l'app (senza console)
      Verifica.cmd          controlla il PC e scrive verifica-quicknotes.txt
      LEGGIMI.txt
      python/               Python embeddable, con python.exe.config per .NET
      lib/                  pywebview, pythonnet, PyYAML
      app/quicknotes/       l'app, con l'interfaccia compilata
    dist/QuickNotes.zip     la stessa cartella, da caricare nella release
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUT = DIST / "QuickNotes"
PACKAGES = [l.strip() for l in (ROOT / "requirements.txt").read_text().splitlines() if l.strip()]

# Estratti da uno zip scaricato, i file portano il marchio "da internet" e .NET Framework rifiuta di caricare
# Python.Runtime.dll (pythonnet: "Failed to resolve Python.Runtime.Loader.Initialize"). loadFromRemoteSources è
# l'opzione documentata di .NET per le app che caricano le proprie DLL così.
DOTNET_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <runtime>
    <loadFromRemoteSources enabled="true"/>
  </runtime>
</configuration>
"""

LEGGIMI = """QuickNotes {version}
==============

Note di meeting e giornate in Markdown, con ricerca, azioni e collegamento a Claude.

Primo avvio
-----------
1. Se hai scaricato lo zip da internet o dalla posta: prima di estrarlo, tasto destro sullo zip >
   Proprieta' > spunta "Sblocca" > OK.
2. Estrai la cartella dove vuoi, per esempio in Documenti. Non servono permessi di amministratore.
3. Doppio clic su QuickNotes.cmd. L'app resta nell'area di notifica accanto all'orologio:
   chiudere la finestra la nasconde, per uscire usa il menu dell'icona.

Se non parte, apri Verifica.cmd: controlla il PC e scrive cosa manca in verifica-quicknotes.txt.

Dove stanno le cose
-------------------
- Note:            %USERPROFILE%\\QuickNotes (file Markdown, leggibili anche con Obsidian o VS Code)
- Configurazione:  %USERPROFILE%\\.quicknotes\\config.json
- Registro:        %USERPROFILE%\\.quicknotes\\quicknotes.log

Tasti globali: Ctrl+Alt+N nota rapida, Ctrl+Alt+D nota del giorno.
Avvio con Windows e collegamento a Claude: Impostazioni (Ctrl+,) dentro l'app.

Nuova versione: chiudi QuickNotes (icona > Esci), sostituisci questa cartella con quella nuova e, se
l'avevi attivato, riattiva "Avvia con Windows". Le note non si toccano.
"""


def run(*cmd: str, cwd: Path | None = None) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32" and cmd[0] == "npm")


def main() -> None:
    if sys.platform != "win32" or sys.maxsize < 2**32:
        sys.exit("Serve Python a 64 bit su Windows: la cartella portatile è per Windows x64.")
    sys.path.insert(0, str(ROOT))
    from quicknotes import __version__ as version
    ver = ".".join(map(str, sys.version_info[:3]))
    short = f"{sys.version_info[0]}{sys.version_info[1]}"
    print(f"QuickNotes {version}, Python {ver}")

    print("1/5 interfaccia")
    run("npm", "run", "build", cwd=ROOT / "frontend")

    print(f"2/5 Python {ver} embeddable")
    cache = DIST / "cache" / f"python-{ver}-embed-amd64.zip"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://www.python.org/ftp/python/{ver}/python-{ver}-embed-amd64.zip"
        print("  scarico", url)
        urllib.request.urlretrieve(url, cache)
    if OUT.exists():
        shutil.rmtree(OUT)
    with zipfile.ZipFile(cache) as z:
        z.extractall(OUT / "python")
    # Il file ._pth decide dove Python cerca i moduli: niente PYTHONPATH, niente cartella corrente.
    (OUT / "python" / f"python{short}._pth").write_text(f"python{short}.zip\n.\n..\\lib\n..\\app\n", encoding="utf-8")
    for exe in ("python.exe", "pythonw.exe"):
        (OUT / "python" / f"{exe}.config").write_text(DOTNET_CONFIG, encoding="utf-8")

    print("3/5 librerie")
    # Stesso Python e stessa piattaforma della destinazione: le ruote scelte da pip sono quelle giuste.
    # Niente --only-binary: proxy_tools, richiesto da pywebview, esiste solo come sorgente (Python puro).
    run(sys.executable, "-m", "pip", "install", "--quiet", "--target", str(OUT / "lib"), *PACKAGES)
    shutil.rmtree(OUT / "lib" / "bin", ignore_errors=True)

    print("4/5 app")
    shutil.copytree(ROOT / "quicknotes", OUT / "app" / "quicknotes", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if not (OUT / "app" / "quicknotes" / "webui" / "index.html").exists():
        sys.exit("Manca l'interfaccia compilata: controlla npm run build.")
    (OUT / "QuickNotes.cmd").write_text(
        '@echo off\r\nstart "" "%~dp0python\\pythonw.exe" -m quicknotes %*\r\n', encoding="ascii")
    (OUT / "Verifica.cmd").write_text(
        '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0python\\python.exe" -m quicknotes verifica\r\npause\r\n', encoding="ascii")
    (OUT / "LEGGIMI.txt").write_text(LEGGIMI.format(version=version).replace("\n", "\r\n"), encoding="utf-8")

    print("5/5 zip")
    archive = Path(shutil.make_archive(str(DIST / "QuickNotes"), "zip", DIST, OUT.name))
    print(f"\nPronto: {archive} ({archive.stat().st_size / 1024 / 1024:.0f} MB)")


if __name__ == "__main__":
    main()
