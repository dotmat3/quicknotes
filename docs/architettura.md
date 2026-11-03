# Architettura di QuickNotes

Questo documento descrive come è costruita l'app. Cosa deve fare è in [piano-implementazione-design.md](piano-implementazione-design.md), l'ordine di lavoro seguito è in [piano-incrementale.md](piano-incrementale.md) (scritto per la versione Rust, che fino alla 0.3.1 ha preceduto quella Python).

Il riferimento visivo è la tavola **Home** del [design](https://claude.ai/artifact/1ZCTE9XczJ49BE4LQyGN2h) ("Homepage · icone, schede VS Code, contenuto in riquadro").

## Obiettivi

In ordine di priorità:

1. **Le note restano dell'utente.** File Markdown leggibili, compatibili con quelli già esistenti. L'indice si può sempre ricostruire.
2. **Gira sui PC aziendali.** Niente installer, niente amministratore, niente eseguibili non firmati.
3. **Fluidità.** Scrivere, cambiare scheda e aprire una vista non devono mai perdere un fotogramma per colpa dell'I/O.
4. **Tutto in locale.** Nessun dato esce dal computer, e l'app funziona senza rete.

### Limiti misurabili

Riferimento: questo PC, 1000 note generate da `scripts/genera_note.py` (o le note di `scripts/demo-note.mjs` dove serve). Misure del 4 novembre 2026.

| Misura | Obiettivo | Misurato |
|---|---|---|
| Avvio a freddo fino alla nota di oggi disegnata, dalla creazione del processo | < 1,5 s | 1,33 s |
| Finestra già attiva nell'area di notifica, seconda apertura visibile | < 300 ms | 0,27 s |
| Tasto premuto, carattere a schermo | < 16 ms | 4–6 ms |
| Cambio scheda | < 50 ms | 28 ms |
| Ricerca Ctrl K, risultati a ogni tasto | < 30 ms | mediana 20 ms, 95° percentile 31 ms |
| Allineamento dell'indice senza modifiche | < 100 ms, senza bloccare l'interfaccia | 50 ms |
| Indicizzazione completa (primo avvio) | < 2 s | 0,82 s |
| Memoria del processo a riposo, escluso WebView2 | < 100 MB | 76 MB |

La versione Rust aveva obiettivi più stretti sull'avvio (400 ms) e sulla memoria (40 MB): l'avvio di Python e di .NET costa circa un secondo e una quarantina di MB. È il prezzo della portabilità, vedi sotto.

## Scelte tecniche

### Python con pywebview, non Rust con Tauri

Fino alla 0.3.1 l'app era in Rust con Tauri 2. Funzionava, ma l'eseguibile non firmato non si poteva avviare su un PC aziendale. La versione Python gira con il Python "embeddable" ufficiale di python.org, il cui `python.exe` è firmato dalla Python Software Foundation, e non chiede di installare nulla.

| Opzione | PC aziendale | Interfaccia | Esito |
|---|---|---|---|
| **Python + pywebview + WebView2** | `python.exe` firmato, cartella portatile | La stessa: Svelte 5 + CodeMirror 6 | **Scelta** |
| Rust + Tauri 2 | Eseguibile non firmato, bloccato | La stessa | Abbandonata con la 0.4.0 |
| Python + Qt WebEngine | Funziona, ma lo zip passa da 14 a ~150 MB | La stessa | Riserva, se .NET fosse bloccato |

pywebview su Windows apre una finestra WinForms (.NET Framework, tramite pythonnet) con dentro WebView2, lo stesso motore di Tauri. L'interfaccia è rimasta identica: è cambiato solo il backend.

Come si riducono i costi dell'avvio:

- **Una sola istanza, residente nell'area di notifica.** Chiudere la finestra la nasconde: riaprirla è quasi immediato.
- **Finestra con lo sfondo del tema già impostato**, visibile da subito: pywebview non carica la pagina in una finestra nascosta. Con l'avvio con Windows (`--nascosta`) la finestra si mostra trasparente finché la pagina non è pronta, poi si nasconde.
- **Dati pronti prima della pagina.** Python inietta tema, preferenze e nota di oggi nella pagina (`window.__QN__`), quindi la prima schermata non aspetta nessuna chiamata.
- **Prima la struttura, poi l'editor**, in blocchi separati compilati da Vite.
- **Indice in sottofondo.** Nessuna operazione su disco blocca la finestra.
- **La nota rapida si prepara nascosta** 1,5 secondi dopo l'avvio, così Ctrl Alt N è immediato.

### Struttura del repository

```
quicknotes/                pacchetto Python: nucleo, app, server MCP
  webui/                   interfaccia compilata (npm run build), non versionata
frontend/                  Svelte 5 + CodeMirror 6, compilato da Vite
scripts/                   prove dal vivo, misure, costruzione dello zip e rilascio
tests/                     prove del nucleo e del server MCP (unittest)
docs/
```

Il server MCP è lo stesso pacchetto avviato come `python -m quicknotes mcp`: lo avvia Claude a ogni sessione e non carica né pywebview né .NET.

### Dipendenze

| Compito | Libreria | Note |
|---|---|---|
| Finestre | `pywebview` 6 (WinForms + WebView2, tramite `pythonnet`) | |
| Area di notifica | `NotifyIcon` di .NET, con il menu nativo `ContextMenu` | pythonnet è già caricato da pywebview: nessuna dipendenza in più |
| Tasti globali | `RegisterHotKey` di Windows, con `ctypes` | Niente hook sulla tastiera, che un antivirus potrebbe scambiare per un keylogger |
| Istanza singola | Named pipe (`multiprocessing.connection`) | |
| Modifiche esterne ai file | `FindFirstChangeNotification` di Windows, con `ctypes` | Più un controllo ogni 10 secondi per le cartelle che non avvisano |
| Indice e ricerca | `sqlite3` della libreria standard, con FTS5 | |
| Frontmatter | `PyYAML` con libyaml | Solo per leggere e per scrivere i metadati modificati |
| MCP | Scritto a mano su `json` | Solo strumenti e prompt |
| Editor | CodeMirror 6, con `@codemirror/search` e `@codemirror/language-data` | |
| Grafo | `d3-force`, disegnato su canvas | |
| Markdown nell'Anteprima | `marked` e `DOMPurify` | |

## Compatibilità con i dati esistenti

In `~/QuickNotes` e `~/.quicknotes` ci sono note e configurazione reali, scritte anche dalle versioni precedenti. L'app li usa così come sono.

| Elemento | Comportamento |
|---|---|
| Cartella delle note | `notes_dir` da `~/.quicknotes/config.json`, oppure `QUICKNOTES_DIR` |
| Configurazione | Stesso file, oppure `QUICKNOTES_CONFIG_DIR`. Le chiavi sconosciute vengono conservate. I tasti in formato pynput (`<ctrl>+<alt>+n`) si convertono alla lettura |
| Id di una nota | Il nome del file senza estensione |
| Nota del giorno | `AAAA/MM/AAAA-MM-GG-giornata.md`, senza rinominare nulla |
| Meeting e note | `AAAA/MM/AAAA-MM-GG-HHMM-titolo.md` |
| Sintassi | `@persona`, `#tag`, `- [ ]`, `due:` (anche `entro:` e `scadenza:`), `done:`, `!decisione` (anche `!decision`, `!dec`), `[[id\|Titolo]]`, `[[Titolo]]`, `![[….excalidraw]]` |
| Audio | `AAAA/MM/audio/<id>-HHMMSS.wav` e righe `🎙️ [Registrazione HH:MM (durata)](file)` |
| Trascrizioni | `### Trascrizione HH:MM`, con paragrafi `[mm:ss]`. `parser.recordings` e `parser.transcript_lines` le leggono per Calendario e Ctrl K; una registrazione cade nel giorno della nota che la contiene |
| Immagini | `images/` accanto alla nota, con `![](images/…)`. Incollate o trascinate: `images/AAAA-MM-GG-HHMMSS.png`. La pagina le carica dal server locale, che serve solo immagini vere dentro la cartella delle note |
| Indice | File `<note>/.quicknotes/index-v4.db`. Gli indici delle versioni precedenti (`index.db`, `index-v3.db`) non vengono toccati |

**Un salvataggio non riscrive ciò che non è cambiato.** Il frontmatter resta testo esattamente com'era finché non si modificano i metadati, e gli a capo restano quelli del file (anche `\r\n`). I file si leggono senza conversione degli a capo e si scrivono in modo atomico.

**Isolamento durante lo sviluppo:** ogni prova usa cartelle temporanee, tramite `QUICKNOTES_DIR` e `QUICKNOTES_CONFIG_DIR`.

## Backend

| Modulo | Compito |
|---|---|
| `parser` | Frontmatter, persone, etichette, azioni con madre e descrizione, decisioni, link, titoli, registrazioni e righe delle trascrizioni. Funzioni pure |
| `edit` | Modifiche su una riga o su un corpo: `with_done`, `with_due`, `with_checked`, `with_person`, `with_tag`, `with_description`, `add_to_section`. Funzioni pure |
| `index` | Schema SQLite, indicizzazione, interrogazioni (ricerca, azioni, decisioni, persone, etichette, collegamenti, grafo) |
| `store` | Lettura e scrittura atomica dei file, allineamento dell'indice, operazioni sulle azioni, immagini |
| `dates` | Titolo del giorno, etichette e colonne delle scadenze |
| `views` | Dati pronti per le viste: `action_board`, `calendar_data`, `person_page`, `people_list`, `tag_page`, `full_graph`, `search_all` |
| `commands` | I comandi della pagina |
| `app` | Finestre, server locale, area di notifica, nota rapida, tasti globali, istanza singola, modifiche esterne |
| `system` | Link e cartelle, avvio con Windows (`HKCU\…\Run`), percorsi di `python.exe` e `pythonw.exe` |
| `mcp` | Server MCP su stdio |
| `check` | `python -m quicknotes verifica` |
| `config` | Lettura e scrittura della configurazione |

**Ctrl K (`search_all`):** note dalla ricerca a testo pieno (15), poi, se una parola ha almeno tre lettere, azioni aperte e decisioni che contengono tutte le parole (5 ciascuna) e le righe `[mm:ss]` delle trascrizioni nelle note già trovate (5). Ogni risultato porta la riga della nota, che si apre mostrandola.

Il riconoscimento di `@` e `#` è scritto a mano: le regole guardano il carattere precedente, e saltando da un `@` o `#` al successivo è anche veloce. Le prove in `tests/` sono le stesse della versione Rust, con gli stessi risultati attesi.

**Indice:** le righe di `notes_fts` hanno lo stesso `rowid` della nota in `notes`, così si cancellano senza scorrere la tabella a testo pieno, dove il percorso non ha un indice.

### Concorrenza

- **Le scritture** passano da un lock su file e indice, e le modifiche di tipo leggi-cambia-scrivi da un secondo lock: due salvataggi non possono mai incrociarsi.
- **Le letture** usano una connessione SQLite separata in modalità WAL, quindi non aspettano una scrittura.
- **I comandi** arrivano dalla pagina in thread separati (pywebview ne avvia uno per chiamata): la finestra non aspetta mai il disco.
- **All'avvio** un thread allinea l'indice ai file; le viste si aggiornano quando finisce.
- **Modifiche esterne:** Windows avvisa quando cambia qualcosa nella cartella delle note; dopo 200 ms senza altri avvisi l'indice si allinea e la pagina riceve `note-changed`. Le scritture dell'app aggiornano già l'indice, quindi lì l'allineamento non trova nulla.
- **Il server MCP** è un altro processo. Scrive sugli stessi file e l'indice è protetto da WAL e da un'attesa di 10 secondi sui lock. L'app vede le sue modifiche grazie agli avvisi di Windows.
- **Thread della finestra:** gli eventi di pywebview come `closing` girano sul thread di WinForms. Da lì non si chiama mai `run_js`, che aspetterebbe una risposta che solo quel thread può dare: il lavoro passa a un altro thread.

### Pagina, comandi ed eventi

- La pagina arriva da un server HTTP su `127.0.0.1`, porta casuale, con un prefisso segreto nell'indirizzo. HTTP/1.1 con connessioni riusate: con HTTP/1.0 ogni file aprirebbe una porta nuova.
- I comandi passano da `window.pywebview.api.invoke(nome, argomenti)` e rispondono `{ok}`, `{err}` con un messaggio da mostrare, o `{missing}`. La pagina non riceve mai percorsi da usare direttamente.
- Gli eventi arrivano con `window.__qnEmit(nome, dati)`: `index-updated`, `note-changed`, `open-page`, `window-shown`, `flush`, `flush-and-close`, `toast`, `capture-open`.
- Le immagini incollate arrivano come byte con una `POST` allo stesso server.

## Frontend

```
frontend/src/
  main.js                 sceglie la finestra (principale o nota rapida)
  api.js                  chiamate al backend Python
  theme/                  6 temi, Personalizzato, Automatico, tinte delle etichette
  state/                  documenti, disposizione, preferenze
  shell/                  barra laterale, striscia compressa, gruppi, schede
  note/                   pagina della nota, editor, Anteprima
  views/                  Azioni, Calendario, Persone, Persona, Etichetta, Grafo, Impostazioni
  overlays/               ricerca, nota rapida, avvisi
```

La finestra principale usa la cornice di Windows: in WinForms una finestra senza cornice non si ridimensiona dai bordi. La nota rapida è senza cornice e si trascina dall'intestazione (`pywebview-drag-region`).

Regole per la fluidità:

- **Nessuna libreria di componenti.** CSS semplice con variabili per i temi. Nei gruppi di schede, cambiare tema cambia solo le variabili.
- **Le schede restano montate solo se servono:** l'`EditorState` di ogni scheda si conserva, ma esiste una sola vista CodeMirror per gruppo. L'`EditorState` sopravvive al componente: i suoi callback non devono leggere proprietà del componente, ma valori copiati alla creazione.
- **Elenchi lunghi virtualizzati:** obiettivo non ancora realizzato. Oggi bacheca e ricerca disegnano tutto; le azioni fatte senza data sono limitate a 30.
- **Salvataggio con un breve ritardo** e invio in sottofondo: scrivere non aspetta mai il disco.
- **Animazioni solo su `transform` e `opacity`**, disattivabili con `animations: false`.

## Sicurezza

Le note possono arrivare da Claude o da una cartella sincronizzata, quindi il loro contenuto non è affidabile.

- **Content Security Policy** inviata con la pagina: solo gli script dell'app e i dati d'avvio (con un nonce diverso a ogni risposta), nessuna connessione verso l'esterno, nessun `<object>`, `<iframe>` o form. Sono ammessi solo gli stili in linea, necessari a Svelte e CodeMirror. Il ponte di pywebview arriva da WebView2, non dalla pagina, quindi la politica non lo tocca.
- **HTML generato sempre sanificato** con DOMPurify (`note/preview.js`), senza stili, classi e id presi dalla nota. I link esterni passano da `open_url`, solo `http` e `https`.
- **Percorsi:** la pagina indica le note per id. Python risolve il percorso e controlla che resti nella cartella delle note.
- **Server locale:** ascolta solo su `127.0.0.1` e risponde solo con il prefisso segreto. Serve i file dell'interfaccia e, sotto `qnfile/`, solo immagini vere dentro la cartella delle note (riconosciute dai primi byte; niente SVG): rifiuta `..`, percorsi assoluti, le note stesse e i file di sistema.
- **Tasti globali** con `RegisterHotKey`: nessun hook sulla tastiera.

## Misure

| Comando | Cosa misura |
|---|---|
| `.venv/Scripts/python scripts/genera_note.py <cartella vuota> 1000` | Genera le note e misura indicizzazione, allineamento, ricerca e azioni |
| `node scripts/misura-avvio.mjs <cartella> [ripetizioni]` | Avvio a freddo: `dati pronti`, `indice allineato`, `prima pittura` e la riapertura da una seconda istanza. Usa `QUICKNOTES_TRACE=<file>`, in cui l'app scrive le tappe in ms dalla creazione del processo |
| `node scripts/cdp.mjs <cartella con 1000 note> "" scripts/misura-ricerca.mjs` | Ricerca Ctrl K a ogni tasto |
| `node scripts/cdp.mjs <cartella con demo-note.mjs> "" scripts/misura-latenza.mjs` | Scrittura (dalla traccia della timeline), cambio scheda e memoria |

**Prova con input di sistema veri:** `scripts/prova-sistema.mjs` usa `scripts/win.mjs`, che tiene aperto un PowerShell con poche funzioni Win32: elenca le finestre del processo, preme tasti e muove il mouse come una persona, manda all'icona dell'area di notifica il messaggio che WinForms riceve quando la si clicca (la sua finestra nascosta si chiama `QuickNotes · area di notifica`) e legge le voci del menu aperto per cliccarle. Così prova tasti globali, primo piano, Alt F4, menu, barra del titolo, bordi e trascinamento delle schede. Mentre gira il PC non va usato, e non deve esserci un'altra QuickNotes aperta.

## Come si sviluppa

| Comando | Effetto |
|---|---|
| `.venv/Scripts/python -m unittest discover -s tests` | Prove del nucleo e del server MCP, in cartelle temporanee |
| `npm --prefix frontend test` | Prove del frontend |
| `npm --prefix frontend run build` | Interfaccia compilata in `quicknotes/webui/` |
| `.venv/Scripts/python -m quicknotes [--debug]` | L'app, con gli strumenti di sviluppo se `--debug` |
| `node scripts/demo-note.mjs <cartella>` | Note di prova simili a quelle del design |
| `node scripts/cdp.mjs <cartella> <foto.png> [script.mjs]` | Avvia l'app in cartelle di prova, la guida via CDP, fotografa e segnala gli errori della pagina. `scripts/prova-*.mjs` sono le prove da usare come `script.mjs`; se una prova fallisce, stampa lo stato della pagina e la coda del registro |
| `node scripts/prova-python.mjs` | Prova completa dell'app su note di prova, senza altri preparativi |
| `node scripts/rilascio.mjs --note "…"` | `QuickNotes.zip` e la descrizione della release in `rilasci/v<versione>/`. Vedi [rilascio.md](rilascio.md) |
