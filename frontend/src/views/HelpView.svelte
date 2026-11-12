<script>
  // Guida e tavola dei comandi: tutto quello che si può fare con tastiera, mouse e sintassi delle note.
  // Il campo in alto filtra le righe di tutte le sezioni.
  import { openPage } from '../state/layout.svelte.js';

  let q = $state('');

  const SECTIONS = [
    {
      title: 'Il ritmo: Agenda, daily, Revisione',
      intro: 'Il daily è il posto dove catturi e scrivi il log. Le azioni vivono nella nota del progetto; Agenda e Revisione dicono cosa fare.',
      rows: [
        ['Ogni mattina', 'Apri Agenda: in ritardo, oggi, in corso, in attesa, domande, prossimi 7 giorni, da smistare'],
        ['Durante il giorno', 'Scrivi nel daily. Sotto # Nome del progetto non serve ripetere l’etichetta: si eredita'],
        ['Il venerdì', 'Revisione, circa 10 minuti: smista, chiudi, pianifica. La barra laterale avvisa dopo 7 giorni'],
        ['Sposta nel progetto', 'Porta un’azione del daily (con figlie e descrizione) nella nota del progetto, sotto l’area; nel daily resta un rimando ↗'],
        ['Archivia fatte', 'Nella vista Progetto: le azioni chiuse passano dalla nota del progetto all’archivio, per mese'],
        ['Azioni › N', 'Aggiunta rapida: #progetto/area, @persona, entro:venerdì, !alta. Va nella nota del progetto, sotto l’area, oppure in Da smistare; Invio aggiunge e resta aperta, Maiusc Invio chiude'],
        ['Azioni › Filtra', 'Tasto /: testo, #progetto/area, @persona, !alta, stato:attesa, entro:settimana, nota:titolo; un - davanti esclude. Filtri apre le scelte multiple; Salva vista le ricorda'],
        ['progetti/nome.md', 'Nota di progetto: type: project, status (attivo, pausa, chiuso), aliases, areas, obiettivo e ## Prossime azioni divise per ### area'],
        ['project: nome', 'Nel frontmatter di una nota di argomento: le sue azioni appartengono al progetto'],
        ['Migrazione', 'Per le note di prima: Ctrl K › Migra le note. Propone progetti e stati, scegli cosa applicare; prima copia la cartella'],
      ],
    },
    {
      title: 'Ovunque nel sistema',
      intro: 'Tasti globali: funzionano anche con l’app nell’area di notifica. Si cambiano in config.json, chiave hotkeys.',
      rows: [
        ['Ctrl Alt N', 'Nota rapida: scrivi e salva nella nota del giorno'],
        ['Ctrl Alt D', 'Apri la nota del giorno'],
        ['Ctrl Alt R', 'Avvia o ferma la registrazione (in arrivo)'],
      ],
    },
    {
      title: 'Finestra e schede',
      intro: 'Le schede funzionano come in VS Code: si trascinano, si dividono in gruppi e si riaprono.',
      rows: [
        ['Ctrl K · Ctrl P · Ctrl O', 'Cerca note, persone, etichette, viste e comandi'],
        ['Ctrl N', 'Nuovo meeting'],
        ['Ctrl Shift N', 'Nuova nota'],
        ['F2 · Doppio clic sul titolo', 'Rinomina la nota: cambiano anche il file e i link delle altre note'],
        ['⋯ › Elimina la nota', 'La nota va nel Cestino di Windows, da dove si ripristina'],
        ['Ctrl 1 … 9', 'Oggi e le viste, nell’ordine della barra laterale'],
        ['Ctrl W · tasto centrale', 'Chiudi la scheda'],
        ['Ctrl Shift T', 'Riapri l’ultima scheda chiusa'],
        ['Alt ← · tasto laterale indietro', 'Torna alla pagina precedente'],
        ['Alt → · tasto laterale avanti', 'Vai alla pagina successiva'],
        ['Ctrl Alt \\', 'Dividi a destra'],
        ['Ctrl \\', 'Comprimi o apri la barra laterale'],
        ['Trascina il bordo della barra laterale', 'Allargala o stringila · doppio clic per la larghezza iniziale'],
        ['Ctrl ,', 'Impostazioni'],
        ['F1 · ?', 'Questa guida'],
        ['Trascina una scheda', 'Riordina, spostala in un altro gruppo o sul bordo per dividere'],
        ['Clic destro su una scheda', 'Chiudi le altre, dividi, sposta, riapri'],
        ['Doppio clic sul divisore', 'Pareggia la larghezza dei gruppi'],
        ['Doppio clic sulla barra del titolo', 'Ingrandisci o ripristina la finestra'],
      ],
    },
    {
      title: 'Scrivere una nota',
      intro: 'Mentre scrivi compaiono suggerimenti, come in VS Code: Invio o Tab accettano, Esc chiude.',
      rows: [
        ['Ctrl T', 'Trasforma la riga in azione, o spuntala'],
        ['Alt S', 'Sull’azione: scegli lo stato (da fare, in corso, in attesa, domanda, annullata, fatta)'],
        ['Ctrl D', 'Segna la riga come decisione'],
        ['Ctrl Shift H', 'Inserisci l’ora'],
        ['Tab · Shift Tab', 'Rientra o riporta indietro: le azioni rientrate diventano sotto-attività'],
        ['Ctrl V · trascina un’immagine', 'Salva l’immagine in images/ accanto alla nota e la mostra nel testo'],
        ['Ctrl F', 'Cerca e sostituisci nella nota'],
        ['Ctrl Z · Ctrl Y', 'Annulla e ripeti'],
        ['Ctrl Spazio', 'Suggerimenti; su una riga vuota, le strutture che puoi scrivere'],
        ['/ a inizio riga', 'Elenco delle strutture: azione, avviso, tabella, codice…'],
        ['due: · entro: · scadenza: · scheduled:', 'Propone le date e controlla il formato'],
        ['- [', 'Propone i sei stati dell’azione'],
        ['#progetto/', 'Propone le aree del progetto'],
        ['prio:', 'Propone alta, media e bassa'],
        ['@ · # · [[', 'Propone persone, etichette e note'],
        ['> [!', 'Propone i tipi di avviso'],
        ['```', 'Propone la lingua del blocco di codice'],
        ['Menu ⋯ della nota', 'Anteprima viva, Sorgente, Affiancata, Anteprima'],
      ],
    },
    {
      title: 'Clic e mouse',
      intro: 'Quello che è già reso si apre con un clic; il testo che stai scrivendo con Ctrl+clic.',
      rows: [
        ['Clic', 'Apri un [[link]] reso, un link web, @persona e #etichetta nelle schede e nell’Anteprima'],
        ['Ctrl+clic', 'Apri @persona, #etichetta o un link mentre scrivi, anche in Sorgente: con Ctrl premuto compare la manina'],
        ['Clic sulla casella', 'Fatta (scrive done: con la data); su un’azione chiusa, la riapre'],
        ['Tasto destro sulla casella', 'Scegli lo stato dell’azione, nell’editor e nelle viste'],
        ['+ in fondo alla scheda', 'Dettagli: priorità e stato con un clic; scadenza, giorno, persona, etichetta, progetto e descrizione. Compare passando sulla scheda; le pillole già presenti si cambiano cliccandole'],
        ['Rotella e trascinamento', 'Nel grafo: avvicina, sposta la vista o un nodo'],
      ],
    },
    {
      title: 'Sintassi delle note',
      intro: 'Le note sono file Markdown nel formato di GitHub, più alcune parole riconosciute dall’app.',
      rows: [
        ['- [ ] testo', 'Azione da fare'],
        ['- [/] testo', 'In corso'],
        ['- [w] testo @persona', 'In attesa di qualcuno: la prima @ è la persona che aspetti'],
        ['- [?] testo', 'Domanda aperta o decisione da prendere'],
        ['- [-] testo', 'Annullata, con il motivo nella descrizione (al posto di [x] e «Deprecato»)'],
        ['- [x] testo', 'Fatta'],
        ['    - [ ] testo', 'Sotto-attività: rientrata sotto un’azione, ne eredita progetto ed etichette'],
        ['@nome', 'Persona'],
        ['#etichetta', 'Etichetta: il colore si sceglie dalla sua pagina. Se è un progetto apre la vista Progetto'],
        ['#progetto/area', 'Etichetta gerarchica: progetto e area insieme, per esempio #llm-training/dedup'],
        ['scheduled:2026-11-12', 'Il giorno in cui farla: compare in Agenda quel giorno. È diverso da due:'],
        ['due:2026-11-10', 'Scadenza (anche entro: e scadenza:)'],
        ['prio:alta · prio:media · prio:bassa', 'Priorità dell’azione (anche priorità:); in bacheca va in cima alla colonna'],
        ['done:2026-11-03', 'Data di completamento: la scrive la spunta'],
        ['!decisione', 'Decisione (anche !dec)'],
        ['[[Titolo]] · [[id|Testo]]', 'Link a un’altra nota'],
        ['> [!NOTE]', 'Avviso: NOTE, TIP, IMPORTANT, WARNING, CAUTION'],
        ['| a | b |', 'Tabella, con la riga | --- | --- | sotto l’intestazione'],
        ['```python', 'Blocco di codice con i colori della lingua'],
        ['[^1] · [^1]: testo', 'Nota a piè di pagina'],
        ['**grassetto** · *corsivo* · ~~barrato~~', 'Stile del testo'],
        ['`codice`', 'Codice nella riga'],
        ['![](images/foto.png)', 'Immagine della nota: si vede al posto del tag, fuori dalla riga del cursore'],
        ['https://…', 'Un indirizzo scritto diventa un link'],
      ],
    },
    {
      title: 'Ricerca Ctrl K',
      intro: 'Senza testo mostra le note recenti e le viste; scrivendo cerca in note, azioni, decisioni e trascrizioni, con l’anteprima a destra.',
      rows: [
        ['parole', 'Cerca nel testo delle note'],
        ['@nome', 'Solo le note con quella persona'],
        ['#etichetta', 'Solo le note con quell’etichetta'],
        ['!parole', 'Cerca tra le decisioni'],
        ['↑ ↓ · Invio', 'Scegli e apri, sulla riga trovata'],
        ['Alt Invio', 'Apri a lato, in un altro gruppo'],
        ['Tab · Shift Tab', 'Solo note, azioni, decisioni o trascrizioni'],
        ['> comando', 'Solo i comandi'],
        ['Ctrl Invio', 'Crea una nota con il testo scritto come titolo'],
        ['Esc', 'Chiudi'],
      ],
    },
    {
      title: 'Micio',
      intro: 'Il gatto vive in fondo alle schede o nella sua stanza. Ogni azione completata vale 5 crocchette, da spendere nel negozio.',
      rows: [
        ['Clic su Micio', 'Ti saluta e dice com’è messa la giornata'],
        ['Vista Micio', 'La stanza, il negozio, mantello, dimensione e cosa fa fuori dalla stanza'],
        ['Passeggia · Gioca · Nascosto', 'In fondo alle schede gira, gioca col gomitolo o non compare'],
        ['Pioggia di pesci', 'Minigioco di 30 secondi: mouse o frecce, Esc per uscire'],
      ],
    },
  ];

  const norm = (s) => s.toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
  const shown = $derived.by(() => {
    const words = norm(q).split(/\s+/).filter(Boolean);
    if (!words.length) return SECTIONS;
    return SECTIONS.map((s) => ({ ...s, rows: s.rows.filter(([k, d]) => words.every((w) => norm(`${k} ${d} ${s.title}`).includes(w))) })).filter((s) => s.rows.length);
  });
</script>

<h1>Guida</h1>
<p class="sub">Comandi, scorciatoie e sintassi delle note. Si apre con F1 o con il pulsante ? in basso a destra.</p>
<input class="filter" type="search" placeholder="Cerca un comando… per esempio «scheda» o «data»" aria-label="Cerca nella guida" bind:value={q} />

{#each shown as s (s.title)}
  <section aria-label={s.title}>
    <h2>{s.title}</h2>
    {#if !q}<p class="intro">{s.intro}</p>{/if}
    <div class="rows">
      {#each s.rows as [keys, what] (keys)}
        <div class="row">
          <span class="keys">{#each keys.split(' · ') as k, i (i)}{#if i}<span class="or">o</span>{/if}<kbd>{k}</kbd>{/each}</span>
          <span class="what">{what}</span>
        </div>
      {/each}
    </div>
  </section>
{:else}
  <p class="sub">Nessun comando trovato per «{q}».</p>
{/each}

<p class="more">Per le impostazioni di tema, viste e tasti apri <button class="link" onclick={() => openPage('settings', 'Impostazioni')}>Impostazioni</button>.</p>

<style>
  .sub { margin: 6px 0 16px; font-size: 13.5px; color: var(--subtle); }
  .filter { width: 100%; max-width: 420px; height: 34px; padding: 0 12px; border: 1px solid var(--border2); border-radius: 8px; background: var(--raised); color: var(--text); font: inherit; font-size: 13.5px; outline: none; }
  .filter:focus { border-color: var(--accent); }
  h2 { margin: 28px 0 4px; font-size: 16px; font-weight: 600; }
  .intro { margin: 0 0 10px; font-size: 13px; color: var(--subtle); }
  .rows { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .row { display: grid; grid-template-columns: minmax(180px, 38%) 1fr; gap: 16px; align-items: baseline; padding: 9px 14px; }
  .row + .row { border-top: 1px solid var(--border); }
  .keys { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 6px; }
  kbd { padding: 1px 7px; border: 1px solid var(--border2); border-bottom-width: 2px; border-radius: 5px; background: var(--surface); font-family: 'Geist Mono', monospace; font-size: 12px; color: var(--text); white-space: nowrap; }
  .or { font-size: 11.5px; color: var(--subtle); }
  .what { font-size: 13.5px; color: var(--text2); }
  .more { margin-top: 28px; font-size: 13px; color: var(--subtle); }
  .link { padding: 0; border: 0; background: transparent; color: var(--accent); text-decoration: underline; text-underline-offset: 3px; }
</style>
