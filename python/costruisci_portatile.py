"""Costruisce la cartella portatile della prova, da copiare sul PC aziendale e usare senza installare nulla.

    python python/costruisci_portatile.py

Dentro: il Python "embeddable" ufficiale di python.org (python.exe firmato dalla Python Software Foundation),
le librerie già scaricate e l'app. Sul PC di destinazione non servono né Python, né pip, né accesso a PyPI.

    dist/QuickNotes-prova/
      QuickNotes.cmd        avvia l'app (senza console)
      Verifica.cmd          controlla il PC e scrive verifica-quicknotes.txt
      python/               Python embeddable
      lib/                  pywebview, pythonnet, PyYAML
      app/quicknotes_py/    l'app, con l'interfaccia compilata
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DIST = HERE / "dist"
OUT = DIST / "QuickNotes-prova"
PACKAGES = ["pywebview==6.2.1", "pyyaml==6.0.3"]
DOTNET_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <runtime>
    <loadFromRemoteSources enabled="true"/>
  </runtime>
</configuration>
"""

LEGGIMI = """QuickNotes - prova Python con pywebview
=======================================

1. Se hai scaricato lo zip da internet o dalla posta: prima di estrarlo, tasto destro sullo zip >
   Proprieta' > spunta "Sblocca" > OK. Altrimenti Windows potrebbe bloccare i file estratti.
2. Estrai la cartella dove vuoi (anche in Documenti o sul Desktop: non servono permessi di amministratore).
3. Doppio clic su Verifica.cmd: controlla WebView2, .NET, cartelle, tasti globali e apre per un attimo
   una finestra di prova. Il risultato e' in verifica-quicknotes.txt, nella stessa cartella.
4. Doppio clic su QuickNotes.cmd per aprire l'app. Usa le note e la configurazione di sempre
   (~/QuickNotes e ~/.quicknotes/config.json). Il registro e' in ~/.quicknotes/quicknotes-py.log.

Cosa c'e' nella prova: nota del giorno, editor, salvataggio, note nuove, [[collegamenti]], immagini,
persone ed etichette nei suggerimenti, Ctrl+Alt+D (nota del giorno) anche con l'app in secondo piano.
Cosa manca: vista Azioni, Calendario, Grafo, schede persona/etichetta, Ctrl K completo, nota rapida,
registrazione, area di notifica, server MCP. Chiudere la finestra chiude l'app.
"""


def run(*cmd: str, cwd: Path | None = None) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32" and cmd[0] == "npm")


def main() -> None:
    if sys.platform != "win32" or sys.maxsize < 2**32:
        sys.exit("Serve Python a 64 bit su Windows: la cartella portatile e' per Windows x64.")
    ver = ".".join(map(str, sys.version_info[:3]))
    short = f"{sys.version_info[0]}{sys.version_info[1]}"

    print("1/5 interfaccia")
    run("npm", "run", "build:py", cwd=REPO / "frontend")

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
    (OUT / "python" / f"python{short}._pth").write_text(
        f"python{short}.zip\n.\n..\\lib\n..\\app\n", encoding="utf-8")
    # Estratti da uno zip scaricato, i file portano il marchio "da internet" e .NET Framework rifiuta di
    # caricare Python.Runtime.dll (pythonnet: "Failed to resolve Python.Runtime.Loader.Initialize").
    # loadFromRemoteSources è l'opzione documentata di .NET per le app che caricano le proprie DLL così.
    for exe in ("python.exe", "pythonw.exe"):
        (OUT / "python" / f"{exe}.config").write_text(DOTNET_CONFIG, encoding="utf-8")

    print("3/5 librerie")
    # Stesso Python e stessa piattaforma della destinazione: le ruote scelte da pip sono quelle giuste.
    # Niente --only-binary: proxy_tools, richiesto da pywebview, esiste solo come sorgente (Python puro).
    run(sys.executable, "-m", "pip", "install", "--quiet", "--target", str(OUT / "lib"), *PACKAGES)
    shutil.rmtree(OUT / "lib" / "bin", ignore_errors=True)

    print("4/5 app")
    shutil.copytree(HERE / "quicknotes_py", OUT / "app" / "quicknotes_py",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (OUT / "QuickNotes.cmd").write_text(
        '@echo off\r\nstart "" "%~dp0python\\pythonw.exe" -m quicknotes_py %*\r\n', encoding="ascii")
    (OUT / "Verifica.cmd").write_text(
        '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0python\\python.exe" -m quicknotes_py verifica\r\npause\r\n',
        encoding="ascii")
    (OUT / "LEGGIMI.txt").write_text(LEGGIMI.replace("\n", "\r\n"), encoding="utf-8")

    print("5/5 zip")
    archive = shutil.make_archive(str(DIST / "QuickNotes-prova"), "zip", DIST, OUT.name)
    size = Path(archive).stat().st_size / 1024 / 1024
    print(f"\nPronto: {archive} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
