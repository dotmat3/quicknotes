<script>
  import { call } from '../api.js';
  import { app, showToast, tagColor } from '../state/app.svelte.js';
  import { focused, openPage } from '../state/layout.svelte.js';
  import { VIEWS, favInfo, pageArg, pageKind, pageTitle } from './nav.js';
  import Icon from './Icon.svelte';

  let { toggleSide } = $props();

  let fly = $state(null);
  let recent = $state([]);
  let people = $state([]);

  const active = $derived(focused().active);
  const todayPage = $derived(app.today ? `note:${app.today.id}` : '');

  // I dati dei pannelli si aggiornano quando si entra nella striscia, non a ogni nota.
  async function loadPanels() {
    recent = await call('recent_notes', { limit: 3 }, []);
    people = await call('top_people', { limit: 3 }, []);
  }
  $effect(() => {
    loadPanels();
  });

  const rec = () => showToast('La registrazione arriva con la tappa dell’audio');
  const settingsTab = (tab) => () => {
    app.settingsTab = tab;
    openPage('settings');
  };
  const actionsFilter = (filter) => () => {
    app.actFilter = filter;
    openPage('view:actions');
  };

  const items = $derived([
    {
      key: 'cerca', label: 'Cerca', icon: 'search', kbd: 'Ctrl K', go: () => (app.palette = true),
      fly: [...recent.map((n) => ({ label: n.title, hint: 'nota', go: () => openPage(`note:${n.id}`, n.title) })), { label: 'Tutte le note e i comandi', hint: 'Ctrl K', go: () => (app.palette = true) }],
    },
    {
      key: 'oggi', label: 'Oggi', icon: 'today', kbd: 'Ctrl 1', page: todayPage, go: () => openPage(todayPage),
      fly: [{ label: 'Nota di oggi', hint: `${app.counts.todayDone}/${app.counts.todayTotal}`, go: () => openPage(todayPage) }],
    },
    ...app.viewOrder
      .filter((k) => app.viewVis[k])
      .map((k, i) => ({
        key: k, label: VIEWS[k].label, icon: VIEWS[k].icon, kbd: `Ctrl ${i + 2}`, page: VIEWS[k].page, go: () => openPage(VIEWS[k].page), dot: k === 'azioni' && app.counts.late > 0,
        fly: {
          calendario: [{ label: 'Apri il calendario', hint: '', go: () => openPage('view:calendar') }],
          azioni: [
            { label: 'In ritardo', hint: String(app.counts.late), go: actionsFilter('ritardo') },
            { label: 'Aperte', hint: String(app.counts.open), go: actionsFilter('aperte') },
            { label: 'Completate', hint: '', go: actionsFilter('completate') },
          ],
          persone: [...people.map((p) => ({ label: `@${p.name}`, hint: `${p.notes} note`, go: () => openPage(`person:${p.name}`) })), { label: 'Tutte le persone', hint: String(app.counts.people), go: () => openPage('view:people') }],
          grafo: [
            { label: 'Tutte le note', hint: '', go: () => { app.graphLocal = false; openPage('view:graph'); } },
            { label: 'Attorno alla nota aperta', hint: '', go: () => { app.graphLocal = true; openPage('view:graph'); } },
          ],
          micio: [
            { label: 'Apri la stanza', hint: '', go: () => openPage('view:micio') },
          ],
        }[k],
      })),
    { key: 'registra', label: 'Registra', icon: 'mic', kbd: 'Ctrl Alt R', go: rec, bottom: true, late: true, spacer: true, fly: [{ label: 'Avvia la registrazione', hint: '', go: rec }] },
    {
      key: 'impostazioni', label: 'Impostazioni', icon: 'settings', kbd: 'Ctrl ,', page: 'settings', go: () => openPage('settings'), bottom: true,
      fly: [
        { label: 'Aspetto', hint: '', go: settingsTab('aspetto') },
        { label: 'Navigazione', hint: '', go: settingsTab('navigazione') },
        { label: 'Etichette', hint: '', go: settingsTab('etichette') },
        { label: 'Claude', hint: '', go: settingsTab('claude') },
      ],
    },
  ]);

  function pick(fn) {
    fly = null;
    fn();
  }

  function onBlur(e) {
    if (!e.currentTarget.contains(e.relatedTarget)) fly = null;
  }

  const pinLabel = (id) => (id === todayPage ? app.today.title : pageKind(id) === 'tag' ? pageArg(id) : pageTitle(id, app.titles));
  const pinColor = (id) => (pageKind(id) === 'tag' ? tagColor(pageArg(id)) : pageKind(id) === 'person' ? 'var(--person)' : 'var(--muted)');
</script>

<nav aria-label="Navigazione">
  <button class="logo" aria-label="Espandi la barra laterale" title="Espandi la barra laterale (Ctrl \)" onclick={toggleSide}>q</button>
  {#each items as it (it.key)}
    {#if it.spacer}
      {#if app.showPins && app.favs.length}
        <div class="sep" aria-hidden="true"></div>
        <div class="favs" role="list" aria-label="Preferiti">
          {#each app.favs as id (id)}
            {@const info = favInfo(id, app.today?.id)}
            {@const color = pinColor(id)}
            <button class="tile" class:on={active === id} style="--c:{color}" aria-label="{pinLabel(id)}, {info.type}" title="{pinLabel(id)}, {info.type}" onclick={() => openPage(id)}>
              <Icon name={info.icon} style="stroke-width:1.6;color:{color}" />
            </button>
          {/each}
        </div>
      {/if}
      <div class="spacer"></div>
    {/if}
    <div
      class="wrap"
      role="presentation"
      onmouseenter={() => (fly = it.key)}
      onmouseleave={() => (fly = null)}
      onfocusin={() => (fly = it.key)}
      onfocusout={onBlur}
      onkeydown={(e) => e.key === 'Escape' && (fly = null)}
    >
      <button class="btn" class:on={it.page && active === it.page} class:late={it.late} aria-label={it.label} aria-expanded={fly === it.key} aria-current={it.page && active === it.page ? 'page' : undefined} onclick={() => pick(it.go)}>
        <Icon name={it.icon} size={18} />
        {#if it.dot}<span class="dot" aria-hidden="true"></span>{/if}
      </button>
      {#if fly === it.key}
        <div class="fly" class:bottom={it.bottom}>
          <div class="panel" role="group" aria-label={it.label}>
            <div class="title"><span>{it.label}</span><kbd>{it.kbd}</kbd></div>
            {#each it.fly as f (f.label)}
              <button class="item" onclick={() => pick(f.go)}><span>{f.label}</span><span class="hint mono">{f.hint}</span></button>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/each}
</nav>

<style>
  nav { flex: 0 0 56px; height: 100%; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 2px 0 10px; }
  .logo { flex: none; width: 30px; height: 30px; margin-bottom: 6px; padding: 0; border: 0; border-radius: 8px; background: var(--accent); color: var(--on-accent); font-family: 'Geist Mono', monospace; font-weight: 600; font-size: 13px; }
  .wrap { position: relative; flex: none; }
  .btn { position: relative; width: 40px; height: 40px; padding: 0; border: 0; border-radius: 10px; display: flex; align-items: center; justify-content: center; background: transparent; color: var(--subtle); }
  .btn:hover, .btn.on { background: var(--hover); }
  .btn.on { color: var(--text); }
  .btn.late { color: var(--late); }
  .dot { position: absolute; top: 8px; right: 8px; width: 6px; height: 6px; border-radius: 50%; background: var(--late); }
  .sep { flex: none; width: 26px; height: 1px; margin: 6px 0; background: var(--border2); }
  .favs { flex: 0 1 auto; min-height: 0; display: flex; flex-direction: column; gap: 4px; overflow-y: auto; scrollbar-width: none; }
  .tile { flex: none; width: 34px; height: 34px; padding: 0; border: 0; border-radius: 9px; display: flex; align-items: center; justify-content: center; background: color-mix(in srgb, var(--c) 15%, transparent); }
  .tile.on { box-shadow: inset 0 0 0 1px var(--c); }
  .spacer { flex: 1 0 8px; }
  /* Il rientro di 8 px fa da ponte: spostandosi verso il pannello il mouse non esce mai dalla zona. */
  .fly { position: absolute; top: 0; left: 40px; z-index: 45; width: 258px; padding-left: 8px; }
  .fly.bottom { top: auto; bottom: 0; }
  .panel { padding: 8px; border-radius: 10px; background: var(--hover); border: 1px solid var(--border3); box-shadow: 0 18px 40px rgba(0, 0, 0, 0.5); }
  .title { display: flex; gap: 8px; padding: 2px 6px 6px; font-size: 13px; font-weight: 600; }
  .title span { flex: 1; }
  .title kbd { font-weight: 400; color: var(--muted); }
  .item { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 30px; padding: 0 6px; border: 0; border-radius: 6px; background: transparent; color: var(--text2); font-size: 13px; text-align: left; }
  .item:hover { background: var(--border2); }
  .item span:first-child { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hint { font-size: 11px; color: var(--muted); }
</style>
