<script>
  import { onMount } from 'svelte';
  import { call } from '../api.js';
  import { setField } from '../state/actions.svelte.js';
  import { tagColor } from '../state/app.svelte.js';
  import { openPage } from '../state/layout.svelte.js';
  import { PRIORITIES, isoToday } from '../note/editor/rules.js';
  import Icon from '../shell/Icon.svelte';

  // Popover di un dettaglio. `anchor` è il rettangolo della pillola che l'ha aperto.
  let { item, kind, index, anchor, close } = $props();

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

  onMount(async () => {
    if (kind === 'person') known = (await call('top_people', { limit: 50 }, [])).map((p) => p.name);
    if (kind === 'tag') known = await call('all_tags', {}, []);
    root.querySelector('input, textarea, button')?.focus();
  });

  const current = $derived(kind === 'person' ? item.people[index] : kind === 'tag' ? item.tag : null);
  const typed = $derived(q.trim().replace(/^[@#]/, '').replace(/\s+/g, kind === 'tag' ? '-' : ''));
  const matches = $derived(known.filter((n) => n.toLowerCase().includes(typed.toLowerCase()) && (kind !== 'person' || n === current || !item.people.includes(n))));
  const isNew = $derived(typed && !known.some((n) => n.toLowerCase() === typed.toLowerCase()));
  const prefix = $derived(kind === 'person' ? '@' : '#');

  function pick(value) {
    setField(item, kind, value, kind === 'person' ? index : undefined);
    close();
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
    if (e.key === 'Enter' && e.target.type === 'text') {
      const first = isNew ? typed : matches[0];
      if (first) pick(first);
    }
    if (e.key === 'Enter' && e.ctrlKey && kind === 'description') saveDesc();
  }

  const style = $derived.by(() => {
    const left = Math.max(8, Math.min(anchor.left, innerWidth - 258));
    const below = anchor.bottom <= innerHeight - 330;
    return `left:${left}px;${below ? `top:${anchor.bottom + 6}px` : `bottom:${innerHeight - anchor.top + 6}px`}`;
  });
  const titles = { due: 'Scadenza', person: 'Persona', tag: 'Etichetta', priority: 'Priorità', description: 'Descrizione' };
</script>

<button class="backdrop" aria-label="Chiudi" onclick={kind === 'description' ? saveDesc : close}></button>
<div class="pop" role="dialog" aria-label={titles[kind]} {style} bind:this={root} onkeydown={onKey} tabindex="-1">
  <div class="title">{titles[kind]}</div>

  {#if kind === 'description'}
    <textarea rows="4" bind:value={desc} aria-label="Descrizione"></textarea>
    <div class="hint">Ctrl ↵ per salvare</div>
  {:else if kind === 'priority'}
    {#each [...PRIORITIES, [null, 'Nessuna', '']] as [value, label, arrow] (label)}
      <button class="opt" class:on={(item.priority ?? null) === value} onclick={() => pick(value)}>
        <span class="arrow" aria-hidden="true">{arrow}</span><span class="grow">{label}</span>
        {#if (item.priority ?? null) === value}<Icon name="check" size={13} style="stroke-width:2.5" />{/if}
      </button>
    {/each}
  {:else if kind === 'due'}
    {#each dueOpts as [label, value] (label)}
      <button class="opt" class:on={item.due === value} onclick={() => pick(value)}>
        <span class="grow">{label}</span><span class="mono meta">{value ? value.slice(8) + '/' + value.slice(5, 7) : ''}</span>
        {#if item.due === value}<Icon name="check" size={13} style="stroke-width:2.5" />{/if}
      </button>
    {/each}
    <label class="date">Altra data<input type="date" value={item.due ?? ''} onchange={(e) => e.target.value && pick(e.target.value)} /></label>
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
    {/if}
  {/if}
</div>

<style>
  .pop { position: fixed; z-index: 40; width: 250px; max-height: 320px; overflow-y: auto; padding: 8px; border-radius: 10px; background: var(--hover); border: 1px solid var(--border3); box-shadow: 0 18px 40px rgba(0, 0, 0, 0.5); }
  .title { padding: 0 4px 6px; font-size: 12px; color: var(--muted); }
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
  .link { display: block; width: 100%; min-height: 30px; margin-top: 6px; padding: 0 8px; border: 0; border-top: 1px solid var(--border3); background: transparent; color: var(--text2); font-size: 12.5px; text-align: left; }
</style>
