<script>
  import { app } from '../state/app.svelte.js';
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
  const widthClass = $derived(kind === 'settings' ? 'settings' : kind === 'view' ? WIDTH[app.viewW] : WIDTH[app.noteW]);
</script>

<div class="top">
  <span class="crumb mono">{crumb}</span>
  {#if kind !== 'settings'}
    <button class="icon-btn" aria-label={fav ? 'Togli dai preferiti' : 'Aggiungi ai preferiti'} aria-pressed={fav} title={fav ? 'Togli dai preferiti' : 'Aggiungi ai preferiti'} style="color:{fav ? 'var(--accent)' : 'var(--subtle)'}" onclick={toggleFav}>
      <Icon name="star" style={fav ? 'fill:currentColor' : ''} />
    </button>
  {/if}
  <button class="icon-btn" aria-label="Altre opzioni" disabled={kind !== 'note'}><Icon name="more" /></button>
</div>

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
  .crumb { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: var(--subtle); }
</style>
