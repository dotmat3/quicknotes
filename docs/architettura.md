# Architettura di QuickNotes

Questo documento descrive come è costruita la nuova app. Cosa deve fare l'app è in [piano-implementazione-design.md](piano-implementazione-design.md), l'ordine di lavoro è in [piano-incrementale.md](piano-incrementale.md).

Il riferimento visivo è la tavola **Home** del [design](https://claude.ai/artifact/1ZCTE9XczJ49BE4LQyGN2h) ("Homepage · icone, schede VS Code, contenuto in riquadro").

## Obiettivi

In ordine di priorità:

1. **Le note restano dell'utente.** File Markdown leggibili, compatibili con quelli già esistenti. L'indice si può sempre ricostruire.
2. **Avvio rapido.** La finestra deve mostrare contenuto vero prima che l'utente se ne accorga.
3. **Fluidità.** Scrivere, cambiare scheda e aprire una vista non devono mai perdere un fotogramma per colpa dell'I/O.
4. **Tutto in locale.** Nessun dato esce dal computer, e l'app funziona senza rete.

### Limiti misurabili

Sono obiettivi, non risultati: vanno misurati a ogni tappa (vedi [Misure](#misure)). Riferimento: questo PC, build di release, circa 1000 note.

| Misura | Obiettivo |
|---|---|
| Avvio a freddo fino alla nota di oggi visibile | < 400 ms |
| Finestra già attiva nell'area di notifica, Ctrl Alt N visibile | < 80 ms |
| Tasto premuto, carattere a schermo | < 16 ms |
| Cambio scheda | < 50 ms |
| Ricerca Ctrl K, risultati a ogni tasto | < 30 ms |
| Reindicizzazione incrementale all'avvio, senza modifiche | < 50 ms, senza bloccare l'interfaccia |
| Server MCP, dall'avvio alla prima risposta | < 50 ms |
| Memoria del processo Rust a riposo | < 40 MB, escluso WebView2 |

## Scelte tecniche

### Rust con Tauri 2, non un'interfaccia tutta nativa

| Opzione | Avvio | Editor con anteprima viva, tabelle, avvisi | Excalidraw | Esito |
|---|---|---|---|---|
| **Tauri 2 + WebView2** | Buono, con le accortezze sotto | CodeMirror 6, già usato prima | Sì, è un componente web | **Scelta** |
| Interfaccia nativa (egui, iced, Slint, gpui) | Ottimo | Da scrivere da zero, compresa l'impaginazione del testo | Non disponibile | Scartata |
| Electron | Lento, porta con sé un intero browser | CodeMirror 6 | Sì | Scartata |

L'avvio di WebView2 ha un costo che Rust non può eliminare. Lo si riduce così:

- **Una sola istanza, residente nell'area di notifica.** Chiudere la finestra la nasconde: riaprirla è quasi immediato.
- **Finestra nascosta finché la pagina non è disegnata**, con lo sfondo del tema già impostato. Niente lampi bianchi.
- **Dati pronti prima della pagina.** Rust legge configurazione e tema prima di creare la finestra e li inietta nella pagina con `initialization_script`, insieme all'id della nota di oggi. Il testo della nota arriva con la prima chiamata. Attenzione: questi dati restano quelli dell'avvio anche se la pagina si ricarica.
- **Prima la struttura, poi l'editor.** Il pacchetto iniziale contiene solo guscio e viste leggere. Il testo della nota compare subito; CodeMirror si carica subito dopo, in un blocco separato, e prende il suo posto senza spostare nulla.
- **Blocchi separati** per viste, Excalidraw e tutto ciò che non serve nella prima schermata.
- **Indice in sottofondo.** Nessuna operazione su disco sul thread principale.

Svelte 5 resta come strato di interfaccia perché compila in JavaScript piccolo, senza DOM virtuale. CodeMirror 6 aggiorna solo la parte visibile del documento, quindi regge note lunghe.

### Struttura del repository

```
Cargo.toml                 workspace Rust
crates/
  quicknotes-core/         note, indice, formato, regole. Nessuna dipendenza grafica
  quicknotes-mcp/          server MCP su stdio, eseguibile separato e leggero
  quicknotes-app/          app Tauri: comandi, finestre, tasti globali, area di notifica
frontend/                  Svelte 5 + CodeMirror 6, compilato da Vite
docs/
```

`quicknotes-mcp` è un eseguibile a parte perché lo avvia Claude a ogni sessione: non deve caricare WebView2 né tutto il resto. Condivide `quicknotes-core` con l'app, quindi le regole sul formato stanno in un solo punto.

### Dipendenze

| Compito | Crate o libreria | Note |
|---|---|---|
| Guscio, finestre, area di notifica | `tauri` 2 | |
| Tasti globali, istanza singola, apertura esterna | `tauri-plugin-global-shortcut`, `-single-instance`, `-opener` | |
| Indice e ricerca | `rusqlite` con `bundled` | SQLite compilato con FTS5, nessuna dipendenza dal sistema |
| Frontmatter | `serde_yaml_ng` | Solo per leggere e per scrivere i metadati modificati |
| Date | `time` o `chrono` | Da decidere alla tappa 1 |
| Modifiche esterne ai file | `notify` | Sostituisce la scansione a ogni interrogazione usata in precedenza |
| Cestino | `trash` | |
| MCP | Scritto a mano su `serde_json` | Solo strumenti e prompt; verificato con il client dell'SDK ufficiale |
| Microfono e riproduzione | `cpal`, `hound`, `rodio` | |
| Trascrizione locale | `whisper-rs` (whisper.cpp) | Dietro una feature: richiede CMake e libclang per compilare |
| Editor | CodeMirror 6, con `@codemirror/search` per Ctrl F e `@codemirror/language-data` per i blocchi di codice | Le grammatiche delle lingue si caricano solo quando compaiono; servono anche ai colori del codice nell'Anteprima |
| Apertura dei link web | `tauri-plugin-opener`, usato solo da Rust | |
| Grafo | `d3-force`, disegnato su canvas | Nel blocco della vista Grafo |
| Markdown nell'Anteprima e nell'esportazione | `marked` e `DOMPurify` | |

## Compatibilità con i dati esistenti

In `~/QuickNotes` e `~/.quicknotes` ci sono già note e configurazione reali. La nuova app li usa così com'è, e **non li modifica durante lo sviluppo**.

| Elemento | Comportamento |
|---|---|
| Cartella delle note | `notes_dir` da `~/.quicknotes/config.json`, oppure `QUICKNOTES_DIR` |
| Configurazione | Stesso file, oppure `QUICKNOTES_CONFIG_DIR`. Le chiavi sconosciute vengono conservate. I tasti in formato pynput (`<ctrl>+<alt>+n`) si convertono alla lettura |
| Id di una nota | Il nome del file senza estensione |
| Nota del giorno | `AAAA/MM/AAAA-MM-GG-giornata.md`, senza rinominare nulla |
| Meeting e note | `AAAA/MM/AAAA-MM-GG-HHMM-titolo.md` |
| Sintassi | `@persona`, `#tag`, `- [ ]`, `due:` (anche `entro:` e `scadenza:`), `!decisione` (anche `!decision`, `!dec`), `[[id\|Titolo]]`, `[[Titolo]]`. Si aggiungono `done:` e `![[….excalidraw]]` |
| Audio | `AAAA/MM/audio/<id>-HHMMSS.wav` e righe `🎙️ [Registrazione HH:MM (durata)](file)` |
| Trascrizioni | `### Trascrizione HH:MM`, con paragrafi `[mm:ss]`. `parser::recordings` e `parser::transcript_lines` le leggono per Calendario e Ctrl K; una registrazione cade nel giorno della nota che la contiene, perché il nome del WAV non ha la data |
| Immagini | `images/` accanto alla nota, con `![](images/…)` |
| Indice | **Nuovo file** `<note>/.quicknotes/index-v3.db`. Il vecchio `index.db` non viene toccato, così la vecchia versione continua a funzionare |

**Un salvataggio non riscrive ciò che non è cambiato.** Il frontmatter resta testo esattamente com'era finché non si modificano i metadati. La versione precedente lo riscriveva a ogni salvataggio; qui un file non cambia mai forma senza motivo. Anche gli a capo restano quelli del file.

**Isolamento durante lo sviluppo:** ogni test e ogni avvio di prova usano cartelle temporanee, tramite `QUICKNOTES_DIR` e `QUICKNOTES_CONFIG_DIR`. Lo script di sviluppo le imposta da solo.

## Backend

### `quicknotes-core`

| Modulo | Compito |
|---|---|
| `parser` | Frontmatter, persone, etichette, azioni con madre e descrizione, decisioni, link, sezioni, registrazioni e righe delle trascrizioni. Funzioni pure |
| `edit` | Modifiche su una riga o su un corpo: `with_done`, `with_due`, `with_person`, `with_tag`, `with_description`, `add_to_section`. Funzioni pure |
| `store` | Lettura e scrittura atomica dei file, una sola fonte di verità |
| `index` | Schema SQLite, indicizzazione incrementale, interrogazioni |
| `dates` | Titolo del giorno, etichette e gruppi delle scadenze |
| `views` | Dati pronti per le viste: `sidebar`, `action_board`, `calendar_data`, `person_page`, `tag_page`, `graph_data`, `search_all` |

**Ctrl K (`search_all`):** note dalla ricerca a testo pieno (15), poi, se una parola ha almeno tre lettere, azioni aperte e decisioni che contengono tutte le parole (5 ciascuna) e le righe `[mm:ss]` delle trascrizioni nelle note già trovate (5). Ogni risultato porta la riga della nota, che si apre mostrandola. I testi per le trascrizioni si leggono dai file: per 15 note costa meno che cercarli nell'indice a testo pieno, dove il percorso non ha un indice.
| `config` | Lettura e scrittura della configurazione |

Il riconoscimento di `@` e `#` è scritto a mano e non usa espressioni regolari: quelle originali usano asserzioni all'indietro, che la libreria `regex` di Rust non supporta. Così è anche più veloce. I test ne fissano il comportamento.

### Concorrenza

- **Le scritture passano da un solo lock** su file e indice. Due salvataggi non possono mai incrociarsi.
- **Le letture** usano una connessione SQLite separata in modalità WAL, quindi non aspettano mai una scrittura.
- **All'avvio** un thread in sottofondo allinea l'indice ai file; le viste si aggiornano quando finisce. L'interfaccia non resta mai in attesa.
- **`notify`** segnala le modifiche esterne, da Obsidian, da Claude o da una sincronizzazione. Gli eventi arrivano raggruppati, e l'app riconosce e ignora le proprie scritture.
- **Il server MCP** è un altro processo. Scrive sugli stessi file, e l'indice è protetto da WAL e `busy_timeout`. L'app vede le sue modifiche grazie a `notify`.

### Comandi verso l'interfaccia

I comandi Tauri sono funzioni `async` che non bloccano il thread principale. Restituiscono JSON, e la pagina non riceve mai percorsi da usare direttamente. Gli aggiornamenti arrivano come eventi: `index-updated`, `note-changed`, `recording-state`.

## Frontend

```
frontend/src/
  main.js                 sceglie la finestra (principale, cattura, registrazione)
  api.js                  chiamate al backend
  theme/                  6 temi, Personalizzato, Automatico, tinte delle etichette
  state/                  documenti, disposizione, preferenze
  shell/                  barra laterale, striscia compressa, gruppi, schede
  note/                   pagina della nota, editor, Anteprima
  views/                  Azioni, Calendario, Persone, Persona, Etichetta, Grafo, Impostazioni
  overlays/               ricerca, popover, esportazione, avvisi
```

Regole per la fluidità:

- **Nessuna libreria di componenti.** CSS semplice con variabili per i temi. Nei gruppi di schede, cambiare tema cambia solo le variabili.
- **Le schede restano montate solo se servono:** l'`EditorState` di ogni scheda si conserva, ma esiste una sola vista CodeMirror per gruppo. L'`EditorState` sopravvive al componente: i suoi callback non devono leggere proprietà del componente, ma valori copiati alla creazione.
- **Elenchi lunghi virtualizzati:** obiettivo non ancora realizzato. Oggi bacheca e ricerca disegnano tutto; le azioni fatte senza data sono limitate a 30.
- **Salvataggio con un breve ritardo** e invio in sottofondo: scrivere non aspetta mai il disco.
- **Animazioni solo su `transform` e `opacity`**, disattivabili con `animations: false`.

## Sicurezza

Le note possono arrivare da Claude o da una cartella sincronizzata, quindi il loro contenuto non è affidabile. Valgono le regole già scritte nel piano del design, in forma più forte con Tauri:

- **CSP rigida:** nessuno script esterno, nessuna connessione di rete. Font inclusi nel pacchetto. Sono ammessi solo gli stili in linea, necessari a Svelte e CodeMirror.
- **Permessi Tauri minimi**, finestra per finestra. La barra del titolo ha una capability a parte (`titlebar.json`), solo per la finestra principale.
- **HTML generato sempre sanificato** con DOMPurify (`note/preview.js`), senza stili, classi e id presi dalla nota. I link esterni passano da `open_url`, solo `http` e `https`. Gli `on…` scritti in una nota fanno comparire in console una segnalazione della CSP mentre DOMPurify legge l'HTML: WebView2 la produce con qualsiasi modo di analizzarlo, e il gestore non viene mai eseguito.
- **`open_file`** rifiuta eseguibili e percorsi che escono dalla cartella delle note, e chiede conferma per i file esterni. Non ancora realizzato: arriva con la tappa 13.
- **Percorsi:** la pagina indica le note per id. Rust risolve il percorso e controlla che resti nella cartella delle note.

## Misure

`node scripts/cdp.mjs <cartella con demo-note.mjs> "" scripts/misura-latenza.mjs` misura scrittura (dalla traccia della timeline), cambio scheda e memoria. Con le 1000 note di `genera_note`, `scripts/misura-ricerca.mjs` misura la ricerca Ctrl K a ogni tasto.

L'app registra i tempi delle fasi di avvio in un file se è impostata `QUICKNOTES_TRACE=<file>`: `main`, `dati pronti`, `finestra creata`, `indice allineato`, `prima pittura`. `node scripts/misura-avvio.mjs <cartella>` ripete l'avvio e dà le mediane. `cargo run --release -p quicknotes-core --example genera_note -- <cartella vuota> 1000` genera le note e misura indice e ricerca.

I risultati vanno annotati in [piano-incrementale.md](piano-incrementale.md) a ogni tappa che può peggiorarli.

**Prova con input di sistema veri:** `scripts/prova-sistema.mjs` usa `scripts/win.mjs`, che tiene aperto un PowerShell con poche funzioni Win32: elenca le finestre del processo, preme tasti e muove il mouse come una persona, manda all'icona dell'area di notifica lo stesso messaggio che le manda Esplora risorse quando la si clicca, e legge le voci del menu aperto per cliccarle. Così prova tasti globali, primo piano, Alt F4, menu, barra del titolo, bordi e trascinamento delle schede. Mentre gira il PC non va usato, e non deve esserci un'altra QuickNotes aperta, che prenderebbe i tasti globali.

## Come si sviluppa

| Comando | Effetto |
|---|---|
| `cargo test --workspace` | Test del backend, in cartelle temporanee |
| `npm --prefix frontend test` | Test del frontend |
| `npm --prefix frontend run build`, poi `cargo build --release -p quicknotes-app` | App di release in `target/release/quicknotes.exe`, con l'interfaccia inclusa |
| `node scripts/demo-note.mjs <cartella>` | Note di prova simili a quelle del design |
| `node scripts/cdp.mjs <cartella> <foto.png> [script.mjs]` | Avvia l'app in cartelle di prova, la guida via CDP, fotografa e segnala gli errori della pagina. `scripts/prova-*.mjs` sono le prove da usare come `script.mjs` |

La compilazione richiede Rust e gli MSVC Build Tools.
