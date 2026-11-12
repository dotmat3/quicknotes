# Branch `progetti-riepilogo`: da rivalutare

Il branch `progetti-riepilogo` (commit `6c74231`, partito da `main` al commit `080b667` del 13 novembre 2026) contiene un lavoro finito e provato con i test, ma **non unito a `main`**. L'utente non era convinto dell'approccio e vuole rivalutarlo con calma. Questa pagina dice cosa c'è dentro, quali scelte comporta e come provarlo, per decidere se unirlo, cambiarlo o buttarlo.

Cosa è già in `main` e non dipende da questo branch: i colori dei progetti (pulsante Colore nella vista Progetto, Impostazioni › Colori) e la sezione Progetti della barra laterale con le tessere colorate.

## Cosa contiene

Tre cose, costruite sulla stessa funzione di riepilogo.

### 1. Il riepilogo di un progetto (`views.projects_overview`)

Una funzione unica calcola, per ogni progetto, anche in pausa o chiuso:

- azioni aperte (solo quelle di primo livello, come nella vista Progetto), in ritardo, in attesa, domande;
- azioni fatte negli ultimi 7 giorni (contano anche le sotto-attività);
- azioni aperte divise per area;
- ultima attività: la data più recente tra azioni fatte, righe di log nei daily e note collegate (l'hub e l'archivio non contano);
- attività degli ultimi 14 giorni, giorno per giorno (azioni fatte più righe di log);
- le prime 3 azioni da fare (prima le scadute, poi quelle in corso, poi per data);
- l'ultima decisione.

La stessa funzione serve la pagina Progetti, la sezione Stato e l'MCP: i numeri coincidono ovunque.

### 2. La sezione `## Stato` scritta nella nota hub

È la parte più discutibile, ed è stata scelta dall'utente rispetto all'alternativa di mostrarla solo a schermo.

- **Dove:** in cima al corpo di ogni nota di progetto (`progetti/*.md`), tra due commenti `<!-- quicknotes:stato -->` e `<!-- /quicknotes:stato -->`.
- **Contenuto:** una riga con i conteggi, le aree, l'ultima attività, "Da fare adesso" con le prime 3 azioni, l'ultima decisione. Solo date assolute (`entro il 20/11/2026`), così il testo cambia quando cambiano i dati e non ogni giorno.
- **Quando si aggiorna:** poco dopo ogni aggiornamento dell'indice (anche per modifiche fatte da Obsidian o da Claude via MCP), all'avvio e a mezzanotte. Riscrive il file solo se il contenuto è diverso: la seconda passata non trova nulla e non si gira in tondo.
- **Il parser salta la sezione,** come un blocco di codice: le azioni citate, le `@persone` e le `#etichette` lì dentro non diventano azioni, log, persone o etichette doppie. Anche la ricerca la ignora.
- **Nell'editor** i due commenti non si vedono (tornano visibili con il cursore sopra) e la sezione appare in un riquadro tenue. Nell'Anteprima i commenti spariscono comunque.
- **Conflitti:** se l'hub è aperto e ha modifiche non salvate mentre l'app riscrive la sezione, il salvataggio non è un conflitto: si tiene il testo dell'editor con la sezione Stato più recente. Una modifica vera fatta fuori dall'app resta un conflitto, come prima.
- **Al primo avvio** l'app scrive la sezione in tutte le note di progetto esistenti, anche quelle in pausa o chiuse.

### 3. La pagina Progetti e l'MCP

- **Pagina Progetti** (variante A delle proposte nella tela di design "Sidebar Progetti", pagina "Tutti i progetti"): si apre cliccando il titolo "Progetti" nella barra laterale o con Ctrl K › Tutti i progetti. Una scheda per progetto attivo (tessera colorata, azioni aperte, pillole "in ritardo" e "in attesa", barra delle aree, fatte in 7 giorni con mini grafico); sotto, i progetti in pausa o chiusi con "Riattiva".
- **MCP:** `list_projects` restituisce il riepilogo di tutti i progetti invece dei soli conteggi per area. Il nuovo strumento `project_overview` dà un progetto nel dettaglio: il riepilogo più azioni per area, attese, domande, decisioni recenti, log dei daily e note collegate. Le istruzioni del server lo suggeriscono per domande come "come va il progetto X?".

## Le scelte da rivalutare

| Domanda | Cosa fa il branch | Alternativa |
|---|---|---|
| Scrivere il riepilogo nel file dell'hub? | Sì, sezione `## Stato` aggiornata dall'app | Mostrarlo solo nell'app, in cima all'hub e nella vista Progetto, senza toccare il file. L'MCP lo avrebbe comunque da `project_overview` |
| Che costo ha scriverlo nel file? | Il file cambia da solo quando cambiano i dati; la cronologia (Git, sincronizzazione) registra queste modifiche; le righe dell'hub scendono di qualche riga | Nessuno, ma il riepilogo non si vede aprendo il file fuori dall'app |
| Dove sta la sezione? | In cima, la si vede subito | In fondo: non sposta le righe delle azioni, ma si vede meno |
| Si può spegnere? | No, non c'è un'impostazione | Un interruttore nelle Impostazioni, oppure solo per alcuni progetti |
| La pagina Progetti | Variante A, schede | Le varianti B (tabella), C (bacheca per stato), D (elenco con anteprima) sono nella stessa tela |

Le parti si possono separare: la pagina Progetti e i due strumenti MCP non dipendono dalla sezione scritta nel file. Tenerli e togliere la sezione Stato vuol dire lasciare fuori `refresh_status_sections`, l'aggancio in `app.py` e la gestione dei commenti in parser, editor e salvataggio.

Nota: il commit tocca anche `README.md`, solo la tabella degli strumenti MCP (`list_projects` e `project_overview`).

## Come provarlo

Meglio con l'utente di prova (`USERNAME=qn-prova`) o una cartella di note di prova, perché all'avvio la sezione Stato viene scritta in tutti gli hub.

```bash
git switch progetti-riepilogo
npm --prefix frontend run build
python -m unittest discover -s tests   # 115 test, tutti verdi al momento del commit
```

Per tornare indietro: `git switch main` e di nuovo `npm --prefix frontend run build`, perché l'interfaccia compilata non è sotto Git.

## Come decidere

- **Unire così com'è:** `git merge progetti-riepilogo` da `main`.
- **Tenere solo pagina e MCP:** partire dal branch e togliere la sezione Stato come descritto sopra.
- **Buttarlo:** `git branch -D progetti-riepilogo`, poi togliere questa pagina e la riga che la richiama in [piano-incrementale.md](piano-incrementale.md).

File principali da leggere: `quicknotes/views.py` (`projects_overview`, `project_overview`, `status_markdown`, `refresh_status_sections`), `quicknotes/app.py` (`schedule_status`), `quicknotes/parser.py` (`STATUS_START`, `status_span`), `frontend/src/views/ProjectsView.svelte`.
