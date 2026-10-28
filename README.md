# QuickNotes

Note rapide per meeting e giornate di lavoro, salvate come semplici file Markdown sul tuo
computer e consultabili da Claude tramite MCP. Si installa con `pip`: l'interfaccia è già
compilata nel pacchetto, Node non serve per usarla.

- **App desktop**: cattura rapida con tasti globali, nota del giorno, ricerca, azioni aperte.
- **Registrazione**: un tasto avvia/ferma il microfono; alla fine l'audio viene trascritto
  **in locale** (faster-whisper) e aggiunto alla nota. Nessun dato esce dal computer.
- **Server MCP**: Claude cerca, legge, elenca azioni e decisioni, e può scrivere nelle note.

## Installazione

Serve Python 3.10 o successivo. La finestra usa WebView2 (Edge), già presente su Windows 10 e 11.
Dalla cartella del progetto:

```bash
python -m venv .venv
# Windows:            .venv\Scripts\activate
# macOS / Linux:      source .venv/bin/activate
pip install -e .
```

Poi avvia l'app:

```bash
python -m quicknotes          # oppure, su Windows senza finestra di console: pythonw -m quicknotes
```

Le note finiscono in `~/QuickNotes` (cambiabile in `~/.quicknotes/config.json`).
L'aspetto segue il tema chiaro/scuro del sistema; per forzarlo imposta `"theme": "light"` o `"dark"`
nello stesso file (oppure con i pulsanti in fondo alla barra laterale). Con `"animations": false`
l'interfaccia diventa istantanea, senza transizioni.
`python -m quicknotes where` mostra i percorsi in uso.

## Collegarlo a Claude

```bash
python -m quicknotes claude-config
```

stampa il blocco JSON già pronto, con il percorso esatto del Python del tuo ambiente.

**Claude Desktop**: menu Claude → Impostazioni → Sviluppatore → *Modifica configurazione*,
incolla la voce `quicknotes` dentro `mcpServers`, salva e **chiudi del tutto** Claude Desktop
prima di riaprirlo. Il server compare tra i connettori del menu "+" nella casella di testo.

**Claude Code**: il comando stampato da `claude-config`, ad esempio
`claude mcp add --transport stdio --scope user quicknotes -- "/percorso/.venv/bin/python" -m quicknotes mcp`.

Esempi di domande:
- "Cosa abbiamo deciso con il cliente X a ottobre?"
- "Quali azioni ho aperte con scadenza questa settimana?"
- "Preparami un briefing per il meeting di domani con Laura" (c'è anche il prompt `briefing_meeting`)
- "Fammi il riepilogo della settimana e salvalo come nota" (prompt `riepilogo_settimanale`)

### Tool esposti a Claude

| Tool | Cosa fa |
|---|---|
| `search_notes` | ricerca per parole (anche parziali) con filtri data, persona, progetto, tipo |
| `list_notes` | elenco cronologico con gli stessi filtri |
| `read_note`, `read_daily_note` | contenuto completo di una nota / del diario di un giorno |
| `list_action_items` | azioni aperte o fatte, per responsabile, progetto, scadenza |
| `list_decisions` | decisioni registrate con `!decisione` |
| `list_people_and_projects` | persone e progetti citati, con conteggi |
| `create_note`, `append_to_note`, `append_to_daily_note` | scrittura (solo se glielo chiedi) |
| `set_action_status` | spunta o riapre un'azione |

## Come si scrive

| Scrivi | Significa |
|---|---|
| `@Marco` | persona citata |
| `#clientex` | tag o progetto |
| `- [ ] @Marco invia preventivo due:2026-10-31` | azione con responsabile e scadenza |
| `- [x] ...` | azione fatta |
| `... !decisione` | decisione presa |

Scorciatoie nell'editor: **Ctrl+T** trasforma la riga in azione (di nuovo: la spunta),
**Ctrl+D** la marca come decisione, **Ctrl+Shift+H** inserisce l'ora, **Invio** continua
l'elenco (Invio su una voce vuota lo chiude), **Ctrl+F** cerca, **Ctrl+N** nuovo meeting,
**Ctrl+Shift+N** nuova nota. Scrivendo `@` o `#` l'editor propone persone e progetti già usati.

Nella ricerca puoi combinare filtri e parole: `@laura #clientex budget`.

## Tasti globali

Funzionano anche con l'app nascosta nell'area di notifica:

| Tasti | Azione |
|---|---|
| Ctrl+Alt+N | nuovo meeting |
| Ctrl+Alt+D | nota del giorno |
| Ctrl+Alt+R | avvia/ferma registrazione |

Si cambiano in `~/.quicknotes/config.json` (formato pynput, es. `"<cmd>+<shift>+n"`).

- **macOS**: alla prima esecuzione concedi a Terminale (o all'app da cui lanci Python)
  i permessi *Accessibilità* e *Monitoraggio input*, e *Microfono* per registrare.
- **Linux con Wayland**: i tasti globali di pynput non funzionano. Associa nelle
  impostazioni di sistema una scorciatoia ai comandi `python -m quicknotes new`,
  `... daily`, `... record`: se l'app è aperta ricevono il comando, altrimenti la avviano.
  Lo stesso trucco funziona ovunque, ad esempio da un launcher.

## Registrazione e trascrizione

L'audio è salvato in WAV accanto alla nota (`AAAA/MM/audio/`) e collegato nel testo. Al
termine parte la trascrizione in sottofondo, aggiunta sotto `### Trascrizione HH:MM` a
paragrafi con il minutaggio `[mm:ss]`, così Claude può citarla.

- Il modello Whisper viene **scaricato al primo uso** (`small` ≈ 500 MB) e poi resta in cache.
- Su CPU `small` trascrive circa alla velocità del parlato; per più velocità usa `base`,
  per più qualità `medium` o `large-v3` (meglio con GPU NVIDIA). Si imposta in
  `whisper_model` nel file di configurazione; `"transcribe_after_recording": false` la disattiva.
- Se la trascrizione fallisce l'audio resta comunque salvato.
- Avvisa i partecipanti quando registri un meeting.

## Struttura dei dati

```
~/QuickNotes/
  2026/10/
    2026-10-27-giornata.md
    2026-10-27-1000-kickoff-cliente-x.md
    audio/2026-10-27-1000-kickoff-cliente-x-100215.wav
  .quicknotes/index.db        indice di ricerca (ricostruibile)
```

I file sono la fonte di verità: puoi modificarli con qualsiasi editor (anche Obsidian o
VS Code), sincronizzarli con il cloud che preferisci o metterli sotto git. L'indice si
riallinea da solo; `python -m quicknotes reindex` lo ricostruisce da zero. Se Claude scrive
in una nota aperta nell'app, l'app la ricarica automaticamente.

## Sviluppo

```bash
pip install -e ".[dev]"
pytest
```

```
quicknotes/
  parser.py       formato note e convenzioni (@, #, azioni, decisioni)
  store.py        archivio su file + indice SQLite FTS5
  mcp_server.py   tool e prompt MCP
  audio.py        microfono e trascrizione (faster-whisper)
  recording.py    registrazione collegata a una nota e trascrizione in sottofondo
  service.py      logica dell'interfaccia senza grafica: elenchi, salvataggio, conflitti, eliminazione
  formatting.py   date, scadenze e anteprime leggibili
  icons.py        icona dell'app (Pillow)
  app.py          finestra pywebview, API per la pagina, area di notifica, tasti globali, istanza singola
  webui/          frontend compilato (generato da frontend/, incluso nel pacchetto)
frontend/         sorgenti dell'interfaccia: Svelte 5 + CodeMirror 6
  src/state.svelte.js     stato dell'app, salvataggio automatico, eventi da Python
  src/editor/             anteprima viva del Markdown, comandi Ctrl+T/D/Shift+H, completamento
  src/components/         barra laterale, elenchi, pagina della nota, dialog
```

La finestra è pywebview: su Windows usa WebView2, cioè Chromium, lo stesso motore di Obsidian.
La pagina chiama i metodi di `Api` in `app.py` (`window.pywebview.api.<metodo>`), Python le manda
eventi con `window.qnEvent(nome, dati)`.

Node serve **solo per modificare l'interfaccia**: il risultato della compilazione finisce in
`quicknotes/webui/`, che va ricompilato e incluso a ogni modifica di `frontend/`.

```bash
cd frontend
npm install
npm run build                     # compila in quicknotes/webui/
npm run dev                       # server di sviluppo; poi, in un altro terminale:
python -m quicknotes --dev        # finestra collegata al server di sviluppo (ricarica a caldo)
# http://localhost:5173/?mock     anteprima nel browser con dati finti, senza Python
```

## Idee per i prossimi passi

- Avvio automatico all'accesso al sistema
- Integrazione calendario per precompilare titolo e partecipanti dei meeting
- Ricerca semantica (embedding locali) accanto a quella testuale
- Riconoscimento di chi parla nella trascrizione
- Modelli di nota personalizzabili (es. 1:1, retro, colloquio)
