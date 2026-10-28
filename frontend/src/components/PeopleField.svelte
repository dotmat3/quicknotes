<script>
  import { person } from '../people.js';
  import Icon from './Icon.svelte';

  // Partecipanti come chip: Invio o virgola aggiunge, Backspace su campo vuoto toglie l'ultimo.
  let { people, suggestions = [], onchange } = $props();
  let text = $state('');
  let input;

  const matches = $derived.by(() => {
    const q = text.trim().toLowerCase();
    if (!q) return [];
    const taken = new Set(people.map((p) => p.name.toLowerCase()));
    return suggestions.filter((s) => s.toLowerCase().includes(q) && !taken.has(s.toLowerCase())).slice(0, 6);
  });
  let active = $state(0);

  function add(name) {
    name = name.trim().replace(/^@/, '').replace(/,$/, '').trim();
    text = '';
    active = 0;
    if (!name || people.some((p) => p.name.toLowerCase() === name.toLowerCase())) return;
    onchange([...people, person(name)]);
  }

  function remove(i) {
    onchange(people.filter((_, j) => j !== i));
    input?.focus();
  }

  function onkeydown(e) {
    if (e.key === 'ArrowDown' && matches.length) {
      active = (active + 1) % matches.length;
      e.preventDefault();
    } else if (e.key === 'ArrowUp' && matches.length) {
      active = (active - 1 + matches.length) % matches.length;
      e.preventDefault();
    } else if ((e.key === 'Enter' || e.key === 'Tab') && matches.length) {
      add(matches[active]);
      e.preventDefault();
    } else if (e.key === 'Enter' || e.key === ',') {
      if (text.trim()) e.preventDefault();
      add(text);
    } else if (e.key === 'Backspace' && !text && people.length) {
      remove(people.length - 1);
    } else if (e.key === 'Escape') {
      text = '';
    }
  }
</script>

<div class="field">
  {#each people as p, i (p.name)}
    <span class="chip">
      <span class="avatar" style:background={p.color}>{p.initials}</span>
      <span class="name">{p.name}</span>
      <button class="remove" title="Togli {p.name}" onclick={() => remove(i)}><Icon name="x" size={12} stroke={2.2} /></button>
    </span>
  {/each}
  <div class="entry">
    <input bind:this={input} bind:value={text} {onkeydown} onblur={() => add(text)}
           placeholder={people.length ? 'Aggiungi' : 'Aggiungi partecipanti'} spellcheck="false" />
    {#if matches.length}
      <ul class="menu">
        {#each matches as m, i (m)}
          <li class:active={i === active}>
            <button onmousedown={(e) => { e.preventDefault(); add(m); }}>{m}</button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</div>

<style>
  .field { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-height: 30px; }
  .chip {
    display: inline-flex; align-items: center; gap: 6px; height: 26px; padding: 0 4px 0 3px;
    border-radius: 999px; background: var(--hover); font-size: 13.5px;
  }
  .avatar {
    width: 20px; height: 20px; border-radius: 50%; color: #fff; font-size: 10px; font-weight: 700;
    display: grid; place-items: center; letter-spacing: 0.02em;
  }
  .remove {
    width: 18px; height: 18px; border-radius: 50%; display: grid; place-items: center; color: var(--faint);
    opacity: 0; transition: opacity var(--fast) var(--ease), background var(--fast) var(--ease);
  }
  .chip:hover .remove { opacity: 1; }
  .remove:hover { background: var(--selected); color: var(--text); }
  .entry { position: relative; flex: 1; min-width: 120px; }
  input { width: 100%; border: 0; background: none; padding: 4px 2px; font-size: 14px; }
  input::placeholder { color: var(--faint); }
  .menu {
    position: absolute; z-index: 10; top: calc(100% + 4px); left: 0; min-width: 200px; margin: 0; padding: 4px;
    list-style: none; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow);
  }
  .menu button { width: 100%; text-align: left; padding: 6px 10px; border-radius: 5px; }
  .menu li.active button, .menu button:hover { background: var(--accent-soft); }
</style>
