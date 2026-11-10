<script>
  import { openPage } from '../state/layout.svelte.js';
  import ActionItem from './ActionItem.svelte';
  import ActionText from './ActionText.svelte';
  import DetailPopover from './DetailPopover.svelte';
  import Icon from '../shell/Icon.svelte';
  import { prioArrow } from '../note/editor/rules.js';

  // Le sezioni comuni a persona ed etichetta: azioni, note, decisioni.
  // Con `items` (schede della bacheca) le azioni si modificano con spunta e pillole; `actions` è in sola lettura.
  let { actions = [], items = null, groups = null, notes = [], decisions = [], notesCount = 0 } = $props();
  const dateLabel = (d) => d?.slice(0, 10) ?? '';

  let popover = $state(null);

  function openPopover(e, item, kind, index) {
    const r = e.currentTarget.getBoundingClientRect();
    const key = `${item.note_id}:${item.line}:${kind}:${index}`;
    popover = popover?.key === key ? null : { key, item, kind, index, anchor: { left: r.left, top: r.top, bottom: r.bottom } };
  }
</script>

<h2>Azioni aperte <span class="mono n">{(items ?? actions).length}</span></h2>
{#if items?.length}
  <!-- Con più progetti (un'area usata in tutti), le azioni sono divise per progetto. -->
  {#each groups && groups.length > 1 ? groups : [{ project: null, items }] as g (g.project ?? '')}
    {#if groups && groups.length > 1}
      <button class="grp" onclick={() => g.project && openPage(`project:${g.project}`)}>{g.project ?? 'Senza progetto'}<span class="mono n">{g.items.length}</span></button>
    {/if}
    <div class="rows">
      {#each g.items as item (`${item.note_id}:${item.line}`)}
        <ActionItem {item} pop={openPopover} popKey={popover?.key} />
      {/each}
    </div>
  {/each}
  {#if popover}
    {#key popover.key}
      <DetailPopover item={popover.item} kind={popover.kind} index={popover.index} anchor={popover.anchor} close={() => (popover = null)} />
    {/key}
  {/if}
{:else if !items && actions.length}
  <div class="rows">
    {#each actions as a, i (i)}
      <div class="row">
        <span class="box" aria-hidden="true"></span>
        <div class="main">
          <div class="t"><ActionText text={a.text} /></div>
          {#if a.parent}<div class="parent">In: {a.parent}</div>{/if}
          <button class="src" onclick={() => openPage(`note:${a.note_id}`, a.note_title)}><Icon name="note" size={12} />{a.note_title}</button>
        </div>
        {#if a.priority}<span class="prio {a.priority}" title="Priorità {a.priority}">{prioArrow(a.priority)} {a.priority}</span>{/if}
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
  .grp { display: flex; align-items: center; gap: 8px; margin: 14px 2px 6px; padding: 0; border: 0; background: transparent; color: var(--muted); font-size: 13px; font-weight: 600; }
  .n { font-size: 12.5px; font-weight: 400; color: var(--subtle); }
  .rows { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .row { display: flex; gap: 12px; align-items: flex-start; padding: 12px 14px; }
  .row + .row { border-top: 1px solid var(--border); }
  .rows :global(.act + .act) { border-top: 1px solid var(--border); }
  .box { flex: none; width: 18px; height: 18px; margin-top: 3px; border-radius: 5px; border: 1.5px solid var(--faint); }
  .main { flex: 1; min-width: 0; }
  .t { font-size: 14.5px; line-height: 1.5; }
  .parent { font-size: 12.5px; color: var(--subtle); }
  .src { display: flex; align-items: center; gap: 4px; margin-top: 3px; padding: 0; border: 0; background: transparent; color: var(--subtle); font-size: 12px; }
  .due { flex: none; font-size: 11.5px; padding: 2px 7px; border-radius: 5px; background: var(--raised); color: var(--muted); }
  .prio { flex: none; font-size: 11.5px; font-weight: 600; padding: 2px 4px; }
  .prio.alta { color: var(--late); }
  .prio.media { color: var(--accent); }
  .prio.bassa { color: var(--subtle); }
  .due.late { background: color-mix(in srgb, var(--late) 14%, transparent); color: var(--late); }
  .none { font-size: 14px; color: var(--subtle); }
  .note, .dec { display: flex; gap: 12px; width: 100%; padding: 8px 0; border: 0; border-bottom: 1px solid var(--line); background: transparent; color: var(--text); font-size: 14.5px; text-align: left; }
  .dec { gap: 10px; border-bottom: 0; padding: 6px 0; }
  .grow { flex: 1; min-width: 0; }
  .d { flex: none; font-size: 12px; color: var(--subtle); }
</style>
