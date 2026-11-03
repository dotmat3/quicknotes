<script>
  import { onMount } from 'svelte';
  import { call, listen } from './api.js';
  import { app, refreshCounts, savePrefs, showToast } from './state/app.svelte.js';
  import { onExternalChange, saveAll } from './state/documents.svelte.js';
  import { closeTabs, focused, openPage, reopen, splitTo, canSide } from './state/layout.svelte.js';
  import Sidebar from './shell/Sidebar.svelte';
  import Rail from './shell/Rail.svelte';
  import Workspace from './shell/Workspace.svelte';
  import TitleBar from './shell/TitleBar.svelte';
  import Icon from './shell/Icon.svelte';
  import { VIEWS } from './shell/nav.js';

  let Palette = $state(null);

  $effect(() => {
    if (app.palette && !Palette) import('./overlays/Palette.svelte').then((m) => (Palette = m.default));
  });

  onMount(() => {
    refreshCounts();
    const offs = [
      listen('index-updated', refreshCounts),
      listen('note-changed', onExternalChange),
      // La finestra si nasconde: si salva subito, anche se l'app resta aperta.
      listen('flush', saveAll),
      // L'app si sta chiudendo: prima si salva tutto.
      listen('flush-and-close', async () => {
        await saveAll();
        call('quit');
      }),
      listen('open-page', (p) => openPage(p.page, p.title)),
      // L'app può restare aperta per giorni: "oggi" va riletto ogni volta che torna visibile.
      listen('window-shown', async () => {
        const t = await call('today_info');
        if (t) app.today = t;
      }),
      listen('toast', showToast),
    ];
    return () => offs.forEach((off) => off.then((f) => f()));
  });

  function toggleSide() {
    app.side = app.side === 'open' ? 'closed' : 'open';
    savePrefs();
  }

  async function newNote(noteType) {
    const n = await call('new_note', { title: '', noteType });
    openPage(`note:${n.id}`, n.title);
  }

  function onKey(e) {
    if (!e.ctrlKey && !e.metaKey) return;
    const k = e.key.toLowerCase();
    if (k === 'k' || k === 'p' || k === 'o') {
      app.palette = !app.palette;
    } else if (k === '\\' && e.altKey) {
      const g = focused();
      if (g.active) splitTo(g.id, g.active, g.id, canSide('right') ? 'right' : 'bottom', true);
    } else if (k === '\\') {
      toggleSide();
    } else if (k === 'w' && !e.shiftKey) {
      const g = focused();
      if (g.active) closeTabs(g.id, [g.active]);
    } else if (k === 't' && e.shiftKey) {
      reopen();
    } else if (k === 'n') {
      newNote(e.shiftKey ? 'note' : 'meeting');
    } else if (k === ',') {
      openPage('settings', 'Impostazioni');
    } else if (/^[1-6]$/.test(k) && !e.altKey) {
      const pages = [`note:${app.today?.id}`, ...app.viewOrder.filter((v) => app.viewVis[v]).map((v) => VIEWS[v].page)];
      const page = pages[Number(k) - 1];
      if (page) openPage(page);
    } else {
      return;
    }
    e.preventDefault();
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="app">
<TitleBar />
<div class="root">
  {#if app.side === 'open'}
    <Sidebar {toggleSide} />
  {:else}
    <Rail {toggleSide} />
  {/if}
  <Workspace />
  {#if app.palette && Palette}
    <Palette />
  {/if}
  {#if app.toast}
    <div class="toast" role="status">
      <span>{app.toast}</span>
      <button class="icon-btn" aria-label="Chiudi" onclick={() => (app.toast = '')}><Icon name="close" size={13} /></button>
    </div>
  {/if}
</div>
</div>

<style>
  .app { height: 100%; display: flex; flex-direction: column; }
  .root { flex: 1; min-height: 0; display: flex; align-items: stretch; }
  .toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 60; display: flex; align-items: center; gap: 12px; max-width: calc(100% - 32px); padding: 10px 10px 10px 14px; border-radius: 10px; background: var(--hover); border: 1px solid var(--border3); box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45); font-size: 13px; }
</style>
