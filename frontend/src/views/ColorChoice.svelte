<script>
  import { app, setTagColor, theme } from '../state/app.svelte.js';
  import { TAG_PALETTE, tagColorId } from '../theme/themes.js';
  import Icon from '../shell/Icon.svelte';

  // Le tinte della tavolozza per un'etichetta o un progetto (la chiave del progetto è la sua etichetta).
  // Il colore scelto ha anche la spunta, così non dipende solo dalla tinta.
  let { tag, label, onpick = () => {} } = $props();
  const current = $derived(tagColorId(tag, app.tagColors));

  function pick(id) {
    setTagColor(tag, id);
    onpick(id);
  }
</script>

<div class="colors" role="radiogroup" aria-label={label}>
  {#each Object.entries(TAG_PALETTE) as [id, [dark, light, name]] (id)}
    {@const c = theme.current.dark ? dark : light}
    <button class="color" class:on={current === id} role="radio" aria-checked={current === id} aria-label={name} title={name} style="background:{c};--c:{c}" onclick={() => pick(id)}>
      {#if current === id}<Icon name="check" size={13} style="stroke-width:3;color:{theme.current.dark ? '#141518' : '#fff'}" />{/if}
    </button>
  {/each}
</div>

<style>
  .colors { display: flex; flex-wrap: wrap; gap: 8px; }
  .color { flex: none; width: 24px; height: 24px; padding: 0; border: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
  .color.on { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--c); }
</style>
