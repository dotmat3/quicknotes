<script>
  import { cubicOut } from 'svelte/easing';
  import { scale } from 'svelte/transition';
  import { app } from '../state.svelte.js';
  import Icon from './Icon.svelte';

  // Menu ⋯ della nota: file, cartella, eliminazione, uscita.
  let open = $state(false);
  let root;

  const items = $derived([
    { label: 'Mostra nella cartella', icon: 'folder', run: () => app.revealNote(), disabled: !app.note?.id },
    { label: 'Apri cartella delle note', icon: 'external', run: () => app.openFolder() },
    { separator: true },
    { label: app.note?.id ? 'Elimina nota' : 'Scarta bozza', icon: 'trash', run: () => app.deleteNote(), danger: true },
    { separator: true },
    { label: 'Esci da QuickNotes', icon: 'logout', run: () => app.quit() },
  ]);

  function choose(item) {
    open = false;
    item.run();
  }

  function outside(e) {
    if (open && !root.contains(e.target)) open = false;
  }

  function keydown(e) {
    if (!open) return;
    const buttons = [...root.querySelectorAll('.menu button:not(:disabled)')];
    const i = buttons.indexOf(document.activeElement);
    if (e.key === 'Escape') {
      open = false;
      root.querySelector('.trigger').focus();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const next = e.key === 'ArrowDown' ? (i + 1) % buttons.length : (i - 1 + buttons.length) % buttons.length;
      buttons[next]?.focus();
    }
  }

  const motion = (d) => (app.animations ? d : 0);
</script>

<svelte:window onpointerdown={outside} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="root" bind:this={root} onkeydown={keydown}>
  <button class="trigger" class:open title="Altro" aria-haspopup="menu" aria-expanded={open} onclick={() => (open = !open)}>
    <Icon name="more" size={18} />
  </button>
  {#if open}
    <div class="menu" role="menu" transition:scale={{ start: 0.96, duration: motion(130), easing: cubicOut }}>
      {#each items as item, i (i)}
        {#if item.separator}
          <div class="sep"></div>
        {:else}
          <button role="menuitem" class:danger={item.danger} disabled={item.disabled} onclick={() => choose(item)}>
            <Icon name={item.icon} size={15} />{item.label}
          </button>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .root { position: relative; }
  .trigger { width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; color: var(--muted);
             transition: background var(--fast) var(--ease), color var(--fast) var(--ease); }
  .trigger:hover, .trigger.open { background: var(--hover); color: var(--text); }
  .menu { position: absolute; z-index: 20; right: 0; top: calc(100% + 6px); min-width: 230px; padding: 5px; transform-origin: top right;
          background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); }
  .menu button { width: 100%; display: flex; align-items: center; gap: 10px; height: 34px; padding: 0 10px; border-radius: 6px;
                 text-align: left; font-size: 13.5px; transition: background var(--fast) var(--ease); }
  .menu button :global(.icon) { color: var(--faint); }
  .menu button:hover:not(:disabled), .menu button:focus-visible { background: var(--hover); outline: none; }
  .menu button:disabled { color: var(--faint); }
  .menu button.danger { color: var(--danger); }
  .menu button.danger :global(.icon) { color: var(--danger); }
  .sep { height: 1px; margin: 5px 6px; background: var(--border); }
</style>
