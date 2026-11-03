<script>
  import { layout, resizeAt, saveLayout } from '../state/layout.svelte.js';
  import Group from './Group.svelte';

  let wrap = $state();

  function onMove(e) {
    if (layout.resize == null) return;
    const r = wrap.getBoundingClientRect();
    resizeAt(layout.resize, layout.dir === 'col' ? (e.clientY - r.top) / r.height : (e.clientX - r.left) / r.width);
  }

  function endResize() {
    if (layout.resize != null) {
      layout.resize = null;
      saveLayout();
    }
  }
</script>

<svelte:window onmousemove={onMove} onmouseup={endResize} />

<div class="split" class:col={layout.dir === 'col'} class:resizing={layout.resize != null} bind:this={wrap}>
  {#each layout.groups as g, i (g.id)}
    {#if i > 0 && !layout.max}
      <div
        class="divider"
        role="separator"
        aria-orientation={layout.dir === 'col' ? 'horizontal' : 'vertical'}
        aria-label="Ridimensiona i gruppi"
        title="Trascina per ridimensionare · doppio clic per pareggiare"
        onmousedown={(e) => { e.preventDefault(); layout.resize = i; }}
        ondblclick={() => { layout.sizes = {}; saveLayout(); }}
      >
        <span class:active={layout.resize === i}></span>
      </div>
    {/if}
    <Group group={g} index={i} />
  {/each}
</div>

<style>
  .split { flex: 1; min-width: 0; height: calc(100% - 16px); margin: 8px 8px 8px 0; display: flex; }
  .split.col { flex-direction: column; }
  .split.resizing { user-select: none; cursor: col-resize; }
  .split.col.resizing { cursor: row-resize; }
  .divider { flex: none; display: flex; justify-content: center; width: 8px; padding: 40px 0; cursor: col-resize; }
  .split.col .divider { width: auto; height: 8px; padding: 0 40px; cursor: row-resize; flex-direction: column; }
  .divider span { display: block; width: 2px; height: 100%; border-radius: 2px; background: transparent; }
  .split.col .divider span { width: 100%; height: 2px; }
  .divider:hover span { background: var(--border3); }
  .divider span.active { background: var(--accent); }
</style>
