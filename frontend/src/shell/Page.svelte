<script>
  import { app } from '../state/app.svelte.js';
  import { MODES, modes, setMode } from '../state/documents.svelte.js';
  import { pageKind, pageArg, pageTitle } from './nav.js';
  import NotePage from '../note/NotePage.svelte';
  import Icon from './Icon.svelte';

  let { page, fav, toggleFav, groupId } = $props();

  // Ogni vista è un blocco a sé: la prima schermata non le carica.
  const LOADERS = {
    'view:actions': () => import('../views/ActionsView.svelte'),
    'view:calendar': () => import('../views/CalendarView.svelte'),
    'view:people': () => import('../views/PeopleView.svelte'),
    'view:graph': () => import('../views/GraphView.svelte'),
    settings: () => import('../views/SettingsView.svelte'),
  };

  const kind = $derived(pageKind(page));
  const crumb = $derived(kind === 'note' ? (app.paths?.[page] ?? '') : kind === 'settings' ? 'Impostazioni' : kind === 'person' ? `Persona · ${pageArg(page)}` : kind === 'tag' ? `Etichetta · #${pageArg(page)}` : `Vista · ${pageTitle(page, app.titles)}`);
  const WIDTH = { leggibile: 'narrow', ampia: 'wide', intera: '' };
  const viewKey = $derived(`${groupId}:${page}`);
  const mode = $derived(modes[viewKey] ?? 'live');
  const widthClass = $derived(kind === 'settings' ? 'settings' : kind === 'view' ? WIDTH[app.viewW] : mode === 'split' ? '' : WIDTH[app.noteW]);

  let menu = $state(false);
  let menuBtn = $state();

  function closeMenu() {
    menu = false;
    menuBtn?.focus();
  }

  function menuKey(e) {
    if (e.key === 'Escape') return closeMenu();
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const items = [...e.currentTarget.querySelectorAll('[role^="menuitem"]')];
    const i = items.indexOf(document.activeElement);
    items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
  }

  function pick(m) {
    menu = false;
    setMode(viewKey, m);
  }
</script>

<div class="top">
  <span class="crumb mono">{crumb}</span>
  {#if kind !== 'settings'}
    <button class="icon-btn" aria-label={fav ? 'Togli dai preferiti' : 'Aggiungi ai preferiti'} aria-pressed={fav} title={fav ? 'Togli dai preferiti' : 'Aggiungi ai preferiti'} style="color:{fav ? 'var(--accent)' : 'var(--subtle)'}" onclick={toggleFav}>
      <Icon name="star" style={fav ? 'fill:currentColor' : ''} />
    </button>
  {/if}
  <div class="more">
    <button class="icon-btn" bind:this={menuBtn} aria-label="Altre opzioni" aria-haspopup="menu" aria-expanded={menu} disabled={kind !== 'note'} onclick={() => (menu = !menu)}><Icon name="more" /></button>
    {#if menu}
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <div class="menu note-menu" role="menu" aria-label="Opzioni della nota" tabindex="-1" onkeydown={menuKey}>
        {#each MODES as [m, label] (m)}
          <button class="menu-item" role="menuitemradio" aria-checked={mode === m} onclick={() => pick(m)} {@attach (el) => { if (mode === m) el.focus(); }}>
            <span class="check">{#if mode === m}<Icon name="check" size={14} />{/if}</span>
            <span style="flex:1">{label}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>

{#if menu}
  <button class="backdrop" aria-label="Chiudi il menu" tabindex="-1" onclick={() => (menu = false)}></button>
{/if}

<article class="page {widthClass}">
  {#key page}
    {#if kind === 'note'}
      <NotePage id={pageArg(page)} {page} {groupId} />
    {:else if kind === 'person'}
      {#await import('../views/PersonView.svelte') then { default: PersonView }}
        <PersonView name={pageArg(page)} />
      {/await}
    {:else if kind === 'tag'}
      {#await import('../views/TagView.svelte') then { default: TagView }}
        <TagView tag={pageArg(page)} />
      {/await}
    {:else}
      {#await LOADERS[page]() then { default: View }}
        <View />
      {/await}
    {/if}
  {/key}
</article>

<style>
  .top { display: flex; align-items: center; gap: 8px; padding: 10px 18px 0; }
  .more { position: relative; }
  .note-menu { top: 34px; right: 0; width: 220px; z-index: 41; }
  .check { width: 14px; display: inline-flex; color: var(--accent); }
  .crumb { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: var(--subtle); }
</style>
