<script>
  import { onMount } from 'svelte';
  import { call } from '../api.js';
  import { app, tagColor } from '../state/app.svelte.js';
  import { applyLayout, focused, layout, openPage, reopen, splitTo, canSide } from '../state/layout.svelte.js';
  import { pageArg } from '../shell/nav.js';
  import Icon from '../shell/Icon.svelte';

  let q = $state('');
  let hits = $state([]);
  let recent = $state([]);
  let sel = $state(0);
  let input = $state();
  let seq = 0;

  onMount(async () => {
    input.focus();
    recent = await call('recent_notes', { limit: 6 }, []);
  });

  const close = () => (app.palette = false);
  const active = () => focused();
  const VIEWS = [
    ['Calendario', 'view:calendar'],
    ['Azioni', 'view:actions'],
    ['Persone', 'view:people'],
    ['Grafo', 'view:graph'],
    ['Impostazioni', 'settings'],
  ];
  const COMMANDS = [
    ['Nuova nota', 'Ctrl Shift N', () => createNote('', 'note')],
    ['Nuovo meeting', 'Ctrl N', () => createNote('', 'meeting')],
    ['Dividi a destra', 'Ctrl Alt \\', () => active().active && splitTo(active().id, active().active, active().id, canSide('right') ? 'right' : 'bottom', true)],
    ['Dividi in basso', '', () => active().active && splitTo(active().id, active().active, active().id, canSide('bottom') ? 'bottom' : 'right', true)],
    ['Unisci tutti i gruppi', '', () => applyLayout(1, layout.dir)],
    ['Layout: due colonne', '', () => applyLayout(2, 'row')],
    ['Layout: due righe', '', () => applyLayout(2, 'col')],
    ['Riapri scheda chiusa', 'Ctrl Shift T', reopen],
  ];

  async function createNote(title, noteType) {
    const n = await call('new_note', { title, noteType });
    openPage(`note:${n.id}`, n.title);
  }

  const ql = $derived(q.trim().toLowerCase());
  const local = $derived(
    !/^[@#!]/.test(ql)
      ? [
          ...VIEWS.filter(([l]) => !ql || l.toLowerCase().includes(ql)).map(([label, page]) => ({ label, hint: 'vista', go: () => openPage(page) })),
          ...COMMANDS.filter(([l]) => ql && l.toLowerCase().includes(ql)).map(([label, hint, go]) => ({ label, hint: hint || 'comando', go })),
        ]
      : [],
  );
  const noteHits = $derived(ql ? hits : recent.map((n) => ({ kind: 'note', label: n.title, hint: n.date.slice(0, 10), page: `note:${n.id}` })));
  const rows = $derived([
    ...noteHits.map((h) => ({
      label: h.label,
      hint: h.hint,
      snippet: h.snippet,
      dot: h.kind === 'tag' ? tagColor(pageArg(h.page)) : null,
      go: () => openPage(h.page, h.kind === 'note' ? h.label : undefined),
    })),
    ...local,
  ]);

  $effect(() => {
    const query = q.trim();
    const mine = ++seq;
    sel = 0;
    if (!query) {
      hits = [];
      return;
    }
    call('search_all', { query }, []).then((r) => {
      if (mine === seq) hits = r;
    });
  });

  function run(r) {
    close();
    r.go();
  }

  function onKey(e) {
    if (e.key === 'Escape') {
      e.stopPropagation();
      close();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      sel = Math.min(sel + 1, rows.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      sel = Math.max(sel - 1, 0);
    } else if (e.key === 'Enter' && e.ctrlKey && q.trim()) {
      e.preventDefault();
      close();
      createNote(q.trim(), 'note');
    } else if (e.key === 'Enter' && rows[sel]) {
      e.preventDefault();
      run(rows[sel]);
    }
  }
</script>

<div class="dim"></div>
<button class="outside" aria-label="Chiudi la ricerca" onclick={close}></button>
<div class="dialog" role="dialog" aria-label="Cerca o apri">
  <label class="field">
    <Icon name="search" size={18} style="color:var(--subtle)" />
    <span class="sr">Cerca o apri</span>
    <input type="text" bind:this={input} bind:value={q} onkeydown={onKey} placeholder="Cerca note, persone, viste…" />
    <kbd>Esc</kbd>
  </label>
  <div class="list" role="listbox" aria-label="Risultati">
    {#each rows as r, i (`${r.label}:${i}`)}
      <button class="row" class:sel={i === sel} role="option" aria-selected={i === sel} onmouseenter={() => (sel = i)} onclick={() => run(r)}>
        {#if r.dot}<span class="dot" aria-hidden="true" style="background:{r.dot}"></span>{/if}
        <span class="text">
          <span class="label">{r.label}</span>
          {#if r.snippet}<span class="snippet">{r.snippet}</span>{/if}
        </span>
        <span class="hint">{r.hint}</span>
      </button>
    {/each}
    {#if !rows.length}
      <div class="none">Nessun risultato · Ctrl ↵ crea la nota «{q}»</div>
    {/if}
  </div>
</div>

<style>
  .dim { position: fixed; inset: 0; z-index: 50; background: rgba(8, 8, 10, 0.55); }
  .outside { position: fixed; inset: 0; z-index: 51; padding: 0; border: 0; background: transparent; cursor: default; }
  .dialog { position: fixed; top: 80px; left: 50%; transform: translateX(-50%); z-index: 52; width: 560px; max-width: calc(100% - 32px); border-radius: 14px; background: var(--raised); border: 1px solid var(--border3); box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6); overflow: hidden; }
  .field { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--border2); }
  .field input { flex: 1; min-width: 0; border: 0; outline: none; background: transparent; color: var(--text); font: inherit; font-size: 16px; }
  .field kbd { color: var(--subtle); }
  .list { padding: 6px; max-height: 400px; overflow-y: auto; }
  .row { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 38px; padding: 4px 12px; border: 0; border-radius: 8px; background: transparent; color: var(--text); font-size: 14px; text-align: left; }
  .row.sel { background: var(--border2); }
  .dot { flex: none; width: 8px; height: 8px; border-radius: 50%; }
  .text { flex: 1; min-width: 0; }
  .label, .snippet { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .snippet { font-size: 12px; color: var(--subtle); }
  .hint { flex: none; font-size: 12px; color: var(--subtle); }
  .none { padding: 12px 10px; font-size: 13px; color: var(--subtle); }
</style>
