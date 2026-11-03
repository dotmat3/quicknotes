# QuickNotes con pywebview (prova)

Questo branch (`prova-pywebview`) verifica se QuickNotes può girare con **Python e pywebview** al posto di
Rust e Tauri, in particolare su un PC aziendale. La parte Rust non è stata toccata e si compila come prima.

La finestra è la stessa: pywebview usa WebView2, come Tauri, e carica la stessa interfaccia di `frontend/`.
Cambia solo il backend, che qui è in Python (`quicknotes_py/`) e usa gli stessi file di note e configurazione.

## Sul PC aziendale

Lo zip contiene tutto, compreso Python: sul PC di destinazione non servono installazioni, permessi di
amministratore né accesso a PyPI.

1. Su questo PC: `python python/costruisci_portatile.py` produce `python/dist/QuickNotes-prova.zip` (circa 14 MB).
2. Portalo sul PC aziendale. Se arriva da internet o dalla posta, prima di estrarlo: tasto destro →
   Proprietà → **Sblocca**.
3. Estrailo dove vuoi e fai doppio clic su **Verifica.cmd**. Il rapporto finisce in `verifica-quicknotes.txt`.
4. Se la verifica passa, apri **QuickNotes.cmd**.

Il `python.exe` incluso è il Python "embeddable" ufficiale di python.org, firmato dalla Python Software
Foundation. Le regole aziendali che bloccano gli eseguibili non firmati, come era quello Tauri, di solito
lo lasciano passare.

### Cosa controlla la verifica

| Controllo | Perché |
|---|---|
| WebView2 e .NET Framework 4.7.2+ | pywebview su Windows usa WinForms (.NET) con WebView2 dentro |
| pythonnet | carica .NET nel processo Python; alcuni criteri lo potrebbero bloccare |
| Cartelle delle note e della configurazione | scrittura e cancellazione di un file di prova |
| Server su 127.0.0.1 | la pagina e le immagini arrivano da lì |
| Tasti globali | `RegisterHotKey`, come Tauri: nessun hook sulla tastiera, che un antivirus potrebbe scambiare per un keylogger |
| Finestra di prova | WebView2 si apre davvero, carica da 127.0.0.1 e il JavaScript riceve una risposta da Python |

## Cosa c'è e cosa manca

C'è: nota del giorno con frecce avanti e indietro, editor con salvataggio automatico e controllo dei
conflitti, note nuove, `[[collegamenti]]` in entrata e in uscita, immagini incollate o trascinate,
suggerimenti di `@persone` e `#etichette`, contatori della barra laterale, modifiche esterne ricaricate,
Impostazioni (tema, cartella delle note), Ctrl+Alt+D anche con l'app in secondo piano, istanza singola.

Manca: viste Azioni, Calendario, Grafo e Persone, schede persona ed etichetta, Ctrl K completo (funziona
l'apertura per titolo), nota rapida, registrazione, area di notifica, avvio con Windows, server MCP.
Questi comandi rispondono `missing` e la pagina mostra liste vuote. Chiudere la finestra chiude l'app.

Differenze rispetto a Tauri:

- **Cornice di Windows** al posto della barra del titolo disegnata dalla pagina: in WinForms una finestra
  senza cornice non si ridimensiona dai bordi.
- **Avvio in circa 1,2 secondi** fino alla pagina disegnata, contro i 400 ms dell'obiettivo Tauri. La
  finestra compare subito con lo sfondo del tema, perché pywebview non carica la pagina in una finestra nascosta.
- **Indice in memoria**, ricostruito dai file a ogni avvio e aggiornato ogni 2 secondi. Non usa e non
  tocca `index-v3.db`.

## Sviluppo

```bash
py -3.12 -m venv python/.venv
python/.venv/Scripts/python -m pip install pywebview==6.2.1 pyyaml==6.0.3
cd frontend && npm run build:py && cd ..          # interfaccia in python/quicknotes_py/webui/
cd python && .venv/Scripts/python -m quicknotes_py    # --debug apre gli strumenti di sviluppo
```

Prove:

```bash
python/.venv/Scripts/python -m unittest discover -s python/tests   # formato delle note
node scripts/prova-python.mjs foto.png                              # app dal vivo, su note di prova
QN_PYTHON=python/dist/QuickNotes-prova/python/pythonw.exe node scripts/prova-python.mjs   # la cartella portatile
```

| File | Compito |
|---|---|
| `quicknotes_py/notes.py` | formato delle note, scrittura atomica, indice in memoria, immagini |
| `quicknotes_py/commands.py` | i comandi della pagina, con gli stessi nomi di `commands.rs` |
| `quicknotes_py/app.py` | finestra, server locale, tasti globali, istanza singola, modifiche esterne |
| `quicknotes_py/check.py` | la verifica |
| `costruisci_portatile.py` | la cartella portatile e lo zip |

Nel frontend cambia solo `api.js`, che sceglie tra Tauri e pywebview (più `images.js` e `TitleBar.svelte`,
che ora passano da lì).
