<script>
  import { onMount } from 'svelte';
  import { call, listen } from './api.js';
  import { app, holdToast, refreshCounts, savePrefs, showToast } from './state/app.svelte.js';
  import { canRename, onExternalChange, saveAll } from './state/documents.svelte.js';
  import Confirm from './overlays/Confirm.svelte';
  import { closeTabs, focused, goBack, goForward, openPage, reopen, splitTo, canSide } from './state/layout.svelte.js';
  import Sidebar from './shell/Sidebar.svelte';
  import Rail from './shell/Rail.svelte';
  import Workspace from './shell/Workspace.svelte';
  import TitleBar from './shell/TitleBar.svelte';
  import Icon from './shell/Icon.svelte';
  import PetLayer from './pet/PetLayer.svelte';
  import { petCheck } from './pet/store.svelte.js';
  import { VIEWS } from './shell/nav.js';

  let Palette = $state(null);

  $effect(() => {
    if (app.palette && !Palette) import('./overlays/Palette.svelte').then((m) => (Palette = m.default));
  });

  onMount(() => {
    refreshCounts();
    const offs = [
      listen('index-updated', refreshCounts),
      listen('index-updated', petCheck),
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

  function ctrlHeld(e) {
    document.documentElement.classList.toggle('qn-ctrl', e.ctrlKey || e.metaKey);
  }

  // Indietro e Avanti come in VS Code: Alt ← / Alt → e i tasti laterali del mouse. Vanno presi prima
  // dell'editor, che altrimenti userebbe Alt ← per spostare il cursore.
  function onNavKey(e) {
    if (e.altKey && !e.ctrlKey && !e.shiftKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
      e.preventDefault();
      e.stopPropagation();
      if (e.key === 'ArrowLeft') goBack();
      else goForward();
    } else if (e.key === 'F1') {
      e.preventDefault();
      openPage('view:help');
    } else if (e.key === 'F2' && !e.ctrlKey && !e.altKey && !e.shiftKey) {
      // Rinomina la nota della scheda attiva, come F2 in Esplora risorse.
      const g = focused();
      if (g.active?.startsWith('note:') && canRename(g.active.slice(5)) && !app.confirm) {
        e.preventDefault();
        app.rename = `${g.id}:${g.active}`;
      }
    }
  }

  // Il browser userebbe i tasti laterali per la sua cronologia: qui navigano tra le pagine dell'app.
  function onMouseNav(e) {
    if (e.button !== 3 && e.button !== 4) return;
    e.preventDefault();
    if (e.type === 'mouseup') {
      if (e.button === 3) goBack();
      else goForward();
    }
  }

  // Un file lasciato fuori dall'editor farebbe aprire il file a WebView2, al posto dell'app. Nell'editor le
  // immagini si inseriscono nella nota; altrove il file si ignora.
  function stayOnPage(e) {
    if (e.dataTransfer?.types.includes('Files')) e.preventDefault();
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
    } else if (/^[1-9]$/.test(k) && !e.altKey) {
      const pages = [`note:${app.today?.id}`, ...app.viewOrder.filter((v) => app.viewVis[v]).map((v) => VIEWS[v].page)];
      const page = pages[Number(k) - 1];
      if (page) openPage(page);
    } else {
      return;
    }
    e.preventDefault();
  }
</script>

<svelte:window
  onkeydowncapture={onNavKey}
  onmousedown={onMouseNav}
  onmouseup={onMouseNav}
  onkeydown={(e) => { ctrlHeld(e); onKey(e); }}
  onkeyup={ctrlHeld}
  onmousemove={ctrlHeld}
  onblur={() => document.documentElement.classList.remove('qn-ctrl')}
  ondragover={stayOnPage}
  ondrop={stayOnPage}
/>

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
  <button class="help" aria-label="Guida e comandi (F1)" title="Guida e comandi · F1" onclick={() => openPage('view:help')}>?</button>
  <PetLayer />
  {#if app.confirm}
    <Confirm />
  {/if}
  {#if app.toast}
    <div class="toast" role="status" onmouseenter={() => holdToast(true)} onmouseleave={() => holdToast(false)}>
      <span>{app.toast}</span>
      <button class="icon-btn" aria-label="Chiudi" onclick={() => (app.toast = '')}><Icon name="close" size={13} /></button>
    </div>
  {/if}
</div>
</div>

<style>
  .app { height: 100%; display: flex; flex-direction: column; }
  .root { flex: 1; min-height: 0; display: flex; align-items: stretch; }
  .help { position: fixed; right: 18px; bottom: 16px; z-index: 50; width: 26px; height: 26px; padding: 0; border: 1px solid var(--border3); border-radius: 50%; background: var(--chrome); color: var(--muted); font-size: 13px; font-weight: 600; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2); }
  .help:hover { color: var(--text); background: var(--hover); }
  .toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 60; display: flex; align-items: center; gap: 12px; max-width: calc(100% - 32px); padding: 10px 10px 10px 14px; border-radius: 10px; background: var(--hover); border: 1px solid var(--border3); box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45); font-size: 13px; }
</style>
