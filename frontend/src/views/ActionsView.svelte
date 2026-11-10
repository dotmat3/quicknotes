<script>
  import { onDestroy } from 'svelte';
  import { listen } from '../api.js';
  import { board, loadBoard, postponeLate } from '../state/actions.svelte.js';
  import { PRIORITIES, STATUSES, dueLabel, prioRank, statusLabel } from '../note/editor/rules.js';
  import { app, savePrefs, tagColor } from '../state/app.svelte.js';
  import { DUE_CHOICES, FILTER_KEYS, NONE, SOURCE_CHOICES, emptyFilters, filterCount, findProject, matchItem, parseQuery } from '../state/actionQuery.js';
  import ActionItem from './ActionItem.svelte';
  import DetailPopover from './DetailPopover.svelte';
  import QuickAdd from './QuickAdd.svelte';
  import Icon from '../shell/Icon.svelte';

  loadBoard();
  const off = listen('index-updated', loadBoard);
  onDestroy(() => off.then((f) => f()));

  let popover = $state(null);
  // Aggiunta rapida aperta, con le scelte già fatte (dalla colonna o dai filtri).
  let quick = $state(null);
  let panel = $state(false);
  let naming = $state(false);
  let viewName = $state('');
  let searchEl = $state();
  let anchorEl = $state();

  // La bacheca occupa lo spazio visibile sotto i filtri: ogni colonna scorre per conto suo e la barra di
  // scorrimento orizzontale resta sul bordo basso della finestra, invece che in fondo alla colonna più lunga.
  let columnsEl = $state();
  let boardH = $state(0);
  $effect(() => {
    const el = columnsEl;
    const scroller = el?.closest('.scroll');
    if (!scroller) return;
    const page = el.parentElement;
    const measure = () => {
      const top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
      const pad = parseFloat(getComputedStyle(page).paddingBottom) || 0;
      // Con una finestra molto bassa si torna allo scorrimento della pagina.
      boardH = Math.max(320, Math.floor(scroller.clientHeight - top - Math.min(pad, 16)));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(scroller);
    // Filtri e intestazione possono andare a capo e spostare la bacheca.
    for (const child of page.children) if (child !== el) ro.observe(child);
    return () => ro.disconnect();
  });

  const filter = $derived(app.actFilter ?? 'aperte');

  // Filtri: le scelte del pannello (a scelta multipla) più le condizioni scritte in Filtra. I progetti in pausa o
  // chiusi restano fuori finché non si chiede di mostrarli.
  const HIDDEN = ['pausa', 'chiuso'];
  const terms = $derived(parseQuery(app.actQ));
  const items = $derived(board.items.filter((i) => (app.actPaused || !HIDDEN.includes(i.project_status)) && matchItem(i, app.actF, terms)));
  const openItems = $derived(items.filter((i) => !i.closed));
  const projectList = $derived(app.counts.projects ?? []);
  const nFilters = $derived(filterCount(app.actF));
  const filtered = $derived(!!(nFilters || app.actQ.trim()));

  // Le scelte del pannello: le aree seguono i progetti scelti, le persone sono quelle delle azioni aperte.
  const chosenProjects = $derived(app.actF.projects.filter((p) => p !== NONE));
  const areaList = $derived.by(() => {
    const ch = chosenProjects;
    const fromProjects = projectList.filter((p) => !ch.length || ch.includes(p.key)).flatMap((p) => p.areas);
    const fromItems = board.items.filter((i) => i.area && (!ch.length || ch.includes(i.project))).map((i) => i.area);
    return [...new Set([...fromProjects, ...fromItems])].sort();
  });
  const peopleList = $derived.by(() => {
    const n = new Map();
    for (const i of board.items) if (!i.closed) for (const p of i.people ?? []) n.set(p, (n.get(p) ?? 0) + 1);
    return [...n].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  });
  const choices = $derived({
    projects: [...projectList.map((p) => [p.key, p.status !== 'attivo' ? `${p.title} (${p.status})` : p.title]), [NONE, 'Senza progetto']],
    areas: [...areaList.map((a) => [a, a]), [NONE, 'Nessuna area']],
    statuses: STATUSES.map(([st, , label]) => [st, label]),
    priorities: [...PRIORITIES.map(([p, label, arrow]) => [p, `${arrow} ${label}`]), [NONE, 'Senza priorità']],
    people: peopleList.map(([p, n]) => [p, `@${p}`, n]),
    due: DUE_CHOICES,
    sources: SOURCE_CHOICES,
  });
  const SECTIONS = [
    ['projects', 'Progetto'],
    ['areas', 'Area'],
    ['statuses', 'Stato'],
    ['priorities', 'Priorità'],
    ['due', 'Scadenza'],
    ['people', 'Persona'],
    ['sources', 'Dove sta'],
  ];
  const TYPED = { tag: '#', person: '@', prio: '!', status: 'stato:', due: 'entro:', note: 'nota:' };
  const labelOf = (key, v) => choices[key].find(([k]) => k === v)?.[1] ?? (key === 'statuses' ? statusLabel(v) : key === 'people' ? `@${v}` : v);
  const activeChips = $derived(FILTER_KEYS.flatMap((k) => app.actF[k].map((v) => ({ key: k, value: v, label: labelOf(k, v), section: SECTIONS.find(([s]) => s === k)[1] }))));

  function toggleF(key, value) {
    const cur = app.actF[key];
    let next = { ...app.actF, [key]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] };
    // Le aree scelte che non appartengono ai progetti scelti si tolgono.
    if (key === 'projects') {
      const ch = next.projects.filter((p) => p !== NONE);
      if (ch.length) {
        const ok = new Set([...projectList.filter((p) => ch.includes(p.key)).flatMap((p) => p.areas), ...board.items.filter((i) => i.area && ch.includes(i.project)).map((i) => i.area)]);
        next = { ...next, areas: next.areas.filter((a) => a === NONE || ok.has(a)) };
      }
    }
    app.actF = next;
    savePrefs();
  }

  function clearFilters() {
    app.actF = emptyFilters();
    app.actQ = '';
    savePrefs();
  }

  // Viste salvate: filtri del pannello, testo di Filtra e "mostra in pausa", con un nome.
  const same = (v) => JSON.stringify({ f: { ...emptyFilters(), ...v.f }, q: v.q ?? '', paused: !!v.paused }) === JSON.stringify({ f: app.actF, q: app.actQ.trim(), paused: !!app.actPaused });
  const current = $derived(app.actViews.find(same)?.name ?? null);

  function applyView(v) {
    app.actF = { ...emptyFilters(), ...structuredClone($state.snapshot(v.f)) };
    app.actQ = v.q ?? '';
    app.actPaused = !!v.paused;
    savePrefs();
  }

  function saveView(e) {
    if (e.key === 'Escape') {
      naming = false;
      return;
    }
    if (e.key !== 'Enter' || !viewName.trim()) return;
    const name = viewName.trim();
    const v = { name, f: $state.snapshot(app.actF), q: app.actQ.trim(), paused: !!app.actPaused };
    app.actViews = [...app.actViews.filter((x) => x.name !== name), v];
    savePrefs();
    naming = false;
    viewName = '';
  }

  function dropView(name) {
    app.actViews = app.actViews.filter((v) => v.name !== name);
    savePrefs();
  }

  const GROUPS = [
    ['late', 'In ritardo', 'var(--late)'],
    ['soon', 'Oggi e domani', 'var(--accent)'],
    ['week', 'Questa settimana', 'var(--muted)'],
    ['later', 'Più avanti', 'var(--subtle)'],
    ['none', 'Senza scadenza', 'var(--faint)'],
  ];

  const doneRecent = $derived(items.filter((i) => i.closed));
  const STATUS_COLORS = { todo: 'var(--muted)', doing: 'var(--accent)', waiting: 'var(--person)', question: 'var(--dec)' };
  const groups = $derived.by(() => {
    const isBoard = app.actView === 'bacheca';
    if (filter === 'completate') return doneRecent.length ? [{ key: 'done', title: 'Completate', color: '#7CC4A8', items: doneRecent }] : [];
    const pool = filter === 'ritardo' ? openItems.filter((i) => i.group === 'late') : openItems;
    let out;
    if (app.actGroup === 'priorita') {
      const COLORS = { alta: 'var(--late)', media: 'var(--accent)', bassa: 'var(--muted)' };
      out = [...PRIORITIES.map(([p, label, arrow]) => ({ key: p, title: `${arrow} ${label}`, color: COLORS[p] })), { key: 'none', title: 'Senza priorità', color: 'var(--faint)' }]
        .map((g) => ({ ...g, items: pool.filter((i) => (i.priority ?? 'none') === g.key) }))
        .filter((g) => g.items.length || (isBoard && filter === 'aperte'));
    } else if (app.actGroup === 'progetto') {
      // Il progetto risolto (etichetta, intestazione, nota) diviso per area. Senza progetto vale la prima
      // etichetta, come prima delle note di progetto: chi non le usa ritrova i suoi gruppi.
      const where = (i) => (i.project ? (i.area ? `${i.project}/${i.area}` : i.project) : (i.tag ?? ''));
      const keys = [...new Set(pool.map(where))].sort((a, b) => (a === '') - (b === '') || a.localeCompare(b));
      out = keys.map((k) => ({ key: k || 'none', title: k ? `#${k.replace('/', ' · ')}` : 'Senza progetto', color: k ? tagColor(k.split('/')[0]) : 'var(--faint)', items: pool.filter((i) => where(i) === k) }));
    } else if (app.actGroup === 'stato') {
      out = STATUSES.filter(([st]) => !['done', 'cancelled'].includes(st))
        .map(([st, , label]) => ({ key: `st-${st}`, title: st === 'question' ? 'Domande' : label, color: STATUS_COLORS[st], items: pool.filter((i) => i.status === st) }))
        .filter((g) => g.items.length || (isBoard && filter === 'aperte'));
    } else {
      out = GROUPS.filter(([k]) => filter === 'aperte' || k === 'late')
        .map(([k, title, color]) => ({ key: k, title, color, items: pool.filter((i) => i.group === k) }))
        // In bacheca le colonne restano anche vuote, tranne "Più avanti" che compare solo se serve.
        .filter((g) => g.items.length || (isBoard && filter === 'aperte' && g.key !== 'later'));
    }
    // In ogni colonna prima le priorità alte; a pari priorità resta l'ordine di scadenza.
    out = out.map((g) => ({ ...g, items: [...g.items].sort((a, b) => prioRank(a.priority) - prioRank(b.priority)) }));
    if (isBoard && filter === 'aperte' && (app.boardDone || app.actGroup === 'stato')) out.push({ key: 'done', title: 'Fatte', color: '#7CC4A8', items: doneRecent });
    return out;
  });

  const weekTotal = $derived(board.done_this_week + board.open);
  const weekPct = $derived(weekTotal ? Math.round((board.done_this_week / weekTotal) * 100) : 0);
  const tabs = $derived([
    ['aperte', 'Aperte', openItems.length],
    ['ritardo', 'In ritardo', openItems.filter((i) => i.group === 'late').length],
    ['completate', 'Completate', doneRecent.length],
  ]);

  function setPref(key, value) {
    app[key] = value;
    savePrefs();
  }

  // Le scelte di partenza dell'aggiunta rapida: un solo progetto (e una sola area) tra i filtri vale come posto.
  function filterPreset() {
    const one = chosenProjects.length === 1 ? chosenProjects[0] : null;
    const areas = app.actF.areas.filter((a) => a !== NONE);
    const area = one && areas.length === 1 ? areas[0] : null;
    const priorities = app.actF.priorities.filter((p) => p !== NONE);
    return { project: one, area, priority: priorities.length === 1 ? priorities[0] : null };
  }

  // Il "+" di una colonna dà la sua scadenza o, raggruppando per progetto o priorità, il suo posto o priorità.
  function columnPreset(g) {
    if (g.key === 'done' || g.key === 'late' || g.key.startsWith('st-')) return null;
    const base = filterPreset();
    if (app.actGroup === 'priorita') return { ...base, priority: g.key === 'none' ? null : g.key };
    if (app.actGroup === 'progetto') {
      if (g.key === 'none') return { ...base, project: null, area: null };
      const [head, ...rest] = g.key.split('/');
      const p = findProject(head, projectList);
      // Un'etichetta che non è un progetto va nel testo, e l'azione in "Da smistare".
      return p ? { ...base, project: p.key, area: rest.join('/') || null } : { ...base, project: null, area: null, text: ` #${g.key}` };
    }
    if (g.key === 'none') return base;
    const due = board.column_due?.[g.key];
    return due ? { ...base, due } : null;
  }

  function presetHint(p) {
    const parts = [];
    if (p.project) parts.push(`${projectList.find((x) => x.key === p.project)?.title ?? p.project}${p.area ? ` › ${p.area}` : ''}`);
    else if (p.text) parts.push(p.text.trim());
    if (p.due) parts.push(`scade ${dueLabel(p.due).label}`);
    if (p.priority) parts.push(`priorità ${p.priority}`);
    return parts.join(' · ') || 'da smistare';
  }

  const openQuick = (preset = filterPreset()) => (quick = preset);

  // N apre l'aggiunta rapida, / porta a Filtra: solo con la vista Azioni in primo piano e fuori dai campi di testo.
  function onWindowKey(e) {
    if (quick || app.palette || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
    if (e.key !== 'n' && e.key !== 'N' && e.key !== '/') return;
    if (e.target?.closest?.('input, textarea, select, [contenteditable="true"], .cm-editor, [role="dialog"]')) return;
    const pane = anchorEl?.closest('.pane');
    if (!pane || !(anchorEl.checkVisibility?.() ?? anchorEl.offsetParent)) return;
    const act = document.activeElement;
    if (act && act !== document.body && !pane.contains(act)) return;
    e.preventDefault();
    if (e.key === '/') searchEl?.focus();
    else openQuick();
  }

  function onSearchKey(e) {
    if (e.key !== 'Escape') return;
    if (app.actQ) app.actQ = '';
    else e.currentTarget.blur();
  }

  function openPopover(e, item, kind, index) {
    const r = e.currentTarget.getBoundingClientRect();
    const key = `${item.note_id}:${item.line}:${kind}:${index}`;
    popover = popover?.key === key ? null : { key, item, kind, index, anchor: { left: r.left, top: r.top, bottom: r.bottom } };
  }

  const SYNTAX = '#progetto o #progetto/area · @persona · !alta, !media, !bassa, !nessuna\nstato:incorso, stato:attesa, stato:domanda, stato:aperte\nentro:oggi, domani, settimana, ritardo, nessuna, 20/11\nnota:titolo · "frase esatta" · un - davanti esclude (-@marco)';
</script>

<svelte:window onkeydown={onWindowKey} />

<div class="head" bind:this={anchorEl}>
  <div class="titles">
    <h1>Azioni</h1>
    <div class="sum">{board.open} aperte · {board.late} in ritardo · {board.done_this_week} completate questa settimana</div>
  </div>
  <button class="btn-new" onclick={() => openQuick()} title="Nuova azione: va nella nota del progetto oppure in Da smistare">
    <Icon name="plus" size={15} />Nuova azione<kbd>N</kbd>
  </button>
  <div class="week">
    <div class="week-top"><span>Settimana {board.week_number}</span><span class="mono">{board.done_this_week} di {weekTotal}</span></div>
    <div class="bar" role="progressbar" aria-label="Azioni completate questa settimana" aria-valuemin="0" aria-valuemax="100" aria-valuenow={weekPct}><div style="width:{weekPct}%"></div></div>
  </div>
</div>

<div class="tools">
  <div class="seg" role="tablist" aria-label="Filtro azioni">
    {#each tabs as [k, label, n] (k)}
      <button role="tab" aria-selected={filter === k} class:on={filter === k} onclick={() => (app.actFilter = k)}>{label}<span class="mono n">{n}</span></button>
    {/each}
  </div>
  <span class="grow"></span>
  <div class="seg" role="radiogroup" aria-label="Raggruppa per">
    <span class="seg-label">Raggruppa</span>
    {#each [['progetto', 'Progetto'], ['scadenza', 'Scadenza'], ['priorita', 'Priorità'], ['stato', 'Stato']] as [v, label] (v)}
      <button role="radio" aria-checked={app.actGroup === v} class:on={app.actGroup === v} onclick={() => setPref('actGroup', v)}>{label}</button>
    {/each}
  </div>
  <div class="seg" role="radiogroup" aria-label="Vista">
    {#each [['bacheca', 'Bacheca', 'board'], ['elenco', 'Elenco', 'list']] as [v, label, icon] (v)}
      <button role="radio" aria-checked={app.actView === v} class:on={app.actView === v} onclick={() => setPref('actView', v)}><Icon name={icon} size={14} />{label}</button>
    {/each}
  </div>
</div>

<div class="filterbar">
  <label class="search">
    <Icon name="search" size={14} /><span class="sr">Filtra le azioni</span>
    <input bind:this={searchEl} type="text" bind:value={app.actQ} onkeydown={onSearchKey} placeholder="Filtra… testo, #progetto/area, @persona, !alta, stato:attesa, entro:venerdì" />
    {#if app.actQ}<button class="clear" aria-label="Svuota il filtro" onclick={() => { app.actQ = ''; searchEl?.focus(); }}><Icon name="close" size={12} /></button>{/if}
    <kbd title="Tasto / per scrivere qui">/</kbd>
    <span class="help" role="note" aria-label="Sintassi del filtro: {SYNTAX}" title={SYNTAX}>?</span>
  </label>
  <button class="fbtn" class:on={panel || nFilters} aria-expanded={panel} aria-controls="act-filters" onclick={() => (panel = !panel)}>
    <Icon name="settings" size={14} />Filtri{#if nFilters}<span class="badge mono">{nFilters}</span>{/if}
  </button>
  {#each app.actViews as v (v.name)}
    <span class="view" class:on={current === v.name}>
      <button class="view-go" onclick={() => (current === v.name ? clearFilters() : applyView(v))} aria-pressed={current === v.name} title="Vista salvata"><Icon name="star" size={11} />{v.name}</button>
      <button class="view-x" aria-label="Elimina la vista {v.name}" title="Elimina la vista" onclick={() => dropView(v.name)}><Icon name="close" size={10} /></button>
    </span>
  {/each}
</div>

{#if panel}
  <div class="fpanel" id="act-filters" role="group" aria-label="Filtri">
    {#each SECTIONS as [key, title] (key)}
      {#if choices[key].length > (key === 'areas' ? 1 : 0)}
        <div class="fsec">
          <div class="fsec-title">{title}</div>
          <div class="fopts" class:many={key === 'people'}>
            {#each choices[key] as [value, label, n] (value)}
              <button class="fchip" class:on={app.actF[key].includes(value)} class:nil={value === NONE} aria-pressed={app.actF[key].includes(value)} onclick={() => toggleF(key, value)}>{label}{#if n}<span class="mono n">{n}</span>{/if}</button>
            {/each}
          </div>
        </div>
      {/if}
    {/each}
    <label class="fl check"><input type="checkbox" checked={app.actPaused} onchange={(e) => setPref('actPaused', e.target.checked)} />Mostra anche i progetti in pausa o chiusi</label>
  </div>
{/if}

{#if filtered || app.actPaused}
  <div class="active" aria-label="Filtri attivi">
    {#each activeChips as c (c.key + c.value)}
      <button class="achip" onclick={() => toggleF(c.key, c.value)} aria-label="Togli {c.section}: {c.label}"><span class="asec">{c.section}</span>{c.label}<Icon name="close" size={10} /></button>
    {/each}
    {#each terms as t, i (i)}
      <span class="achip typed" title="Scritto in Filtra">{t.neg ? 'non ' : ''}{t.kind === 'text' ? `“${t.value}”` : TYPED[t.kind] + t.value}</span>
    {/each}
    {#if app.actPaused}<button class="achip" onclick={() => setPref('actPaused', false)} aria-label="Nascondi i progetti in pausa o chiusi">anche in pausa o chiusi<Icon name="close" size={10} /></button>{/if}
    <span class="grow"></span>
    <span class="mono found">{openItems.length} aperte su {board.open}</span>
    {#if filtered && !current}
      {#if naming}
        <!-- svelte-ignore a11y_autofocus -->
        <input class="vname" type="text" aria-label="Nome della vista" placeholder="Nome della vista ↵" bind:value={viewName} onkeydown={saveView} onblur={() => (naming = false)} autofocus />
      {:else}
        <button class="text-btn" onclick={() => (naming = true)}><Icon name="star" size={12} />Salva vista</button>
      {/if}
    {/if}
    {#if filtered}<button class="text-btn" onclick={clearFilters}>Togli i filtri</button>{/if}
  </div>
{/if}

{#if app.actView === 'bacheca'}
  <div class="columns" bind:this={columnsEl} style={boardH ? `--board-h:${boardH}px` : ''}>
    {#each groups as g (g.key)}
      {@const preset = columnPreset(g)}
      <section class="column" aria-label={g.title}>
        <div class="col-head">
          <span class="dot" style="background:{g.color}" aria-hidden="true"></span><span class="col-title">{g.title}</span><span class="mono n2">{g.items.length}</span>
          <span class="grow"></span>
          {#if g.key === 'late' && app.actGroup !== 'progetto' && g.items.length}
            <button class="text-btn" onclick={postponeLate}>Sposta a domani</button>
          {:else if preset}
            <button class="icon-btn add" aria-label="Aggiungi a {g.title}" title="Aggiungi a {g.title} · {presetHint(preset)}" onclick={() => openQuick(preset)}><Icon name="plus" size={14} /></button>
          {/if}
        </div>
        {#each g.items as item (`${item.note_id}:${item.line}`)}
          <ActionItem {item} card pop={openPopover} popKey={popover?.key} />
        {:else}
          <div class="col-empty">{filtered ? 'Nessuna azione con questi filtri' : 'Nessuna azione'}</div>
        {/each}
      </section>
    {/each}
  </div>
{:else}
  {#each groups as g (g.key)}
    <section class="list-group" aria-label={g.title}>
      <div class="col-head list">
        <span class="dot" style="background:{g.color}" aria-hidden="true"></span><span class="col-title">{g.title}</span><span class="mono n2">{g.items.length}</span>
        <span class="grow"></span>
        {#if g.key === 'late' && app.actGroup !== 'progetto' && g.items.length}<button class="text-btn" onclick={postponeLate}>Sposta a domani</button>{/if}
      </div>
      <div class="rows">
        {#each g.items as item (`${item.note_id}:${item.line}`)}
          <ActionItem {item} pop={openPopover} popKey={popover?.key} />
        {/each}
      </div>
    </section>
  {/each}
{/if}
{#if board.loaded && !groups.some((g) => g.items.length) && app.actView !== 'bacheca'}
  <div class="none">{filtered ? 'Nessuna azione con questi filtri.' : 'Niente da mostrare qui.'}</div>
{/if}

{#if quick}
  <QuickAdd preset={quick} close={() => (quick = null)} />
{/if}

{#if popover}
  {#key popover.key}
    <DetailPopover item={popover.item} kind={popover.kind} index={popover.index} anchor={popover.anchor} close={() => (popover = null)} />
  {/key}
{/if}

<style>
  .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 24px; margin-bottom: 20px; }
  .titles { flex: 1 1 260px; }
  .sum { margin-top: 4px; font-size: 13.5px; color: var(--subtle); }
  .week { flex: 0 1 200px; }
  .week-top { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 12px; color: var(--subtle); }
  .bar { height: 6px; border-radius: 3px; background: var(--hover); overflow: hidden; }
  .bar div { height: 100%; background: var(--accent); }
  .btn-new { display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 10px 0 12px; border: 1px solid color-mix(in srgb, var(--accent) 55%, transparent); border-radius: 9px; background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--text); font-size: 13px; font-weight: 500; }
  .btn-new:hover { background: color-mix(in srgb, var(--accent) 26%, transparent); }
  .btn-new kbd { margin-left: 2px; }
  .tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 4px; }
  .grow { flex: 1; }
  .seg { display: flex; align-items: center; padding: 2px; border-radius: 9px; background: var(--raised); border: 1px solid var(--border); }
  .seg button { display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .seg button.on { background: var(--border2); color: var(--text); }
  .seg-label { padding: 0 8px 0 10px; font-size: 12px; color: var(--subtle); }
  .n { font-size: 11px; opacity: 0.75; }

  .filterbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 12px; }
  .search { flex: 1 1 320px; display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 8px 0 11px; border: 1px solid var(--border2); border-radius: 9px; background: var(--chrome); color: var(--subtle); }
  .search:focus-within { border-color: var(--accent); }
  .search input { flex: 1; min-width: 0; border: 0; outline: none; background: transparent; color: var(--text); font: inherit; font-size: 13px; }
  .search input::placeholder { color: var(--faint); }
  .search .clear { display: grid; place-items: center; width: 20px; height: 20px; padding: 0; border: 0; border-radius: 5px; background: transparent; color: var(--subtle); }
  .search .clear:hover { background: var(--hover); color: var(--text); }
  .help { display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; border: 1px solid var(--border3); font-size: 11px; color: var(--subtle); cursor: help; }
  .fbtn { display: flex; align-items: center; gap: 6px; height: 34px; padding: 0 12px; border: 1px solid var(--border2); border-radius: 9px; background: var(--raised); color: var(--muted); font-size: 12.5px; }
  .fbtn:hover, .fbtn.on { color: var(--text); }
  .fbtn.on { border-color: var(--border3); background: var(--border2); }
  .badge { min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; background: var(--accent); color: var(--on-accent, #fff); font-size: 11px; line-height: 18px; text-align: center; }
  .view { display: flex; align-items: center; height: 30px; border: 1px solid var(--border2); border-radius: 999px; background: transparent; }
  .view.on { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 14%, transparent); }
  .view-go { display: flex; align-items: center; gap: 5px; height: 100%; padding: 0 4px 0 10px; border: 0; background: transparent; color: var(--muted); font-size: 12.5px; }
  .view.on .view-go, .view-go:hover { color: var(--text); }
  .view-x { display: grid; place-items: center; width: 22px; height: 100%; padding: 0 6px 0 2px; border: 0; background: transparent; color: var(--faint); opacity: 0; }
  .view:hover .view-x, .view-x:focus-visible { opacity: 1; }
  .view-x:hover { color: var(--text); }

  .fpanel { display: flex; flex-wrap: wrap; gap: 14px 28px; margin-top: 10px; padding: 14px 16px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); }
  .fsec { flex: 1 1 220px; min-width: 0; }
  .fsec-title { margin-bottom: 7px; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--subtle); }
  .fopts { display: flex; flex-wrap: wrap; gap: 5px; }
  .fopts.many { max-height: 96px; overflow-y: auto; scrollbar-width: thin; }
  .fchip { display: flex; align-items: center; gap: 5px; height: 26px; padding: 0 10px; border: 1px solid var(--border2); border-radius: 999px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .fchip:hover { background: var(--hover); color: var(--text); }
  .fchip.nil { font-style: italic; }
  .fchip.on { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--text); }
  .fl { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--subtle); }
  .fl.check { flex-basis: 100%; gap: 6px; cursor: pointer; }

  .active { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; font-size: 12px; }
  .achip { display: flex; align-items: center; gap: 6px; height: 24px; padding: 0 8px; border: 1px solid var(--border2); border-radius: 6px; background: var(--raised); color: var(--text); font-size: 12px; }
  button.achip:hover { border-color: var(--border3); }
  .achip :global(svg) { color: var(--subtle); }
  .achip.typed { border-style: dashed; color: var(--muted); font-family: 'Geist Mono', monospace; font-size: 11.5px; }
  .asec { color: var(--subtle); }
  .found { color: var(--subtle); }
  .vname { height: 26px; width: 180px; padding: 0 8px; border: 1px solid var(--accent); border-radius: 7px; background: var(--surface); color: var(--text); font: inherit; font-size: 12.5px; outline: none; }

  .columns { display: flex; gap: 12px; align-items: flex-start; overflow-x: auto; overflow-y: hidden; max-height: var(--board-h, none); margin-top: 18px; padding-bottom: 10px; }
  /* 10px sono lo spazio della barra orizzontale sotto le colonne. */
  .column { flex: 0 0 272px; display: flex; flex-direction: column; gap: 8px; max-height: calc(var(--board-h, 100000px) - 10px); overflow-y: auto; overscroll-behavior: contain; padding: 10px; border-radius: 12px; background: var(--card); border: 1px solid var(--border); scrollbar-width: thin; }
  /* L'intestazione della colonna resta in cima mentre le schede scorrono. */
  .column .col-head { position: sticky; top: -10px; z-index: 1; margin: -10px -10px 0; padding: 12px 14px 6px; border-radius: 12px 12px 0 0; background: var(--card); }
  .col-head { display: flex; align-items: center; gap: 8px; min-height: 26px; padding: 2px 4px; }
  .col-head .add { width: 26px; height: 26px; }
  .text-btn { display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 8px; border: 0; border-radius: 6px; background: transparent; color: var(--muted); font-size: 12px; }
  .text-btn:hover { background: var(--hover); color: var(--text); }
  .col-head.list { padding: 0 4px 8px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; }
  .col-title { font-size: 13px; font-weight: 600; }
  .n2 { font-size: 12px; color: var(--subtle); }
  .col-empty { padding: 14px 6px; border: 1px dashed var(--border2); border-radius: 10px; text-align: center; font-size: 12.5px; color: var(--subtle); }
  .list-group { margin-top: 20px; }
  .rows { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .rows :global(.act + .act) { border-top: 1px solid var(--border); }
  .none { padding: 48px 0; text-align: center; color: var(--subtle); }
</style>
