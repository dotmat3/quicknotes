# Stato del lavoro

Aggiornato al 13 novembre 2026. Come è costruita l'app è in [architettura.md](architettura.md), le regole di prodotto in [piano-implementazione-design.md](piano-implementazione-design.md), come si pubblica una versione in [rilascio.md](rilascio.md).

## Dove siamo

- **Ultima versione pubblicata:** 0.6.0 (10 novembre 2026, tag `v0.6.0`): progetti, stati delle azioni, Agenda e Revisione settimanale.
- **Su `main` dopo la 0.6.0, non ancora rilasciato:** azioni rapide di Agenda e Revisione sulla riga della nota, cattura veloce tolta da Agenda, barra laterale ridimensionabile, colori dei progetti con le tessere colorate nella barra laterale, nome di Micio.
- **Git:** si lavora su `main`, il ramo principale (fino al 13 novembre si chiamava `rust-tauri`). Il primo `main`, fermo al commit `eb05f3e` della prima versione Python, è nella storia: il codice cancellato si legge con `git show eb05f3e:<percorso>`. Il branch `progetti-riepilogo` non è unito, vedi sotto.

## Per ripartire

1. Leggere questo file e [architettura.md](architettura.md). Il riferimento visivo è la tavola Home del [design](https://claude.ai/artifact/1ZCTE9XczJ49BE4LQyGN2h), che si legge con l'azione `read` dello strumento Artifact e `path: "project/Home.dc.html"`.
2. Controllare che tutto sia ancora verde:

```bash
.venv/Scripts/python -m unittest discover -s tests
npm --prefix frontend test
npm --prefix frontend run build
node scripts/prova-python.mjs
```

**Dati reali:** `~/QuickNotes` e `~/.quicknotes` contengono le note vere dell'utente. Ogni prova deve usare `QUICKNOTES_DIR` e `QUICKNOTES_CONFIG_DIR`, come fanno gli script. Avviare `python -m quicknotes` a mano, senza queste variabili, lavora sulle note vere e crea la nota del giorno.

**Con l'app dell'utente aperta:** non va chiusa. Le prove si avviano con `USERNAME=qn-prova` davanti al comando, così l'istanza di prova non finisce nella finestra dell'utente; nella copia di prova mancano solo i tasti globali, già presi.

## Le prove nell'app vera

`node scripts/cdp.mjs <cartella> <foto.png o ""> scripts/<prova>`, sempre con una cartella di prova nuova, preparata così:

| Prova | Cartella | Note |
|---|---|---|
| `prova-python.mjs` | Nessuna: si avvia da sola con `node scripts/prova-python.mjs` | Scrittura, salvataggio, comandi, modifiche esterne, immagini, chiusura |
| `prova-editor.mjs` | Vuota | |
| `prova-azioni.mjs`, `prova-viste.mjs`, `prova-desktop.mjs`, `prova-modalita.mjs`, `prova-gruppi.mjs`, `prova-collegamenti.mjs`, `prova-gfm.mjs`, `prova-guida.mjs`, `prova-ricerca.mjs`, `prova-priorita.mjs`, `prova-rinomina.mjs` | Con `node scripts/demo-note.mjs <cartella>` | |
| `prova-micio.mjs` | Con `demo-note.mjs` | Serve anche `QN_CFG=<cartella cfg>`: alla fine legge le preferenze salvate |
| `prova-agenda.mjs` | Con `node scripts/demo-progetti.mjs <cartella>` | Agenda, Progetto, Revisione e stati delle azioni, controllati anche nei file |
| `prova-migrazione.mjs` | Con `node scripts/demo-migrazione.mjs <cartella>` | Note nel formato di prima della 0.6.0 |
| `prova-immagini.mjs` | Con `demo-note.mjs` | L'ultimo passaggio mette un'immagine negli appunti di Windows e preme Ctrl V davvero: sostituisce gli appunti, e per qualche secondo il PC non va usato |
| `prova-sistema.mjs` | Con `demo-note.mjs` | Tasti e mouse veri per circa 20 secondi: il PC non va usato. Nessun'altra QuickNotes aperta. Alla fine esce dall'app dal menu |
| `prova-schede.mjs`, poi `prova-riavvio.mjs` | Con `demo-note.mjs` | Stessa cartella e stesso `QN_CFG=<cartella cfg>`. La prima chiude l'app, quindi aspettare 2 secondi prima della seconda |
| `misura-latenza.mjs` | Con `demo-note.mjs` | Scrittura, cambio scheda e memoria. Il passaggio sulla lista di 500 righe oggi si blocca, vedi i difetti |
| `misura-ricerca.mjs` | Con 1000 note di `genera_note.py` | Tempi di `search_all` e di Ctrl K a ogni tasto |

Se una prova stampa `ERRORI DELLA PAGINA`, va considerata fallita anche quando tutti i controlli `ok:` sono passati. Una prova può dichiarare gli errori che provoca di proposito con `export const expectedErrors`: `cdp.mjs` li conta a parte.

**Limiti dell'ambiente:** in Git Bash i comandi molto lunghi con heredoc possono fallire con `unexpected EOF`; meglio scrivere i file con lo strumento apposito. `ln -s` copia le cartelle invece di collegarle. `gh` non è installato: le release si caricano a mano su GitHub.

## Prossimi passi

1. **Dall'utente, sul PC aziendale:** migrare le note vere con la vista Migrazione, usare la 0.6.0 per una settimana, poi regolare le soglie di Agenda e Revisione in `quicknotes/views.py` (2, 7 e 14 giorni).
2. **Prossima versione:** rilasciare quello che è su `main` dopo la 0.6.0, dopo aver corretto i contatori della barra laterale (primo difetto qui sotto).

## Da decidere con l'utente

- **Branch `progetti-riepilogo`, non unito:** pagina con tutti i progetti, sezione `## Stato` scritta nelle note hub, panoramica dei progetti via MCP. Cosa contiene, le scelte da rivalutare e come provarlo in [branch-progetti-riepilogo.md](branch-progetti-riepilogo.md).
- **Registrazione:** non è disponibile nella versione Python (vedi [architettura.md](architettura.md#registrazione-non-disponibile)). Va deciso se portarla, e allora valgono le domande aperte della tappa 12 in [piano-incrementale.md](piano-incrementale.md) (video, fine della registrazione, soglie dello spazio), oppure togliere dall'interfaccia il pulsante Registra, il tasto Ctrl Alt R e le impostazioni che oggi non hanno effetto.
- **Pulsanti `+` delle pillole:** nascosti lasciano a volte una riga vuota nelle schede; mostrandoli al passaggio del mouse senza riservare spazio, le schede si sposterebbero sotto il puntatore.
- **Proposte ancora non confermate** in [piano-implementazione-design.md](piano-implementazione-design.md#proposte-non-ancora-confermate), tra cui figlia in ritardo e figlie in Calendario.
- **Note del giorno vuote:** l'app le crea a ogni avvio e con le frecce, e il Calendario con "Crea la nota del giorno".

## Difetti e limiti noti

Verificati il 13 novembre 2026:

- **Contatori dopo un salvataggio dall'editor:** scrivendo o spuntando un'azione nella nota, il salvataggio non emette `index-updated`, quindi i contatori della barra laterale (Oggi, Azioni) e le viste già aperte restano vecchi finché non arriva un altro evento. Provato: "Oggi 1/4" resta tale dopo aver aggiunto un'azione, anche cambiando pagina. Le modifiche fatte dalle viste e quelle esterne invece aggiornano tutto.
- **Registrazione:** il pulsante Registra della barra laterale aperta non fa nulla; Ctrl Alt R e Registra della striscia compressa mostrano solo un avviso. Il tasto viene comunque tolto alle altre app.
- **`misura-latenza.mjs`:** il passaggio sulla lista unica di 500 righe aspetta che l'ultima riga compaia nel testo dell'editor, ma CodeMirror disegna solo le righe visibili, e la misura si blocca. Le misure precedenti a quel passaggio sono valide.
- **Indicizzazione completa** sopra l'obiettivo dei 2 secondi (2,5 s con 1000 note), ma uguale per la 0.4.0 misurata lo stesso giorno: dipende dallo stato del PC. Vedi [architettura.md](architettura.md#limiti-misurabili).

Ereditati dalla versione Rust (l'interfaccia è la stessa), non ricontrollati uno per uno dopo il passaggio a Python:

- **Nota rapida subito dopo l'avvio:** la finestra si prepara dopo circa 1,5 secondi. Prima di allora Ctrl Alt N apre la finestra principale.
- **Calendario:** "Ieri" e "domani" non sono nel pannello rapido di Oggi, a differenza della tavola Home. Una registrazione aggiunta giorni dopo a una nota compare nel giorno della nota, non in quello della registrazione: il nome del WAV non ha la data.
- **Ctrl K:** ci sono i tipi Note, Azioni, Decisioni e Trascrizioni; mancano il filtro "Ultimi 90 giorni" e l'ordinamento della tavola Ricerca. Le trascrizioni si cercano solo nelle 15 note trovate dalla ricerca a testo pieno.
- **Pagina Persona:** le azioni si possono solo leggere, senza spunta né pillole. Il piano del design prevede le pillole solo in bacheca, elenco e pagina etichetta.
- **Scorciatoia Ctrl K W** non implementata, come proposto nel piano del design.
- **Grafo:** le note del giorno vuote sono nascoste con "Note isolate" spento, che è il valore iniziale. I link verso note inesistenti non diventano nodi.
- **Anteprima e tabelle:** i file collegati che non sono immagini mostrano solo il nome; i link a file non si aprono. Le immagini dal web restano un segnaposto con il nome, per scelta.
- **Immagini:** il nome è data e ora (`AAAA-MM-GG-HHMMSS.png`); sopra i 10 MB l'app chiede conferma, sopra i 50 MB rifiuta. Non si ridimensionano né si comprimono. Un'immagine mancante fa comparire in console un 404 prima del segnaposto.
- **Menu `⋯`:** contiene solo le modalità. Esporta, Allega un file e Inserisci uno schizzo erano le tappe 13 e 14 della versione Rust.
- **Dipendenze di sviluppo:** `npm audit` segnala avvisi su `vitest` e sul plugin Svelte di Vite. Non finiscono nel pacchetto dell'app.
