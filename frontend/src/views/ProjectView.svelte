<script>
  import { onDestroy } from 'svelte';
  import { call, listen } from '../api.js';
  import { addProjectAction, archiveDone, board, setProjectStatus } from '../state/actions.svelte.js';
  import { app, tagColor } from '../state/app.svelte.js';
  import { openAt, openPage } from '../state/layout.svelte.js';
  import ActionItem from './ActionItem.svelte';
  import DetailPopover from './DetailPopover.svelte';
  import Icon from '../shell/Icon.svelte';

  // Un progetto: tutto quello che lo riguarda, raccolto da tutte le note, senza che la nota di progetto cresca.
  let { slug } = $props();
  let p = $state(null);
  let error = $state('');
  let popover = $state(null);
  let adding = $state(false);
  let draft = $state('');
  let area = $state('');

  async function load() {
    try {
      p = await call('project_page', { slug });
      error = '';
      if (p) app.titles[`project:${slug}`] = p.title;
    } catch (e) {
      error = String(e);
    }
  }
  $effect(() => {
    board.version;
    slug;
    load();
  });
  const off = listen('index-updated', load);
  onDestroy(() => off.then((f) => f()));

  const STATUS = [['attivo', 'Attivo'], ['pausa', 'In pausa'], ['chiuso', 'Chiuso']];
  const color = $derived(tagColor(slug));

  async function add(e) {
    if (e.key === 'Escape') {
      adding = false;
      return;
    }
    if (e.key !== 'Enter' || !draft.trim()) return;
    await addProjectAction(p.key, draft.trim(), area || null);
    draft = '';
    load();
  }

  function openPopover(e, item, kind, index) {
    const r = e.currentTarget.getBoundingClientRect();
    const key = `${item.note_id}:${item.line}:${kind}:${index}`;
    popover = popover?.key === key ? null : { key, item, kind, index, anchor: { left: r.left, top: r.top, bottom: r.bottom } };
  }

  const openNote = (id, title, line) => openAt(`note:${id}`, line, title);
  const day = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : '');
</script>

{#if error}
  <p class="none">{error}</p>
{:else if p}
  <div class="head">
    <div class="titles">
      <div class="kicker"><Icon name="folder" size={12} style="vertical-align:-1px" /> {`Progetto${p.aliases.length ? ` · anche ${p.aliases.join(', ')}` : ''}`}</div>
      <h1 style="color:{color}">{p.title}</h1>
      <div class="sum">{p.open} {p.open === 1 ? 'azione aperta' : 'azioni aperte'} · {p.done_week} fatte negli ultimi 7 giorni{p.areas.length ? ` · aree: ${p.areas.join(', ')}` : ''}</div>
    </div>
    <div class="seg" role="radiogroup" aria-label="Stato del progetto">
      {#each STATUS as [v, label] (v)}
        <button role="radio" aria-checked={p.status === v} class:on={p.status === v} onclick={() => p.status !== v && setProjectStatus(p.key, v)}>{label}</button>
      {/each}
    </div>
  </div>

  <div class="tools">
    <button class="btn" onclick={() => openPage(`note:${p.hub_id}`, p.title)}><Icon name="note" size={14} />Apri hub</button>
    <button class="btn" disabled={!p.closed_in_hub} title="Sposta le azioni chiuse dalla nota di progetto all'archivio, per mese" onclick={() => archiveDone(p.key)}><Icon name="archive" size={14} />{`Archivia fatte${p.closed_in_hub ? ` (${p.closed_in_hub})` : ''}`}</button>
    {#if p.archive_id}<button class="btn" onclick={() => openPage(`note:${p.archive_id}`)}>Archivio</button>{/if}
    <button class="btn primary" aria-expanded={adding} onclick={() => (adding = !adding)}><Icon name="plus" size={14} />azione</button>
  </div>
  {#if adding}
    <div class="new">
      <!-- svelte-ignore a11y_autofocus -->
      <input type="text" aria-label="Nuova azione nella nota di progetto" placeholder="Nuova azione… va nella nota di progetto" bind:value={draft} onkeydown={add} autofocus />
      <select aria-label="Area" bind:value={area}>
        <option value="">Senza area</option>
        {#each p.areas as a (a)}<option value={a}>{a}</option>{/each}
      </select>
    </div>
  {/if}

  {#each p.groups as g (g.area ?? '')}
    <h2>{g.area ?? (p.groups.length > 1 ? 'Senza area' : 'Azioni aperte')} <span class="mono n">{g.items.length}</span></h2>
    <div class="rows">
      {#each g.items as item (`${item.note_id}:${item.line}`)}
        <ActionItem {item} pop={openPopover} popKey={popover?.key} />
      {/each}
    </div>
  {:else}
    {#if !p.waiting.length && !p.questions.length}<p class="empty">Nessuna azione aperta. Il pulsante «+ azione» ne aggiunge una alla nota di progetto.</p>{/if}
  {/each}

  {#if p.waiting.length}
    <h2>In attesa <span class="mono n">{p.waiting.length}</span></h2>
    <div class="rows">
      {#each p.waiting as item (`${item.note_id}:${item.line}`)}<ActionItem {item} pop={openPopover} popKey={popover?.key} />{/each}
    </div>
  {/if}
  {#if p.questions.length}
    <h2>Domande <span class="mono n">{p.questions.length}</span></h2>
    <div class="rows">
      {#each p.questions as item (`${item.note_id}:${item.line}`)}<ActionItem {item} pop={openPopover} popKey={popover?.key} />{/each}
    </div>
  {/if}

  <div class="cols">
    <section>
      <h2>Decisioni recenti <span class="mono n">{p.decisions.length}</span></h2>
      {#each p.decisions as d, i (i)}
        <button class="line" onclick={() => openNote(d.note_id)}><span class="mono when">{day(d.date)}</span><span class="grow">{d.text}</span></button>
      {:else}<p class="empty">Nessuna decisione con <span class="mono">!decisione</span>.</p>{/each}
    </section>
    <section>
      <h2>Log dei daily <span class="mono n">14 giorni</span></h2>
      {#each p.log as l, i (i)}
        <button class="line" onclick={() => openNote(l.note_id, undefined, l.line)}><span class="mono when">{day(l.date)}</span><span class="grow">{l.text}</span></button>
      {:else}<p class="empty">Le righe dei daily sotto l’intestazione del progetto compaiono qui.</p>{/each}
    </section>
  </div>

  <h2>Note del progetto <span class="mono n">{p.notes.length}</span></h2>
  <div class="notes">
    {#each p.notes as n (n.id)}
      <button class="line" onclick={() => openNote(n.id, n.title)}><Icon name={n.is_daily ? 'today' : 'note'} size={13} /><span class="grow">{n.title}</span><span class="mono when">{day(n.date)}</span></button>
    {:else}<p class="empty">Nessuna nota collegata.</p>{/each}
  </div>
{/if}

{#if popover}
  {#key popover.key}
    <DetailPopover item={popover.item} kind={popover.kind} index={popover.index} anchor={popover.anchor} close={() => (popover = null)} />
  {/key}
{/if}

<style>
  .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 20px; }
  .titles { flex: 1 1 260px; }
  .kicker { font-size: 12.5px; color: var(--subtle); }
  .sum { margin-top: 4px; font-size: 13.5px; color: var(--subtle); }
  .seg { display: flex; padding: 2px; border-radius: 9px; background: var(--raised); border: 1px solid var(--border); }
  .seg button { height: 28px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .seg button.on { background: var(--border2); color: var(--text); }
  .tools { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
  .btn:disabled { opacity: 0.5; }
  .new { display: flex; gap: 8px; margin-top: 10px; }
  .new input { flex: 1; min-width: 0; height: 36px; padding: 0 10px; border: 1px solid var(--accent); border-radius: 8px; background: var(--surface); color: var(--text); font: inherit; font-size: 13.5px; outline: none; }
  .new select { height: 36px; padding: 0 8px; border: 1px solid var(--border2); border-radius: 8px; background: var(--raised); color: var(--text); font: inherit; font-size: 13px; }
  h2 { margin: 26px 0 10px; font-size: 15px; font-weight: 600; }
  .n { font-size: 12px; font-weight: 400; color: var(--subtle); }
  .rows { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .rows :global(.act + .act) { border-top: 1px solid var(--border); }
  .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0 24px; }
  .line { display: flex; align-items: flex-start; gap: 10px; width: 100%; padding: 6px 4px; border: 0; border-radius: 6px; background: transparent; color: var(--text); font-size: 13.5px; text-align: left; }
  .line:hover { background: var(--hover); }
  .when { flex: none; font-size: 11.5px; color: var(--subtle); padding-top: 2px; }
  .grow { flex: 1; min-width: 0; }
  .empty { margin: 0; font-size: 13px; color: var(--faint); }
  .none { padding: 48px 0; text-align: center; color: var(--subtle); }
</style>
