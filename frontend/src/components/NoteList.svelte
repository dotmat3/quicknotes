<script>
  import { fade, slide } from 'svelte/transition';
  import { app } from '../state.svelte.js';
  import Icon from './Icon.svelte';

  const TYPE_LABELS = { meeting: 'Meeting', daily: 'Nota del giorno', note: 'Nota' };
  let search = $state();

  const showActions = $derived(app.view === 'actions');
  const groups = $derived.by(() => {
    const out = [];
    for (const item of showActions ? app.actions : app.notes) {
      if (out.at(-1)?.section !== item.section) out.push({ section: item.section, items: [] });
      out.at(-1).items.push(item);
    }
    return out;
  });

  $effect(() => {
    if (search && app.focus?.target === 'search') {
      app.focus = null;
      search.focus();
      search.select();
    }
  });

  // frecce su/giu' nell'elenco: apre la nota precedente/successiva
  function listKeydown(e) {
    if (showActions || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
    e.preventDefault();
    const i = app.notes.findIndex((n) => n.id === app.note?.id);
    const next = app.notes[Math.max(0, Math.min(app.notes.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))];
    if (next) app.open(next.id);
  }

  function searchKeydown(e) {
    if (e.key === 'Escape' && app.search) {
      e.preventDefault();
      app.setSearch('');
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      e.currentTarget.closest('.pane').querySelector('.list')?.focus();
    }
  }

  function intoView(node, selected) {
    const run = (on) => on && node.scrollIntoView({ block: 'nearest' });
    run(selected);
    return { update: run };
  }

  const motion = (d) => (app.animations ? d : 0);
</script>

<section class="pane">
  <header>
    <h1>{app.paneTitle}</h1>
    {#if !showActions}
      <button class="icon-btn" title="Nuova nota (Ctrl+Shift+N)" onclick={() => app.newDraft('note')}>
        <Icon name="pen" size={17} />
      </button>
    {/if}
  </header>

  <div class="search">
    <Icon name="search" size={15} />
    <input bind:this={search} value={app.search} spellcheck="false" onkeydown={searchKeydown}
           placeholder={showActions ? 'Cerca nelle azioni' : 'Cerca  ·  @persona  #progetto'}
           oninput={(e) => app.setSearch(e.currentTarget.value)} />
    {#if app.search}
      <button class="clear" title="Cancella" onclick={() => app.setSearch('')}><Icon name="x" size={13} stroke={2.2} /></button>
    {/if}
  </div>

  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <div class="list" tabindex="0" role="listbox" aria-label={app.paneTitle} onkeydown={listKeydown}>
    {#if showActions}
      {#each groups as g (g.section)}
        <div class="section">{g.section}</div>
        {#each g.items as item (item.key)}
          <div class="action" class:done={item.done} out:slide={{ duration: motion(180) }}>
            <button class="box" class:checked={item.done} title="Segna come fatta" aria-label="Segna come fatta"
                    onclick={() => app.completeAction(item)}>
              <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>
            </button>
            <button class="action-body" onclick={() => app.open(item.noteId)}>
              <span class="action-text">{item.text}</span>
              <span class="meta">
                {#if item.due}<span class="due {item.level}">{item.due}</span>{/if}
                <span class="from">{item.noteTitle}</span>
              </span>
            </button>
          </div>
        {/each}
      {/each}
    {:else}
      {#each groups as g (g.section)}
        <div class="section">{g.section}</div>
        {#each g.items as item (item.id)}
          <button class="note" class:selected={item.id === app.note?.id} role="option"
                  aria-selected={item.id === app.note?.id} use:intoView={item.id === app.note?.id}
                  onclick={() => app.open(item.id)}>
            <span class="row">
              <span class="title">{item.title}</span>
              <span class="when">{item.when}</span>
            </span>
            {#if item.preview}<span class="preview">{item.preview}</span>{/if}
            <span class="meta">
              <Icon name={item.icon} size={13} />
              {#if item.project}<span class="project">#{item.project}</span>{/if}
              {#if item.people.length}<span class="people">{item.people.join(', ')}</span>{/if}
              {#if !item.project && !item.people.length}<span>{TYPE_LABELS[item.type] ?? 'Nota'}</span>{/if}
            </span>
          </button>
        {/each}
      {/each}
    {/if}
    {#if !groups.length}
      <div class="empty" in:fade={{ duration: motion(150) }}>
        {#if app.search}Nessun risultato per «{app.search}»
        {:else if showActions}Nessuna azione aperta.
        {:else}Nessuna nota qui.{/if}
      </div>
    {/if}
  </div>
</section>

<style>
  .pane { height: 100%; display: flex; flex-direction: column; background: var(--list-bg); min-width: 0; }
  header { display: flex; align-items: center; justify-content: space-between; padding: 16px 14px 10px 20px; }
  h1 { margin: 0; font: 650 19px/1.2 var(--font-display); letter-spacing: -0.01em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .icon-btn { width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; color: var(--muted);
              transition: background var(--fast) var(--ease), color var(--fast) var(--ease); }
  .icon-btn:hover { background: var(--hover); color: var(--text); }

  .search { display: flex; align-items: center; gap: 8px; height: 36px; margin: 0 14px 8px; padding: 0 10px; border-radius: 9px;
            background: var(--hover); color: var(--faint); border: 1px solid transparent;
            transition: background var(--fast) var(--ease), border-color var(--fast) var(--ease); }
  .search:focus-within { background: var(--surface); border-color: var(--border-strong); }
  .search input { flex: 1; min-width: 0; border: 0; background: none; padding: 0; font-size: 14px; color: var(--text); }
  .search input::placeholder { color: var(--faint); }
  .clear { width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center; color: var(--muted); }
  .clear:hover { background: var(--selected); }

  .list { flex: 1; overflow-y: auto; padding: 0 8px 16px; outline: none; }
  .section { position: sticky; top: 0; z-index: 1; background: var(--list-bg); font-size: 11.5px; font-weight: 650;
             letter-spacing: 0.06em; text-transform: uppercase; color: var(--faint); padding: 14px 12px 6px; }

  .note { display: flex; flex-direction: column; gap: 3px; width: 100%; padding: 10px 12px; border-radius: 9px; text-align: left;
          transition: background var(--fast) var(--ease); }
  .note:hover { background: var(--hover); }
  .note.selected { background: var(--selected); }
  .row { display: flex; align-items: baseline; gap: 10px; }
  .title { flex: 1; min-width: 0; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .when { flex: none; font-size: 12px; color: var(--faint); font-variant-numeric: tabular-nums; }
  .preview { color: var(--muted); font-size: 13.5px; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2;
             -webkit-box-orient: vertical; overflow: hidden; }
  .meta { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--faint); min-width: 0; }
  .meta > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .project { color: var(--tag); }
  .people { color: var(--muted); }

  .action { display: flex; align-items: flex-start; gap: 10px; padding: 9px 12px; border-radius: 9px; transition: background var(--fast) var(--ease); }
  .action:hover { background: var(--hover); }
  .box { flex: none; width: 18px; height: 18px; margin-top: 1px; border-radius: 5px; border: 1.6px solid var(--border-strong); display: grid; place-items: center;
         background: var(--surface); cursor: pointer; transition: background var(--fast) var(--ease), border-color var(--fast) var(--ease), transform var(--fast) var(--ease); }
  .box:hover { border-color: var(--accent); }
  .box:active { transform: scale(0.88); }
  .box svg { width: 12px; height: 12px; fill: none; stroke: var(--on-accent); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round;
             stroke-dasharray: 24; stroke-dashoffset: 24; transition: stroke-dashoffset var(--normal) var(--ease); }
  .box.checked { background: var(--accent); border-color: var(--accent); }
  .box.checked svg { stroke-dashoffset: 0; }
  .action-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; text-align: left; }
  .action-text { line-height: 1.4; transition: color var(--normal) var(--ease); }
  .action.done .action-text { color: var(--faint); text-decoration: line-through; }
  .due { flex: none; font-weight: 600; color: var(--muted); }
  .due.warning { color: var(--warning); }
  .due.danger { color: var(--danger); }

  .empty { padding: 40px 16px; text-align: center; color: var(--faint); font-size: 13.5px; }
</style>
