<script>
  import { cubicOut } from 'svelte/easing';
  import { fade, fly, scale } from 'svelte/transition';
  import { app } from '../state.svelte.js';
  import Icon from './Icon.svelte';

  // Conferma breve in basso (toast) e dialog di conferma o avviso.
  const motion = (d) => (app.animations ? d : 0);
  let accept = $state();

  $effect(() => {
    if (app.dialog) accept?.focus();
  });

  function keydown(e) {
    const d = app.dialog;
    if (!d) return;
    if (e.key === 'Escape' && (d.cancellable || !d.reject)) {
      e.preventDefault();
      d.resolve(false);
    }
    e.stopPropagation();  // con un dialog aperto le scorciatoie della finestra non valgono
  }
</script>

<svelte:window onkeydowncapture={keydown} />

{#if app.toast}
  {#key app.toast.id}
    <div class="toast" role="status" in:fly={{ y: 10, duration: motion(180), easing: cubicOut }} out:fade={{ duration: motion(140) }}>
      <Icon name={app.toast.icon} size={15} stroke={2.2} />
      <span>{app.toast.text}</span>
    </div>
  {/key}
{/if}

{#if app.dialog}
  {@const d = app.dialog}
  <div class="scrim" transition:fade={{ duration: motion(150) }}>
    <div class="dialog" role="alertdialog" aria-modal="true" aria-labelledby="dialog-title" aria-describedby="dialog-text"
         transition:scale={{ start: 0.96, duration: motion(160), easing: cubicOut }}>
      <h2 id="dialog-title">{d.title}</h2>
      <p id="dialog-text">{d.text}</p>
      <div class="buttons">
        {#if d.reject}<button class="secondary" onclick={() => d.resolve(false)}>{d.reject}</button>{/if}
        <button class="primary" class:danger={d.danger} bind:this={accept} onclick={() => d.resolve(true)}>{d.accept}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .toast {
    position: fixed; left: 50%; bottom: 24px; translate: -50% 0; z-index: 50; max-width: calc(100vw - 48px);
    display: flex; align-items: center; gap: 8px; padding: 9px 14px 9px 12px; border-radius: 10px;
    background: var(--text); color: var(--bg); font-size: 13.5px; font-weight: 500; box-shadow: var(--shadow);
    pointer-events: none;
  }
  .toast span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .scrim { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; background: var(--scrim); }
  .dialog { width: min(440px, calc(100vw - 32px)); padding: 22px 22px 18px; border-radius: 14px; background: var(--surface);
            border: 1px solid var(--border); box-shadow: var(--shadow); user-select: text; }
  h2 { margin: 0 0 8px; font: 650 17px/1.3 var(--font-display); }
  p { margin: 0 0 20px; color: var(--muted); line-height: 1.5; white-space: pre-line; overflow-wrap: anywhere; }
  .buttons { display: flex; justify-content: flex-end; gap: 8px; }
  .buttons button { height: 34px; padding: 0 14px; border-radius: 8px; font-weight: 600; transition: background var(--fast) var(--ease); }
  .secondary { background: var(--hover); }
  .secondary:hover { background: var(--selected); }
  .primary { background: var(--accent); color: var(--on-accent); }
  .primary:hover { background: var(--accent-hover); }
  .primary.danger { background: var(--danger); }
  .primary.danger:hover { filter: brightness(0.92); }
</style>
