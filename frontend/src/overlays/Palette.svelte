<script>
  // Ctrl K: note, azioni, decisioni, trascrizioni, viste e comandi, con l'anteprima del risultato scelto.
  import { onMount, tick } from 'svelte';
  import { call } from '../api.js';
  import { app, copyNoteLink, tagColor } from '../state/app.svelte.js';
  import { applyLayout, focused, layout, openAt, openBeside, openPage, reopen, splitTo, canSide } from '../state/layout.svelte.js';
  import { MODES, askDelete, canDelete, canRename, setMode } from '../state/documents.svelte.js';
  import { pageArg, pageIcon } from '../shell/nav.js';
  import Icon from '../shell/Icon.svelte';

  let q = $state(app.paletteQuery ?? '');
  app.paletteQuery = '';
  let hits = $state([]);
  let recent = $state([]);
  let sel = $state(0);
  let tab = $state('all');
  let input = $state();
  let listEl = $state();
  let seq = 0;

  // L'Anteprima porta con sé marked, DOMPurify e i colori del codice: arriva dopo che la finestra è aperta.
  let renderMarkdown = $state(null);

  onMount(async () => {
    input.focus();
    import('../note/preview.js').then((m) => (renderMarkdown = m.renderMarkdown));
    recent = await call('recent_notes', { limit: 6 }, []);
  });

  const close = () => (app.palette = false);
  const active = () => focused();
  const activeNote = () => (active().active?.startsWith('note:') ? pageArg(active().active) : null);
  const VIEWS = [
    ['Agenda', 'view:agenda'],
    ['Calendario', 'view:calendar'],
    ['Azioni', 'view:actions'],
    ['Revisione settimanale', 'view:review'],
    ['Migra le note (progetti e stati)', 'view:migration'],
    ['Persone', 'view:people'],
    ['Grafo', 'view:graph'],
    ['Impostazioni', 'settings'],
    ['Guida e comandi', 'view:help'],
  ];
  const COMMANDS = [
    ['Nuova nota', 'Ctrl Shift N', () => createNote('', 'note')],
    ['Nuovo meeting', 'Ctrl N', () => createNote('', 'meeting')],
    ['Nuovo progetto', '', () => Object.assign(app, { side: 'open', newProject: true })],
    ['Dividi a destra', 'Ctrl Alt \\', () => active().active && splitTo(active().id, active().active, active().id, canSide('right') ? 'right' : 'bottom', true)],
    ['Dividi in basso', '', () => active().active && splitTo(active().id, active().active, active().id, canSide('bottom') ? 'bottom' : 'right', true)],
    ['Unisci tutti i gruppi', '', () => applyLayout(1, layout.dir)],
    ['Layout: due colonne', '', () => applyLayout(2, 'row')],
    ['Layout: due righe', '', () => applyLayout(2, 'col')],
    ['Riapri scheda chiusa', 'Ctrl Shift T', reopen],
    ['Rinomina la nota', 'F2', () => activeNote() && canRename(activeNote()) && (app.rename = `${active().id}:${active().active}`)],
    ['Elimina la nota', '', () => activeNote() && canDelete(activeNote()) && askDelete(activeNote())],
    ...MODES.map(([m, label]) => [`Modalità della nota: ${label}`, '', () => active().active?.startsWith('note:') && setMode(`${active().id}:${active().active}`, m)]),
  ];

  async function createNote(title, noteType) {
    const n = await call('new_note', { title, noteType });
    openPage(`note:${n.id}`, n.title);
  }

  // I gruppi, nell'ordine in cui compaiono. `tab` è il tipo che li mostra da solo.
  const GROUPS = {
    facet: ['Persone ed etichette', 'all'],
    recent: ['Note recenti', 'note'],
    note: ['Note', 'note'],
    action: ['Azioni', 'action'],
    decision: ['Decisioni', 'decision'],
    transcript: ['Trascrizioni', 'transcript'],
    view: ['Viste', 'command'],
    command: ['Comandi', 'command'],
  };
  const TABS = [['all', 'Tutto'], ['note', 'Note'], ['action', 'Azioni'], ['decision', 'Decisioni'], ['transcript', 'Trascrizioni'], ['command', 'Comandi']];

  const raw = $derived(q.trim());
  const commandsOnly = $derived(raw.startsWith('>'));
  const ql = $derived(raw.replace(/^>\s*/, '').toLowerCase());
  // Le parole da evidenziare: senza filtri @ # e senza il ! delle decisioni.
  const words = $derived(raw.split(/\s+/).filter((w) => w && !/^[@#>]/.test(w)).map((w) => w.replace(/^!/, '').replace(/^decisione$/i, '').toLowerCase()).filter(Boolean));

  const isDaily = (page) => /-giornata$/.test(page);
  const items = $derived.by(() => {
    const out = [];
    if (!commandsOnly) {
      const found = raw ? hits : recent.map((n) => ({ kind: 'recent', label: n.title, hint: n.date.slice(0, 10), page: `note:${n.id}` }));
      for (const h of found) out.push({ ...h, group: h.kind === 'person' || h.kind === 'tag' ? 'facet' : h.kind });
    }
    const localOk = commandsOnly || !/^[@#!]/.test(ql);
    if (localOk) {
      for (const [label, page] of VIEWS) if (!ql || label.toLowerCase().includes(ql)) out.push({ group: 'view', kind: 'view', label, hint: 'vista', page });
      for (const [label, hint, go] of COMMANDS) if ((ql || commandsOnly) && label.toLowerCase().includes(ql)) out.push({ group: 'command', kind: 'command', label, hint: hint || 'comando', go });
    }
    const order = Object.keys(GROUPS);
    return out.sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group));
  });
  const counts = $derived(Object.fromEntries(TABS.map(([k]) => [k, k === 'all' ? items.length : items.filter((i) => GROUPS[i.group][1] === k).length])));
  const showTabs = $derived(!!raw && !commandsOnly);
  const shown = $derived(tab === 'all' || !showTabs ? items : items.filter((i) => GROUPS[i.group][1] === tab));
  const current = $derived(shown[sel]);

  $effect(() => {
    const query = raw;
    const mine = ++seq;
    sel = 0;
    if (!query || commandsOnly) {
      hits = [];
      return;
    }
    call('search_all', { query }, []).then((r) => {
      if (mine === seq) hits = r;
    });
  });

  // Un tipo senza risultati non resta scelto.
  $effect(() => {
    if (tab !== 'all' && !counts[tab]) tab = 'all';
  });

  function go(r, beside) {
    close();
    if (r.go) return r.go();
    const title = r.kind === 'note' || r.kind === 'recent' ? r.label : undefined;
    if (beside) openBeside(r.page, title, r.line);
    else openAt(r.page, r.line, title);
  }

  async function select(i) {
    sel = Math.max(0, Math.min(i, shown.length - 1));
    await tick();
    listEl?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' });
  }

  function cycleTab(step) {
    const open = TABS.filter(([k]) => counts[k]).map(([k]) => k);
    tab = open[(open.indexOf(tab) + step + open.length) % open.length] ?? 'all';
    sel = 0;
  }

  function onKey(e) {
    if (e.key === 'Escape') {
      e.stopPropagation();
      close();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      select(sel + (e.key === 'ArrowDown' ? 1 : -1));
    } else if (e.key === 'Tab' && showTabs) {
      e.preventDefault();
      cycleTab(e.shiftKey ? -1 : 1);
    } else if (e.key === 'Enter' && e.ctrlKey && raw && !commandsOnly) {
      e.preventDefault();
      close();
      createNote(raw, 'note');
    } else if (e.key === 'Enter' && current) {
      e.preventDefault();
      go(current, e.altKey && !!current.page?.startsWith('note:'));
    }
  }

  // Il testo con i pezzi trovati dalla ricerca a testo pieno, segnati da « ».
  const marked = (s) => s.replace(/(^|\s)#{1,6}\s/g, '$1').split(/[«»]/).map((t, i) => ({ t, on: i % 2 === 1 }));

  // Anteprima della nota scelta: chiesta poco dopo che la scelta si ferma, e ricordata.
  const cache = new Map();
  let preview = $state(null);
  let pane = $state();
  let content = $state();
  let timer;
  const previewId = $derived(current?.page?.startsWith('note:') ? pageArg(current.page) : null);
  // Il riquadro resta finché ci sono note tra i risultati: la finestra non cambia larghezza scorrendo.
  const hasPane = $derived(shown.some((r) => r.page?.startsWith('note:')));

  $effect(() => {
    const id = previewId;
    const line = current?.line;
    clearTimeout(timer);
    if (!id) {
      preview = null;
      return;
    }
    timer = setTimeout(async () => {
      if (!cache.has(id)) cache.set(id, await call('read_note', { id }, null));
      if (previewId === id) preview = { note: cache.get(id), line };
    }, cache.has(id) ? 0 : 60);
    return () => clearTimeout(timer);
  });

  // Si mostrano una quarantina di righe: attorno alla riga trovata, oppure dall'inizio.
  $effect(() => {
    const p = preview;
    const hl = words;
    const render = renderMarkdown;
    if (!content) return;
    if (!p?.note || !render) return content.replaceChildren();
    const lines = p.note.body.split('\n');
    const start = p.line ? Math.max(0, p.line - 7) : 0;
    const part = lines.slice(start, start + 40).join('\n') + (start + 40 < lines.length ? '\n\n…' : '');
    content.replaceChildren(...render(part, tagColor, p.note.path).childNodes);
    highlight(content, hl);
    const first = content.querySelector('mark');
    pane.scrollTop = first ? Math.max(0, first.offsetTop - pane.clientHeight / 3) : 0;
  });

  function highlight(root, list) {
    if (!list.length) return;
    const re = new RegExp(list.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'gi');
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) if (re.test(walker.currentNode.data)) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const frag = document.createDocumentFragment();
      let last = 0;
      for (const m of node.data.matchAll(re)) {
        frag.append(node.data.slice(last, m.index), Object.assign(document.createElement('mark'), { textContent: m[0] }));
        last = m.index + m[0].length;
      }
      frag.append(node.data.slice(last));
      node.replaceWith(frag);
    }
  }
</script>

{#snippet rowIcon(r)}
  {#if r.kind === 'action'}
    <span class="box" aria-hidden="true"></span>
  {:else if r.kind === 'decision'}
    <Icon name="flag" style="color:var(--dec)" />
  {:else if r.kind === 'transcript'}
    <Icon name="mic" style="color:var(--late)" />
  {:else if r.kind === 'tag'}
    <span class="dot" aria-hidden="true" style="background:{tagColor(pageArg(r.page))}"></span>
  {:else if r.kind === 'command'}
    <Icon name="right" style="color:var(--subtle)" />
  {:else}
    <Icon name={pageIcon(r.page, isDaily(r.page))} style="color:{isDaily(r.page) ? 'var(--accent)' : 'var(--subtle)'}" />
  {/if}
{/snippet}

<div class="dim"></div>
<button class="outside" aria-label="Chiudi la ricerca" onclick={close}></button>
<!-- Esc chiude anche quando il fuoco è su un pulsante del riquadro. -->
<div class="dialog" class:wide={hasPane} role="dialog" tabindex="-1" aria-label="Cerca o apri" onkeydown={(e) => e.key === 'Escape' && (e.stopPropagation(), close())}>
  <label class="field">
    <Icon name="search" size={18} style="color:var(--subtle)" />
    <span class="sr">Cerca o apri</span>
    <input type="text" bind:this={input} bind:value={q} onkeydown={onKey} placeholder="Cerca note, azioni, persone, viste… · > per i comandi" />
    <kbd>Esc</kbd>
  </label>
  {#if showTabs}
    <div class="tabs" role="tablist" aria-label="Tipo di risultato">
      {#each TABS.filter(([k]) => k === 'all' || counts[k]) as [k, label] (k)}
        <button role="tab" aria-selected={tab === k} class:on={tab === k} tabindex="-1" onmousedown={(e) => e.preventDefault()} onclick={() => { tab = k; sel = 0; }}>{label} <span class="count">{counts[k]}</span></button>
      {/each}
    </div>
  {/if}
  <div class="body">
    <div class="list" role="listbox" aria-label="Risultati" bind:this={listEl}>
      {#each shown as r, i (`${r.kind}:${r.page ?? r.label}:${r.line ?? ''}:${i}`)}
        {#if i === 0 || shown[i - 1].group !== r.group}<div class="head" role="presentation">{GROUPS[r.group][0]}</div>{/if}
        <!-- La scelta segue il mouse solo quando si muove: righe che scorrono sotto un puntatore fermo non la cambiano. -->
        <button class="row {r.kind}" class:sel={i === sel} role="option" aria-selected={i === sel} onmousemove={() => (sel = i)} onclick={(e) => go(r, e.altKey && !!r.page?.startsWith('note:'))}>
          {@render rowIcon(r)}
          <span class="text">
            {#if r.kind === 'transcript'}
              <span class="label"><span class="ctx">{r.snippet} · <span class="mono">{r.hint}</span></span> «{r.label}»</span>
            {:else}
              <span class="label">{r.label}</span>
              {#if r.snippet && r.kind === 'note'}<span class="snippet">{#each marked(r.snippet) as s, j (j)}{#if s.on}<mark>{s.t}</mark>{:else}{s.t}{/if}{/each}</span>{/if}
              {#if r.snippet && r.kind !== 'note'}<span class="snippet">{r.snippet}</span>{/if}
            {/if}
          </span>
          {#if r.kind === 'action'}
            {#if r.hint}<span class="due {r.level ?? ''}">{r.hint}</span>{/if}
          {:else if r.kind !== 'transcript'}
            <span class="hint" class:mono={r.kind !== 'command' && r.kind !== 'view'}>{r.hint}</span>
          {/if}
        </button>
      {/each}
      {#if !shown.length}
        <div class="none">{commandsOnly ? 'Nessun comando' : `Nessun risultato · Ctrl ↵ crea la nota «${raw}»`}</div>
      {/if}
    </div>
    {#if hasPane}
      <!-- Titolo e pulsanti restano fermi: scorre solo il testo, portato alla prima parola trovata. -->
      <aside class="pane" aria-label="Anteprima del risultato">
        {#if !previewId}
          <p class="none">Nessuna anteprima per viste e comandi.</p>
        {:else if preview?.note}
          <div class="phead">
            <div class="path mono">{preview.note.path}</div>
            <h2>{preview.note.title}</h2>
            <div class="pills">
              {#if preview.note.date_label}<span class="pill">{preview.note.date_label}</span>{/if}
              {#each preview.note.people as p (p)}<span class="pill person">@{p}</span>{/each}
            </div>
          </div>
        {/if}
        <div class="scroll" bind:this={pane}><div class="pv content" bind:this={content}></div></div>
        {#if previewId && preview?.note}
          <div class="actions">
            <button class="btn primary" onclick={() => go(current)}>Apri</button>
            <button class="btn" onclick={() => go(current, true)}>Apri a lato</button>
            <button class="btn" onclick={() => copyNoteLink(preview.note.id, preview.note.title)}><Icon name="clip" size={14} />Copia [[link]]</button>
          </div>
        {/if}
      </aside>
    {/if}
  </div>
  <div class="foot" aria-hidden="true">
    <span><kbd>↑ ↓</kbd> scegli</span>
    <span><kbd>↵</kbd> apri</span>
    <span><kbd>Alt ↵</kbd> apri a lato</span>
    <span><kbd>Ctrl ↵</kbd> crea nota</span>
    {#if showTabs}<span><kbd>Tab</kbd> tipo</span>{/if}
    <span><kbd>@ # !</kbd> persona, etichetta, decisione</span>
    <span><kbd>&gt;</kbd> solo comandi</span>
  </div>
</div>

<style>
  .dim { position: fixed; inset: 0; z-index: 50; background: rgba(8, 8, 10, 0.55); }
  .outside { position: fixed; inset: 0; z-index: 51; padding: 0; border: 0; background: transparent; cursor: default; }
  .dialog { position: fixed; top: 64px; left: 50%; transform: translateX(-50%); z-index: 52; display: flex; flex-direction: column; width: 620px; max-width: calc(100% - 32px); max-height: calc(100% - 96px); border-radius: 14px; background: var(--raised); border: 1px solid var(--border3); box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6); overflow: hidden; }
  .dialog.wide { width: 1000px; }
  .field { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--border2); }
  .field input { flex: 1; min-width: 0; border: 0; outline: none; background: transparent; color: var(--text); font: inherit; font-size: 16px; }
  .field kbd { color: var(--subtle); }
  .tabs { display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; border-bottom: 1px solid var(--border2); }
  .tabs button { height: 26px; padding: 0 10px; border: 0; border-radius: 6px; background: transparent; color: var(--muted); font-size: 12px; }
  .tabs button.on { background: var(--border2); color: var(--text); }
  .count { font-family: 'Geist Mono', monospace; color: var(--subtle); }
  .body { display: flex; min-height: 0; height: min(520px, calc(100vh - 260px)); }
  .list { flex: 1 1 440px; min-width: 0; padding: 6px; overflow-y: auto; }
  .head { padding: 10px 10px 4px; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--subtle); }
  .row { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 36px; padding: 5px 10px; border: 0; border-radius: 8px; background: transparent; color: var(--text); font-size: 14px; text-align: left; }
  .row.note, .row.recent { align-items: flex-start; }
  .row.note :global(svg), .row.recent :global(svg) { margin-top: 3px; }
  .row.sel { background: var(--border2); }
  .box { flex: none; width: 15px; height: 15px; border-radius: 4px; border: 1.5px solid var(--faint); }
  .dot { flex: none; width: 8px; height: 8px; margin: 0 4px; border-radius: 50%; }
  .text { flex: 1; min-width: 0; }
  .label, .snippet { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row.action .label, .row.decision .label, .row.transcript .label { font-size: 13.5px; }
  .ctx { color: var(--muted); }
  .snippet { font-size: 12px; color: var(--subtle); }
  mark, .content :global(mark) { background: color-mix(in srgb, var(--accent) 26%, transparent); color: var(--text); border-radius: 3px; padding: 0 1px; }
  .hint { flex: none; font-size: 12px; color: var(--subtle); }
  .mono { font-family: 'Geist Mono', monospace; font-size: 11.5px; }
  .due { flex: none; padding: 1px 6px; border-radius: 4px; background: var(--hover); color: var(--muted); font-family: 'Geist Mono', monospace; font-size: 11px; }
  .due.late { background: color-mix(in srgb, var(--late) 14%, transparent); color: var(--late); }
  .due.soon { color: var(--text); }
  .none { padding: 12px 10px; font-size: 13px; color: var(--subtle); }
  .pane { flex: 1 1 380px; min-width: 0; display: flex; flex-direction: column; border-left: 1px solid var(--border2); background: var(--surface); }
  .phead { padding: 18px 20px 0; }
  .scroll { position: relative; flex: 1; min-height: 0; padding: 0 20px 12px; overflow-y: auto; }
  .pane > .none { padding: 18px 20px; }
  .path { color: var(--subtle); overflow-wrap: anywhere; }
  .pane h2 { margin: 4px 0 8px; font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
  .pills { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
  .pill { padding: 2px 8px; border-radius: 999px; background: var(--hover); color: var(--muted); font-size: 12px; }
  .pill.person { background: color-mix(in srgb, var(--person) 13%, transparent); color: var(--person); }
  .content { font-size: 13.5px; }
  .content :global(:is(h1, h2, h3)) { margin: 14px 0 4px; font-size: 14px; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 20px 14px; border-top: 1px solid var(--border); }
  .actions .btn { display: flex; align-items: center; gap: 6px; height: 30px; font-size: 13px; }
  .foot { display: flex; flex-wrap: wrap; gap: 6px 16px; padding: 8px 16px; border-top: 1px solid var(--border2); background: var(--chrome); font-size: 11.5px; color: var(--subtle); }
  .foot kbd { font-family: 'Geist Mono', monospace; color: var(--text); }
  @media (max-width: 860px) {
    .dialog.wide { width: 620px; }
    .pane { display: none; }
  }
</style>
