<script>
  import { onMount } from 'svelte';
  import NoteList from './components/NoteList.svelte';
  import NotePage from './components/NotePage.svelte';
  import Overlays from './components/Overlays.svelte';
  import Sidebar from './components/Sidebar.svelte';
  import { call } from './api.js';
  import { app } from './state.svelte.js';

  // larghezze delle colonne, trascinabili e ricordate
  const LIMITS = { sidebar: [180, 320, 232], list: [260, 520, 340] };
  let widths = $state(loadWidths());
  let dragging = $state(null);

  function loadWidths() {
    try {
      const saved = JSON.parse(localStorage.getItem('qn.widths') ?? '{}');
      return { sidebar: saved.sidebar ?? LIMITS.sidebar[2], list: saved.list ?? LIMITS.list[2] };
    } catch {
      return { sidebar: LIMITS.sidebar[2], list: LIMITS.list[2] };
    }
  }

  function startDrag(e, which) {
    e.preventDefault();
    const handle = e.currentTarget;
    handle.setPointerCapture(e.pointerId);
    const startX = e.clientX;
    const start = widths[which];
    const [min, max] = LIMITS[which];
    dragging = which;
    const move = (ev) => (widths[which] = Math.round(Math.min(max, Math.max(min, start + ev.clientX - startX))));
    const up = () => {
      dragging = null;
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      try {
        localStorage.setItem('qn.widths', JSON.stringify(widths));
      } catch {}
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
  }

  // barra del titolo di Windows chiara o scura come la pagina
  const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
  let systemDark = $state(darkQuery.matches);
  darkQuery.addEventListener('change', (e) => (systemDark = e.matches));
  $effect(() => {
    call('titlebar', app.theme === 'dark' || (app.theme === 'auto' && systemDark));
  });

  $effect(() => {
    const root = document.documentElement;
    if (app.theme === 'auto') delete root.dataset.theme;
    else root.dataset.theme = app.theme;
    root.dataset.motion = app.animations ? 'on' : 'off';
  });

  // scorciatoie della finestra; i tasti propri del browser (stampa, ricarica, ...) sono disattivati
  const BROWSER_KEYS = new Set(['p', 'g', 'j', 'u', 'o', 'r', 'h', 'l', 'e', 'k']);
  function keydown(e) {
    if (!(e.ctrlKey || e.metaKey) || e.altKey) {
      if (e.key === 'F5' || e.key === 'F3' || e.key === 'F7' || e.key === 'F12') e.preventDefault();
      return;
    }
    const key = e.key.toLowerCase();
    const handled = {
      n: () => app.newDraft(e.shiftKey ? 'note' : 'meeting'),
      f: () => app.requestFocus('search'),
      s: () => app.save(),
    }[key];
    if (handled) {
      e.preventDefault();
      handled();
    } else if (BROWSER_KEYS.has(key) && !e.defaultPrevented) {
      e.preventDefault();
    }
  }

  // menu contestuale solo dove si scrive (correttore ortografico, copia/incolla)
  function contextmenu(e) {
    if (!e.target.closest('.cm-content, input, textarea')) e.preventDefault();
  }

  onMount(() => app.start());
</script>

<svelte:window onkeydown={keydown} oncontextmenu={contextmenu} />

<div class="shell" class:dragging style:--sidebar-w="{widths.sidebar}px" style:--list-w="{widths.list}px">
  <Sidebar />
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="splitter" class:active={dragging === 'sidebar'} onpointerdown={(e) => startDrag(e, 'sidebar')}></div>
  <NoteList />
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="splitter" class:active={dragging === 'list'} onpointerdown={(e) => startDrag(e, 'list')}></div>
  {#if app.note}
    <NotePage note={app.note} />
  {:else}
    <div class="loading"></div>
  {/if}
</div>

<Overlays />

<style>
  .shell { height: 100%; display: grid; grid-template-columns: var(--sidebar-w) 1px var(--list-w) 1px minmax(0, 1fr); }
  .shell.dragging { cursor: col-resize; }
  .shell.dragging :global(*) { cursor: col-resize !important; user-select: none !important; }
  .splitter { position: relative; background: var(--border); z-index: 5; transition: background var(--fast) var(--ease); }
  .splitter::after { content: ''; position: absolute; inset: 0 -4px; cursor: col-resize; }
  .splitter:hover, .splitter.active { background: var(--accent); }
  .loading { background: var(--bg); }
</style>
