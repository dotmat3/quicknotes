# QuickNotes

Note rapide per meeting e giornate di lavoro, salvate come semplici file Markdown sul tuo computer e
consultabili da Claude tramite MCP. Nessun dato esce dal computer.

- **App desktop** per Windows: nota del giorno, editor Markdown con anteprima viva, azioni con scadenze,
  calendario, persone ed etichette, grafo dei collegamenti, ricerca Ctrl K, nota rapida con un tasto globale.
- **Server MCP**: Claude cerca, legge, elenca azioni e decisioni, e può scrivere nelle note se glielo chiedi.

## Installazione

Scarica `QuickNotes.zip` dall'[ultima release](https://github.com/dotmat3/quicknotes/releases/latest).
Dentro c'è tutto, Python compreso: non si installa nulla e non servono permessi di amministratore.

1. Prima di estrarlo: tasto destro sullo zip → Proprietà → spunta **Sblocca**.
2. Estrai la cartella dove vuoi, per esempio in `Documenti`.
3. Apri `QuickNotes.cmd`. L'app resta nell'area di notifica accanto all'orologio: chiudere la finestra la
   nasconde, per uscire usa il menu dell'icona.

Se non parte, `Verifica.cmd` controlla WebView2, .NET, cartelle e tasti globali e scrive cosa manca in
`verifica-quicknotes.txt`. Serve Windows 10 o 11 a 64 bit con WebView2, già presente nelle versioni recenti.

Le note finiscono in `%USERPROFILE%\QuickNotes`, la configurazione in `%USERPROFILE%\.quicknotes\config.json`
(per cambiare cartella: `"notes_dir"`). Avvio con Windows e tema si scelgono nelle Impostazioni (Ctrl+,).

Per aggiornare: chiudi QuickNotes dal menu dell'icona, sostituisci la cartella con quella nuova e, se l'avevi
attivato, riattiva l'avvio con Windows. Le note non si toccano.

## Collegarlo a Claude

Impostazioni → **Claude** mostra la configurazione già pronta, con il percorso del Python della tua cartella.

- **Claude Desktop**: menu Claude → Impostazioni → Sviluppatore → *Modifica configurazione*, incolla la voce
  `quicknotes` dentro `mcpServers`, salva e **chiudi del tutto** Claude Desktop prima di riaprirlo.
- **Claude Code**: il comando `claude mcp add …` mostrato nella stessa pagina.

Esempi di domande:
- "Cosa abbiamo deciso con il cliente X a ottobre?"
- "Quali azioni ho aperte con scadenza questa settimana?"
- "Preparami un briefing per il meeting di domani con Laura" (c'è anche il prompt `briefing_meeting`)
- "Fammi il riepilogo della settimana e salvalo come nota" (prompt `riepilogo_settimanale`)

| Strumento | Cosa fa |
|---|---|
| `search_notes` | ricerca per parole (anche parziali) con filtri data, persona, progetto, tipo |
| `list_notes` | elenco cronologico con gli stessi filtri |
| `read_note`, `read_daily_note` | una nota o la nota di un giorno, con i collegamenti in uscita e in entrata |
| `get_backlinks` | note che citano una nota con `[[link]]`, con la riga in cui lo fanno |
| `list_action_items` | azioni per stato, responsabile, progetto, area, scadenza o `scheduled:` (senza i progetti in pausa, se non richiesto) |
| `list_decisions` | decisioni registrate con `!decisione` |
| `list_people_and_projects` | persone e progetti citati, con conteggi |
| `create_note`, `append_to_note`, `append_to_daily_note` | scrittura, solo se glielo chiedi |
| `set_action_status` | spunta, riapre o cambia lo stato di un'azione, e ne imposta `scheduled:` |
| `list_projects` | progetti con stato, alias, aree e azioni aperte |
| `agenda` | cosa fare adesso: in ritardo, oggi, in corso, in attesa, domande, prossimi 7 giorni, da smistare |
| `weekly_review` | i passi della Revisione settimanale e il riepilogo della settimana |

## Come si scrive

| Scrivi | Significa |
|---|---|
| `- [ ] @Marco invia preventivo due:2026-10-31` | azione con responsabile e scadenza (anche `entro:`, `scadenza:`) |
| `- [/]` · `- [w] … @Laura` · `- [?]` · `- [-]` | in corso · in attesa di Laura · domanda aperta · annullata (il motivo nella descrizione) |
| `scheduled:2026-11-12` | il giorno in cui farla: compare in Agenda; la scadenza resta `due:` |
| `    - [ ] testo` | sotto-attività, rientrata sotto un'azione |
| `- [x] … done:2026-11-03` | azione fatta: la data la scrive la spunta |
| `@Marco`, `#clientex`, `#llm-training/dedup` | persona, etichetta o progetto, progetto con area |
| `… !decisione` | decisione presa (anche `!dec`) |
| `[[Titolo]]`, `[[id\|Testo]]` | link a un'altra nota: dopo `[[` l'editor propone le note |

Nell'editor: **Ctrl+T** trasforma la riga in azione (di nuovo: la spunta), **Ctrl+D** la segna come
decisione, **Ctrl+Shift+H** inserisce l'ora, **Ctrl+V** o il trascinamento salvano un'immagine in `images/`
accanto alla nota. Nella ricerca **Ctrl+K** si combinano filtri e parole: `@laura #clientex budget`,
`!budget` cerca solo tra le decisioni. Tutte le scorciatoie sono nella Guida dell'app (**F1**).

Nella vista **Azioni**, **N** apre l'aggiunta rapida: `Valutare MinHash #llm-training/dedup @Marco entro:venerdì
!alta` finisce nella nota del progetto, sotto `### dedup`; senza progetto va nella nota `da-smistare.md`, che
Agenda e Revisione mostrano tra le azioni da smistare. Nella vista non si aggiunge più nulla alla nota di oggi.
**/** porta al campo Filtra (`#progetto/area @persona !alta stato:attesa entro:settimana nota:titolo`, un `-`
davanti esclude); **Filtri** apre le scelte multiple per progetto, area, stato, priorità, scadenza, persona e
tipo di nota, e una combinazione si può salvare come vista.

Tasti globali, anche con l'app nascosta: **Ctrl+Alt+N** nota rapida, **Ctrl+Alt+D** nota del giorno. Si
cambiano in `config.json`, sotto `"hotkeys"`.

## Struttura dei dati

```
%USERPROFILE%\QuickNotes\
  2026\11\
    2026-11-03-giornata.md
    2026-11-03-1000-kickoff-cliente-x.md
    images\2026-11-03-101530.png
  .quicknotes\index-v4.db        indice di ricerca, si ricostruisce dai file
```

### Progetti, Agenda e Revisione

Il daily resta il posto dove catturi e scrivi il log; le azioni vivono in una nota corta per progetto
(`progetti/llm-training.md`, con `type: project`, `status`, `aliases`, `areas` e `## Prossime azioni`
divise per `### area`). Sotto `# LLM Training` in un daily le azioni appartengono già al progetto. La vista
**Progetto** raccoglie da tutte le note azioni per area, attese, domande, decisioni, note collegate e log dei
daily; **Agenda** dice cosa fare adesso; **Revisione** guida la pulizia del venerdì. "Sposta nel progetto"
porta un'azione dal daily alla nota del progetto, "Archivia fatte" toglie dalla nota del progetto le azioni
chiuse. Le note scritte prima della 0.6.0 si migrano dall'app (Ctrl K › Migra le note, o Impostazioni › Note):
la vista propone le note di progetto e le righe da cambiare regola per regola, si sceglie cosa applicare e prima
di scrivere si copia la cartella. Lo stesso da riga di comando: `scripts/migra_note.py --dry-run`.

I file sono la fonte di verità: si possono modificare con qualsiasi editor (anche Obsidian o VS Code),
sincronizzare o mettere sotto git. L'indice si riallinea da solo quando un file cambia;
`python -m quicknotes reindex` lo ricostruisce da zero. Se Claude scrive in una nota aperta nell'app,
l'app la ricarica.

## Micio

Un gatto in pixel art che cammina o gioca in fondo alle schede, sopra le note. La vista Micio è la sua stanza:
ci sono un negozio di oggetti, la scelta di mantello e dimensione e il minigioco «Pioggia di pesci».
Ogni azione completata da quando c'è Micio vale 5 crocchette, che si contano dall'indice. Valgono quindi anche
le azioni spuntate in Obsidian o da Claude. Preferenze, oggetti e crocchette spese stanno in `config.json`
(chiave `ui.pet`).

Lo sprite viene dal [Cat Pack di Glem](https://octopusinkus.itch.io/cat-pack), versione gratuita. Il gatto nero
è diviso in tre livelli (corpo da tingere, dettagli, occhi) in `frontend/src/pet/sprite/`. Le animazioni sono in
`frontend/src/pet/animazioni.js` e si calibrano fotogramma per fotogramma con il Banco animazioni.

## Sviluppo

Serve Python 3.12 a 64 bit e Node 20 o successivo.

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -e .
cd frontend && npm install && npm run build && cd ..   # interfaccia in quicknotes/webui/
.venv/Scripts/python -m quicknotes                      # --debug apre gli strumenti di sviluppo
```

`npm run dev` apre l'interfaccia nel browser con dati di ripiego, senza Python, per lavorare sulla grafica.

Prove:

```bash
.venv/Scripts/python -m unittest discover -s tests            # formato, archivio, viste, server MCP
cd frontend && npx vitest run && cd ..                        # regole dell'editor
node scripts/prova-python.mjs                                 # l'app vera, su note di prova
node scripts/demo-note.mjs <cartella>                         # note di esempio per le prove sotto
node scripts/cdp.mjs <cartella> foto.png scripts/prova-viste.mjs
node scripts/demo-progetti.mjs <cartella>                     # progetti e stati, per prova-agenda.mjs
node scripts/cdp.mjs <cartella> foto.png scripts/prova-agenda.mjs
node scripts/demo-migrazione.mjs <cartella>                   # note nel formato di prima, per prova-migrazione.mjs
node scripts/cdp.mjs <cartella> foto.png scripts/prova-migrazione.mjs
```

Le prove `scripts/prova-*.mjs` guidano l'app vera tramite CDP. `prova-sistema.mjs` e l'ultimo passaggio
di `prova-immagini.mjs` usano mouse, tastiera e appunti veri: durante quelle il PC non va usato.

Rilascio: `node scripts/rilascio.mjs` costruisce `QuickNotes.zip` (con `scripts/costruisci.py`) e la
descrizione della release in `rilasci/v<versione>/`. Vedi [docs/rilascio.md](docs/rilascio.md).

```
quicknotes/
  parser.py      formato delle note: frontmatter, @persone, #etichette, azioni, decisioni, link
  edit.py        modifiche a una riga o a una sezione (spunta, scadenza, persona, etichetta, descrizione)
  index.py       indice SQLite con ricerca a testo pieno (FTS5)
  store.py       file e indice: lettura, scrittura atomica, allineamento, azioni, immagini
  views.py       dati per le viste: bacheca, calendario, persone, etichette, grafo, Ctrl K
  commands.py    i comandi chiamati dalla pagina
  app.py         finestre pywebview, server locale, area di notifica, nota rapida, tasti globali
  mcp.py         server MCP su stdio
  check.py       python -m quicknotes verifica
frontend/        interfaccia: Svelte 5 + CodeMirror 6, compilata in quicknotes/webui/
scripts/         prove dal vivo, misure, costruzione e rilascio
tests/           prove del nucleo e del server MCP
```

L'architettura è descritta in [docs/architettura.md](docs/architettura.md).
