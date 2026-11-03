<script>
  import { onDestroy } from 'svelte';
  import { call, listen } from '../api.js';
  import { openPage } from '../state/layout.svelte.js';

  let people = $state(null);
  const load = async () => (people = await call('people_list', {}, []));
  load();
  const off = listen('index-updated', load);
  onDestroy(() => off.then((f) => f()));

  const initials = (n) => n.split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join('').toUpperCase() || '?';
  function sub(p) {
    const parts = [p.last_seen?.slice(0, 10) ?? ''];
    if (p.late) parts.push(`${p.late} in ritardo`);
    else parts.push(p.open ? `${p.open} ${p.open === 1 ? 'azione aperta' : 'azioni aperte'}` : 'nessuna azione');
    return parts.filter(Boolean).join(' · ');
  }
</script>

<h1>Persone</h1>
{#if people}
  <div class="list">
    {#each people as p (p.name)}
      <button class="row" onclick={() => openPage(`person:${p.name}`)}>
        <span class="avatar" aria-hidden="true">{initials(p.name)}</span>
        <span class="grow"><span class="name">@{p.name}</span><span class="sub" class:late={p.late}>{sub(p)}</span></span>
        <span class="mono n">{p.notes} note</span>
      </button>
    {:else}
      <p class="none">Le persone citate con @nome compaiono qui.</p>
    {/each}
  </div>
{/if}

<style>
  .list { margin-top: 20px; }
  .row { display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px 0; border: 0; border-bottom: 1px solid var(--line); background: transparent; color: var(--text); text-align: left; }
  .avatar { width: 32px; height: 32px; flex: none; border-radius: 50%; background: color-mix(in srgb, var(--person) 16%, transparent); color: var(--person); font-size: 11px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
  .grow { flex: 1; min-width: 0; }
  .name { display: block; font-size: 14.5px; }
  .sub { display: block; font-size: 12.5px; color: var(--subtle); }
  .sub.late { color: var(--late); }
  .n { font-size: 12px; color: var(--subtle); }
  .none { color: var(--subtle); }
</style>
