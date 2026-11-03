<script>
  import { onDestroy } from 'svelte';
  import { listen } from '../api.js';
  import { addAction, board, loadBoard } from '../state/actions.svelte.js';
  import { app, savePrefs, tagColor } from '../state/app.svelte.js';
  import ActionItem from './ActionItem.svelte';
  import DetailPopover from './DetailPopover.svelte';
  import Icon from '../shell/Icon.svelte';

  loadBoard();
  const off = listen('index-updated', loadBoard);
  onDestroy(() => off.then((f) => f()));

  let draft = $state('');
  let popover = $state(null);

  const filter = $derived(app.actFilter ?? 'aperte');
  const items = $derived(board.items);
  const openItems = $derived(items.filter((i) => !i.done));

  const GROUPS = [
    ['late', 'In ritardo', 'var(--late)'],
    ['soon', 'Oggi e domani', 'var(--accent)'],
    ['week', 'Questa settimana', 'var(--muted)'],
    ['later', 'Più avanti', 'var(--subtle)'],
    ['none', 'Senza scadenza', 'var(--faint)'],
  ];

  const doneRecent = $derived(items.filter((i) => i.done));
  const groups = $derived.by(() => {
    const isBoard = app.actView === 'bacheca';
    if (filter === 'completate') return doneRecent.length ? [{ key: 'done', title: 'Completate', color: '#7CC4A8', items: doneRecent }] : [];
    const pool = filter === 'ritardo' ? openItems.filter((i) => i.group === 'late') : openItems;
    let out;
    if (app.actGroup === 'progetto') {
      const tags = [...new Set(pool.map((i) => i.tag ?? ''))].sort((a, b) => (a === '') - (b === '') || a.localeCompare(b));
      out = tags.map((t) => ({ key: t || 'none', title: t ? `#${t}` : 'Senza progetto', color: t ? tagColor(t) : 'var(--faint)', items: pool.filter((i) => (i.tag ?? '') === t) }));
    } else {
      out = GROUPS.filter(([k]) => filter === 'aperte' || k === 'late')
        .map(([k, title, color]) => ({ key: k, title, color, items: pool.filter((i) => i.group === k) }))
        // In bacheca le colonne restano anche vuote, tranne "Più avanti" che compare solo se serve.
        .filter((g) => g.items.length || (isBoard && filter === 'aperte' && g.key !== 'later'));
    }
    if (isBoard && filter === 'aperte' && app.boardDone) out.push({ key: 'done', title: 'Fatte', color: '#7CC4A8', items: doneRecent });
    return out;
  });

  const weekTotal = $derived(board.done_this_week + board.open);
  const weekPct = $derived(weekTotal ? Math.round((board.done_this_week / weekTotal) * 100) : 0);
  const tabs = $derived([
    ['aperte', 'Aperte', board.open],
    ['ritardo', 'In ritardo', board.late],
    ['completate', 'Completate', doneRecent.length],
  ]);

  function setPref(key, value) {
    app[key] = value;
    savePrefs();
  }

  function onAdd(e) {
    if (e.key !== 'Enter' || !draft.trim()) return;
    addAction(draft);
    draft = '';
  }

  function openPopover(e, item, kind, index) {
    const r = e.currentTarget.getBoundingClientRect();
    const key = `${item.note_id}:${item.line}:${kind}:${index}`;
    popover = popover?.key === key ? null : { key, item, kind, index, anchor: { left: r.left, top: r.top, bottom: r.bottom } };
  }
</script>

<div class="head">
  <div class="titles">
    <h1>Azioni</h1>
    <div class="sum">{board.open} aperte · {board.late} in ritardo · {board.done_this_week} completate questa settimana</div>
  </div>
  <div class="week">
    <div class="week-top"><span>Settimana {board.week_number}</span><span class="mono">{board.done_this_week} di {weekTotal}</span></div>
    <div class="bar" role="progressbar" aria-label="Azioni completate questa settimana" aria-valuemin="0" aria-valuemax="100" aria-valuenow={weekPct}><div style="width:{weekPct}%"></div></div>
  </div>
</div>

<label class="new">
  <Icon name="plus" /><span class="sr">Nuova azione</span>
  <input type="text" bind:value={draft} onkeydown={onAdd} placeholder="Aggiungi un’azione… finisce nella nota di oggi" /><kbd>↵</kbd>
</label>

<div class="tools">
  <div class="seg" role="tablist" aria-label="Filtro azioni">
    {#each tabs as [k, label, n] (k)}
      <button role="tab" aria-selected={filter === k} class:on={filter === k} onclick={() => (app.actFilter = k)}>{label}<span class="mono n">{n}</span></button>
    {/each}
  </div>
  <span class="grow"></span>
  <div class="seg" role="radiogroup" aria-label="Raggruppa per">
    <span class="seg-label">Raggruppa</span>
    {#each [['scadenza', 'Scadenza'], ['progetto', 'Progetto']] as [v, label] (v)}
      <button role="radio" aria-checked={app.actGroup === v} class:on={app.actGroup === v} onclick={() => setPref('actGroup', v)}>{label}</button>
    {/each}
  </div>
  <div class="seg" role="radiogroup" aria-label="Vista">
    {#each [['bacheca', 'Bacheca', 'board'], ['elenco', 'Elenco', 'list']] as [v, label, icon] (v)}
      <button role="radio" aria-checked={app.actView === v} class:on={app.actView === v} onclick={() => setPref('actView', v)}><Icon name={icon} size={14} />{label}</button>
    {/each}
  </div>
</div>

{#if app.actView === 'bacheca'}
  <div class="columns">
    {#each groups as g (g.key)}
      <section class="column" aria-label={g.title}>
        <div class="col-head"><span class="dot" style="background:{g.color}" aria-hidden="true"></span><span class="col-title">{g.title}</span><span class="mono n2">{g.items.length}</span></div>
        {#each g.items as item (`${item.note_id}:${item.line}`)}
          <ActionItem {item} card pop={openPopover} popKey={popover?.key} />
        {:else}
          <div class="col-empty">Nessuna azione</div>
        {/each}
      </section>
    {/each}
  </div>
{:else}
  {#each groups as g (g.key)}
    <section class="list-group" aria-label={g.title}>
      <div class="col-head list"><span class="dot" style="background:{g.color}" aria-hidden="true"></span><span class="col-title">{g.title}</span><span class="mono n2">{g.items.length}</span></div>
      <div class="rows">
        {#each g.items as item (`${item.note_id}:${item.line}`)}
          <ActionItem {item} pop={openPopover} popKey={popover?.key} />
        {/each}
      </div>
    </section>
  {/each}
{/if}
{#if board.loaded && !groups.some((g) => g.items.length) && app.actView !== 'bacheca'}
  <div class="none">Niente da mostrare qui.</div>
{/if}

{#if popover}
  {#key popover.key}
    <DetailPopover item={popover.item} kind={popover.kind} index={popover.index} anchor={popover.anchor} close={() => (popover = null)} />
  {/key}
{/if}

<style>
  .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 24px; margin-bottom: 20px; }
  .titles { flex: 1 1 260px; }
  .sum { margin-top: 4px; font-size: 13.5px; color: var(--subtle); }
  .week { flex: 0 1 200px; }
  .week-top { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 12px; color: var(--subtle); }
  .bar { height: 6px; border-radius: 3px; background: var(--hover); overflow: hidden; }
  .bar div { height: 100%; background: var(--accent); }
  .new { display: flex; align-items: center; gap: 10px; height: 44px; padding: 0 14px; margin-bottom: 16px; border: 1px solid var(--border2); border-radius: 10px; background: var(--chrome); color: var(--subtle); }
  .new input { flex: 1; min-width: 0; border: 0; outline: none; background: transparent; color: var(--text); font: inherit; font-size: 14px; }
  .tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 4px; }
  .grow { flex: 1; }
  .seg { display: flex; align-items: center; padding: 2px; border-radius: 9px; background: var(--raised); border: 1px solid var(--border); }
  .seg button { display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .seg button.on { background: var(--border2); color: var(--text); }
  .seg-label { padding: 0 8px 0 10px; font-size: 12px; color: var(--subtle); }
  .n { font-size: 11px; opacity: 0.75; }
  .columns { display: flex; gap: 12px; align-items: flex-start; overflow-x: auto; margin-top: 18px; padding-bottom: 10px; }
  .column { flex: 0 0 272px; display: flex; flex-direction: column; gap: 8px; padding: 10px; border-radius: 12px; background: var(--card); border: 1px solid var(--border); }
  .col-head { display: flex; align-items: center; gap: 8px; padding: 2px 4px; }
  .col-head.list { padding: 0 4px 8px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; }
  .col-title { font-size: 13px; font-weight: 600; }
  .n2 { font-size: 12px; color: var(--subtle); }
  .col-empty { padding: 14px 6px; border: 1px dashed var(--border2); border-radius: 10px; text-align: center; font-size: 12.5px; color: var(--subtle); }
  .list-group { margin-top: 20px; }
  .rows { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .rows :global(.act + .act) { border-top: 1px solid var(--border); }
  .none { padding: 48px 0; text-align: center; color: var(--subtle); }
</style>
