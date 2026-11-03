<script>
  // Barra del titolo disegnata dalla pagina, come in VS Code: si trascina per spostare la finestra,
  // il doppio clic la ingrandisce. Chiudere la nasconde nell'area di notifica, come la X di sistema.
  import { onMount } from 'svelte';
  import { call, inTauri } from '../api.js';
  import { app } from '../state/app.svelte.js';
  import { focused, openPage } from '../state/layout.svelte.js';
  import { updates } from '../state/updates.svelte.js';
  import { pageTitle } from './nav.js';

  let win = null;
  let maximized = $state(false);

  const title = $derived.by(() => {
    const page = focused()?.active;
    return page ? `${pageTitle(page, app.titles)} — QuickNotes` : 'QuickNotes';
  });

  onMount(() => {
    if (!inTauri) return;
    let off = null;
    import('@tauri-apps/api/window').then(async ({ getCurrentWindow }) => {
      win = getCurrentWindow();
      maximized = await win.isMaximized();
      off = await win.onResized(async () => (maximized = await win.isMaximized()));
    });
    return () => off?.();
  });
</script>

<header class="titlebar" data-tauri-drag-region>
  <span class="title" data-tauri-drag-region>{title}</span>
  {#if updates.available}
    <button class="update" title="Apri Impostazioni › Informazioni" onclick={() => { app.settingsTab = 'info'; openPage('settings', 'Impostazioni'); }}>Aggiornamento {updates.available.version}</button>
  {/if}
  <div class="controls">
    <button aria-label="Riduci a icona" title="Riduci a icona" onclick={() => win?.minimize()}>
      <svg viewBox="0 0 10 10" aria-hidden="true"><path d="M0 5.5h10" /></svg>
    </button>
    <button aria-label={maximized ? 'Ripristina' : 'Ingrandisci'} title={maximized ? 'Ripristina' : 'Ingrandisci'} onclick={() => win?.toggleMaximize()}>
      {#if maximized}
        <svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2.5 2.5V.5h7v7h-2M.5 2.5h7v7h-7z" /></svg>
      {:else}
        <svg viewBox="0 0 10 10" aria-hidden="true"><path d="M.5 .5h9v9h-9z" /></svg>
      {/if}
    </button>
    <button class="close" aria-label="Chiudi" title="Chiudi" onclick={() => call('hide_main')}>
      <svg viewBox="0 0 10 10" aria-hidden="true"><path d="M.5 .5l9 9M9.5 .5l-9 9" /></svg>
    </button>
  </div>
</header>

<style>
  .titlebar { flex: none; position: relative; display: flex; align-items: center; justify-content: center; height: 32px; user-select: none; }
  .title { max-width: calc(100% - 300px); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12.5px; color: var(--subtle); }
  .update { position: absolute; top: 5px; right: 150px; height: 22px; padding: 0 10px; border: 0; border-radius: 11px; background: var(--accent); color: var(--on-accent); font-size: 12px; font-weight: 600; }
  .controls { position: absolute; top: 0; right: 0; bottom: 0; display: flex; }
  .controls button { width: 46px; height: 100%; padding: 0; border: 0; border-radius: 0; background: transparent; color: var(--muted); display: flex; align-items: center; justify-content: center; }
  .controls button:hover { background: var(--hover); color: var(--text); }
  .controls .close:hover { background: #e81123; color: #fff; }
  svg { width: 10px; height: 10px; fill: none; stroke: currentColor; stroke-width: 1; shape-rendering: crispEdges; }
  .close svg { shape-rendering: geometricPrecision; }
</style>
