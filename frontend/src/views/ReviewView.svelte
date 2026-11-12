<script>
  import { onDestroy } from 'svelte';
  import { call, listen } from '../api.js';
  import { board, setProjectStatus } from '../state/actions.svelte.js';
  import { app, refreshCounts, savePrefs, showToast, tagColor } from '../state/app.svelte.js';
  import { openAt, openPage } from '../state/layout.svelte.js';
  import ActionItem from './ActionItem.svelte';
  import DetailPopover from './DetailPopover.svelte';
  import Icon from '../shell/Icon.svelte';

  // La pulizia del venerdì, circa 10 minuti: un pannello per passo, le azioni si sistemano direttamente qui.
  let data = $state(null);
  let open = $state({ inbox: true });
  let popover = $state(null);
  let withNote = $state(true);

  async function load() {
    data = await call('weekly_review', {}, { steps: [], days_since: null, week_number: 0 });
  }
  $effect(() => {
    board.version;
    load();
  });
  const off = listen('index-updated', load);
  onDestroy(() => off.then((f) => f()));

  const since = $derived(data?.days_since == null ? 'Prima revisione' : data.days_since === 0 ? 'Ultima revisione: oggi' : `Ultima revisione: ${data.days_since} ${data.days_since === 1 ? 'giorno' : 'giorni'} fa`);

  async function finish() {
    try {
      const today = await call('review_done');
      app.lastReview = today;
      savePrefs();
      if (withNote) {
        const n = await call('create_review_note');
        openPage(`note:${n.id}`, n.title);
      }
      showToast('Revisione fatta. Alla prossima settimana.');
    } catch (e) {
      showToast(String(e));
    }
    await Promise.all([refreshCounts(), load()]);
  }

  function openPopover(e, item, kind, index) {
    const r = e.currentTarget.getBoundingClientRect();
    const key = `${item.note_id}:${item.line}:${kind}:${index}`;
    popover = popover?.key === key ? null : { key, item, kind, index, anchor: { left: r.left, top: r.top, bottom: r.bottom } };
  }
</script>

<div class="head">
  <div class="titles">
    <div class="kicker">Revisione · settimana {data?.week_number ?? ''}</div>
    <h1>Revisione settimanale</h1>
    <div class="sum">{since}. Circa 10 minuti: apri un passo alla volta.</div>
  </div>
</div>

{#each data?.steps ?? [] as st, n (st.key)}
  <section class="step" class:empty={!st.count}>
    <button class="step-head" aria-expanded={!!open[st.key]} onclick={() => (open[st.key] = !open[st.key])}>
      <span class="num mono">{n + 1}</span>
      <span class="grow"><span class="title">{st.title}</span><span class="hint">{st.hint}</span></span>
      <span class="count mono" class:zero={!st.count}>{st.kind === 'summary' ? '' : st.count}</span>
      <Icon name="down" size={14} style="transition:transform .12s;transform:rotate({open[st.key] ? 180 : 0}deg)" />
    </button>
    {#if open[st.key]}
      <div class="body">
        {#if st.kind === 'actions'}
          {#if st.items.length}
            <div class="rows">
              {#each st.items as item (`${item.note_id}:${item.line}`)}
                <ActionItem {item} quick="review" pop={openPopover} popKey={popover?.key} />
              {/each}
            </div>
          {:else}<p class="ok">Niente qui.</p>{/if}
        {:else if st.kind === 'groups'}
          {#each st.groups as g (g.name)}
            <div class="group">«{g.label}» · {g.items.length} copie</div>
            <div class="rows">
              {#each g.items as item (`${item.note_id}:${item.line}`)}
                <ActionItem {item} quick="review" pop={openPopover} popKey={popover?.key} />
              {/each}
            </div>
          {:else}<p class="ok">Nessun duplicato.</p>{/each}
        {:else if st.kind === 'projects'}
          {#each st.projects as p (p.key)}
            <div class="proj">
              <Icon name="folder" size={14} style="color:{tagColor(p.key)}" /><span class="grow">{p.title}{#if p.open} · {p.open} aperte{/if}</span>
              <button class="q" onclick={() => openPage(`project:${p.key}`, p.title)}>Apri</button>
              {#if p.status === 'attivo'}
                <button class="q" onclick={() => setProjectStatus(p.key, 'pausa')}>Metti in pausa</button>
              {:else}
                <button class="q" onclick={() => setProjectStatus(p.key, 'attivo')}>Riattiva</button>
                {#if p.status !== 'chiuso'}<button class="q" onclick={() => setProjectStatus(p.key, 'chiuso')}>Chiudi il progetto</button>{/if}
              {/if}
            </div>
          {:else}<p class="ok">Niente qui.</p>{/each}
        {:else if st.kind === 'summary'}
          {@const s = st.summary}
          <div class="stats">
            <div class="stat"><div class="v">{s.done}</div><div class="l">fatte</div></div>
            <div class="stat"><div class="v">{s.cancelled}</div><div class="l">annullate</div></div>
            <div class="stat"><div class="v">{s.decisions.length}</div><div class="l">decisioni</div></div>
          </div>
          {#if s.decisions.length}
            <h3>Decisioni</h3>
            {#each s.decisions as d, i (i)}
              <button class="line" onclick={() => openAt(`note:${d.note_id}`)}><span class="mono when">{d.date.slice(8, 10)}/{d.date.slice(5, 7)}</span><span class="grow">{d.text}</span></button>
            {/each}
          {/if}
          {#if s.done_items.length}
            <h3>Fatte</h3>
            <ul class="done">{#each s.done_items as t, i (i)}<li>{t}</li>{/each}</ul>
          {/if}
        {/if}
      </div>
    {/if}
  </section>
{/each}

{#if data}
  <div class="finish">
    <label class="check"><input type="checkbox" bind:checked={withNote} />Crea la nota «Revisione settimana {data.week_number}»</label>
    <button class="btn primary" onclick={finish}><Icon name="check" size={14} />Fine revisione</button>
  </div>
{/if}

{#if popover}
  {#key popover.key}
    <DetailPopover item={popover.item} kind={popover.kind} index={popover.index} anchor={popover.anchor} close={() => (popover = null)} />
  {/key}
{/if}

<style>
  .head { margin-bottom: 18px; }
  .kicker { font-size: 12.5px; color: var(--subtle); }
  .sum { margin-top: 4px; font-size: 13.5px; color: var(--subtle); }
  .step { margin-top: 8px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); }
  .step.empty .title { color: var(--muted); }
  .step-head { display: flex; align-items: center; gap: 12px; width: 100%; padding: 12px 14px; border: 0; background: transparent; color: var(--text); text-align: left; }
  .num { flex: none; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--border2); font-size: 11.5px; color: var(--muted); }
  .grow { flex: 1; min-width: 0; }
  .title { display: block; font-size: 14px; font-weight: 600; }
  .hint { display: block; margin-top: 1px; font-size: 12px; color: var(--subtle); }
  .count { font-size: 12.5px; color: var(--text); }
  .count.zero { color: var(--faint); }
  .body { padding: 0 14px 14px; }
  .rows { border-radius: 10px; border: 1px solid var(--border); background: var(--surface); }
  .rows :global(.act + .act) { border-top: 1px solid var(--border); }
  .group { margin: 10px 2px 6px; font-size: 12.5px; font-weight: 600; color: var(--muted); }
  .proj { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 4px; font-size: 13.5px; }
  .proj + .proj { border-top: 1px solid var(--border); }
  .q { height: 26px; padding: 0 9px; border: 1px solid var(--border2); border-radius: 7px; background: transparent; color: var(--muted); font-size: 12px; }
  .q:hover { background: var(--hover); color: var(--text); }
  .ok { margin: 0; font-size: 13px; color: var(--faint); }
  .stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .stat { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border2); }
  .v { font-size: 20px; font-weight: 600; }
  .l { font-size: 12px; color: var(--subtle); }
  h3 { margin: 16px 0 6px; font-size: 13px; font-weight: 600; color: var(--muted); }
  .line { display: flex; align-items: flex-start; gap: 10px; width: 100%; padding: 5px 4px; border: 0; border-radius: 6px; background: transparent; color: var(--text); font-size: 13.5px; text-align: left; }
  .line:hover { background: var(--hover); }
  .when { flex: none; font-size: 11.5px; color: var(--subtle); padding-top: 2px; }
  .done { margin: 0; padding-left: 18px; font-size: 13px; color: var(--muted); }
  .finish { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 12px 16px; margin: 20px 0 8px; }
  .check { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); }
</style>
