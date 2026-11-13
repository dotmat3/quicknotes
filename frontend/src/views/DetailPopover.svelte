<script>
  import { onMount, tick, untrack } from 'svelte';
  import { call } from '../api.js';
  import { moveAction, setField, setScheduled, setStatus } from '../state/actions.svelte.js';
  import { tagColor } from '../state/app.svelte.js';
  import { openPage } from '../state/layout.svelte.js';
  import { PRIORITIES, STATUSES, isoToday } from '../note/editor/rules.js';
  import StatusBox from './StatusBox.svelte';
  import Icon from '../shell/Icon.svelte';

  // Popover di un dettaglio. `anchor` è il rettangolo della pillola che l'ha aperto. Con `kind` 'add' è il
  // pannello Dettagli della scheda: priorità e stato con un clic, gli altri campi portano al loro popover.
  let { item, kind: firstKind, index: firstIndex, anchor, close } = $props();
  let kind = $state(untrack(() => firstKind));
  let index = $state(untrack(() => firstIndex));

  let q = $state('');
  let known = $state([]);
  let desc = $state(item.description);
  let root = $state();

  const plus = (n) => {
    const d = new Date();
    d.setDate(d.getDate() + n);
    return isoToday(d);
  };

  // Da lunedì a domenica i giorni restano quelli futuri di questa settimana, più le scelte fisse.
  const dueOpts = [
    ['Oggi', plus(0)],
    ['Domani', plus(1)],
    ['Tra una settimana', plus(7)],
    ['Nessuna', null],
  ];

  // Sposta nel progetto: prima il progetto, poi l'area.
  let projects = $state([]);
  let chosen = $state(null);

  async function prepare() {
    root.querySelector('input, textarea, button')?.focus();
    if (kind === 'person') known = (await call('top_people', { limit: 50 }, [])).map((p) => p.name);
    if (kind === 'tag') known = await call('all_tags', {}, []);
    if (kind === 'move') projects = (await call('projects', {}, [])).filter((p) => p.status !== 'chiuso');
  }
  onMount(prepare);

  // Dal pannello Dettagli al popover del campo scelto, nello stesso punto.
  async function go(k) {
    kind = k;
    if (k === 'person') index = item.people.length;
    q = '';
    await tick();
    prepare();
  }

  const current = $derived(kind === 'person' ? item.people[index] : kind === 'tag' ? item.tag : null);
  const typed = $derived(q.trim().replace(/^[@#]/, '').replace(/\s+/g, kind === 'tag' ? '-' : ''));
  const matches = $derived(known.filter((n) => n.toLowerCase().includes(typed.toLowerCase()) && (kind !== 'person' || n === current || !item.people.includes(n))));
  const isNew = $derived(typed && !known.some((n) => n.toLowerCase() === typed.toLowerCase()));
  const prefix = $derived(kind === 'person' ? '@' : '#');

  function pick(value, field = kind) {
    if (field === 'status') setStatus(item, value);
    else if (field === 'priority') setField(item, 'priority', value);
    else if (kind === 'scheduled') setScheduled(item, value);
    else if (kind === 'move') moveAction(item, chosen.key, value);
    else setField(item, kind, value, kind === 'person' ? index : undefined);
    close();
  }

  const projMatches = $derived(projects.filter((p) => !typed || p.title.toLowerCase().includes(typed.toLowerCase()) || p.key.includes(typed.toLowerCase())));
  const areaMatches = $derived(chosen ? chosen.areas.filter((a) => !typed || a.includes(typed.toLowerCase())) : []);
  const newArea = $derived(chosen && typed && !chosen.areas.includes(typed.toLowerCase()) ? typed.toLowerCase() : '');

  function choose(p) {
    chosen = p;
    q = '';
    root.querySelector('input')?.focus();
  }

  function saveDesc() {
    if (desc !== item.description) setField(item, 'description', desc);
    close();
  }

  function onKey(e) {
    if (e.key === 'Escape') {
      e.stopPropagation();
      if (kind === 'description') saveDesc();
      else close();
    }
    if (e.key === 'Enter' && e.target.type === 'text' && kind === 'move') {
      if (!chosen) {
        if (projMatches[0]) choose(projMatches[0]);
      } else pick(newArea || areaMatches[0] || null);
      return;
    }
    if (e.key === 'Enter' && e.target.type === 'text') {
      const first = isNew ? typed : matches[0];
      if (first) pick(first);
    }
    if (e.key === 'Enter' && e.ctrlKey && kind === 'description') saveDesc();
  }

  const style = $derived.by(() => {
    const left = Math.max(8, Math.min(anchor.left, innerWidth - (kind === 'add' ? 300 : 258)));
    const below = anchor.bottom <= innerHeight - 330;
    return `left:${left}px;${below ? `top:${anchor.bottom + 6}px` : `bottom:${innerHeight - anchor.top + 6}px`}`;
  });
  // Le righe del pannello Dettagli, con il valore attuale a destra.
  const DETAILS = $derived([
    ['due', 'calendar', 'Scadenza', item.due_label],
    ['scheduled', 'day', 'Pianifica un giorno', item.scheduled_label],
    ['person', 'person', 'Aggiungi una persona', item.people.length ? item.people.map((p) => `@${p}`).join(' ') : ''],
    ['tag', 'hash', 'Etichetta', item.tag && (item.raw ?? '').toLowerCase().includes(`#${item.tag}`) ? `#${item.tag}` : ''],
    ['move', 'folder', 'Sposta nel progetto', item.project ? `${item.project}${item.area ? `/${item.area}` : ''}` : ''],
    ['description', 'pen', 'Descrizione', item.description ? 'c’è' : ''],
  ]);
  const titles = { add: 'Dettagli', due: 'Scadenza', scheduled: 'Quando farla', person: 'Persona', tag: 'Etichetta', priority: 'Priorità', description: 'Descrizione', status: 'Stato', move: 'Sposta nel progetto' };
</script>

<button class="backdrop" aria-label="Chiudi" onclick={kind === 'description' ? saveDesc : close}></button>
<div class="pop" class:wide={kind === 'add'} role="dialog" aria-label={titles[kind]} {style} bind:this={root} onkeydown={onKey} tabindex="-1">
  <div class="title">{titles[kind]}</div>

  {#if kind === 'add'}
    <div class="arow" role="group" aria-label="Priorità">
      <span class="alabel">Priorità</span>
      {#each PRIORITIES as [value, label, arrow] (value)}
        <button class="achip" class:on={item.priority === value} aria-pressed={item.priority === value} title="Priorità {label}" onclick={() => pick(item.priority === value ? null : value, 'priority')}>{arrow} {label}</button>
      {/each}
    </div>
    <div class="arow" role="group" aria-label="Stato">
      <span class="alabel">Stato</span>
      {#each STATUSES.filter(([v]) => v !== 'done') as [value, , label] (value)}
        <button class="abox" class:on={(item.status ?? 'todo') === value} aria-pressed={(item.status ?? 'todo') === value} aria-label="Stato {label}" title={label} onclick={() => pick(value, 'status')}><StatusBox small status={value} {label} /></button>
      {/each}
    </div>
    <div class="sep"></div>
    {#each DETAILS as [k, icon, label, value] (k)}
      <button class="opt" onclick={() => go(k)}>
        <Icon name={icon} size={13} /><span class="grow">{label}</span>{#if value}<span class="meta clip">{value}</span>{/if}
      </button>
    {/each}
  {:else if kind === 'description'}
    <textarea rows="4" bind:value={desc} aria-label="Descrizione"></textarea>
    <div class="hint">Ctrl ↵ per salvare</div>
  {:else if kind === 'priority'}
    {#each [...PRIORITIES, [null, 'Nessuna', '']] as [value, label, arrow] (label)}
      <button class="opt" class:on={(item.priority ?? null) === value} onclick={() => pick(value)}>
        <span class="arrow" aria-hidden="true">{arrow}</span><span class="grow">{label}</span>
        {#if (item.priority ?? null) === value}<Icon name="check" size={13} style="stroke-width:2.5" />{/if}
      </button>
    {/each}
  {:else if kind === 'status'}
    {#each STATUSES as [value, mark, label] (value)}
      <button class="opt" class:on={(item.status ?? 'todo') === value} onclick={() => pick(value)}>
        <StatusBox small status={value} label={label} /><span class="grow">{label}</span><span class="mono meta">[{mark}]</span>
      </button>
    {/each}
  {:else if kind === 'due' || kind === 'scheduled'}
    {@const cur = kind === 'due' ? item.due : item.scheduled}
    {#each dueOpts as [label, value] (label)}
      <button class="opt" class:on={cur === value} onclick={() => pick(value)}>
        <span class="grow">{label}</span><span class="mono meta">{value ? value.slice(8) + '/' + value.slice(5, 7) : ''}</span>
        {#if cur === value}<Icon name="check" size={13} style="stroke-width:2.5" />{/if}
      </button>
    {/each}
    <label class="date">Altra data<input type="date" value={cur ?? ''} onchange={(e) => e.target.value && pick(e.target.value)} /></label>
    {#if kind === 'scheduled'}<div class="hint">Il giorno in cui farla. La scadenza resta a parte.</div>{/if}
  {:else if kind === 'move'}
    {#if !chosen}
      <input class="search" type="text" aria-label="Cerca un progetto" placeholder="Cerca un progetto…" bind:value={q} />
      <div class="list">
        {#each projMatches as p (p.key)}
          <button class="opt" class:on={p.key === item.project} onclick={() => choose(p)}>
            <Icon name="folder" size={13} /><span class="grow">{p.title}</span><span class="mono meta">{p.status === 'attivo' ? p.open : p.status}</span>
          </button>
        {:else}
          <div class="hint">Nessun progetto. Creane uno dalla barra laterale, sezione Progetti.</div>
        {/each}
      </div>
    {:else}
      <button class="link back" onclick={() => { chosen = null; q = ''; }}><Icon name="left" size={12} />{chosen.title}</button>
      <input class="search" type="text" aria-label="Area" placeholder="Area, oppure scrivine una nuova…" bind:value={q} />
      <div class="list">
        {#each areaMatches as a (a)}
          <button class="opt" class:on={a === item.area} onclick={() => pick(a)}><span class="grow">### {a}</span></button>
        {/each}
        {#if newArea}<button class="opt" onclick={() => pick(newArea)}><span class="grow">### {newArea}</span><span class="mono meta">nuova</span></button>{/if}
        <button class="opt" onclick={() => pick(null)}><span class="grow">Senza area</span></button>
      </div>
      <div class="hint">Va nella nota del progetto con figlie e descrizione; nella nota di partenza resta un rimando.</div>
    {/if}
  {:else}
    <input class="search" type="text" aria-label={titles[kind]} placeholder={kind === 'person' ? 'Cerca o scrivi un nome…' : 'Cerca o scrivi un’etichetta…'} bind:value={q} />
    <div class="list">
      {#each matches as n (n)}
        <button class="opt" class:on={n === current} onclick={() => pick(n)}>
          {#if kind === 'tag'}<span class="dot" style="background:{tagColor(n)}"></span>{/if}
          <span class="grow">{prefix}{n}</span>
          {#if n === current}<Icon name="check" size={13} style="stroke-width:2.5" />{/if}
        </button>
      {/each}
      {#if isNew}
        <button class="opt" onclick={() => pick(typed)}><span class="grow">{prefix}{typed}</span><span class="mono meta">nuova</span></button>
      {/if}
      {#if current && !q}
        <button class="opt" onclick={() => pick(null)}><span class="grow">Togli</span></button>
      {/if}
    </div>
    {#if kind === 'tag' && item.tag}
      <button class="link" onclick={() => { openPage(`tag:${item.tag}`); close(); }}>Apri la pagina di #{item.tag}</button>
    {:else if kind === 'person' && current}
      <button class="link" onclick={() => { openPage(`person:${current}`); close(); }}>Apri la pagina di @{current}</button>
    {/if}
  {/if}
</div>

<style>
  .pop { position: fixed; z-index: 40; width: 250px; max-height: 320px; overflow-y: auto; padding: 8px; border-radius: 10px; background: var(--hover); border: 1px solid var(--border3); box-shadow: 0 18px 40px rgba(0, 0, 0, 0.5); }
  .title { padding: 0 4px 6px; font-size: 12px; color: var(--muted); }
  .pop.wide { width: 292px; }
  .arow { display: flex; align-items: center; gap: 4px; min-height: 32px; padding: 0 4px; }
  .alabel { width: 54px; flex: none; font-size: 12px; color: var(--muted); }
  .achip { height: 26px; padding: 0 7px; border: 1px solid var(--border3); border-radius: 999px; background: transparent; color: var(--text); font-size: 12px; white-space: nowrap; }
  .abox { display: grid; place-items: center; width: 28px; height: 28px; padding: 0; border: 1px solid transparent; border-radius: 7px; background: transparent; }
  .achip:hover, .abox:hover { background: var(--border2); }
  .achip.on, .abox.on { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 16%, transparent); }
  .sep { height: 1px; margin: 6px 4px; background: var(--border3); }
  .clip { max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .opt { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 32px; padding: 0 8px; border: 0; border-radius: 6px; background: transparent; color: var(--text); font-size: 13px; text-align: left; }
  .opt:hover, .opt.on { background: var(--border2); }
  .grow { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .meta { font-size: 11.5px; color: var(--muted); }
  .dot { flex: none; width: 8px; height: 8px; border-radius: 50%; }
  .arrow { flex: none; width: 12px; color: var(--muted); text-align: center; }
  input, textarea { width: 100%; border: 1px solid var(--border3); border-radius: 6px; background: var(--sunk); color: var(--text); font: inherit; font-size: 13px; }
  .search { height: 30px; margin-bottom: 6px; padding: 0 8px; }
  textarea { display: block; padding: 8px; resize: vertical; }
  .hint { margin-top: 4px; font-size: 11.5px; color: var(--muted); }
  .date { display: flex; align-items: center; gap: 8px; margin-top: 6px; padding: 6px 4px 0; border-top: 1px solid var(--border3); font-size: 12.5px; color: var(--muted); white-space: nowrap; }
  .date input { flex: 1; min-width: 0; height: 30px; padding: 0 6px; font-size: 12.5px; }
  .back { display: flex !important; align-items: center; gap: 6px; margin: 0 0 6px !important; border-top: 0 !important; color: var(--text) !important; }
  .link { display: block; width: 100%; min-height: 30px; margin-top: 6px; padding: 0 8px; border: 0; border-top: 1px solid var(--border3); background: transparent; color: var(--text2); font-size: 12.5px; text-align: left; }
</style>
