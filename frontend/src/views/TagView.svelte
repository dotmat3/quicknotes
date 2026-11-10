<script>
  import { call } from '../api.js';
  import { board } from '../state/actions.svelte.js';
  import { app, savePrefs, tagColor, theme } from '../state/app.svelte.js';
  import { openPage, replacePage } from '../state/layout.svelte.js';
  import { TAG_PALETTE, tagColorId } from '../theme/themes.js';
  import NoteLinks from './NoteLinks.svelte';
  import Icon from '../shell/Icon.svelte';

  let { tag } = $props();
  let t = $state(null);
  let picking = $state(false);

  // Si ricarica anche dopo ogni modifica dalle pillole, che ricarica la bacheca.
  $effect(() => {
    board.version;
    call('tag_page', { tag }).then((r) => {
      // Un'etichetta che è un progetto apre la vista Progetto al posto della scheda.
      if (r?.project) replacePage(`tag:${tag}`, `project:${r.project}`);
      else t = r;
    });
  });

  const current = $derived(tagColorId(tag, app.tagColors));

  function pick(id) {
    app.tagColors = { ...app.tagColors, [tag]: id };
    picking = false;
    savePrefs();
  }

  function goBoard() {
    app.actView = 'bacheca';
    app.actGroup = 'progetto';
    app.actFilter = 'aperte';
    openPage('view:actions');
  }
</script>

{#if t}
  <div class="head">
    <div class="titles">
      <div class="kicker">Etichetta</div>
      <h1 style="color:{tagColor(tag)}">#{t.tag}</h1>
      <div class="sum">{t.notes_count} note · {t.actions.length} {t.actions.length === 1 ? 'azione aperta' : 'azioni aperte'} · {t.people.length} {t.people.length === 1 ? 'persona' : 'persone'}</div>
    </div>
    <button class="btn" aria-expanded={picking} onclick={() => (picking = !picking)}><span class="swatch" style="background:{tagColor(tag)}" aria-hidden="true"></span>Colore</button>
    <button class="btn" onclick={goBoard}><Icon name="board" size={14} />Apri nella bacheca</button>
  </div>
  {#if picking}
    <div class="colors" role="radiogroup" aria-label="Colore di #{t.tag}">
      {#each Object.entries(TAG_PALETTE) as [id, [dark, light, label]] (id)}
        {@const c = theme.current.dark ? dark : light}
        <button class="color" class:on={current === id} role="radio" aria-checked={current === id} aria-label={label} title={label} style="background:{c};--c:{c}" onclick={() => pick(id)}>
          {#if current === id}<Icon name="check" size={13} style="stroke-width:3;color:{theme.current.dark ? '#141518' : '#fff'}" />{/if}
        </button>
      {/each}
    </div>
  {/if}
  <NoteLinks items={t.actions} groups={t.groups} notes={t.notes} decisions={t.decisions} notesCount={t.notes_count} />
  {#if t.people.length}
    <h2>Persone coinvolte</h2>
    <div class="people">
      {#each t.people as p (p)}<button class="person" onclick={() => openPage(`person:${p}`)}>@{p}</button>{/each}
    </div>
  {/if}
{/if}

<style>
  .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 20px; }
  .titles { flex: 1 1 260px; }
  .kicker { font-size: 12.5px; color: var(--subtle); }
  .sum { margin-top: 4px; font-size: 13.5px; color: var(--subtle); }
  .swatch { width: 12px; height: 12px; border-radius: 50%; }
  .colors { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--card); }
  .color { flex: none; width: 24px; height: 24px; padding: 0; border: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
  .color.on { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--c); }
  h2 { margin: 28px 0 10px; font-size: 16px; font-weight: 600; }
  .people { display: flex; flex-wrap: wrap; gap: 8px; }
  .person { height: 32px; padding: 0 12px; border: 1px solid var(--border2); border-radius: 999px; background: transparent; color: var(--person); font-size: 13px; }
</style>
