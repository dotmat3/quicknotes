<script>
  import { app, tagColor } from '../state/app.svelte.js';
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
        dot: k === 'azioni' && app.counts.late > 0,
      })),
  ]);

  const isCurrent = (page) => active === page || (page === 'view:people' && active && pageKind(active) === 'person');

  function pinLabel(id) {
    if (id === todayPage) return app.today.title;
    const t = pageTitle(id, app.titles);
    return pageKind(id) === 'tag' ? pageArg(id) : t;
  }

  function pinColor(id) {
    const kind = pageKind(id);
    if (kind === 'tag') return tagColor(pageArg(id));
    if (kind === 'person') return 'var(--person)';
    return 'var(--muted)';
  }
</script>

<aside aria-label="Navigazione">
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
        {#if n.dot}<span class="dot" aria-hidden="true"></span>{/if}
        <span class="meta mono">{n.meta}</span>
      </button>
    {/each}
  </nav>

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
  aside { flex: 0 0 240px; display: flex; flex-direction: column; min-height: 0; padding: 2px 10px 10px; font-size: 13.5px; }
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
  .tile { flex: none; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 7px; }
  .type { flex: none; font-size: 11px; color: var(--faint); }
  .empty { padding: 4px 10px; font-size: 12.5px; line-height: 1.45; color: var(--subtle); }
  .spacer { flex: 1 0 8px; }
  .faint { color: var(--faint); }
</style>
