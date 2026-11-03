# Piano incrementale

Ordine di lavoro per costruire QuickNotes in Rust. Alla fine di ogni tappa c'è qualcosa che funziona e si può provare. Le regole di prodotto sono in [piano-implementazione-design.md](piano-implementazione-design.md), le scelte tecniche in [architettura.md](architettura.md).

**Legenda:** ⬜ da fare · 🟡 in corso · ✅ fatta e verificata

## Come riprendere il lavoro

Stato al 3 novembre 2026, dopo la chiusura delle tappe 6, 7 e 8.

**Git:** il lavoro è sul ramo `rust-tauri`. `main` resta al commit `eb05f3e`, quello della versione Python, il cui codice cancellato si legge con `git show eb05f3e:<percorso>`. Le modifiche locali a `README.md` sono dell'utente: non vanno incluse nei commit e non vanno perse.

**Per ripartire:**

1. Leggere questo file, [architettura.md](architettura.md) e [piano-implementazione-design.md](piano-implementazione-design.md). Il riferimento visivo è la tavola Home del [design](https://claude.ai/artifact/1ZCTE9XczJ49BE4LQyGN2h), che si legge con l'azione `read` dello strumento Artifact e `path: "project/Home.dc.html"`.
2. In Git Bash Rust non è nel `PATH`: serve `export PATH="$HOME/.cargo/bin:$PATH"`.
3. Controllare che tutto sia ancora verde:

```bash
cargo test --workspace --exclude quicknotes-app
npm --prefix frontend test
npm --prefix frontend run build
cargo build --release -p quicknotes-app -p quicknotes-mcp
node scripts/demo-note.mjs <cartella di prova vuota>
node scripts/cdp.mjs <cartella di prova> foto.png scripts/prova-azioni.mjs
```

**Le prove nell'app vera** (`node scripts/cdp.mjs <cartella> "" scripts/<prova>`), da usare sempre con una cartella di prova nuova:

| Prova | Cartella | Note |
|---|---|---|
| `prova-editor.mjs` | Vuota | |
| `prova-azioni.mjs`, `prova-viste.mjs`, `prova-desktop.mjs`, `prova-modalita.mjs`, `prova-gruppi.mjs` | Con `demo-note.mjs` | |
| `misura-latenza.mjs` | Con `demo-note.mjs` | Stampa le misure di scrittura, cambio scheda e memoria |
| `prova-schede.mjs`, poi `prova-riavvio.mjs` | Con `demo-note.mjs` | Stessa cartella e stesso `QN_CFG=<cartella cfg>`. La prima chiude l'app, quindi aspettare 2 secondi prima della seconda |

Se una prova stampa `ERRORI DELLA PAGINA`, va considerata fallita anche quando tutti i controlli `ok:` sono passati. Una prova può dichiarare gli errori che provoca di proposito con `export const expectedErrors`: `cdp.mjs` li conta a parte.

**Strumenti già installati su questo PC:** Rust 1.99 con Rustup, Visual Studio Build Tools 2022, Node 23. Non ci sono CMake né libclang, che serviranno a `whisper-rs` alla tappa 12.

**Dati reali:** `~/QuickNotes` e `~/.quicknotes` contengono le note vere dell'utente e finora non sono stati toccati. Ogni prova deve usare `QUICKNOTES_DIR` e `QUICKNOTES_CONFIG_DIR`, come fanno gli script. Avviare `target/release/quicknotes.exe` a mano, senza queste variabili, lavora sulle note vere e crea la nota del giorno.

**Limiti dell'ambiente:** in Git Bash i comandi molto lunghi con heredoc possono fallire con `unexpected EOF`; meglio scrivere i file con lo strumento apposito. `ln -s` copia le cartelle invece di collegarle.

### Prossimi passi, in ordine

1. **Chiudere le tappe in corso:** vedi "Resta da fare" sotto ciascuna. Le più utili: registrazioni nel Calendario e scelta della nota nel Grafo (9), il tempo della ricerca a ogni tasto (10), il confronto a schermo dei temi mai guardati (5).
2. **Provare a mano ciò che le prove automatiche non raggiungono:** tasti globali, menu dell'area di notifica, chiusura con la X, finestra nota rapida che compare davvero.
3. **Tappa 12, audio.** Il pulsante Registra oggi non fa nulla nella barra aperta e mostra un avviso nella striscia.
4. **Tappe 13-15:** file ed esportazione, schizzi, rilascio.

### Da decidere con l'utente

- **Pulsanti `+` delle pillole:** nascosti lasciano a volte una riga vuota nelle schede; mostrandoli al passaggio del mouse senza riservare spazio, le schede si sposterebbero sotto il puntatore.
- **Proposte ancora non confermate** in [piano-implementazione-design.md](piano-implementazione-design.md#proposte-non-ancora-confermate), tra cui figlia in ritardo e figlie in Calendario.
- **Note del giorno vuote:** l'app le crea a ogni avvio e con le frecce, e il Calendario con "Crea la nota del giorno".

### Difetti e limiti noti

- **Nota rapida subito dopo l'avvio:** la finestra si prepara dopo circa 1,5 secondi. Prima di allora Ctrl Alt N apre la finestra principale.
- **Calendario:** le registrazioni non compaiono ancora. "Ieri" e "domani" non sono nel pannello rapido di Oggi, a differenza della tavola Home.
- **Pagina Persona:** le azioni si possono solo leggere, senza spunta né pillole. Il piano del design prevede le pillole solo in bacheca, elenco e pagina etichetta.
- **Scorciatoia Ctrl K W** non implementata, come proposto nel piano del design. Ctrl W e Ctrl 1…6 funzionano in WebView2: la pagina li riceve prima del browser.
- **Tema all'avvio:** lo sfondo iniziale della finestra è sempre scuro, ma non si vede perché la finestra resta nascosta fino alla prima pittura.
- **`quicknotes-mcp.exe`** non è ancora incluso nell'installer; le Impostazioni avvisano se manca accanto all'app.
- **README** descrive ancora la versione Python: si aggiorna alla tappa 15.
- **Grafo:** mostra solo i collegamenti attorno alla nota di oggi, con una disposizione a cerchio semplice.
- **Anteprima e tabelle:** immagini e file collegati mostrano solo il nome, finché la tappa 13 non porta l'apertura sicura dei file. I link a file non si aprono.
- **Menu `⋯`:** contiene solo le modalità. Esporta, Allega un file e Inserisci uno schizzo arrivano con le tappe 13 e 14.
- **Dipendenze di sviluppo:** `npm audit` segnala avvisi su `vitest` e sul plugin Svelte di Vite. Non finiscono nel pacchetto dell'app.

## Criteri validi per ogni tappa

- `cargo test --workspace` e i test del frontend passano.
- Nessuna prova tocca `~/QuickNotes` o `~/.quicknotes`.
- Se la tappa può peggiorare i tempi, le misure vengono riprese e annotate in [Misure raccolte](#misure-raccolte).

## Tappe

### ✅ 0. Strumenti e struttura

Rust, MSVC, workspace, `.gitignore`, dati di prova.
**Fatta quando:** `cargo build --workspace` funziona da zero.

### ✅ 1. Il formato delle note (`parser`, `edit`, `dates`)

Frontmatter conservato com'è, `@`, `#`, azioni con madre e descrizione, `due:`, `done:`, decisioni, `[[link]]`, sezioni, `![[…]]`. Modifiche su riga: `with_done`, `with_due`, `with_person`, `with_tag`, `with_description`, `add_to_section`. Titolo del giorno e gruppi delle scadenze.
**Fatta quando:** i test coprono i casi elencati nel piano del design e i casi limite della versione precedente, comprese le note in formato vecchio.

### ✅ 2. Archivio e indice (`store`, `index`)

Scrittura atomica, nuove note, nota del giorno, indicizzazione incrementale, ricerca FTS5, azioni, decisioni, persone, etichette, link in entrata.
**Fatta quando:** una copia delle note reali si indicizza senza errori e le risposte sono coerenti; misurati i tempi con ~1000 note.

### ✅ 3. Server MCP (`quicknotes-mcp`)

Gli strumenti e i prompt della versione precedente, con `done:` scritto dalla stessa operazione usata dall'app.
**Fatta quando:** un client MCP di prova esegue tutti gli strumenti; misurato il tempo fino alla prima risposta.

Viene prima dell'interfaccia perché è utile da subito con le note reali e mette alla prova il nucleo.

### ✅ 4. Guscio Tauri e prima schermata

Finestra nascosta fino alla prima pittura, tema senza lampi, dati iniettati all'avvio, istanza singola, tracciamento dei tempi, CSP.
**Fatta quando:** l'app si apre con una pagina vuota a tema giusto; misurato l'avvio a freddo. Questa misura decide se la strada Tauri regge gli obiettivi: se è lontana, ci si ferma a rivederla prima di costruirci sopra.

### 🟡 5. Temi e barra laterale

Token, 6 temi, Personalizzato, Automatico, font inclusi. Barra aperta come in Home, striscia compressa con pannelli rapidi e preferiti. Una sola scheda, nota di oggi in sola lettura. Dati finti per lavorare nel browser.
**Fatta quando:** il confronto a schermo con la tavola Home è fedele in tutti i temi.
**Resta da fare:** confronto a schermo fatto solo con Carta e Grafite, senza misure di fedeltà. Mancano le varianti Mezzanotte, Salvia, Lavanda, Nebbia e il Personalizzato, scritti ma mai guardati.

### ✅ 6. Editor

CodeMirror 6 in un blocco separato, anteprima viva, salvataggio automatico, modifiche esterne, completamento di `@`, `#` e `[[`, comandi di spunta che scrivono `done:`, rientro di sotto-attività e descrizioni, avvisi e tabelle.
**Fatta quando:** si può usare l'app per scrivere davvero, senza mai perdere testo chiudendola; misurata la latenza di scrittura.
**Provati** (`prova-editor.mjs`, `prova-modalita.mjs`): tabelle nell'anteprima viva, menu `⋯` con le modalità Anteprima viva, Sorgente, Affiancata e Anteprima, Anteprima sanificata, note a piè di pagina, link `[[…]]` ed esterni, `open_url` che rifiuta i file, Ctrl F, completamento di `@`, `#` e `[[`. Latenza misurata.
**Spostato alla tappa 12:** il minutaggio `[mm:ss]`, che serve solo con l'audio.

### ✅ 7. Schede e gruppi

Più schede, fino a 4 gruppi, divisione, trascinamento, riapertura, stessa nota in due gruppi sincronizzata, annulla e cursore conservati.
**Fatta quando:** i comportamenti della tavola Home funzionano tutti con note vere.
**Provati:** divisione, sincronizzazione, riordino e trascinamento sul bordo, chiusura e riapertura, disposizione ricordata dopo un riavvio (`prova-schede.mjs`, `prova-riavvio.mjs`, `prova-editor.mjs`). Divisore e doppio clic, ingrandimento, menu contestuale delle schede, chiusura di un gruppo, Ctrl 1…6 e Ctrl W (`prova-gruppi.mjs`).

### ✅ 8. Azioni

Bacheca ed elenco, raggruppamento, pillole con popover, sotto-attività, campo nuova azione, colonne con scadenze reali.
**Fatta quando:** ogni modifica dalle pillole si ritrova corretta nel file, anche con la nota aperta in un editor.
**Provati** (`prova-azioni.mjs`): oltre a pillole e sotto-attività, il "+" delle colonne per scadenza e per progetto, "Sposta a domani" su più note, spunta e pillole nella pagina etichetta.
**Da rivedere con l'utente:** i pulsanti `+` nascosti lasciano a volte una riga vuota nelle schede (vedi "Da decidere").

### 🟡 9. Altre viste

Calendario, Persone, Persona, Etichetta con colore, Grafo, Impostazioni.
**Fatte e provate a livello base.** **Resta da fare:** registrazioni nel Calendario, scelta della nota nel Grafo, scheda "Note e registrazione" nelle Impostazioni.

### 🟡 10. Ricerca Ctrl K

Note, viste, comandi, filtri `@`, `#`, `!`.
**Fatta quando:** i risultati arrivano entro l'obiettivo a ogni tasto.
**Resta da fare:** misurare il tempo a ogni tasto nell'app; manca il pannello di anteprima e i risultati nelle trascrizioni.

### 🟡 11. Area di notifica, tasti globali, finestre secondarie

Nota rapida e finestra di registrazione precaricate e nascoste. Chiudere la finestra la nasconde. Migrazione dei tasti.
**Provati via CDP:** nota rapida (scrittura, riconoscimento, salvataggio), salvataggio all'evento di chiusura e all'uscita, riapertura con una seconda istanza.
**Scritti ma mai provati dal vivo:** tasti globali, menu dell'area di notifica, X della finestra, comparsa e messa a fuoco della nota rapida. **Manca:** la finestra di registrazione, con la tappa 12.

### ⬜ 12. Audio

Registrazione con pausa e annullamento, riproduzione dal minutaggio (`[mm:ss]` come pulsante nell'editor, vedi il piano del design), trascrizione con `whisper-rs`. Scelta da verificare: qualità e velocità rispetto a faster-whisper, su una registrazione reale.

### ⬜ 13. File ed esportazione

Link a file con apertura sicura, allegati, HTML e Markdown. PDF con `PrintToPdf` di WebView2, che da Tauri dovrebbe essere raggiungibile tramite `with_webview`: da verificare per primo.

### ⬜ 14. Schizzi Excalidraw

Prima una prova isolata, offline, di Excalidraw in Svelte. Poi editor, anteprima SVG e incorporamento.

### ⬜ 15. Rilascio

Installer, README, avvio automatico facoltativo, passaggio dalla versione Python, prova finale su una copia delle note reali.

## Misure raccolte

Tutte su questo PC con build di release. L'avvio è a cache del disco calda: dopo un riavvio del PC sarà più lento.

| Tappa | Misura | Risultato | Obiettivo |
|---|---|---|---|
| 2 | Indicizzazione completa di 1000 note | 1,24 s | In sottofondo, senza limite |
| 2 | Allineamento senza modifiche, 1000 note | 3,6 ms | < 50 ms ✅ |
| 2 | Ricerca a testo pieno, 1000 note | 7-9 ms | < 30 ms ✅ |
| 2 | 500 azioni aperte | 4,7 ms | |
| 3 | Dimensione di `quicknotes-mcp.exe` | 3,6 MB | |
| 3 | Connessione dal client SDK, processo compreso | 180 ms | < 50 ms: non confrontabile, comprende Node. Da rifare direttamente |
| 11 | Avvio a freddo fino alla prima pittura, 1000 note | **496 ms** (di cui circa 390 ms per creare WebView2) | < 400 ms ❌ |
| 11 | Riapertura con una seconda istanza, fino alla sua uscita | 26 ms | < 80 ms ✅, ma il tempo di comparsa della finestra non è compreso |
| 11 | Dimensione di `quicknotes.exe` | 8,9 MB | |
| 6 | Scrittura, dal tasto alla pittura, nota del giorno di prova | mediana 4,2 ms, 95° percentile 6,8 ms | < 16 ms ✅ |
| 6 | Scrittura, stessa nota con 2000 righe in sezioni | mediana 5,0 ms, 95° percentile 6,9 ms | < 16 ms ✅ |
| 6 | Scrittura in fondo a una lista unica di 500 righe | mediana 5,7 ms, 95° percentile 7,0 ms | < 16 ms ✅ |
| 6 | Scrittura in fondo a un blocco unico di 2000 righe (caso limite) | mediana 23 ms | < 16 ms ❌, vedi sotto |
| 6 | Cambio scheda, dal clic all'editor dipinto | mediana 25 ms, 95° percentile 29 ms | < 50 ms ✅ |
| 6 | Memoria di `quicknotes.exe` a riposo, escluso WebView2 | 9-11 MB privati, 33-35 MB di insieme di lavoro | < 40 MB ✅ |
| 6 | Blocco iniziale della pagina (`App`), dopo l'aggiunta del menu `⋯` | 39 kB, 14,5 kB compressi | |

**L'avvio a freddo supera l'obiettivo.** La creazione di WebView2 è fuori dal controllo di Rust. Idea da provare: mostrare subito la finestra con lo sfondo del tema, così la risposta si percepisce prima, controllando che non compaia un lampo.

**Come si misura la scrittura:** `misura-latenza.mjs` legge la traccia della timeline di WebView2, dalla `keydown` alla fine della prima pittura. Un segnale in pagina dopo `requestAnimationFrame` non va bene: aspetta anche il lavoro in sottofondo dopo il fotogramma, e su una nota lunga dava 24 ms invece di 5.

**Caso limite della scrittura:** l'analizzatore Markdown di CodeMirror riusa solo i blocchi di primo livello. Scrivendo dentro un blocco unico molto lungo, per esempio 2000 righe senza righe vuote che diventano un'unica lista, a ogni tasto rianalizza tutto il blocco. Con 500 righe resta sotto i 6 ms; non si interviene finché non capita con note vere.

## Registro delle decisioni prese lungo il percorso

| Data | Decisione | Motivo |
|---|---|---|
| 2026-11-03 | Tauri 2 con Svelte 5 e CodeMirror 6 | Vedi [architettura.md](architettura.md#rust-con-tauri-2-non-uninterfaccia-tutta-nativa) |
| 2026-11-03 | Indice in un file nuovo, `index-v3.db` | La versione precedente resta utilizzabile sulle stesse note |
| 2026-11-03 | Server MCP scritto a mano, senza `rmcp` | Bastano strumenti e prompt, parte della specifica stabile. Nessun runtime asincrono all'avvio. Verificato con il client dell'SDK ufficiale |
| 2026-11-03 | Le scritture si serializzano con un lock, non con un thread dedicato | Stessa garanzia con meno codice |
| 2026-11-03 | Niente dati finti nel browser: le prove guidano l'app vera via CDP (`scripts/cdp.mjs`) | Prova tutto il percorso fino ai file, e non c'è una seconda versione del backend da mantenere |
| 2026-11-03 | Gruppi e schede fatti insieme alla tappa 5 | La disposizione è la struttura portante del guscio |
| 2026-11-03 | Conflitti: se il file è cambiato fuori dall'app, il testo in sospeso va in una nota "(conflitto HH:MM)" | Non si perde mai nulla, senza fusioni automatiche che potrebbero sbagliare |
| 2026-11-03 | La nota del giorno si crea anche spostandosi tra i giorni con le frecce | L'editor lavora su un file. Da rivedere se lascia troppe note vuote |
| 2026-11-03 | Chiudere la finestra la nasconde; si esce dal menu dell'area di notifica | Riaprire è immediato |
| 2026-11-03 | All'avvio si ripristinano le schede; se la nota di oggi non c'è, si apre e diventa attiva | Il lavoro resta dov'era, ma ogni giorno nuovo parte dalla sua nota |
| 2026-11-03 | La nota rapida si prepara 1,5 secondi dopo l'avvio | Non pesa sull'avvio e dopo è immediata |
| 2026-11-03 | Commit del lavoro sul ramo `rust-tauri`, senza `README.md` né `crates/quicknotes-app/gen/schemas` (generata da Tauri) | Richiesta dell'utente |
| 2026-11-03 | Le modalità si scelgono dal menu `⋯` e da Ctrl K; fuori dall'anteprima viva una barra in basso permette di cambiarle o tornare indietro | La tavola Home non le mostra; la barra in basso è quella prevista nel piano del design |
| 2026-11-03 | La modalità vale per la coppia gruppo e scheda, come annulla e cursore, e non si ricorda dopo un riavvio | La stessa nota può stare in Affiancata in un gruppo e in anteprima viva nell'altro |
| 2026-11-03 | Nell'Anteprima le caselle sono in sola lettura | Abbinare una casella dell'HTML alla riga giusta del file non è sicuro (liste in citazioni, elenchi numerati); si spunta nelle altre modalità |
| 2026-11-03 | `open_url` passa da `tauri-plugin-opener` lato Rust; la pagina non ha permessi sul plugin | Solo `http` e `https`, controllati in Rust |
| 2026-11-03 | Il "+" di una colonna scrive la scadenza del primo giorno di quella colonna (Oggi e domani: oggi; Questa settimana: dopodomani; Più avanti: il lunedì dopo). Raggruppando per progetto scrive l'etichetta. Se il testo ha già una scadenza o un'etichetta, vale quella | La tavola mostra il "+" senza dire cosa fa. Il giorno si cambia poi con la pillola |
| 2026-11-03 | "In ritardo" non ha il "+" ma "Sposta a domani", in bacheca e in elenco. Sposta solo le azioni di primo livello, senza conferma, e un avviso dice quante | Aggiungere un'azione già in ritardo non ha senso. Le figlie hanno scadenze proprie. Con la nota aperta, la modifica arriva all'editor e si annulla da lì |
| 2026-11-03 | La pagina etichetta riceve le stesse schede della bacheca (`BoardItem`) e si ricarica con la bacheca | Un solo modo di mostrare e modificare un'azione |
| 2026-11-03 | Gli `on…` nell'HTML delle note fanno comparire in console una segnalazione della CSP mentre DOMPurify legge l'HTML | Succede con qualsiasi modo di analizzare HTML in WebView2. Il gestore non viene mai eseguito: la prova lo controlla |
