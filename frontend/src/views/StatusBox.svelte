<script>
  import { statusLabel } from '../note/editor/rules.js';

  // La casella di un'azione con il segno del suo stato. Clic: fatta o riaperta; tasto destro: lo stato.
  let { status = 'todo', small = false, label = '', onclick, oncontextmenu } = $props();

  const PATHS = {
    done: '<path d="m5 12 5 5 9-10"/>',
    doing: '<rect x="5" y="5" width="7" height="14" rx="1.5" style="stroke:none;fill:currentColor"/>',
    waiting: '<circle cx="12" cy="12" r="6"/><path d="M12 9v3.5l2 1.5"/>',
    question: '<path d="M9.5 9.3a2.6 2.6 0 0 1 5 .9c0 1.7-2.5 2.2-2.5 3.8M12 17h.01"/>',
    cancelled: '<path d="M7 12h10"/>',
  };
</script>

{#if onclick}
  <button
    class="box st-{status}"
    class:small
    role="checkbox"
    aria-checked={status === 'done' ? 'true' : status === 'todo' ? 'false' : 'mixed'}
    aria-label="{label} · {statusLabel(status)}"
    title="{statusLabel(status)} · clic: {status === 'done' || status === 'cancelled' ? 'riapri' : 'fatta'} · tasto destro: stato"
    {onclick}
    {oncontextmenu}
  >
    {#if PATHS[status]}<svg viewBox="0 0 24 24" aria-hidden="true">{@html PATHS[status]}</svg>{/if}
  </button>
{:else}
  <!-- Solo il segno, dentro un altro controllo (per esempio una voce di menu). -->
  <span class="box st-{status}" class:small aria-hidden="true">
    {#if PATHS[status]}<svg viewBox="0 0 24 24">{@html PATHS[status]}</svg>{/if}
  </span>
{/if}

<style>
  .box { flex: none; width: 18px; height: 18px; margin-top: 0.5px; padding: 0; border-radius: 5px; display: flex; align-items: center; justify-content: center; border: 1.5px solid var(--faint); background: transparent; color: var(--faint); }
  .box.small { width: 15px; height: 15px; margin-top: 1px; border-radius: 4px; }
  svg { width: 72%; height: 72%; fill: none; stroke: currentColor; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
  .st-done { border: 0; background: var(--accent); color: var(--on-accent); }
  .st-doing { border-color: var(--accent); color: var(--accent); }
  .st-waiting { border-color: var(--person); color: var(--person); }
  .st-question { border-color: var(--dec); color: var(--dec); }
  .st-cancelled { color: var(--faint); }
  .box:hover:not(.st-done) { border-color: var(--accent); }
</style>
