<script>
  import { onDestroy } from 'svelte';
  import { call, listen } from '../api.js';
  import { board } from '../state/actions.svelte.js';
  import { app, savePrefs, tagColor } from '../state/app.svelte.js';
  import { AGENDA_FILTERS, emptyFilters } from '../state/actionQuery.js';
  import { openPage } from '../state/layout.svelte.js';
  import ActionItem from './ActionItem.svelte';
  import DetailPopover from './DetailPopover.svelte';
  import Icon from '../shell/Icon.svelte';

  // Cosa fare adesso. Ogni azione compare nella prima sezione in cui rientra; i progetti in pausa restano fuori.
  let data = $state(null);
  let project = $state('');
  let popover = $state(null);
  let closedSections = $state({ next: false, inbox: false });

  async function load() {
    data = await call('agenda', { project: project || null }, { sections: [], projects: [], open: 0, title: '' });
  }
  // Si ricarica dopo ogni modifica (la bacheca cresce di versione) e quando cambia un file.
  $effect(() => {
    board.version;
    project;
    load();
  });
  const off = listen('index-updated', load);
  onDestroy(() => off.then((f) => f()));

  const COLORS = { late: 'var(--late)', today: 'var(--accent)', doing: 'var(--accent)', waiting: 'var(--person)', question: 'var(--dec)', next: 'var(--muted)', inbox: 'var(--faint)' };
  const HINTS = {
    late: 'Scadenza passata.',
    today: 'Scadono oggi o pianificate per oggi (scheduled:).',
    waiting: 'Per persona: chi aspetti. Quelle ferme da più di 7 giorni sono segnate.',
    question: 'Domande aperte e decisioni da prendere, per progetto.',
    next: 'Scadenza o scheduled: nei prossimi 7 giorni.',
    inbox: 'Nate in un daily di più di 2 giorni fa, senza progetto o senza data: spostale nel progetto o pianificale.',
  };
  const sections = $derived(data?.sections ?? []);
  const empty = $derived(data && !sections.some((s) => s.count));

  // Agenda mostra ogni azione una volta sola, nella prima sezione in cui rientra; Azioni, con il filtro della
  // sezione, le mostra tutte, con raggruppamenti e filtri. Il progetto scelto qui resta scelto.
  const LINK_HINTS = {
    late: 'tutte quelle con la scadenza passata',
    today: 'tutte quelle che scadono oggi o pianificate fino a oggi',
    doing: 'tutte quelle in corso',
    waiting: 'tutte quelle in attesa',
    question: 'tutte le domande aperte',
    next: 'tutte quelle con scadenza o scheduled: nei prossimi 7 giorni',
    inbox: 'tutte quelle da smistare',
  };
  function showInActions(key) {
    app.actF = { ...emptyFilters(), ...structuredClone(AGENDA_FILTERS[key]), projects: project ? [project] : [] };
    Object.assign(app, { actQ: '', actFilter: 'aperte' });
    savePrefs();
    openPage('view:actions');
  }

  function openPopover(e, item, kind, index) {
    const r = e.currentTarget.getBoundingClientRect();
    const key = `${item.note_id}:${item.line}:${kind}:${index}`;
    popover = popover?.key === key ? null : { key, item, kind, index, anchor: { left: r.left, top: r.top, bottom: r.bottom } };
  }
</script>

<div class="head">
  <div class="titles">
    <div class="kicker">Agenda</div>
    <h1>{data?.title || 'Oggi'}</h1>
    <div class="sum">{data?.open ?? 0} {data?.open === 1 ? 'azione' : 'azioni'} da guardare{project ? ` · solo ${data?.projects.find((p) => p.key === project)?.title ?? project}` : ''}</div>
  </div>
  <button class="btn" onclick={() => openPage('view:review')}><Icon name="review" size={14} />Revisione{#if app.counts.reviewDue}<span class="dot" aria-label="da fare"></span>{/if}</button>
</div>

{#if data?.projects.length}
  <div class="chips" role="radiogroup" aria-label="Progetto">
    <button class="chip" role="radio" aria-checked={!project} class:on={!project} onclick={() => (project = '')}>Tutti</button>
    {#each data.projects as p (p.key)}
      <button class="chip" role="radio" aria-checked={project === p.key} class:on={project === p.key} onclick={() => (project = project === p.key ? '' : p.key)}><span class="pdot" style="background:{tagColor(p.key)}" aria-hidden="true"></span>{p.title}<span class="mono n">{p.open}</span></button>
    {/each}
  </div>
{/if}

{#if empty}
  <div class="none">Niente da fare adesso. Le azioni con <span class="mono">scheduled:</span> o una scadenza compariranno qui.</div>
{/if}

{#each sections.filter((s) => s.count) as s (s.key)}
  <section class="sec" aria-label={s.title}>
    <div class="sec-top">
      <button class="sec-head" aria-expanded={!closedSections[s.key]} onclick={() => (closedSections[s.key] = !closedSections[s.key])}>
        <Icon name="right" size={12} style="transition:transform .12s;transform:rotate({closedSections[s.key] ? 0 : 90}deg)" />
        <span class="dot2" style="background:{COLORS[s.key]}" aria-hidden="true"></span>
        <span class="sec-title">{s.title}</span><span class="mono n2">{s.count}</span>
        {#if HINTS[s.key]}<span class="hint">{HINTS[s.key]}</span>{/if}
      </button>
      {#if AGENDA_FILTERS[s.key]}
        <button class="to-actions" onclick={() => showInActions(s.key)} aria-label="{s.title}: tutte in Azioni" title="Apri Azioni con {LINK_HINTS[s.key]}{project ? ', solo di questo progetto' : ''}">Tutte in Azioni<Icon name="right" size={11} /></button>
      {/if}
    </div>
    {#if !closedSections[s.key]}
      {#each s.groups as g (g.label ?? '')}
        {#if g.label}<div class="group">{g.label}<span class="mono n2">{g.items.length}</span></div>{/if}
        <div class="rows">
          {#each g.items as item (`${item.note_id}:${item.line}`)}
            <ActionItem {item} quick="agenda" pop={openPopover} popKey={popover?.key} />
          {/each}
        </div>
      {/each}
    {/if}
  </section>
{/each}

{#if popover}
  {#key popover.key}
    <DetailPopover item={popover.item} kind={popover.kind} index={popover.index} anchor={popover.anchor} close={() => (popover = null)} />
  {/key}
{/if}

<style>
  .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 20px; margin-bottom: 18px; }
  .titles { flex: 1 1 260px; }
  .kicker { font-size: 12.5px; color: var(--subtle); }
  .sum { margin-top: 4px; font-size: 13.5px; color: var(--subtle); }
  .btn .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--late); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
  .chip { display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border: 1px solid var(--border2); border-radius: 999px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .chip.on { background: var(--border2); color: var(--text); }
  .pdot { flex: none; width: 8px; height: 8px; border-radius: 50%; }
  .n { font-size: 11px; opacity: 0.75; }
  .sec { margin-top: 18px; }
  .sec-top { display: flex; align-items: flex-start; gap: 8px; }
  .sec-head { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 0 4px 8px; border: 0; background: transparent; color: var(--text); text-align: left; }
  .to-actions { flex: none; display: flex; align-items: center; gap: 4px; height: 22px; padding: 0 6px 0 8px; border: 0; border-radius: 6px; background: transparent; color: var(--subtle); font-size: 12px; }
  .to-actions:hover { background: var(--hover); color: var(--text); }
  .dot2 { width: 8px; height: 8px; border-radius: 50%; }
  .sec-title { font-size: 14px; font-weight: 600; }
  .n2 { font-size: 12px; color: var(--subtle); }
  .hint { flex: 1 1 200px; font-size: 12px; color: var(--faint); }
  .group { display: flex; align-items: center; gap: 8px; margin: 10px 4px 6px; font-size: 12.5px; font-weight: 600; color: var(--muted); }
  .rows { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .rows :global(.act + .act) { border-top: 1px solid var(--border); }
  .none { padding: 48px 0; text-align: center; color: var(--subtle); }
</style>
