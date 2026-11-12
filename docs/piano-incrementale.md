# Piano incrementale

> **Dalla 0.4.0 QuickNotes è in Python** (pywebview), con la stessa interfaccia: questo piano è il registro delle tappe fatte con la versione Rust e resta valido come elenco delle funzionalità. Comandi, prove e misure attuali sono in [architettura.md](architettura.md).

Ordine di lavoro per costruire QuickNotes in Rust. Alla fine di ogni tappa c'è qualcosa che funziona e si può provare. Le regole di prodotto sono in [piano-implementazione-design.md](piano-implementazione-design.md), le scelte tecniche in [architettura.md](architettura.md).

**Legenda:** ⬜ da fare · 🟡 in corso · ✅ fatta e verificata

## Come riprendere il lavoro

Stato al 3 novembre 2026, dopo la chiusura delle tappe dalla 5 alla 11. Resta la tappa 12 (audio, video e spazio su disco), poi file, schizzi e rilascio.

**Git:** il lavoro è sul ramo `main`, il principale (fino al 13 novembre 2026 si chiamava `rust-tauri`; il vecchio `main` era fermo al commit `eb05f3e`, quello della prima versione Python, il cui codice cancellato si legge con `git show eb05f3e:<percorso>`). Le modifiche locali a `README.md` sono dell'utente: non vanno incluse nei commit e non vanno perse.

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
| `prova-azioni.mjs`, `prova-viste.mjs`, `prova-desktop.mjs`, `prova-modalita.mjs`, `prova-gruppi.mjs`, `prova-collegamenti.mjs`, `prova-gfm.mjs`, `prova-guida.mjs`, `prova-ricerca.mjs` | Con `demo-note.mjs` | |
| `prova-immagini.mjs` | Con `demo-note.mjs` | L'ultimo passaggio mette un'immagine negli appunti di Windows e preme Ctrl V davvero: sostituisce gli appunti, e per qualche secondo il PC non va usato |
| `prova-sistema.mjs` | Con `demo-note.mjs` | Tasti e mouse veri per circa 20 secondi: il PC non va usato. Nessun'altra QuickNotes aperta. Alla fine esce dall'app dal menu |
| `misura-latenza.mjs` | Con `demo-note.mjs` | Stampa le misure di scrittura, cambio scheda e memoria |
| `misura-ricerca.mjs` | Con 1000 note di `genera_note` | Stampa i tempi di `search_all` e di Ctrl K a ogni tasto |
| `prova-schede.mjs`, poi `prova-riavvio.mjs` | Con `demo-note.mjs` | Stessa cartella e stesso `QN_CFG=<cartella cfg>`. La prima chiude l'app, quindi aspettare 2 secondi prima della seconda |

Se una prova stampa `ERRORI DELLA PAGINA`, va considerata fallita anche quando tutti i controlli `ok:` sono passati. Una prova può dichiarare gli errori che provoca di proposito con `export const expectedErrors`: `cdp.mjs` li conta a parte.

**Strumenti già installati su questo PC:** Rust 1.99 con Rustup, Visual Studio Build Tools 2022, Node 23. Non ci sono CMake né libclang, che serviranno a `whisper-rs` alla tappa 12.

**Prima delle prove:** se `quicknotes.exe` è già aperto (per esempio dall'utente, sulle note vere), va chiuso. Con l'istanza singola una prova finirebbe nella sua finestra, e la build non può sostituire l'eseguibile.

**Dati reali:** `~/QuickNotes` e `~/.quicknotes` contengono le note vere dell'utente e finora non sono stati toccati. Ogni prova deve usare `QUICKNOTES_DIR` e `QUICKNOTES_CONFIG_DIR`, come fanno gli script. Avviare `target/release/quicknotes.exe` a mano, senza queste variabili, lavora sulle note vere e crea la nota del giorno.

**Limiti dell'ambiente:** in Git Bash i comandi molto lunghi con heredoc possono fallire con `unexpected EOF`; meglio scrivere i file con lo strumento apposito. `ln -s` copia le cartelle invece di collegarle.

### Prossimi passi, in ordine

1. **Prima versione da distribuire (tappa 15, avviata):** creare il repository GitHub pubblico per le release e pubblicare `QuickNotes.exe` e `quicknotes-mcp.exe` costruiti con `scripts/rilascio.mjs`. Passi in [rilascio.md](rilascio.md).
2. **Tappa 12, audio, video e spazio su disco**, compresa la finestra di registrazione spostata qui dalla tappa 11. Prima delle righe di codice servono le risposte su video e soglie (vedi "Da decidere") e la scelta di come compilare `whisper-rs`, che richiede CMake e libclang (non installati).
3. **Da provare a mano, l'unica cosa che le prove non raggiungono:** il clic fisico sull'icona dell'area di notifica (la prova manda all'icona lo stesso messaggio di Esplora risorse) e i tasti laterali di un mouse vero.
4. **Tappe 13-15:** file ed esportazione (le immagini incollate ci sono già), schizzi, rilascio.

### Da decidere con l'utente

- **Pulsanti `+` delle pillole:** nascosti lasciano a volte una riga vuota nelle schede; mostrandoli al passaggio del mouse senza riservare spazio, le schede si sposterebbero sotto il puntatore.
- **Proposte ancora non confermate** in [piano-implementazione-design.md](piano-implementazione-design.md#proposte-non-ancora-confermate), tra cui figlia in ritardo e figlie in Calendario.
- **Note del giorno vuote:** l'app le crea a ogni avvio e con le frecce, e il Calendario con "Crea la nota del giorno".
- **Video, tappa 12:** cosa si registra (tutto lo schermo, una finestra scelta, la webcam), quale audio (microfono, audio del sistema, entrambi) e con quale qualità (risoluzione e fotogrammi, che decidono i MB al minuto).
- **Fine della registrazione, tappa 12:** se il riquadro deve comparire sempre o si può dire "Non chiedere più, fai sempre così"; se "Elimina dopo la trascrizione" vale anche per l'audio o solo per i video.
- **Note non collegate, tappa 12:** se la regola proposta va bene (nessun link, persona, etichetta o azione, come le "Note isolate" del Grafo) o se una nota con solo testo, ma citata da nessuno, conta già come non collegata.
- **Soglie dello spazio, tappa 12:** quelle proposte (10 GB per la cartella, 5 GB di video, 10% o 5 GB liberi sul disco) e se l'utente le può cambiare dalle Impostazioni.

### Difetti e limiti noti

- **Nota rapida subito dopo l'avvio:** la finestra si prepara dopo circa 1,5 secondi. Prima di allora Ctrl Alt N apre la finestra principale.
- **Calendario:** "Ieri" e "domani" non sono nel pannello rapido di Oggi, a differenza della tavola Home. Una registrazione aggiunta giorni dopo a una nota compare nel giorno della nota, non in quello della registrazione: il nome del WAV non ha la data.
- **Ctrl K:** ci sono i tipi Note, Azioni, Decisioni e Trascrizioni; mancano il filtro "Ultimi 90 giorni" e l'ordinamento della tavola Ricerca. Le trascrizioni si cercano solo nelle 15 note trovate dalla ricerca a testo pieno.
- **Impostazioni › Note e registrazione:** modello, lingua, file audio e minutaggio si salvano in `config.json` ma servono solo dalla tappa 12. La cartella delle note si apre ma non si cambia dall'app.
- **Pagina Persona:** le azioni si possono solo leggere, senza spunta né pillole. Il piano del design prevede le pillole solo in bacheca, elenco e pagina etichetta.
- **Scorciatoia Ctrl K W** non implementata, come proposto nel piano del design. Ctrl W e Ctrl 1…6 funzionano in WebView2: la pagina li riceve prima del browser.
- **Tema all'avvio:** lo sfondo iniziale della finestra è sempre scuro, ma non si vede perché la finestra resta nascosta fino alla prima pittura.
- **`quicknotes-mcp.exe`** è un file a parte nella release; le Impostazioni avvisano se manca accanto all'app.
- **README** descrive ancora la versione Python. Contiene modifiche locali dell'utente non salvate in Git: va aggiornato insieme a lui.
- **Eseguibile senza firma del codice:** al primo avvio Windows mostra SmartScreen ("Esegui comunque"); alcune politiche aziendali bloccano i programmi non firmati. Serve un certificato, dell'azienda o un servizio come Azure Trusted Signing.
- **Barra del titolo:** passando sul pulsante Ingrandisci non compare il menu dei layout a scatto di Windows 11, che richiede la cornice di sistema.
- **File trascinati da Esplora risorse:** con il gestore di Tauri disattivato, la pagina riceve i file senza percorso. Le immagini si leggono già come contenuto e si salvano in `images/`; gli altri allegati, alla tappa 13, si leggeranno allo stesso modo oppure si aggiungeranno dal menu `⋯`. Un file lasciato fuori dall'editor si ignora.
- **Grafo:** le note del giorno vuote sono nascoste con "Note isolate" spento, che è il valore iniziale. I link verso note inesistenti non diventano nodi.
- **Anteprima e tabelle:** i file collegati che non sono immagini mostrano solo il nome, finché la tappa 13 non porta l'apertura sicura dei file. I link a file non si aprono. Le immagini dal web restano un segnaposto con il nome, per scelta.
- **Immagini:** il nome è data e ora (`AAAA-MM-GG-HHMMSS.png`); sopra i 10 MB l'app chiede conferma, sopra i 50 MB rifiuta. Non si ridimensionano né si comprimono. Un'immagine mancante fa comparire in console un 404 prima del segnaposto.
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

### ✅ 5. Temi e barra laterale

Token, 6 temi, Personalizzato, Automatico, font inclusi. Barra aperta come in Home, striscia compressa con pannelli rapidi e preferiti. Una sola scheda, nota di oggi in sola lettura. Dati finti per lavorare nel browser.
**Fatta quando:** il confronto a schermo con la tavola Home è fedele in tutti i temi.
**Verificata dall'utente** il 3 novembre 2026: tutti i temi vanno bene.
**Aggiunta su richiesta:** barra del titolo disegnata dalla pagina, come in VS Code, con titolo della scheda attiva e pulsanti Riduci, Ingrandisci/Ripristina e Chiudi (che nasconde nell'area di notifica). La finestra non ha più la cornice di sistema.

### ✅ 6. Editor

CodeMirror 6 in un blocco separato, anteprima viva, salvataggio automatico, modifiche esterne, completamento di `@`, `#` e `[[`, comandi di spunta che scrivono `done:`, rientro di sotto-attività e descrizioni, avvisi e tabelle.
**Fatta quando:** si può usare l'app per scrivere davvero, senza mai perdere testo chiudendola; misurata la latenza di scrittura.
**Provati** (`prova-editor.mjs`, `prova-modalita.mjs`): tabelle nell'anteprima viva, menu `⋯` con le modalità Anteprima viva, Sorgente, Affiancata e Anteprima, Anteprima sanificata, note a piè di pagina, link `[[…]]` ed esterni, `open_url` che rifiuta i file, Ctrl F, completamento di `@`, `#` e `[[`. Latenza misurata.
**Suggerimenti mentre si scrive, come in VS Code** (`prova-guida.mjs`): `due:`, `entro:`, `scadenza:` propongono le date con il giorno per esteso e segnalano un formato sbagliato o una data inesistente; `done:` propone oggi e ieri; `!` propone `!decisione`; `- [` l'azione; ``` la lingua, e chiude il blocco; `|` a inizio riga una tabella; `/` a inizio riga o Ctrl Spazio su una riga vuota l'elenco delle strutture.
**Caselle delle azioni:** allineate al testo (scarto misurato da 2,2 px a 0 nell'editor, da 2,4 a −0,1 px nelle schede).
**Spostato alla tappa 12:** il minutaggio `[mm:ss]`, che serve solo con l'audio.
**GitHub Markdown come nella tavola Markdown** (`prova-gfm.mjs`): avvisi con icona ed etichette del design (Nota, Suggerimento, Importante, Avvertenza, Attenzione); scrivendo `> [!` compare l'elenco dei tipi con icona e descrizione; blocchi di codice con il nome della lingua e i colori della sintassi, nell'editor e nell'Anteprima (`@codemirror/language-data`, lingue caricate quando servono); note a piè di pagina e indirizzi nudi anche nell'anteprima viva; in Sorgente i segni hanno i colori della tavola; `<details>` ammesso nell'Anteprima.

### ✅ 7. Schede e gruppi

Più schede, fino a 4 gruppi, divisione, trascinamento, riapertura, stessa nota in due gruppi sincronizzata, annulla e cursore conservati.
**Fatta quando:** i comportamenti della tavola Home funzionano tutti con note vere.
**Indietro e Avanti come in VS Code** (`prova-guida.mjs`): Alt ← e Alt →, e i tasti laterali del mouse. La cronologia ricorda gruppo e pagina; tornando su una scheda chiusa la riapre.
**Guida** (`view:help`): pulsante ? in basso a destra, F1 o Ctrl K. Tavola dei comandi e della sintassi, con un campo per filtrarla.
**Tasto centrale del mouse:** chiude la scheda sotto il puntatore, anche se non è attiva (`prova-gruppi.mjs`).
**Correzione del 3 novembre:** nell'app vera il trascinamento delle schede non partiva, perché su Windows il gestore di trascinamento di Tauri intercetta tutto. Ora è disattivato (`disable_drag_drop_handler`). Le prove non se ne accorgevano: Playwright simula il trascinamento senza passare dal sistema.
**Provati:** divisione, sincronizzazione, riordino e trascinamento sul bordo, chiusura e riapertura, disposizione ricordata dopo un riavvio (`prova-schede.mjs`, `prova-riavvio.mjs`, `prova-editor.mjs`). Divisore e doppio clic, ingrandimento, menu contestuale delle schede, chiusura di un gruppo, Ctrl 1…6 e Ctrl W (`prova-gruppi.mjs`).

### ✅ 8. Azioni

Bacheca ed elenco, raggruppamento, pillole con popover, sotto-attività, campo nuova azione, colonne con scadenze reali.
**Fatta quando:** ogni modifica dalle pillole si ritrova corretta nel file, anche con la nota aperta in un editor.
**Provati** (`prova-azioni.mjs`): oltre a pillole e sotto-attività, il "+" delle colonne per scadenza e per progetto, "Sposta a domani" su più note, spunta e pillole nella pagina etichetta.
**Da rivedere con l'utente:** i pulsanti `+` nascosti lasciano a volte una riga vuota nelle schede (vedi "Da decidere").

### ✅ 9. Altre viste

Calendario, Persone, Persona, Etichetta con colore, Grafo, Impostazioni.
**Fatte e provate a livello base.**
**Registrazioni nel Calendario** (`prova-ricerca.mjs`): le righe `🎙️ [Registrazione HH:MM (durata)](file)` e i titoli `Trascrizione HH:MM` diventano voci con il microfono, nel giorno della nota; un clic apre la nota sulla riga, che si accende per un attimo. Legenda "Nota o registrazione" come nella tavola Home.
**Impostazioni › Note e registrazione** (`prova-ricerca.mjs`): cartella delle note con "Apri la cartella", schema delle note del giorno, sezioni; modello di trascrizione, lingua, "Conserva il file audio" e "Minutaggio cliccabile", salvati in `config.json` con le chiavi della versione precedente. "File e schizzi" della tavola arriva con le tappe 13 e 14.
**Grafo, rifatto su richiesta:** tutte le note come in Obsidian, con persone ed etichette. Disposizione a forze (`d3-force`) su canvas, zoom con la rotella, spostamento della vista e dei nodi, passaggio del mouse che evidenzia i vicini, clic che apre la nota, persona o etichetta. Filtri per persone, etichette, note del giorno e note isolate; campo "Evidenzia"; modalità "Locale" con profondità 1-3 attorno all'ultima nota aperta. Provato con `prova-collegamenti.mjs` e guardato con 1000 note.
**Note collegate:** la pillola "N collegamenti" apre un riquadro con le note che citano questa e quelle citate; un clic apre la nota. Si aggiorna quando cambiano i `[[link]]`.

### ✅ 10. Ricerca Ctrl K

Note, viste, comandi, filtri `@`, `#`, `!`.
**Fatta quando:** i risultati arrivano entro l'obiettivo a ogni tasto.
**Misurato** (`misura-ricerca.mjs`): entro l'obiettivo anche dopo le aggiunte, vedi le misure.
**Come nella tavola Ricerca** (`prova-ricerca.mjs`): risultati divisi in Note, Azioni, Decisioni e Trascrizioni, con i tipi e i conteggi in alto (Tab li scorre); anteprima a destra con percorso, titolo, data, persone e le parole evidenziate; Apri, Apri a lato (anche Alt Invio) e Copia [[link]]; `>` per i soli comandi; riga dei tasti in basso. Le azioni hanno la scadenza colorata, le trascrizioni nota, ora e minutaggio. Ogni risultato apre la nota sulla sua riga. Le note del giorno si chiamano con la data, come nelle schede.
**Corretti durante la prova:** Esc non chiudeva Ctrl K se il fuoco era su un pulsante dell'anteprima. Le righe che scorrevano sotto un puntatore fermo cambiavano la scelta, e Alt Invio poteva aprire il risultato sbagliato: ora la scelta segue il mouse solo quando si muove, come in VS Code.

### ✅ 11. Area di notifica, tasti globali, finestre secondarie

Nota rapida e finestra di registrazione precaricate e nascoste. Chiudere la finestra la nasconde. Migrazione dei tasti.
**Provati via CDP:** nota rapida (scrittura, riconoscimento, salvataggio), salvataggio all'evento di chiusura e all'uscita, riapertura con una seconda istanza.
**Provati dal vivo** (`prova-sistema.mjs`, con tasti e mouse veri): Ctrl Alt N mostra la nota rapida in primo piano con il fuoco nel campo, Esc la nasconde e il testo resta, Ctrl Invio salva e passa alla finestra principale; Ctrl Alt D apre la nota del giorno; Ctrl Alt R per ora avvisa; Alt F4 nasconde senza chiudere; il clic sull'icona dell'area di notifica riapre; il menu ha le quattro voci, "Nota rapida" funziona ed "Esci" chiude il processo. Con il mouse: doppio clic sulla barra del titolo (ingrandisci e ripristina), spostamento della finestra dalla barra, ridimensionamento dal bordo destro, trascinamento di una scheda davanti alla prima.
**Spostato alla tappa 12:** la finestra di registrazione, che senza audio non avrebbe niente da fare.

### ⬜ 12. Audio, video e spazio su disco

Ampliata il 3 novembre su richiesta dell'utente: oltre all'audio, la registrazione di video, una scelta esplicita di cosa fare alla fine di ogni registrazione e lo spazio occupato nelle Impostazioni. Si procede in quest'ordine, e ogni passo si chiude con le sue prove prima del successivo.

**1. Registrazione audio.** Finestra di registrazione precaricata e nascosta (tavola Registrazione), avviata da Ctrl Alt R, dal pulsante Registra e dal menu dell'area di notifica. Pausa e ripresa (il tempo esclude le pause), annullamento, livello del microfono. WAV 16 kHz mono in `AAAA/MM/audio/<id>-HHMMSS.wav`, circa 1,9 MB al minuto. Durante la registrazione il file si scrive in una cartella di lavoro dentro la cartella delle note (non in `%TEMP%`): una chiusura improvvisa non lo perde, e al riavvio l'app propone di recuperarlo.

**2. Registrazione video.** Prima una prova isolata, come per gli schizzi, per scegliere la strada:
- **Nativa:** cattura con Windows Graphics Capture e compressione H.264 con Media Foundation, dal codice Rust. Nessun programma esterno, ma più codice da scrivere.
- **ffmpeg** accanto all'app: meno codice, ma circa 80 MB in più nel pacchetto.

La prova misura CPU durante la registrazione, MB al minuto e ritardo tra audio e video, su 10 minuti reali. Il file è un MP4 (H.264 e AAC) in `AAAA/MM/video/<id>-HHMMSS.mp4`; nella nota va una riga `🎬 [Video HH:MM (durata)](video/…)`, che Calendario e Ctrl K mostrano come le registrazioni audio. Cosa si registra è da decidere (vedi "Da decidere").

**3. Alla fine di ogni registrazione, audio o video, l'app chiede cosa fare.** Un riquadro "Registrazione terminata" con durata e dimensione del file, e le scelte:
- **Trascrivi:** ora, più tardi (nella nota resta un pulsante "Trascrivi") o mai.
- **Associa a:** la nota attiva, la nota di oggi, una nuova nota, oppure un'altra nota cercata come in Ctrl K. Il file si sposta accanto alla nota scelta e la riga va nella sua sezione "Trascrizioni".
- **Il file:** conservalo, oppure eliminalo dopo la trascrizione. Per un video anche "Conserva solo l'audio", che occupa molto meno.
- **Elimina la registrazione**, con conferma: il file va nel Cestino, non sparisce.

Il riquadro propone l'ultima scelta fatta. Se lo si chiude senza scegliere, o l'app si chiude, il file resta e la riga va nella nota di oggi: non si perde mai una registrazione. Questa regola sostituisce quella del piano del design ("Destinazione della registrazione"), che va aggiornato quando la tappa parte.

**4. Trascrizione** con `whisper-rs`, anche dell'audio estratto da un video. Avanzamento sul pulsante Registra, come prevede il design. Scelta da verificare: qualità e velocità rispetto a faster-whisper, su una registrazione reale. Serve prima decidere come compilarlo: richiede CMake e libclang, non installati.

**5. Riproduzione dal minutaggio:** `[mm:ss]` diventa un pulsante nell'editor (vedi il piano del design). Per l'audio la riproduzione è in Rust; per un video si apre un riquadro con il video al punto giusto, oppure il lettore di sistema (da decidere con la prova del passo 2).

**6. Spazio su disco nelle Impostazioni.** Una sezione "Spazio occupato" nella scheda Note e registrazione:
- totale della cartella delle note, diviso tra note (`.md`), audio, video, immagini, allegati e schizzi, indice di ricerca; più lo spazio libero sul disco;
- i file più grandi, con "Mostra nella cartella" ed "Elimina" (nel Cestino, con conferma, e con un avviso se una nota li cita ancora);
- il calcolo gira in Rust in sottofondo e non blocca mai la pagina; si aggiorna aprendo la scheda e dopo ogni registrazione.

**Avvisi quando lo spazio è troppo:** nella sezione, in evidenza, se si supera una soglia; e nel riquadro di fine registrazione, se quel file la fa superare. Soglie proposte, da confermare: cartella delle note oltre 10 GB, video oltre 5 GB, spazio libero sul disco sotto il 10% o sotto 5 GB. Se la cartella è sincronizzata (OneDrive, Dropbox), un avviso dice che anche i video verranno caricati.

**7. Note e file non collegati, nelle Impostazioni.** Aggiunta su richiesta dell'utente, nella stessa scheda, sotto "Spazio occupato". Due elenchi:
- **Note non collegate a niente:** nessun `[[link]]` in entrata o in uscita, nessuna `@persona`, nessuna `#etichetta`, nessuna azione. È la stessa regola delle "Note isolate" del Grafo, così i due posti dicono la stessa cosa. Le note del giorno vuote, che l'app crea da sola, stanno in un gruppo a parte, che si svuota con un solo pulsante.
- **File non citati da nessuna nota:** immagini, audio, video, allegati e schizzi che nessuna nota cita più (per esempio dopo aver cancellato la riga che li mostrava). Di solito è qui che si libera davvero spazio.

Per ogni voce: titolo o nome del file, data, dimensione e percorso. Un clic apre l'anteprima a destra, la stessa di Ctrl K per le note, l'immagine o il lettore per i file. Si può aprire la nota, mostrarla nella cartella, oppure selezionare più voci e premere "Elimina", con il totale dello spazio liberato. Eliminare porta sempre nel Cestino, dopo una conferma che elenca cosa sparisce. Una nota si porta dietro le sue registrazioni (`note_files`, come nella versione precedente), e la conferma lo dice. Un file citato da una nota non compare mai nell'elenco: il controllo si rifà subito prima di eliminare, perché nel frattempo una nota potrebbe averlo citato.

**Fatta quando:**
- registrazione audio e video, scelta finale, trascrizione e riproduzione funzionano su registrazioni reali di almeno 10 minuti;
- nessuna chiusura (Esci, chiusura forzata, spegnimento del PC) perde una registrazione;
- lo spazio mostrato coincide con quello misurato da Esplora risorse;
- gli elenchi delle note e dei file non collegati non contengono mai una nota o un file citato, e nulla si elimina senza passare dal Cestino;
- sono annotati CPU e memoria durante la registrazione, MB al minuto e tempo di trascrizione per minuto d'audio.

**Prove automatiche:** un dispositivo audio finto (un WAV letto al posto del microfono, scelto con una variabile d'ambiente) e una registrazione video breve della finestra dell'app. Così le prove non dipendono dal microfono. Il riquadro di fine registrazione e la sezione dello spazio si provano via CDP, su cartelle di prova con file di dimensioni note. Per gli elenchi dei non collegati, la cartella di prova ha note isolate, note del giorno vuote, file citati e file orfani, compreso un file citato solo da un `[[link]]` o solo da un'immagine in una tabella.

### 🟡 13. File ed esportazione

Link a file con apertura sicura, allegati, HTML e Markdown. PDF con `PrintToPdf` di WebView2, che da Tauri dovrebbe essere raggiungibile tramite `with_webview`: da verificare per primo.

**✅ Immagini incollate nella nota**, aggiunte su richiesta dell'utente e fatte il 3 novembre (`prova-immagini.mjs`):
- **Incollare:** Ctrl V con un'immagine negli appunti (uno screenshot, un'immagine copiata dal browser o da Esplora risorse) la salva in `images/` accanto alla nota. È la cartella che usava già la versione precedente, vedi [architettura.md](architettura.md). Al cursore va il tag Markdown standard `![](images/AAAA-MM-GG-HHMMSS.png)`, così il file resta leggibile in qualsiasi editor Markdown e su GitHub. Due immagini nello stesso secondo ricevono un numero. Funziona anche trascinando un file immagine nella nota, che oggi arriva alla pagina senza percorso: il contenuto si legge dalla pagina e si salva come per l'incolla.
- **Formato:** gli screenshot si salvano in PNG; JPEG, GIF e WebP restano come sono. Si accettano solo immagini, riconosciute dal contenuto e non solo dall'estensione. Si accetta anche BMP; SVG no, perché può contenere script. Sopra i 10 MB l'app chiede prima di salvarla, sopra i 50 MB rifiuta.
- **Vista nella nota:** nell'anteprima viva il tag diventa l'immagine, alla larghezza della nota, e torna testo quando il cursore è sulla riga, come i link e le tabelle. L'immagine compare anche in Anteprima, nelle tabelle e nel riquadro di Ctrl K. Il testo tra parentesi quadre resta la descrizione dell'immagine. Un file mancante mostra un segnaposto con il nome.
- **Sicurezza:** la pagina non legge file liberamente. Rust serve le immagini con il protocollo `qnfile` (`http://qnfile.localhost/<percorso nella cartella delle note>`), che risponde solo a file immagine veri dentro la cartella delle note e rifiuta `..`, percorsi assoluti e nomi codificati. La CSP ammette `qnfile` solo come sorgente di immagini, non per `fetch`, e non ammette immagini dal web. Gli `<img>` dell'HTML delle note perdono l'indirizzo già durante la sanificazione e lo riprendono solo se è un'immagine della cartella delle note: nessuna richiesta parte verso internet.
- **Spazio:** le immagini contano nella sezione "Spazio occupato". Togliendo il tag dalla nota, il file non si cancella: compare tra i "File non citati" della tappa 12, da dove lo si elimina.

**Fatta quando:** uno screenshot incollato compare subito nella nota, il file è in `images/` e il testo della nota contiene solo il tag Markdown; la nota riaperta, l'Anteprima e un editor esterno mostrano la stessa immagine; un percorso che esce dalla cartella delle note, per esempio `![](../../x.png)`, non viene mai servito.

**Provato** (`prova-immagini.mjs` e test di `images.rs`): incolla e trascinamento con il tag giusto e un PNG vero in `images/`; immagine nell'anteprima viva, testo del tag con il cursore sulla riga; con testo semplice negli appunti vince il testo; un file che si spaccia per PNG viene rifiutato senza lasciare tracce; un'immagine lasciata fuori dall'editor non fa uscire la pagina dall'app; il protocollo serve l'immagine e rifiuta nota, percorsi fuori dalla cartella e file di sistema; `fetch` non può leggere `qnfile`; Anteprima con due immagini e un'immagine dal web come segnaposto; **appunti veri di Windows e Ctrl V vero**. Non provato: un'immagine copiata da un browser vero, che mette negli appunti anche HTML.
**Corretto durante la prova:** gli `<img>` dell'Anteprima cominciavano a caricare l'indirizzo scritto nella nota prima di essere sostituiti, anche verso il web (la CSP lo bloccava, ma il tentativo partiva).

### ⬜ 14. Schizzi Excalidraw

Prima una prova isolata, offline, di Excalidraw in Svelte. Poi editor, anteprima SVG e incorporamento.

### 🟡 15. Rilascio

Eseguibile da distribuire, README, avvio automatico facoltativo, passaggio dalla versione Python, prova finale su una copia delle note reali.
**Fatto il 3 novembre, anticipato su richiesta dell'utente per distribuire una prima versione ai colleghi** (guida per chi rilascia in [rilascio.md](rilascio.md), per chi la usa in [installazione.md](installazione.md)):
- un eseguibile da scaricare da GitHub Releases e avviare, senza installer né amministratore, con il server MCP come secondo file;
- nessun aggiornamento automatico: Impostazioni › Informazioni mostra la versione e apre la pagina delle release;
- "Avvia con Windows", con l'app nascosta nell'area di notifica (`--nascosta`);
- `scripts/rilascio.mjs` costruisce i due eseguibili e la descrizione della release; versione 0.3.0.

Il primo giro aveva installer NSIS e aggiornamenti firmati (`tauri-plugin-updater`), provati con installer veri. Tolti lo stesso giorno su richiesta dell'utente: vedi le decisioni.
**Provato:** l'eseguibile di `rilascio.mjs` si avvia sulle note di prova, la scheda Informazioni ha il link alle release, il server MCP accanto all'app è riconosciuto.
**Non provato:** il download vero da GitHub, un PC aziendale con le sue politiche, il primo avvio da parte di un collega.
**Resta da fare:** README, passaggio dalla versione Python (la configurazione e le note sono già compatibili), prova finale su una copia delle note reali, firma del codice.

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
| 10 | `search_all` chiamato dalla pagina, IPC compreso, 1000 note | mediana 8,8 ms, 95° percentile 21 ms; la più lenta è `@gi` (21 ms) | |
| 10 | Ctrl K, dal tasto ai risultati aggiornati a schermo, 1000 note | mediana 11 ms, 95° percentile 15 ms | < 30 ms ✅ |
| 10 | `search_all` con azioni, decisioni e trascrizioni, IPC compreso, 1000 note | mediana 13,8 ms, 95° percentile 22 ms (prima delle correzioni: 16,8 e 21,8) | |
| 10 | Ctrl K con tipi e gruppi, dal tasto ai risultati a schermo, 1000 note | mediana 17,8 ms, 95° percentile 24,4 ms (prima delle correzioni: 23 e 31,5) | < 30 ms ✅ |
| 10 | Ctrl K, dal tasto all'anteprima aggiornata | mediana 20 ms; 95° percentile 98 ms, perché la prima volta che si sceglie una nota il riquadro aspetta 60 ms che la scelta si fermi | |
| 6 | Scrittura e cambio scheda, ripresi dopo le tappe 9-11 | scrittura 3,9 / 5,1 / 5,8 ms di mediana; cambio scheda 25,9 ms; memoria 11,2 MB privati | invariati ✅ |
| 13 | Scrittura e cambio scheda, ripresi dopo le immagini nell'anteprima viva | scrittura 4,2 / 5,1 / 5,8 ms di mediana; cambio scheda 25,3 ms; memoria 10,1 MB privati | invariati ✅ |

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
| 2026-11-03 | Barra del titolo della pagina, finestra senza cornice di sistema. "Chiudi" chiama `hide_main`, che salva e nasconde come la X di sistema | Richiesta dell'utente. Il `close()` di Tauri dalla pagina non arrivava al gestore che nasconde la finestra |
| 2026-11-03 | La finestra di riserva, mostrata dopo 3 secondi se la pagina non risponde, non compare se la pagina l'ha già mostrata | Prima poteva rimostrare una finestra appena chiusa |
| 2026-11-03 | Grafo completo con `d3-force` su canvas, letto dall'indice in una sola interrogazione (`full_graph`) | Richiesta dell'utente: come Obsidian. Il canvas regge migliaia di nodi; un elenco nascosto di pulsanti lo rende usabile da tastiera |
| 2026-11-03 | "Note isolate" parte spento | L'app crea una nota del giorno vuota a ogni avvio: accese, riempirebbero il grafo di punti |
| 2026-11-03 | Una regola sola per i clic: il contenuto reso (link resi, Anteprima, tabelle, schede, grafo) si apre con un clic e ha sempre la manina; il testo che si sta scrivendo (`@`, `#`, link sulla riga del cursore, tutto in Sorgente) si apre con Ctrl+clic e la manina compare solo con Ctrl premuto | Richiesta dell'utente. Prima nelle tabelle `@` e `#` avevano la manina ma non si aprivano, e in Sorgente non si apriva nulla |
| 2026-11-03 | Il menu `⋯` compare solo dove ha voci: nota (modalità, "Copia il link alla nota"), persona ed etichetta ("Cerca … nelle note"). Nelle viste e nelle Impostazioni non c'è | Richiesta dell'utente: prima nelle viste era un pulsante disattivato |
| 2026-11-03 | Alt ← e Alt → navigano tra le pagine anche dentro l'editor | Come in VS Code su Windows. CodeMirror li userebbe per spostare il cursore di una parola sintattica |
| 2026-11-03 | La Guida è una scheda come le altre, non un riquadro sopra la pagina | Si può tenere aperta accanto alla nota, in un altro gruppo |
| 2026-11-03 | Ctrl K cerca azioni, decisioni e trascrizioni solo da tre lettere in su; i testi delle 15 note trovate si leggono dai file | Con una o due lettere troverebbero quasi tutto. Le due scelte hanno riportato Ctrl K sotto i 30 ms al 95° percentile |
| 2026-11-03 | Una registrazione cade nel giorno della nota che la contiene | Il nome del WAV ha solo l'ora. Una registrazione aggiunta giorni dopo a una vecchia nota finisce nel giorno della nota |
| 2026-11-03 | Le scelte della registrazione si salvano già, con le chiavi della versione precedente (`whisper_model`, `language`, `keep_audio`, `transcript_timestamps`); la cartella delle note non si cambia dall'app | La scheda era prevista alla tappa 9. Cambiare cartella richiede di rifare l'indice e di riaprire tutto: resta in `config.json` |
| 2026-11-03 | La finestra di registrazione passa alla tappa 12 | Senza audio sarebbe una finestra finta |
| 2026-11-03 | Aprendo una nota da Ctrl K o dal Calendario, la riga trovata si accende e sfuma con un'animazione CSS | Una decorazione spenta solo da un timer poteva restare accesa in una scheda nascosta nel frattempo |
| 2026-11-03 | `prova-sistema.mjs` usa tasti e mouse veri, attraverso PowerShell e Win32 | Playwright simula gli eventi dentro la pagina e non raggiunge tasti globali, area di notifica, primo piano e bordi della finestra. Il trascinamento delle schede rotto alla tappa 7 non l'aveva visto |
| 2026-11-03 | La tappa 12 comprende anche registrazione video, una scelta esplicita alla fine di ogni registrazione (trascrivere, a quale nota associarla, conservare o eliminare il file) e lo spazio occupato nelle Impostazioni, con avvisi | Richiesta dell'utente. I video pesano molto più dell'audio: lo spazio va mostrato e tenuto d'occhio |
| 2026-11-03 | Immagini incollate in `images/` accanto alla nota, con il tag Markdown standard (tappa 13); in Impostazioni gli elenchi delle note e dei file non collegati, da ispezionare ed eliminare nel Cestino (tappa 12, passo 7) | Richiesta dell'utente. `images/` è la cartella della versione precedente; il tag standard tiene le note leggibili fuori dall'app |
| 2026-11-03 | Immagini servite da un protocollo dell'app (`qnfile`), non con l'asset protocol di Tauri | Il protocollo controlla in Rust che il file sia un'immagine vera dentro la cartella delle note; l'asset protocol servirebbe qualsiasi file del suo ambito |
| 2026-11-03 | Le immagini incollate si chiamano con data e ora e non si comprimono | Il nome non dipende dal titolo, che può cambiare. Il file resta quello copiato |
| 2026-11-03 | Release in un repository GitHub pubblico, anche separato dal codice | Scelta dell'utente. GitHub non scarica le release dei repository privati senza account |
| 2026-11-03 | `--cartella-note=` e `--cartella-config=` come le variabili d'ambiente | Restano anche quando l'app viene riaperta dalla shell, che non passa le variabili. Nati per l'installer, servono anche per tenere note e configurazione in un'altra cartella |
| 2026-11-03 | Niente installer né aggiornamenti automatici: `QuickNotes.exe` e `quicknotes-mcp.exe` da scaricare dalle release, con nomi fissi | Scelta dell'utente, dopo il primo giro con installer NSIS e `tauri-plugin-updater`. Il link `releases/latest/download/QuickNotes.exe` porta sempre all'ultima versione; la chiave di firma degli aggiornamenti non serve più |
| 2026-11-03 | Versione 0.3.0 per la prima distribuzione | Mancano ancora audio, file e schizzi: non è una 1.0 |
| 2026-11-03 | Gli `on…` nell'HTML delle note fanno comparire in console una segnalazione della CSP mentre DOMPurify legge l'HTML | Succede con qualsiasi modo di analizzare HTML in WebView2. Il gestore non viene mai eseguito: la prova lo controlla |
