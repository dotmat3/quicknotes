<script>
  import { app, savePrefs, tagColor } from '../state/app.svelte.js';
  import { createProject } from '../state/actions.svelte.js';
  import { emptyFilters } from '../state/actionQuery.js';
  import { focused, openPage } from '../state/layout.svelte.js';
  import { VIEWS, favInfo, pageArg, pageKind, pageTitle } from './nav.js';
  import Icon from './Icon.svelte';

  let { toggleSide } = $props();

  const active = $derived(focused().active);
  const todayPage = $derived(app.today ? `note:${app.today.id}` : '');
  const nav = $derived([
    { key: 'oggi', label: 'Oggi', icon: 'today', page: todayPage, meta: `${app.counts.todayDone}/${app.counts.todayTotal}` },
    ...app.viewOrder
      .filter((k) => app.viewVis[k])
      .map((k) => ({
        key: k,
        ...VIEWS[k],
        meta: k === 'azioni' ? String(app.counts.open) : k === 'persone' ? String(app.counts.people) : '',
        dot: (k === 'azioni' && app.counts.late > 0) || (k === 'revisione' && app.counts.reviewDue),
        dotTitle: k === 'revisione' && app.counts.reviewDue ? 'Sono passati più di 7 giorni dall’ultima revisione' : undefined,
      })),
  ]);

  // Progetti: prima gli attivi, poi quelli in pausa o chiusi, compressi in fondo.
  const projects = $derived(app.counts.projects ?? []);
  const live = $derived(projects.filter((p) => p.status === 'attivo'));
  const resting = $derived(projects.filter((p) => p.status !== 'attivo'));
  let showResting = $state(false);
  let draft = $state('');

  function toggleProject(key) {
    app.projOpen = { ...app.projOpen, [key]: !app.projOpen[key] };
    savePrefs();
  }

  function openArea(p, area) {
    app.actF = { ...emptyFilters(), projects: [p.key], areas: area ? [area] : [] };
    Object.assign(app, { actQ: '', actFilter: 'aperte' });
    savePrefs();
    openPage('view:actions');
  }

  async function addProject(e) {
    if (e.key === 'Escape') {
      app.newProject = false;
      draft = '';
      return;
    }
    if (e.key !== 'Enter' || !draft.trim()) return;
    const created = await createProject(draft.trim());
    if (created) openPage(`project:${created.key}`, created.title);
    app.newProject = false;
    draft = '';
  }

  // Le aree con azioni aperte e quelle dichiarate, nell'ordine della nota di progetto.
  const areasOf = (p) => [...new Set([...p.areas, ...Object.keys(p.open_by_area ?? {}).filter(Boolean)])];

  const isCurrent = (page) => active === page || (page === 'view:people' && active && pageKind(active) === 'person');

  function pinLabel(id) {
    if (id === todayPage) return app.today.title;
    const t = pageTitle(id, app.titles);
    return pageKind(id) === 'tag' ? pageArg(id) : t;
  }

  // Larghezza: si trascina il bordo destro (o si usano le frecce sulla maniglia); doppio clic la riporta a 240.
  const SIDE_MIN = 200;
  const SIDE_MAX = 480;
  const SIDE_DEFAULT = 240;
  let dragging = $state(false);
  let aside;

  function setWidth(w) {
    app.sideW = Math.round(Math.max(SIDE_MIN, Math.min(SIDE_MAX, w)));
  }

  function startResize(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragging = true;
  }

  function onResize(e) {
    if (dragging) setWidth(e.clientX - aside.getBoundingClientRect().left);
  }

  function endResize() {
    if (!dragging) return;
    dragging = false;
    savePrefs();
  }

  function resetWidth() {
    setWidth(SIDE_DEFAULT);
    savePrefs();
  }

  function resizeKey(e) {
    const step = e.shiftKey ? 40 : 10;
    if (e.key === 'ArrowLeft') setWidth(app.sideW - step);
    else if (e.key === 'ArrowRight') setWidth(app.sideW + step);
    else if (e.key === 'Home') setWidth(SIDE_MIN);
    else if (e.key === 'End') setWidth(SIDE_MAX);
    else return;
    e.preventDefault();
    savePrefs();
  }

  function pinColor(id) {
    const kind = pageKind(id);
    if (kind === 'tag' || kind === 'project') return tagColor(pageArg(id));
    if (kind === 'person') return 'var(--person)';
    return 'var(--muted)';
  }
</script>

<aside aria-label="Navigazione" style="flex-basis:{app.sideW}px" class:resizing={dragging} bind:this={aside}>
  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
  <div
    class="resizer"
    class:active={dragging}
    role="separator"
    tabindex="0"
    aria-orientation="vertical"
    aria-label="Ridimensiona la barra laterale"
    aria-valuenow={app.sideW}
    aria-valuemin={SIDE_MIN}
    aria-valuemax={SIDE_MAX}
    title="Trascina per ridimensionare · doppio clic per la larghezza iniziale"
    onpointerdown={startResize}
    onpointermove={onResize}
    onpointerup={endResize}
    onpointercancel={endResize}
    ondblclick={resetWidth}
    onkeydown={resizeKey}
  ><span></span></div>
  <div class="head">
    <span class="logo" aria-hidden="true">q</span>
    <span class="name">QuickNotes</span>
    <button class="icon-btn" aria-label="Comprimi la barra laterale" title="Comprimi la barra laterale (Ctrl \)" onclick={toggleSide}><Icon name="collapse" /></button>
  </div>

  <button class="box search" onclick={() => (app.palette = true)}>
    <Icon name="search" size={14} /><span>Cerca o apri…</span><kbd>Ctrl K</kbd>
  </button>

  <nav aria-label="Sezioni">
    {#each nav as n (n.key)}
      <button class="row" class:on={isCurrent(n.page)} aria-current={isCurrent(n.page) ? 'page' : undefined} onclick={() => openPage(n.page)}>
        <Icon name={n.icon} /><span class="grow">{n.label}</span>
        {#if n.dot}<span class="dot" title={n.dotTitle} aria-label={n.dotTitle} role={n.dotTitle ? 'img' : undefined} aria-hidden={n.dotTitle ? undefined : 'true'}></span>{/if}
        <span class="meta mono">{n.meta}</span>
      </button>
    {/each}
  </nav>

  <div class="pins-title">
    <Icon name="folder" size={13} /><span class="grow">Progetti</span>
    <button class="icon-btn mini-add" aria-label="Nuovo progetto" title="Nuovo progetto" aria-expanded={app.newProject} onclick={() => (app.newProject = !app.newProject)}><Icon name="plus" size={13} /></button>
  </div>
  <div class="projects">
    {#if app.newProject}
      <!-- svelte-ignore a11y_autofocus -->
      <input class="new-project" type="text" aria-label="Nome del nuovo progetto" placeholder="Nome del progetto ↵" bind:value={draft} onkeydown={addProject} onblur={() => { if (!draft.trim()) app.newProject = false; }} autofocus />
    {/if}
    {#each live as p (p.key)}
      {@const areas = areasOf(p)}
      <div class="proj">
        {#if areas.length}
          <button class="twist" aria-label={app.projOpen[p.key] ? `Chiudi le aree di ${p.title}` : `Mostra le aree di ${p.title}`} aria-expanded={!!app.projOpen[p.key]} onclick={() => toggleProject(p.key)}>
            <Icon name="right" size={11} style="transition:transform .12s;transform:rotate({app.projOpen[p.key] ? 90 : 0}deg)" />
          </button>
        {:else}<span class="twist" aria-hidden="true"></span>{/if}
        <button class="row proj-row" class:on={active === `project:${p.key}`} onclick={() => openPage(`project:${p.key}`, p.title)}>
          <span class="pdot" style="background:{tagColor(p.key)}" aria-hidden="true"></span><span class="grow clip">{p.title}</span><span class="meta mono">{p.open || ''}</span>
        </button>
      </div>
      {#if app.projOpen[p.key]}
        {#each areas as a (a)}
          <button class="row area-row" onclick={() => openArea(p, a)}>
            <span class="grow clip">{a}</span><span class="meta mono">{p.open_by_area?.[a] || ''}</span>
          </button>
        {/each}
      {/if}
    {:else}
      {#if !app.newProject}<div class="empty">Nessun progetto</div>{/if}
    {/each}
    {#if resting.length}
      <button class="row resting" aria-expanded={showResting} onclick={() => (showResting = !showResting)}>
        <Icon name="right" size={11} style="transition:transform .12s;transform:rotate({showResting ? 90 : 0}deg)" /><span class="grow">In pausa o chiusi</span><span class="meta mono">{resting.length}</span>
      </button>
      {#if showResting}
        {#each resting as p (p.key)}
          <button class="row area-row rest-row" class:on={active === `project:${p.key}`} onclick={() => openPage(`project:${p.key}`, p.title)}>
            <span class="pdot faded" style="background:{tagColor(p.key)}" aria-hidden="true"></span><span class="grow clip">{p.title}</span><span class="meta">{p.status}</span>
          </button>
        {/each}
      {/if}
    {/if}
  </div>

  {#if app.showPins}
    <div class="pins-title"><Icon name="star" size={13} />Preferiti</div>
    <div class="pins">
      {#each app.favs as id (id)}
        {@const info = favInfo(id, app.today?.id)}
        {@const color = pinColor(id)}
        <button class="row pin" class:on={active === id} aria-label="{pinLabel(id)}, {info.type}" onclick={() => openPage(id)}>
          <span class="tile" aria-hidden="true"><Icon name={info.icon} style="stroke-width:1.6;color:{color};fill:color-mix(in srgb, {color} 22%, transparent)" /></span>
          <span class="grow clip">{pinLabel(id)}</span><span class="type">{info.type}</span>
        </button>
      {:else}
        <div class="empty">Usa la stella in alto a destra di una nota per aggiungerla qui.</div>
      {/each}
    </div>
  {/if}

  <div class="spacer"></div>
  <button class="box rec"><Icon name="mic" style="color:var(--late)" /><span>Registra</span><kbd>Ctrl Alt R</kbd></button>
  <button class="row small" class:on={active === 'settings'} aria-current={active === 'settings' ? 'page' : undefined} onclick={() => openPage('settings')}>
    <Icon name="settings" /><span class="grow">Impostazioni</span><kbd class="faint">Ctrl ,</kbd>
  </button>
</aside>

<style>
  aside { position: relative; flex: 0 0 240px; display: flex; flex-direction: column; min-width: 0; min-height: 0; padding: 2px 10px 10px; font-size: 13.5px; }
  aside.resizing { user-select: none; cursor: col-resize; }
  /* La maniglia sta nel margine destro della barra, come i divisori tra i gruppi di schede. */
  .resizer { position: absolute; top: 40px; bottom: 40px; right: 0; z-index: 2; width: 8px; display: flex; justify-content: center; cursor: col-resize; touch-action: none; outline: none; }
  .resizer span { display: block; width: 2px; height: 100%; border-radius: 2px; background: transparent; }
  .resizer:hover span, .resizer:focus-visible span { background: var(--border3); }
  .resizer.active span { background: var(--accent); }
  .head { display: flex; align-items: center; gap: 8px; padding: 0 2px 12px 6px; }
  .logo { width: 22px; height: 22px; border-radius: 6px; background: var(--accent); color: var(--on-accent); display: flex; align-items: center; justify-content: center; font-family: 'Geist Mono', monospace; font-weight: 600; font-size: 13px; }
  .name { flex: 1; font-weight: 600; }
  .box { display: flex; align-items: center; gap: 8px; flex: none; height: 36px; padding: 0 10px; border: 1px solid var(--border2); border-radius: 10px; background: var(--raised); font-size: 13px; text-align: left; }
  .box span { flex: 1; }
  .search { margin-bottom: 14px; color: var(--subtle); }
  .rec { margin-bottom: 10px; color: var(--text); }
  .rec kbd { color: var(--subtle); }
  nav { display: flex; flex-direction: column; gap: 2px; flex: none; }
  .row { display: flex; align-items: center; gap: 10px; flex: none; width: 100%; height: 34px; padding: 0 10px; border: 0; border-radius: 8px; font-size: 13.5px; text-align: left; background: transparent; color: var(--muted); }
  .row:hover, .row.on { background: var(--hover); }
  .row.on { color: var(--text); }
  .row.small { font-size: 13px; }
  .row.pin { padding: 0 10px 0 6px; }
  .grow { flex: 1; min-width: 0; }
  .clip { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .meta { font-size: 11px; color: var(--subtle); }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--late); }
  .pins-title { display: flex; align-items: center; gap: 6px; flex: none; padding: 22px 10px 6px; font-size: 12px; color: var(--subtle); }
  .pins { min-height: 0; overflow-y: auto; scrollbar-width: none; }
  .projects { flex: 0 1 auto; min-height: 60px; max-height: 40%; overflow-y: auto; scrollbar-width: none; }
  .mini-add { width: 22px; height: 22px; margin-right: 4px; }
  .proj { display: flex; align-items: center; }
  .twist { flex: none; display: flex; align-items: center; justify-content: center; width: 18px; height: 30px; padding: 0; border: 0; background: transparent; color: var(--subtle); }
  .proj-row { flex: 1; width: auto; min-width: 0; height: 30px; padding-left: 4px; gap: 8px; }
  .pdot { flex: none; width: 8px; height: 8px; border-radius: 50%; }
  .pdot.faded { opacity: 0.5; }
  .rest-row { padding-left: 22px; gap: 8px; }
  .area-row { height: 28px; padding-left: 32px; font-size: 12.5px; }
  .resting { height: 28px; gap: 6px; font-size: 12px; color: var(--subtle); }
  .new-project { width: 100%; height: 30px; margin-bottom: 4px; padding: 0 8px; border: 1px solid var(--accent); border-radius: 8px; background: var(--surface); color: var(--text); font: inherit; font-size: 13px; outline: none; }
  .tile { flex: none; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 7px; }
  .type { flex: none; font-size: 11px; color: var(--faint); }
  .empty { padding: 4px 10px; font-size: 12.5px; line-height: 1.45; color: var(--subtle); }
  .spacer { flex: 1 0 8px; }
  .faint { color: var(--faint); }
</style>
