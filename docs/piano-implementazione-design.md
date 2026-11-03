# Implementazione del design: decisioni e piano

Documento per riprendere il lavoro sul nuovo design di QuickNotes. Raccoglie le decisioni prese, i problemi trovati confrontando il design con il codice precedente e l'ordine di lavoro proposto.

**Design:** https://claude.ai/code/artifact/047edbb9-7e5d-4230-bc8a-6875cb0e38ce (i sorgenti delle tavole sono in `project/*.dc.html`; si leggono con l'azione `read` dello strumento Artifact).

> **Aggiornamento del 3 novembre 2026:** l'app si implementa in **Rust con Tauri 2**, non più in Python con pywebview. Le decisioni di prodotto qui sotto restano valide. Le parti tecniche che citano Python, pywebview, `sounddevice` o espressioni regolari con asserzioni all'indietro descrivono il comportamento atteso, ma lo strumento è quello indicato in [architettura.md](architettura.md). Lo stato di avanzamento è in [piano-incrementale.md](piano-incrementale.md).

## Stato al 2 novembre 2026

- **Non è stato implementato nulla** del nuovo design.
- Il codice precedente è stato rimosso dalla cartella di lavoro. I riferimenti qui sotto lo descrivono in modo generico, per il comportamento e non per file o funzioni.
- I nomi di funzioni e moduli che compaiono nel piano sono proposte per il nuovo codice.
- Nessuna parte del piano è stata provata nell'app. Il comportamento di pywebview descritto più avanti viene solo dalla lettura dei suoi sorgenti.
- Etichette colorate, sotto-attività, barra chiusa, pillole delle azioni, file, esportazione e schizzi sono già nella tavola Home del design, ma non sono state aperte in un browser. Per i colori è stato calcolato solo il contrasto. Per barra chiusa e pillole è stata eseguita anche la logica della tavola in Node, senza disegnarla.
- L'editor degli schizzi nel design è un'imitazione: gli strumenti si selezionano ma non disegnano. Excalidraw non è ancora stato integrato né provato, e nemmeno la generazione del PDF.

## Decisioni

### Confermate dall'utente

| Tema | Decisione |
|---|---|
| Base dell'app | La tavola **Home** è il riferimento: è la più recente e le altre la contraddicono su barra a icone, pannello destro e modalità |
| Tavole aggiuntive | Cattura e Registrazione; Markdown e Ricerca; Grafo e Persona completi |
| Tavole escluse | **Revisione**: versioni, diff, attività di Claude. Anche le impostazioni MCP con interruttori per gli strumenti |
| Schede | Gruppi come in VS Code: fino a 4, con trascinamento. La stessa nota può stare in due gruppi, sincronizzata dal vivo |
| Elenco note | **Eliminato**, come nel design: spariscono colonna, "Tutte le note" e filtri Meeting/Nota. Si arriva alle note con Ctrl K, Calendario, etichette e persone |
| Date di completamento | Spuntando un'azione, l'app scrive `done:AAAA-MM-GG` nel file |
| Modalità dell'editor | L'anteprima viva resta il default; si aggiungono Sorgente, Affiancata e Anteprima |
| Persone | Solo i nomi `@` grezzi: niente `persone/*.md`, alias o "Scheda". `@Giulia` e `@G.Ferri` restano due persone |
| Sezioni della nota del giorno | Create quando servono: la nota parte vuota e il titolo si aggiunge al primo salvataggio in quella sezione |
| Etichette | Ogni etichetta può avere un colore diverso, scelto dalla sua pagina o da Impostazioni › Etichette |
| Sotto-attività | **Opzione A, checklist nella scheda** (tavola `SottoA`): si scrivono con il rientro e in bacheca appare solo l'azione madre. Regole in [Sotto-attività](#sotto-attività) |
| Barra laterale | **Aperta come predefinita**. Da compressa usa una **variante dell'opzione E**: icone con pannelli rapidi e preferiti colorati (tavola `BarraE`, versione finale in Home). Regole in [Barra laterale](#barra-laterale) |
| Dettagli delle azioni | **Opzione A, pillole sulla riga** (tavola `DettagliA`, versione finale in Home). Regole in [Dettagli delle azioni](#dettagli-delle-azioni) |
| Nuove funzioni | Link a file, esportazione in PDF e HTML, schizzi Excalidraw incorporati nelle note con la sintassi di Obsidian. I dettagli sono proposte, elencate qui sotto |
| Miglioramento scelto | Il minutaggio `[mm:ss]` riproduce l'audio, con un comando "Ascolta" |
| Miglioramenti scartati | Registro decisioni in Azioni, trascinamento delle schede per cambiare scadenza, promemoria arretrati in Oggi |

### Proposte non ancora confermate

Queste sono scelte mie. Vanno riviste prima di scrivere il codice.

| Tema | Proposta | Motivo |
|---|---|---|
| Tema "Automatico" | Si aggiunge ai 6 temi e al Personalizzato, e resta il default: Grafite con sistema scuro, Carta con sistema chiaro. Il vecchio tema chiaro diventa Carta, quello scuro Grafite | L'app precedente seguiva il sistema; il design non lo prevede |
| Font | Geist e Geist Mono inclusi nel pacchetto (`@fontsource-variable/*`), non da Google Fonts | L'app promette che nessun dato esce dal computer e deve funzionare offline |
| Scheda Claude nelle impostazioni | Mostra la configurazione reale da copiare e l'elenco degli strumenti in sola lettura. Niente interruttore "Consenti modifiche" né "Riavvia" | Claude non ha uno strumento di modifica, e il server stdio lo avvia Claude |
| Anteprima trascrizione dal vivo | Si toglie dalla tavola Registrazione | Whisper lavora a blocchi e sarebbe troppo pesante su CPU durante la registrazione |
| Ctrl+Alt+N | Apre la nota rapida; "Nuovo meeting" resta su Ctrl+N. L'impostazione del vecchio tasto globale per il nuovo meeting si migra a quello della nota rapida | Lo chiede la tavola Cattura; resta un comando da riga di comando per creare un meeting |
| Ctrl+F | Cerca nella nota aperta (`@codemirror/search`); Ctrl+O diventa sinonimo di Ctrl K | Senza elenco, la ricerca che prima stava su Ctrl+F non ha più un posto |
| Ctrl+K W | Si toglie "Chiudi tutte" su questa combinazione | È in conflitto con Ctrl K, che apre la ricerca |
| Colonna "Più avanti" | Si aggiunge alla bacheca e compare solo quando contiene azioni | Senza, le scadenze oltre questa settimana non avrebbero una colonna |
| Stato della barra laterale | Parte aperta al primo avvio e dopo "Ripristina predefiniti". Se la comprimi, resta compressa agli avvii successivi | La barra aperta è la base, ma una scelta esplicita non va annullata a ogni avvio |
| Pulsanti `+` delle pillole | Le pillole vuote compaiono al passaggio del mouse o con la tastiera; quelle piene restano sempre visibili | Con molte schede, quattro pulsanti tratteggiati su ognuna coprirebbero il contenuto |
| Pillole nella nota | Le pillole compaiono in bacheca, elenco e pagina etichetta. Nell'editor i dettagli si scrivono nel testo | Nell'editor la riga è già il dato; aggiungere controlli sopra il testo creerebbe due modi di modificarla |
| Descrizione di un'azione | Righe rientrate subito sotto l'azione, prima delle sue figlie. `@` e `#` nella descrizione non cambiano persona ed etichetta dell'azione | Il file resta Markdown leggibile, e le righe rientrate sono già testo della voce di elenco |
| Priorità delle azioni | Non si aggiunge | Non è stata chiesta, e `!` indica già `!decisione` |
| Formati di esportazione | PDF, HTML e Markdown; niente Word | Sono i formati chiesti, più una copia portabile delle note |
| File allegati | Copiati in `allegati/` accanto alla nota; un'impostazione permette di puntare all'originale | Le copie sopravvivono se l'originale viene spostato |
| Formato degli schizzi | `.excalidraw` in `allegati/`, con accanto un'anteprima `.excalidraw.svg` | Il JSON resta il formato standard di Excalidraw, e l'anteprima evita di caricare l'editor per leggere una nota |
| Destinazione della registrazione | La nota attiva, se è salvata e non è una nota del giorno; altrimenti la nota del giorno, sezione "Trascrizioni". Il selettore cambia solo la sezione | Il WAV viene salvato accanto alla nota già all'avvio |
| Preferenze | Preferiti, viste, schede e larghezze in `config.json`, chiave `ui` | Sopravvivono a un reset di WebView2 e si possono modificare a mano |
| Colori delle etichette | Salvati in `config.json`, `ui.tag_colors`, come id della tinta (`{"casa": "verde"}`). Non nei file Markdown | Le note restano Markdown semplice e le tinte seguono il tema |
| Colore iniziale di un'etichetta | Ricavato dal nome, finché non viene cambiato | Stessa etichetta, stesso colore, senza configurare nulla |
| Figlia in ritardo | Segna in ritardo anche la madre, e la scheda indica quale figlia è in ritardo | Altrimenti la scadenza resterebbe nascosta dentro la checklist. Non ancora nel design |
| Figlie in Calendario e Persona | Il Calendario mostra le scadenze delle figlie. La pagina Persona elenca le figlie assegnate a quella persona, con il nome della madre | Una persona a cui è assegnata solo una figlia altrimenti non vedrebbe il proprio compito. Non ancora nel design |
| Colonna di una madre | Dipende solo dalla scadenza della madre; senza scadenza, va in "Senza scadenza" | Regola semplice; l'avviso di ritardo copre il caso urgente |
| Livelli di rientro | L'interfaccia mostra un solo livello: le righe più interne valgono come figlie della madre di primo livello | Una checklist dentro una scheda non regge più livelli. Il file non viene toccato |
| Chiusura dal file o da Claude | La conferma esiste solo nella bacheca e nelle viste. Scrivendo `[x]` nell'editor o usando il tool MCP si chiude solo quella riga; le figlie aperte di una madre chiusa escono dalle azioni aperte | Editor e tool MCP non hanno un momento in cui chiedere conferma |
| Conteggi | Azioni aperte, "N di 4 azioni" e barra settimanale contano solo le azioni di primo livello | Una lista lunga non deve falsare i totali |
| Nuove sotto-attività | Si scrivono nella nota, con Tab su una riga `- [ ]`. La bacheca non ha un campo per aggiungerle | Tiene semplice la prima versione. Da rivedere dopo l'uso |

## Differenze tra design e codice precedente

### Contraddizioni interne al design

- Le modalità della nota cambiano da una tavola all'altra: Modifica/Lettura/.md (Main), Sorgente/Affiancata/Anteprima (Markdown), Modifica/Lettura/Differenze (Revisione), nessuna (Home). Vale la decisione qui sopra.
- La tavola Main ha un pannello destro (Collegamenti, Struttura, Proprietà) che in Home non esiste. Si segue Home: i collegamenti in entrata diventano la pillola "N collegamenti", che apre un riquadro con l'elenco.
- Le tavole più vecchie hanno Decisioni e Registrazioni nella barra; Home no. Avendo scartato il registro, **nessuna vista elenca tutte le decisioni**: restano in Calendario, Etichetta e Persona.
- La tavola Impostazioni e la tavola Markdown dichiarano "11 strumenti", un numero che non corrispondeva a quelli esposti dal server MCP. Non va scritto un numero fisso.

### Cose mostrate che il backend precedente non aveva

| Nel design | Situazione precedente | Cosa fare |
|---|---|---|
| "Completate questa settimana", barra settimanale | `- [x]` non registra la data | `done:` nel file. Le azioni spuntate fuori dall'app non hanno data e compaiono solo in "Fatte" |
| Titolo "Domenica 1 novembre" e file `2026-11-01.md` | Il file è `AAAA-MM-GG-giornata.md`, il titolo "Giornata di domenica 01/11/2026" | Calcolare il titolo solo a schermo; **non rinominare** i file esistenti |
| "Giulia Ferri", alias, statistiche "prima menzione" | Solo nomi `@` | Mostrare `@Giulia`; le date si ricavano dalle note |
| Calendario con registrazioni | Nessun evento registrazione nell'indice | Leggere le righe `🎙️ [Registrazione HH:MM (durata)](file)` nei testi |
| Risultati "Trascrizioni" nella ricerca | La ricerca a testo pieno restituisce solo la nota | Cercare le righe `[mm:ss]` nei testi delle note trovate |
| "Sposta a domani", "+" sulle colonne, campo nuova azione | Si può solo spuntare, senza riaprire | Nuove operazioni su stato e scadenza; le azioni nuove vanno nella nota di oggi, sezione "Priorità" |
| Pausa e annulla registrazione | Non supportati | Aggiungerli (vedi Backend) |
| Riproduzione audio | Assente | `Player` lato Python (vedi Backend) |
| "Briefing in Claude" | L'app non può avviare Claude | Copia il prompt negli appunti e mostra un avviso |

### Conseguenze da accettare

- Senza elenco, una nota vecchia di cui non si ricorda il titolo si trova solo con la ricerca nel testo. La ricerca Ctrl K deve quindi funzionare bene anche senza testo: note recenti, viste, comandi.
- "Nuovo meeting" non ha più un pulsante nel design: resta Ctrl+N e un comando in Ctrl K.
- Ogni avvio crea una nota del giorno vuota. È il motivo per cui le sezioni si creano solo quando servono.

## Architettura

### Backend

**Parser delle note**
- `DONE_RE` e il campo `done_on` delle azioni.
- `with_done(riga, giorno)` e `with_due(riga, giorno)`.
- `headings(corpo)` e `add_to_section(corpo, sezione, blocco)`.
- `TIMESTAMP_RE` e `RECORDING_RE`.
- Azioni con il riferimento alla madre: una riga `- [ ]` rientrata è figlia dell'ultima azione di primo livello sopra di essa.
- `description` delle azioni: le righe rientrate che non sono caselle, subito sotto l'azione.
- `with_person(riga, indice, nome)`, `with_tag(riga, etichetta)` e `with_description(righe, testo)`.
- `file_links(corpo)` per i link a file e `embeds(corpo)` per `![[…]]`.

**Archivio e indice**
- Le colonne `done_on` e `parent_id` per le azioni, con una nuova versione dello schema. L'indice si ricostruisce da solo.
- `complete_with_children`: chiude madre e figlie aperte con una sola scrittura del file. Le figlie già chiuse conservano la loro data.
- L'operazione che cambia lo stato di un'azione scrive o toglie `done:`. Vale anche per il tool MCP, che deve passare dalla stessa operazione.
- `set_action_details`: una sola operazione per scadenza, persona, etichetta e descrizione. Prima di scrivere controlla che la riga non sia cambiata; se è cambiata, non scrive e chiede di ricaricare.
- Aggiunta di testo con sezione opzionale, `audio_path`, `graph_rows`.
- `attach_file`, `resolve_file`, `save_sketch`: i percorsi relativi non possono uscire dalla cartella delle note.
- L'elenco delle azioni restituisce anche `done_on` e `project`.

**Formattazione**
- L'etichetta di scadenza usa testi come `30 ott`, `oggi`, `lun 2 nov` e i livelli `late`, `soon`, `normal`.
- Il raggruppamento delle scadenze usa le chiavi `late`, `soon`, `week`, `later`, `none`. "Questa settimana" arriva fino a domenica.
- `daily_title` e icone `calendar` e `file`.
- Se le regole sulle date compaiono anche nel frontend, le due versioni vanno tenute allineate.

**Servizio per l'interfaccia**: le funzioni per navigazione, elenco note e selettore rapido non servono più; da prevedere:
- `sidebar`: avanzamento di oggi, azioni aperte e in ritardo, numero di persone.
- `action_board`: gruppi, etichetta tolta dal testo o presa dal progetto, azioni fatte. Le fatte senza data vanno limitate (circa 30), perché nel tempo possono diventare centinaia. Ogni madre porta le sue figlie e l'avanzamento; le figlie non sono voci a sé.
- `calendar_data(da, a)`, `people_items`, `person_page`, `tag_page`, `graph_data`.
- `search_all(query, tipo, giorni, ordine)`, con i filtri `@`, `#` e `!`.
- `capture`, `add_action`, `sections(id_nota)`.
- `export_note(id_nota, formato, opzioni)`.

**Audio e registrazione**
- Pausa e ripresa della registrazione, con il tempo trascorso che esclude le pause.
- Annullamento, che cancella il WAV, `set_section`, `configure(modello)`.
- `keep_audio`: il WAV si cancella solo dopo una trascrizione riuscita. Se fallisce resta, come promette il messaggio d'errore.
- `transcript_timestamps`: toglie `[mm:ss]` dal testo.
- `Player`: riproduce con `sounddevice` da Python. Evita un server HTTP con supporto Range e il passaggio di decine di MB in base64 alla pagina (18 minuti di WAV sono circa 35 MB).

**Configurazione**: `keep_audio`, `transcript_timestamps`, `ui` (compreso `ui.tag_colors`), migrazione del tasto globale verso `quick_note`, `claude_config()` condivisa tra impostazioni e riga di comando.

**Applicazione desktop**
- Attenzione: la mappa dei tasti globali va aggiornata insieme alla configurazione, altrimenti Ctrl+Alt+N smette di funzionare senza alcun errore.
- I comandi dell'app e la riga di comando ricevono `capture`; il menu dell'area di notifica riceve "Nota rapida".
- Il calcolo chiaro/scuro e il colore di sfondo iniziale devono conoscere i nuovi temi, compreso `custom`, che è basato su `ui.custom.base`.
- Alla chiusura vanno salvate **tutte** le note modificate: la pagina deve restituire un elenco delle modifiche in sospeso, non una sola nota.
- L'arresto della registrazione invia l'evento `append` alla finestra principale, così funziona anche dalla finestra di registrazione. Se l'app si chiude durante una registrazione, l'aggiunta avviene direttamente sull'archivio, passando anche la sezione.
- Se la pagina principale non è ancora pronta, la nota rapida va scritta direttamente sull'archivio, per non perderla: l'invio di un evento alla pagina non segnala se è arrivato.
- Serve `open_url`, limitato a `http` e `https`, per i link dell'anteprima.
- Serve `open_file`, con le regole di sicurezza descritte in [File collegati](#file-collegati).

### Finestre secondarie (Cattura e Registrazione)

Sono finestre pywebview nascoste create all'avvio (`hidden=True`, `frameless=True`, `on_top=True`) con la stessa API della finestra principale.

- URL: `index.html#capture` e `index.html#recorder`; il punto d'ingresso del frontend sceglie il componente in base all'hash. Dai sorgenti di pywebview 6.2.1, `http.py` toglie il frammento e `window._resolve_url` lo conserva. **Da provare per primo:** le query string invece non sarebbero adatte.
- Alla chiusura vengono nascoste, non distrutte (`events.closing` restituisce `False`).
- All'uscita dall'app vanno distrutte tutte: su Windows l'app termina solo quando non resta nessuna finestra (`winforms.py`, `on_close`).
- Il cambio di tema va inviato anche a queste finestre.

### Stato del frontend

Lo stato del frontend precedente teneva una sola nota alla volta. Con i gruppi di schede va diviso in due:

- **Documenti**: una mappa `chiave → documento`, ciascuno con payload, testo, stato di salvataggio, coda di salvataggi e collegamenti. La chiave resta stabile quando una bozza riceve un id. Il controllo delle modifiche esterne gira su tutti i documenti aperti.
- **Disposizione**: `gruppi[{id, schede, attiva}]`, direzione, dimensioni, gruppo ingrandito, gruppo attivo, schede chiuse.
- **Pagine**: `note:<chiave>`, `person:<nome>`, `project:<nome>`, `view:calendar|actions|people|graph`, `settings`. Quando si salva la disposizione si usa l'id della nota, non la chiave.

**Sincronizzazione della stessa nota in due gruppi:** ogni vista CodeMirror inoltra le proprie modifiche alle altre viste dello stesso documento con un'annotazione, per evitare rimbalzi. Le modifiche inoltrate vanno escluse dalla cronologia delle altre viste (`Transaction.addToHistory.of(false)`). Per ogni coppia gruppo e scheda va conservato l'`EditorState`, così annulla e cursore sopravvivono al cambio di scheda. Una scheda che torna visibile può avere uno stato vecchio: va riallineata al testo del documento.

Il comportamento di trascinamento, divisione, chiusura e riapertura è già scritto in `Home.dc.html`, righe 588-698 e 1426-1491. Si può portare quasi com'è.

### Componenti

| Azione | Componenti |
|---|---|
| Parti principali | Guscio dell'app, barra laterale (240 px, compressa 56 px), pagina nota, stato, dati finti, foglio di stile |
| Da creare | `Workspace`, `Group`, `SidebarRail`, `SearchPalette`, `CalendarView`, `ActionsView`, `ActionRow`, `ActionPills`, `SubtaskList`, `TagColorPicker`, `tags.js`, `PeopleView`, `GraphView`, `SettingsView`, `PersonPage`, `TagPage`, `Preview`, `ExportDialog`, `FileChip`, `SketchEmbed`, `SketchEditor`, `CaptureWindow`, `RecorderWindow`, `themes.js`, `editor/markdown.js` |
| Da non riproporre | Elenco note, selettore rapido, controllo di registrazione separato, pagina unica per persone ed etichette |
| Di supporto | Editor, menu della nota, campo persone (come pillole), riquadro dei collegamenti, sovrapposizioni, icone |

La trascrizione in corso si mostra sul pulsante "Registra" della barra laterale.

### Etichette colorate

Riferimento: tavola Home, funzioni `tagPalette` (righe 512-518) e `tagSwatches` (riga 559), e scheda Impostazioni › Etichette.

| Id | Temi scuri | Temi chiari | | Id | Temi scuri | Temi chiari |
|---|---|---|---|---|---|---|
| `ambra` | `#E8A84A` | `#7F4C04` | | `blu` | `#8DB4F0` | `#2259BA` |
| `corallo` | `#F28B7D` | `#A12D22` | | `ciano` | `#5CC6D0` | `#0A6370` |
| `rosa` | `#EE8FBD` | `#9C2465` | | `verde` | `#7CC48F` | `#1F6937` |
| `viola` | `#C3A2F2` | `#7238B8` | | `oliva` | `#BDC46A` | `#535C12` |
| `grigio` | `#B4B1A9` | `#5C5951` | | | | |

- **Contrasto:** il testo sulla pillola (sfondo al 14% della stessa tinta) è almeno 4,6:1 sulle superfici di tutti i temi predefiniti. Il tema Personalizzato usa la colonna della sua base e può scendere sotto questa soglia, perché i suoi colori sono liberi.
- **Dove si vede il colore:** testo delle note, pillole, schede delle azioni, gruppi per progetto, titolo della pagina etichetta, linguette, preferiti, ricerca e grafo. Un'azione fatta usa il colore tenue.
- **Dove si sceglie:** dal pulsante "Colore" nella pagina dell'etichetta, o da Impostazioni › Etichette. Il colore selezionato ha anche un segno di spunta, così non dipende solo dalla tinta.
- **Valori iniziali nel mock:** `#quicknotes` ambra, `#lavoro-q4` ciano, `#casa` verde, `#lettura` rosa. Il blu è evitato per `#lavoro-q4` perché è il colore delle `@persone`.
- "Ripristina predefiniti" azzera anche i colori scelti.
- Le tavole più vecchie (Azioni, Ricerca, Grafo e altre) mostrano ancora le etichette nel colore precedente: vale Home.

### Sotto-attività

Riferimenti: tavola `SottoA` per file e bacheca affiancati; tavola Home per bacheca, elenco, pagina etichetta e nota del giorno (righe 805-840).

```markdown
- [ ] Preventivo cucina #casa due:2026-11-06
    - [x] Misurare la parete del lavello done:2026-11-01
    - [ ] Richiedere tre preventivi @Marco
    - [ ] Scegliere il top in quarzo due:2026-11-04
```

- **In bacheca** appare solo la madre, con "1 di 3", una barra di avanzamento e la checklist richiudibile.
- **Le figlie** ereditano etichetta e persone della madre; persone e scadenza proprie si scrivono sulla loro riga.
- **Spuntare una figlia** scrive `done:` su quella riga. Non chiude la madre, nemmeno se è l'ultima: compare il pulsante "Tutte fatte · Chiudi l'azione".
- **Spuntare una madre con figlie aperte** chiede conferma: "Restano N aperte", con "Completa tutte" e "Annulla".
- **Riaprire una madre** non riapre le figlie.

Le altre tre proposte restano sul canvas come riferimento, ma sono scartate:

| Opzione | Comportamento | Motivo per scartarla |
|---|---|---|
| B, schede autonome | Ogni figlia è una scheda; la madre si chiude da sola | Riempie presto la bacheca, e la chiusura automatica può sorprendere se si aggiunge una figlia dopo |
| C, passi in sequenza | `1. [ ]` numerato; appare solo il passo corrente | Serve solo ai lavori con un ordine preciso. Si può aggiungere in seguito senza cambiare i file già scritti |
| D, azione-nota | `- [ ] [[Nota]]`; le figlie stanno nella nota collegata | Introduce un secondo modo di definire le figlie. I link `[[...]]` restano comunque disponibili nel testo |

### Barra laterale

Riferimento: tavola Home, `FLY` e `railItems` (righe 1178-1202). La tavola `BarraE` resta come confronto, ma vale Home.

- **Predefinito:** la barra è aperta, da 240 px, ed è quella già approvata nella tavola Home: ricerca, Oggi e viste con i conteggi, Preferiti, Registra e Impostazioni. La scelta dell'opzione E non la cambia. Si comprime con il pulsante in alto o con Ctrl \\.
- **Da compressa:** striscia da 56 px. La `q` in alto la riapre; sotto ci sono Cerca, Oggi e le viste, poi i preferiti, e in fondo Registra e Impostazioni.
- **Pannello rapido:** passando sopra un'icona, o raggiungendola con la tastiera, si apre un pannello con nome, scorciatoia e scelte rapide. Il clic sull'icona apre la vista, Esc chiude il pannello.
- **Contenuti del pannello:**

| Icona | Scelte rapide |
|---|---|
| Cerca | Note recenti, ricerca completa |
| Oggi | Nota di oggi, ieri, domani |
| Calendario | Questa settimana, mese corrente |
| Azioni | In ritardo, aperte, completate, con i conteggi |
| Persone | Persone recenti, tutte le persone |
| Grafo | Attorno alla nota aperta |
| Registra | Avvia la registrazione |
| Impostazioni | Aspetto, Navigazione, Etichette, Claude |

- **Preferiti:** gli stessi della barra aperta, come riquadri colorati con il colore dell'etichetta o delle persone. Il nome è nel suggerimento al passaggio del mouse. Con molti preferiti la loro zona scorre, e Registra e Impostazioni restano visibili.
- **Da fare nell'app, non nel mock:** un breve ritardo prima dell'apertura (circa 120 ms), per non far lampeggiare i pannelli quando si scorre la barra. Nel mock le voci "ieri" e "domani" aprono il Calendario sul giorno, perché le altre note del giorno non esistono.

### Dettagli delle azioni

Riferimento: tavola Home, `actRow` (riga 892) e popover `pop` (riga 1493). La tavola `DettagliA` mostra il testo scritto nel file accanto alle pillole.

```markdown
- [ ] Mandare a @Giulia la bozza del budget Q4 #lavoro-q4 due:2026-11-02
    Allegare il foglio costi aggiornato.
    - [ ] Raccogliere le voci di ottobre
```

- **Dove:** bacheca, elenco e pagina etichetta, solo sulle azioni aperte di primo livello. Le azioni fatte mostrano i dati senza modificarli. Le sotto-attività mantengono il testo scritto nella nota.
- **Campi:** scadenza, persona, etichetta e descrizione. Ogni pillola apre un piccolo popover, che si chiude con Esc o con un clic fuori.
- **Scadenza:** scelte rapide e "Altra data". Scrive `due:` e sposta la scheda nella colonna giusta. "Nessuna" toglie `due:`.
- **Persona:** una pillola per ogni `@` della riga. Cambiare persona sostituisce il nome al suo posto, così la frase resta corretta; aggiungerne una la scrive in fondo. Togliere una persona in mezzo alla frase cancella solo il nome, quindi la frase va eventualmente riletta.
- **Etichetta:** ricerca con colore e creazione di un'etichetta nuova; dal popover si apre anche la sua pagina. Se la riga ha più `#`, la pillola gestisce la prima e lascia invariate le altre.
- **Descrizione:** testo su più righe, scritto con il rientro sotto l'azione e mostrato sotto il titolo.
- **Scrittura:** se la nota è aperta, la modifica passa dallo stesso meccanismo di "Inserimento in sezione in una nota aperta", così resta annullabile. Se il file è cambiato nel frattempo, l'app non scrive e chiede di ricaricare.
- **Tastiera:** aprendo un popover il focus entra nel popover e, alla chiusura, torna sulla pillola. Nel mock il focus non si sposta: va implementato nell'app.
- **Limite del mock:** la nota del giorno segue le modifiche, ma Calendario, Persona e la nota Riunione budget no.

Le altre proposte restano sul canvas come riferimento:

| Tema | Opzioni scartate |
|---|---|
| Barra chiusa | A, icone con etichetta · B, sparisce e riappare · C, dentro la barra delle schede · D, dock in basso |
| Dettagli delle azioni | B, pannello laterale · C, la riga si apre · D, frase libera riconosciuta · E, comandi con `/` |

Le tavole `BarraKit` e `DettagliKit` servono solo a far funzionare queste proposte.

### File collegati

Riferimento: tavola Home, nota "Riunione budget Q4", e `fileChips` (riga 1396).

```markdown
[Preventivi fornitori.pdf](allegati/preventivi-fornitori.pdf)
[Contratto 2025.pdf](<file:///D:/Contratti/contratto 2025.pdf>)
```

- **Formato:** link Markdown normali, così la nota resta leggibile anche fuori dall'app.
- **Come si aggiungono:** dal menu `⋯` della nota o da Ctrl K. Il trascinamento nella nota non è ancora disegnato.
- **Copia:** per impostazione predefinita il file finisce in `allegati/` accanto alla nota, e un nome già presente riceve un numero. Con l'opzione disattivata la nota punta all'originale.
- **Nell'interfaccia:** i file appaiono come riquadri con nome, tipo e dimensione. Un file mancante mostra "File non trovato" e non si apre.

**Sicurezza.** Le note possono arrivare da Claude o da una cartella sincronizzata, quindi un link può puntare a un eseguibile. `open_file` deve:
- risolvere il percorso sul lato Python e rifiutare i relativi che escono dalla cartella delle note;
- rifiutare eseguibili e script (`.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.js`, `.lnk`, `.msi` e simili), anche dentro `allegati/`;
- chiedere conferma, mostrando il percorso completo, per i file fuori dalla cartella delle note;
- accettare solo percorsi locali: niente `file://` verso condivisioni di rete.

### Esportazione

Riferimento: tavola Home, finestra "Esporta la nota" (`exportFormats` e `exportRows`, righe 1412-1424).

| Formato | Risultato | Opzioni |
|---|---|---|
| PDF | Da stampare o inviare | A4 o Letter, aspetto chiaro o tema attuale, schizzi e immagini, azioni completate |
| HTML | Pagina che si apre in un browser | Aspetto, file unico con le immagini incorporate, schizzi e immagini, azioni completate |
| Markdown | Copia della nota | Copia dei file collegati, azioni completate |

- Si apre dal menu `⋯` o con Ctrl Shift E. Il percorso di destinazione si sceglie prima di esportare; il design mostra solo un percorso d'esempio, quindi il selettore è da disegnare.
- HTML e PDF nascono dalla stessa pagina generata con `marked` e sanificata con DOMPurify, con il foglio di stile incorporato e senza script.
- Gli schizzi diventano immagini; gli altri file restano link.
- **PDF, da verificare per primo:** WebView2 ha `PrintToPdfAsync`, ma non è stato verificato se si può raggiungere da pywebview. L'alternativa è `window.print()`, che apre la finestra di stampa con "Salva come PDF".

### Schizzi Excalidraw

Riferimento: tavola Home, nota "Requisiti e architettura" e pagina `sketch`.

```markdown
![[schizzo-architettura.excalidraw]]
```

- **File:** `allegati/schizzo-architettura.excalidraw` (il JSON di Excalidraw) e `schizzo-architettura.excalidraw.svg`, riscritto a ogni salvataggio.
- **Nella nota:** l'anteprima viva e l'Anteprima mostrano l'SVG, sanificato con DOMPurify, con un pulsante "Modifica". Un file mancante mostra un segnaposto con il nome.
- **Modifica:** lo schizzo si apre in una scheda, come una nota, con salvataggio automatico. La stessa scheda può stare in due gruppi soltanto se si risolve la sincronizzazione: per la prima versione conviene aprirla in un solo gruppo.
- **Temi:** l'SVG salvato usa colori fissi; il comportamento nei temi scuri va deciso provandolo con Excalidraw reale.
- **Da fare:** Ctrl K e il menu `⋯` creano un nuovo schizzo e inseriscono il riferimento alla posizione del cursore. Nel mock aprono sempre lo schizzo d'esempio.

**Da verificare prima di implementare:**
- `@excalidraw/excalidraw` è un componente React. Va montato in un componente Svelte, con React e l'editor in un blocco caricato solo quando si apre uno schizzo.
- Deve funzionare offline: anche i suoi font e le altre risorse vanno inclusi nel pacchetto, e nessuna richiesta deve uscire dal computer. Serve una prova con la rete disattivata.
- Va misurato quanto cresce il pacchetto dell'interfaccia.

### Editor Markdown

- **Avvisi:** righe `> [!NOTE]` nell'anteprima viva, con il selettore che appare scrivendo `> [!`. Colori dalla tavola Markdown: NOTE `#4493F8`, TIP `#3FB950`, IMPORTANT `#AB7DF8`, WARNING `#D29922`, CAUTION `#F85149`.
- **Tabelle:** vanno in uno `StateField`, non in un `ViewPlugin`, perché CodeMirror vieta le decorazioni a blocco dai plugin. Si mostra il testo grezzo quando il cursore è nella tabella.
- **Note a piè di pagina:** `@lezer/markdown` non le riconosce; `[^1]` va gestito con un'espressione regolare.
- **Spunte:** i comandi che spuntano un'attività o un'azione devono scrivere e togliere `done:`, e la scritta va nascosta come `due:`.
- **Sotto-attività:** Tab e Maiusc+Tab rientrano e riportano indietro una riga `- [ ]`. Il rientro si mantiene andando a capo.
- **Minutaggio:** `[mm:ss]` a inizio riga diventa un pulsante. Il WAV è quello della riga `Registrazione HH:MM` che corrisponde al titolo `Trascrizione HH:MM` precedente; se non c'è, l'ultimo link audio sopra la riga.
- **Descrizione delle azioni:** le righe rientrate sotto un'azione mantengono il rientro andando a capo e non contano come sotto-attività.
- **File e schizzi:** i link a file diventano riquadri e `![[….excalidraw]]` diventa l'anteprima dello schizzo; quando il cursore è sulla riga si vede il testo grezzo.
- **Modalità:** `Compartment` per passare dall'anteprima viva al sorgente, con numeri di riga e font monospace. La barra in basso appare solo fuori dall'anteprima viva.

**Sicurezza dell'Anteprima.** Le note possono arrivare da Claude o da una cartella sincronizzata, e la pagina ha accesso a `pywebview.api`, che comprende operazioni come l'eliminazione delle note. L'HTML generato da `marked` va **sempre** sanificato con DOMPurify. I clic sui link vanno intercettati: i `[[link]]` restano nell'app, quelli esterni passano da `open_url`. Le icone degli avvisi vanno messe con una maschera CSS, così non servono SVG nell'HTML sanificato.

**Inserimento in sezione in una nota aperta.** Python e JavaScript contano le posizioni nel testo in modo diverso (gli emoji come 🎙️ falsano gli indici). Quindi Python restituisce il testo nuovo (`add_to_section`) e la pagina calcola prefisso e suffisso comuni, poi invia a CodeMirror solo la differenza. Così c'è una sola implementazione e la modifica resta annullabile.

### Temi

- I valori dei 6 temi sono in `Home.dc.html`, righe 504-509. L'id `crepuscolo` ha come nome visibile "Lavanda": conviene usare `lavanda`.
- `onAccent` e `resolveTheme` (righe 519-541) si possono riprendere.
- I token del design vanno mappati su nomi semantici propri dell'app, non introdotti come `--t-*`.
- Attenzione al testo secondario: il suo corrispondente nel design è `--t-subtle`, non `--t-faint`, che è più tenue.

### Scorciatoie

| Tasto | Azione |
|---|---|
| Ctrl K, Ctrl P, Ctrl O | Ricerca e comandi |
| Ctrl F | Cerca nella nota |
| Ctrl Shift E | Esporta la nota |
| Ctrl N, Ctrl Shift N | Nuovo meeting, nuova nota |
| Ctrl W, Ctrl Shift T | Chiudi scheda, riapri scheda chiusa |
| Ctrl \\ | Comprimi la barra laterale |
| Ctrl Alt \\ | Dividi a destra |
| Ctrl 1…6 | Oggi e viste, nell'ordine della barra |
| Ctrl , | Impostazioni |
| Ctrl Alt N, D, R (globali) | Nota rapida, nota del giorno, registrazione |

Ctrl W e Ctrl 1…6 vanno provati in WebView2: non è stato verificato se il browser li intercetta prima della pagina.

## Ordine di lavoro proposto

1. **Backend e test:** parser (comprese sotto-attività e descrizioni), archivio, formattazione, servizio, audio, apertura sicura dei file. Si può provare tutto senza interfaccia.
2. **Temi, font e guscio:** token, `themes.js`, tinte delle etichette, barra laterale aperta e compressa, foglio di stile, con dati finti presi dal design.
3. **Stato e schede:** documenti, gruppi, divisione, trascinamento, sincronizzazione. È la parte più rischiosa, conviene farla prima delle viste.
4. **Pagina nota ed editor:** intestazione a pillole, avvisi, tabelle, modalità, Anteprima sanificata, `done:`, rientro delle sotto-attività, link a file.
5. **Viste:** Azioni con pillole e checklist delle sotto-attività, Calendario, Persone, Persona, Etichetta con scelta del colore, Grafo, Impostazioni.
6. **Ricerca Ctrl K** con pannello di anteprima e comandi.
7. **Finestre** Cattura e Registrazione, riproduzione audio, area di notifica.
8. **Esportazione:** prima la verifica del PDF, poi HTML, PDF e Markdown.
9. **Schizzi:** prima una prova isolata di Excalidraw in Svelte, offline; poi editor, anteprima e incorporamento. Se la prova fallisce, le altre funzioni non ne risentono.
10. **README e interfaccia compilata** inclusa nel pacchetto. Il README oggi descrive elenco, Ctrl+O e temi vecchi.

### Test da prevedere

- Il servizio per l'interfaccia, sulle nuove funzioni al posto di navigazione, elenco note e selettore rapido.
- La registrazione, compreso l'evento `append` che riceve `section` e `toast`.
- L'app e l'archivio, sulle azioni e sulla configurazione.
- `with_done` e `with_due`: rientro conservato, nessuno spazio doppio, ordine `due:` poi `done:`, riapertura.
- `add_to_section`: sezione assente, nota vuota, titoli dentro un blocco di codice, sezione seguita da un'altra, maiuscole.
- Il raggruppamento delle scadenze di domenica e a cavallo della settimana.
- Sotto-attività nel parser: rientro con spazi e tabulazioni, più livelli, figlia senza madre, righe `- [ ]` dentro un blocco di codice.
- `complete_with_children`: chiude solo le figlie aperte e conserva le date già scritte.
- Eredità di etichetta e persone, e conteggi limitati alle azioni di primo livello.
- Colore di un'etichetta: stabile a parità di nome, con precedenza a `ui.tag_colors`; un id di tinta sconosciuto torna al colore automatico.
- Descrizioni nel parser: più righe, azione con descrizione e figlie, riga rientrata senza azione sopra.
- `with_person`: sostituzione al posto giusto con più `@`, aggiunta in fondo, rimozione senza spazi doppi. `with_tag` lascia invariate le altre etichette.
- `set_action_details`: rifiuta la scrittura se la riga è cambiata, e non tocca `done:`.
- `open_file`: rifiuta eseguibili, percorsi relativi fuori dalla cartella e condivisioni di rete; chiede conferma per i file esterni.
- `attach_file`: nomi già presenti, copia e collegamento all'originale.
- `embeds` e `file_links`: riferimenti dentro un blocco di codice, nomi con spazi, file mancanti.
- Esportazione: l'HTML non contiene script, gli schizzi diventano immagini e le opzioni vengono rispettate.
- Migrazione del tasto globale verso `quick_note`.
- `audio_path` rifiuta file fuori dalla cartella delle note.
- `keep_audio=False` tiene il WAV se la trascrizione fallisce.

### Verifica dell'interfaccia

- Anteprima con dati finti: server di sviluppo del frontend aperto in una modalità che non richiede il backend. Edge è installato e si può guidare con `playwright-core` (`channel: 'msedge'`), senza scaricare un browser. Questa strada non è ancora stata provata.
- Da provare a schermo: pannelli della barra compressa ai bordi della finestra, popover delle pillole in fondo alla bacheca e in più gruppi, temi chiari.
- Le finestre secondarie, i tasti globali, l'audio, il PDF e l'apertura dei file si possono verificare solo nell'app vera. Per non toccare i dati reali, l'app deve poter usare cartelle temporanee per note e configurazione, per esempio tramite variabili d'ambiente.

## Appendice: bozza per il parser

Viene da una patch annullata sul codice precedente. È stata applicata ma mai eseguita da un test. `DUE_RE` e `FENCE_RE` non sono definite qui: indicano le espressioni per la scadenza `due:` e per l'apertura di un blocco di codice.

```python
DONE_RE = re.compile(r"\bdone\s*:\s*(\d{4}-\d{2}-\d{2})", re.I)


def _squeeze(line: str) -> str:
    """Toglie gli spazi rimasti doppi dopo aver levato un'etichetta, senza toccare il rientro."""
    indent = line[:len(line) - len(line.lstrip())]
    return indent + re.sub(r"[ \t]{2,}", " ", line.strip())


def with_done(line: str, day: str | None) -> str:
    """La riga di un'azione con la data di completamento indicata (None la toglie)."""
    bare = _squeeze(DONE_RE.sub("", line))
    return f"{bare} done:{day}" if day else bare


def with_due(line: str, day: str | None) -> str:
    """La riga di un'azione con la scadenza indicata (None la toglie), prima di un eventuale done:."""
    done = DONE_RE.search(line)
    bare = _squeeze(DONE_RE.sub("", DUE_RE.sub("", line)))
    return bare + (f" due:{day}" if day else "") + (f" done:{done.group(1)}" if done else "")


def add_to_section(body: str, section: str | None, block: str) -> str:
    """Il corpo con `block` in fondo alla sezione indicata, creata alla fine della nota se manca.

    Senza sezione il blocco va in fondo alla nota, separato da una riga vuota.
    """
    block = block.strip("\n")
    lines = body.rstrip("\n").split("\n") if body.strip() else []
    start, level, in_fence = None, 0, False
    for i, line in enumerate(lines if section else []):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence and (m := HEADING_LINE_RE.match(line)) and m.group(2).lower() == section.lower():
            start, level = i, len(m.group(1))
            break
    if start is None:
        tail = [f"## {section}", block] if section else [block]
        return "\n".join(lines + ([""] if lines else []) + tail) + "\n"
    end, in_fence = len(lines), False
    for i in range(start + 1, len(lines)):
        if FENCE_RE.match(lines[i]):
            in_fence = not in_fence
        elif not in_fence and (m := HEADING_LINE_RE.match(lines[i])) and len(m.group(1)) <= level:
            end = i
            break
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[:end] + [block] + lines[end:]) + "\n"
```

`HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")`
