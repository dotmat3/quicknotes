<script>
  import { openPage } from '../state/layout.svelte.js';
  import ActionText from './ActionText.svelte';
  import Icon from '../shell/Icon.svelte';

  // Le sezioni comuni a persona ed etichetta: azioni, note, decisioni.
  let { actions = [], notes = [], decisions = [], notesCount = 0 } = $props();
  const dateLabel = (d) => d?.slice(0, 10) ?? '';
</script>

<h2>Azioni aperte <span class="mono n">{actions.length}</span></h2>
{#if actions.length}
  <div class="rows">
    {#each actions as a, i (i)}
      <div class="row">
        <span class="box" aria-hidden="true"></span>
        <div class="main">
          <div class="t"><ActionText text={a.text} /></div>
          {#if a.parent}<div class="parent">In: {a.parent}</div>{/if}
          <button class="src" onclick={() => openPage(`note:${a.note_id}`, a.note_title)}><Icon name="note" size={12} />{a.note_title}</button>
        </div>
        {#if a.due_label}<span class="mono due" class:late={a.due_level === 'late'}>{a.due_label}</span>{/if}
      </div>
    {/each}
  </div>
{:else}
  <p class="none">Nessuna azione aperta.</p>
{/if}

<h2>Note <span class="mono n">{notesCount}</span></h2>
{#each notes as n (n.id)}
  <button class="note" onclick={() => openPage(`note:${n.id}`, n.title)}><span class="grow">{n.title}</span><span class="mono d">{dateLabel(n.date)}</span></button>
{/each}

{#if decisions.length}
  <h2>Decisioni</h2>
  {#each decisions as d, i (i)}
    <button class="dec" onclick={() => openPage(`note:${d.note_id}`)}><Icon name="flag" style="margin-top:4px;color:var(--dec)" /><span class="grow">{d.text}</span><span class="mono d">{dateLabel(d.date)}</span></button>
  {/each}
{/if}

<style>
  h2 { margin: 28px 0 10px; font-size: 16px; font-weight: 600; }
  .n { font-size: 12.5px; font-weight: 400; color: var(--subtle); }
  .rows { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .row { display: flex; gap: 12px; align-items: flex-start; padding: 12px 14px; }
  .row + .row { border-top: 1px solid var(--border); }
  .box { flex: none; width: 18px; height: 18px; margin-top: 3px; border-radius: 5px; border: 1.5px solid var(--faint); }
  .main { flex: 1; min-width: 0; }
  .t { font-size: 14.5px; line-height: 1.5; }
  .parent { font-size: 12.5px; color: var(--subtle); }
  .src { display: flex; align-items: center; gap: 4px; margin-top: 3px; padding: 0; border: 0; background: transparent; color: var(--subtle); font-size: 12px; }
  .due { flex: none; font-size: 11.5px; padding: 2px 7px; border-radius: 5px; background: var(--raised); color: var(--muted); }
  .due.late { background: color-mix(in srgb, var(--late) 14%, transparent); color: var(--late); }
  .none { font-size: 14px; color: var(--subtle); }
  .note, .dec { display: flex; gap: 12px; width: 100%; padding: 8px 0; border: 0; border-bottom: 1px solid var(--line); background: transparent; color: var(--text); font-size: 14.5px; text-align: left; }
  .dec { gap: 10px; border-bottom: 0; padding: 6px 0; }
  .grow { flex: 1; min-width: 0; }
  .d { flex: none; font-size: 12px; color: var(--subtle); }
</style>
