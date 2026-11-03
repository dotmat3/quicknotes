<script>
  import { call } from '../api.js';
  import NoteLinks from './NoteLinks.svelte';

  let { name } = $props();
  let p = $state(null);
  let error = $state('');

  $effect(() => {
    call('person_page', { name }).then((r) => (p = r), (e) => (error = String(e)));
  });

  const initials = (n) => n.split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join('').toUpperCase() || '?';
</script>

{#if error}
  <p>{error}</p>
{:else if p}
  <div class="head">
    <span class="avatar" aria-hidden="true">{initials(p.name)}</span>
    <h1>@{p.name}</h1>
  </div>
  <div class="stats">
    <div class="stat"><div class="v">{p.notes_count}</div><div class="l">{p.notes_count === 1 ? 'nota' : 'note'}</div></div>
    <div class="stat"><div class="v">{p.actions.length}</div><div class="l">{p.actions.length === 1 ? 'azione aperta' : 'azioni aperte'}</div></div>
    <div class="stat"><div class="v">{p.decisions.length}</div><div class="l">{p.decisions.length === 1 ? 'decisione' : 'decisioni'}</div></div>
  </div>
  <NoteLinks actions={p.actions} notes={p.notes} decisions={p.decisions} notesCount={p.notes_count} />
{/if}

<style>
  .head { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
  .avatar { width: 56px; height: 56px; flex: none; border-radius: 50%; background: color-mix(in srgb, var(--person) 18%, transparent); color: var(--person); font-size: 19px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
  h1 { font-size: 28px !important; }
  .stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .stat { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border2); }
  .v { font-size: 20px; font-weight: 600; }
  .l { font-size: 12px; color: var(--subtle); }
</style>
