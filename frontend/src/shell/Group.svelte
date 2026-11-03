<script>
  import { app, savePrefs } from '../state/app.svelte.js';
  import { activate, applyLayout, canSide, closeGroup, closeTabs, layout, moveTab, reopen, saveLayout, splitTo, weights } from '../state/layout.svelte.js';
  import { pageIcon, pageKind, pageArg, pageTitle } from './nav.js';
  import { tagColor } from '../state/app.svelte.js';
  import Icon from './Icon.svelte';
  import Page from './Page.svelte';

  let { group: g, index } = $props();

  let menu = $state(null);

  const focused = $derived(layout.focus === g.id);
  const multi = $derived(layout.groups.length > 1);
  const isMax = $derived(layout.max === g.id);
  const hidden = $derived(layout.max && !isMax);
  const weight = $derived(layout.max ? 1 : weights()[index]);
  const splitSide = $derived(canSide('right') ? 'right' : canSide('bottom') ? 'bottom' : null);
  const zones = $derived(['center', ...['left', 'right', 'top', 'bottom'].filter((s) => canSide(s))]);
  const fav = $derived(!!g.active && app.favs.includes(g.active));

  const isDaily = (id) => pageKind(id) === 'note' && pageArg(id).endsWith('-giornata');
  const iconColor = (id, on) => (pageKind(id) === 'tag' ? tagColor(pageArg(id)) : on ? 'var(--muted)' : 'var(--faint)');

  function toggleFav() {
    app.favs = fav ? app.favs.filter((x) => x !== g.active) : [...app.favs, g.active];
    savePrefs();
  }

  function menuItems(id) {
    const i = g.tabs.indexOf(id);
    const others = g.tabs.filter((x) => x !== id);
    const right = g.tabs.slice(i + 1);
    return [
      { label: 'Chiudi', kbd: 'Ctrl W', run: () => closeTabs(g.id, [id]) },
      { label: 'Chiudi le altre', run: () => closeTabs(g.id, others), disabled: !others.length },
      { label: 'Chiudi quelle a destra', run: () => closeTabs(g.id, right), disabled: !right.length },
      { label: 'Chiudi tutte', run: () => closeTabs(g.id, [...g.tabs]) },
      { label: 'Dividi a destra', kbd: 'Ctrl Alt \\', run: () => splitTo(g.id, id, g.id, 'right', true), disabled: !canSide('right'), sep: true },
      { label: 'Dividi in basso', run: () => splitTo(g.id, id, g.id, 'bottom', true), disabled: !canSide('bottom') },
      { label: 'Unisci tutti i gruppi', run: () => applyLayout(1, layout.dir), disabled: !multi },
      {
        label: 'Sposta nel gruppo accanto',
        disabled: !multi,
        run: () => {
          const nb = layout.groups[index + 1] ?? layout.groups[index - 1];
          if (nb) moveTab(g.id, id, nb.id, null);
        },
      },
      { label: 'Riapri scheda chiusa', kbd: 'Ctrl Shift T', run: reopen, disabled: !layout.closed.length, sep: true },
    ];
  }

  function dragStart(e, id) {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', id);
    layout.drag = { g: g.id, id };
    menu = null;
  }

  function dragEnd() {
    layout.drag = layout.dropZone = layout.dropTab = null;
  }

  function tabOver(e, id) {
    if (!layout.drag) return;
    e.preventDefault();
    if (!(layout.dropTab?.g === g.id && layout.dropTab.id === id)) {
      layout.dropTab = { g: g.id, id };
      layout.dropZone = null;
    }
  }

  function tabDrop(e, id) {
    e.preventDefault();
    if (layout.drag) moveTab(layout.drag.g, layout.drag.id, g.id, g.tabs.indexOf(id));
  }

  function zoneOver(e, z) {
    e.preventDefault();
    if (!(layout.dropZone?.g === g.id && layout.dropZone.k === z)) {
      layout.dropZone = { g: g.id, k: z };
      layout.dropTab = null;
    }
  }

  function zoneDrop(e, z) {
    e.preventDefault();
    const d = layout.drag;
    if (!d) return;
    if (z === 'center') moveTab(d.g, d.id, g.id, null);
    else splitTo(d.g, d.id, g.id, z, false);
  }
</script>

<main class="pane" class:hidden class:lit={multi && focused} style="flex:{weight} 1 0" aria-label="Gruppo {index + 1}" onmousedown={() => { if (!focused) { layout.focus = g.id; saveLayout(); } }}>
  <div class="bar">
    <div class="tabs" role="tablist" aria-label="Schede aperte">
      {#each g.tabs as id, i (id)}
        {@const on = id === g.active}
        {@const title = pageTitle(id, app.titles)}
        <div
          class="tab"
          class:on
          class:first={i === 0}
          class:dragging={layout.drag?.g === g.id && layout.drag.id === id}
          class:drop-before={layout.dropTab?.g === g.id && layout.dropTab.id === id && !(layout.drag?.g === g.id && layout.drag.id === id)}
          draggable="true"
          role="presentation"
          ondragstart={(e) => dragStart(e, id)}
          ondragover={(e) => tabOver(e, id)}
          ondrop={(e) => tabDrop(e, id)}
          ondragend={dragEnd}
          onmousedown={(e) => { if (e.button === 1) e.preventDefault(); }}
          onauxclick={(e) => { if (e.button === 1) { e.preventDefault(); closeTabs(g.id, [id]); } }}
        >
          <button class="tab-main" role="tab" aria-selected={on} {title} onclick={() => activate(g.id, id)} oncontextmenu={(e) => { e.preventDefault(); menu = id; layout.focus = g.id; }}>
            <Icon name={pageIcon(id, isDaily(id))} style="color:{iconColor(id, on)}" />
            <span class="clip">{title}</span>
          </button>
          <button class="tab-close" aria-label="Chiudi {title}" onclick={() => closeTabs(g.id, [id])}><Icon name="close" size={13} /></button>
          {#if menu === id}
            <div class="menu tab-menu" role="menu" aria-label="Azioni per {title}">
              {#each menuItems(id) as it (it.label)}
                {#if it.sep}<div class="menu-sep" role="separator"></div>{/if}
                <button class="menu-item" role="menuitem" disabled={it.disabled} onclick={() => { menu = null; it.run(); }}><span style="flex:1">{it.label}</span><kbd>{it.kbd ?? ''}</kbd></button>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
    <div class="fill" role="presentation" ondragover={(e) => { if (layout.drag) { e.preventDefault(); layout.dropTab = null; } }} ondrop={(e) => { e.preventDefault(); if (layout.drag) moveTab(layout.drag.g, layout.drag.id, g.id, null); }}>
      <button class="icon-btn" aria-label="Apri una nota" title="Apri una nota (Ctrl P)" onclick={() => (app.palette = true)}><Icon name="plus" /></button>
    </div>
    <div class="acts">
      <button class="icon-btn" aria-label={splitSide === 'bottom' ? 'Dividi in basso' : 'Dividi a destra'} title={splitSide === 'bottom' ? 'Dividi in basso' : 'Dividi a destra'} disabled={!splitSide || !g.active} onclick={() => splitTo(g.id, g.active, g.id, splitSide, true)}><Icon name={splitSide === 'bottom' ? 'splitH' : 'splitV'} /></button>
      {#if multi}
        <button class="icon-btn" class:pressed={isMax} aria-label={isMax ? 'Ripristina i gruppi' : 'Ingrandisci questo gruppo'} title={isMax ? 'Ripristina i gruppi' : 'Ingrandisci questo gruppo'} aria-pressed={isMax} onclick={() => { layout.max = isMax ? null : g.id; layout.focus = g.id; }}><Icon name={isMax ? 'restore' : 'maximize'} /></button>
        <button class="icon-btn" aria-label="Chiudi il gruppo" title="Chiudi il gruppo · le schede passano al gruppo accanto" onclick={() => closeGroup(g.id)}><Icon name="close" size={14} /></button>
      {/if}
    </div>
  </div>

  <div class="scroll">
    {#if g.active}
      <Page page={g.active} {fav} {toggleFav} groupId={g.id} />
    {:else}
      <div class="empty">
        <div class="empty-title">Nessuna scheda aperta</div>
        <div class="empty-actions">
          {#if app.today}<button class="btn primary" onclick={() => activate(g.id, `note:${app.today.id}`) || (g.tabs.includes(`note:${app.today.id}`) || g.tabs.push(`note:${app.today.id}`))}>Apri la nota di oggi</button>{/if}
          <button class="btn" onclick={() => (app.palette = true)}>Cerca · Ctrl K</button>
        </div>
      </div>
    {/if}
  </div>

  {#if layout.drag}
    <div class="zones">
      {#each zones as z (z)}
        <div class="zone {z}" role="presentation" ondragover={(e) => zoneOver(e, z)} ondrop={(e) => zoneDrop(e, z)}></div>
      {/each}
      {#if layout.dropZone?.g === g.id}
        <div class="preview {layout.dropZone.k}"></div>
      {/if}
    </div>
  {/if}
</main>

{#if menu}
  <button class="backdrop" aria-label="Chiudi il menu" onclick={() => (menu = null)}></button>
{/if}

<style>
  .pane { position: relative; min-width: 0; min-height: 0; display: flex; flex-direction: column; border-radius: 12px; overflow: hidden; background: var(--surface); border: 1px solid var(--border); }
  .pane.lit { border-color: var(--border3); }
  .pane.hidden { display: none; }
  .bar { flex: none; display: flex; align-items: stretch; height: 38px; border-radius: 12px 12px 0 0; background: var(--bar); }
  .tabs { display: flex; align-items: stretch; flex: 0 1 auto; min-width: 0; }
  .tab { position: relative; display: flex; align-items: center; flex: 0 1 190px; width: 190px; min-width: 56px; border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); background: transparent; color: var(--faint); }
  .tab.first { border-top-left-radius: 11px; }
  .tab.on { background: var(--surface); color: var(--text); border-bottom-color: var(--surface); }
  .tab.dragging { opacity: 0.45; }
  .tab.drop-before { box-shadow: inset 2px 0 0 var(--accent); }
  .tab-main { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; height: 100%; padding: 0 4px 0 12px; border: 0; background: transparent; color: inherit; font-size: 13px; text-align: left; }
  .clip { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tab-close { flex: none; width: 22px; height: 22px; margin-right: 6px; padding: 0; border: 0; border-radius: 5px; background: transparent; display: flex; align-items: center; justify-content: center; color: var(--faint); }
  .tab.on .tab-close { color: var(--muted); }
  .tab-close:hover { background: var(--hover); }
  .tab-menu { top: 40px; left: 0; }
  .fill { flex: 1; display: flex; align-items: center; padding-left: 4px; border-bottom: 1px solid var(--border); }
  .acts { flex: none; display: flex; align-items: center; gap: 2px; padding-right: 6px; border-bottom: 1px solid var(--border); }
  .icon-btn.pressed { background: var(--hover); color: var(--text); }
  .scroll { flex: 1; min-height: 0; overflow: auto; }
  .empty { padding: 120px 0; text-align: center; color: var(--subtle); }
  .empty-title { font-size: 15px; color: var(--muted); }
  .empty-actions { display: flex; justify-content: center; gap: 8px; margin-top: 16px; }
  .zones { position: absolute; left: 0; right: 0; bottom: 0; top: 38px; z-index: 25; }
  .zone { position: absolute; }
  .zone.center { inset: 0; }
  .zone.left { left: 0; top: 0; bottom: 0; width: 28%; }
  .zone.right { right: 0; top: 0; bottom: 0; width: 28%; }
  .zone.top { left: 28%; right: 28%; top: 0; height: 30%; }
  .zone.bottom { left: 28%; right: 28%; bottom: 0; height: 30%; }
  .preview { position: absolute; pointer-events: none; border-radius: 10px; border: 2px solid var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); }
  .preview.center { inset: 8px; }
  .preview.left { left: 8px; top: 8px; bottom: 8px; width: calc(50% - 12px); }
  .preview.right { right: 8px; top: 8px; bottom: 8px; width: calc(50% - 12px); }
  .preview.top { left: 8px; right: 8px; top: 8px; height: calc(50% - 12px); }
  .preview.bottom { left: 8px; right: 8px; bottom: 8px; height: calc(50% - 12px); }
</style>
