<script>
  import { onDestroy, onMount } from 'svelte';
  import { call } from '../api.js';
  import { app, showToast, tagColor } from '../state/app.svelte.js';
  import { closeTabs, focused, openPage } from '../state/layout.svelte.js';
  import { MODES, docs, loadDoc, modes, save, savedStates, setApplyToViews, setMode, setText, views } from '../state/documents.svelte.js';
  import { noteStats } from './editor/rules.js';
  import Icon from '../shell/Icon.svelte';

  let { id, page, groupId } = $props();

  const viewKey = $derived(`${groupId}:${page}`);
  let host = $state();
  let error = $state('');
  let editorReady = $state(false);
  let view = null;
  let editorMod = null;

  const mode = $derived(modes[viewKey] ?? 'live');

  const doc = $derived(docs[id]);
  const note = $derived(doc?.note);
  const stats = $derived(doc ? noteStats(doc.text) : { done: 0, total: 0, people: [] });
  const people = $derived.by(() => {
    const seen = new Map();
    for (const p of [...(note?.people ?? []), ...stats.people]) if (!seen.has(p.toLowerCase())) seen.set(p.toLowerCase(), p);
    return [...seen.values()];
  });

  async function suggest(kind, query) {
    if (kind === 'person') return (await call('top_people', { limit: 50 }, [])).map((p) => p.name);
    if (kind === 'tag') return call('all_tags', {}, []);
    return call('search_titles', { query, limit: 12 }, []);
  }

  async function onOpen(kind, target) {
    if (kind === 'person') return openPage(`person:${target}`);
    if (kind === 'tag') return openPage(`tag:${target.toLowerCase()}`);
    if (kind === 'url') {
      if (/^https?:\/\//i.test(target)) return call('open_url', { url: target });
      return showToast(`Per ora si aprono solo i link web: ${target}`);
    }
    const found = await call('resolve_link', { target });
    if (found) openPage(`note:${found.id}`, found.title);
    else showToast(`Nota non trovata: ${target}`);
  }

  async function mountEditor() {
    const editor = await import('./editor/setup.js');
    if (destroyed) return;
    editorMod = editor;
    // Lo stato conservato sopravvive a questo componente: i suoi callback non devono dipendere dalla vista corrente.
    const noteId = id;
    const myKey = viewKey;
    const myPage = page;
    const onChange = (text, update) => {
      setText(noteId, text);
      if (update) {
        // La stessa nota in un altro gruppo riceve solo la modifica, senza entrare nella sua cronologia.
        for (const [key, other] of views) if (key !== myKey && key.endsWith(`:${myPage}`)) editor.applyPeer(other, update);
      }
    };
    const stored = savedStates.get(viewKey);
    const state = stored && editor.stateText(stored) === docs[id].text ? stored : editor.createState(docs[id].text, { onChange, onOpen, tagColor, suggest });
    view = editor.createView(host, state);
    editor.setMode(view, mode, tagColor);
    views.set(viewKey, view);
    editorReady = true;
    setApplyToViews((noteId, text) => {
      for (const [key, v] of views) if (key.endsWith(`:note:${noteId}`)) editor.applyText(v, text);
    });
    if (focused().id === groupId && mode !== 'preview') view.focus();
  }

  // Il focus passa all'editor solo quando la modalità cambia, non al montaggio.
  let lastMode = null;
  $effect(() => {
    const m = mode;
    if (!editorReady) return;
    editorMod.setMode(view, m, tagColor);
    if (lastMode && lastMode !== m && m !== 'preview') view.focus();
    lastMode = m;
  });

  let destroyed = false;
  onMount(async () => {
    try {
      const d = await loadDoc(id);
      app.titles[page] = d.note.tab_title;
      (app.paths ??= {})[page] = d.note.path;
      await mountEditor();
    } catch (e) {
      error = String(e);
    }
  });

  onDestroy(() => {
    destroyed = true;
    if (view) {
      savedStates.set(viewKey, view.state);
      views.delete(viewKey);
      view.destroy();
    }
    save(id);
  });

  async function goDay(delta) {
    const n = await call('daily_note', { date: note.date.slice(0, 10), delta });
    openPage(`note:${n.id}`, n.title);
  }

  export function focusEditor() {
    if (mode !== 'preview') view?.focus();
  }
</script>

{#if error}
  <h1>Nota non disponibile</h1>
  <p class="err">{error}</p>
  <button class="btn" onclick={() => closeTabs(groupId, [page])}>Chiudi la scheda</button>
{:else if note}
  {#if note.is_daily}
    <div class="kicker">
      <button class="day" aria-label="Giorno precedente" onclick={() => goDay(-1)}><Icon name="left" size={14} /></button>
      <span>Nota del giorno</span>
      <button class="day" aria-label="Giorno successivo" onclick={() => goDay(1)}><Icon name="right" size={14} /></button>
    </div>
  {/if}
  <h1 class:big={note.is_daily}>{note.title}</h1>
  <div class="pills">
    {#if !note.is_daily}<span class="pill static">{note.date_label}</span>{/if}
    {#if note.links_in.length}<button class="pill">{note.links_in.length} {note.links_in.length === 1 ? 'collegamento' : 'collegamenti'}</button>{/if}
    {#if stats.total}<span class="pill static">{stats.done} di {stats.total} azioni</span>{/if}
    {#each people as p (p.toLowerCase())}<button class="pill person" onclick={() => openPage(`person:${p}`)}>@{p}</button>{/each}
  </div>
  <div class="body" class:split={mode === 'split'}>
    <div class="host" class:gone={mode === 'preview'} bind:this={host}>
      {#if !editorReady}<div class="plain">{doc.text}</div>{/if}
    </div>
    {#if mode === 'split' || mode === 'preview'}
      {#await import('./Preview.svelte') then { default: Preview }}
        <div class="side"><Preview text={doc.text} {onOpen} /></div>
      {/await}
    {/if}
  </div>
  {#if mode !== 'live'}
    <div class="modebar" role="group" aria-label="Modalità della nota">
      {#each MODES as [m, label] (m)}
        <button class:on={mode === m} aria-pressed={mode === m} onclick={() => setMode(viewKey, m)}>{label}</button>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .kicker { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; font-size: 13px; color: var(--subtle); }
  .day { width: 28px; height: 28px; padding: 0; border: 0; border-radius: 6px; background: transparent; color: var(--subtle); display: flex; align-items: center; justify-content: center; }
  .day:hover { background: var(--hover); }
  h1.big { font-size: 32px; line-height: 1.15; }
  .pills { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 12px 0 22px; min-height: 26px; }
  .pill.static { display: inline-flex; align-items: center; }
  .person { color: var(--person); }
  .plain { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text2); }
  .err { margin: 12px 0; color: var(--late); }
  .body.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 32px; }
  .body.split .side { padding-left: 32px; border-left: 1px solid var(--border2); }
  .gone { display: none; }
  .modebar { position: sticky; bottom: 12px; z-index: 6; display: flex; width: max-content; margin: 0 auto; padding: 3px; gap: 2px; border-radius: 9px; background: var(--chrome); border: 1px solid var(--border3); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3); }
  .modebar button { height: 26px; padding: 0 12px; border: 0; border-radius: 6px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .modebar button:hover { background: var(--hover); }
  .modebar button.on { background: var(--hover); color: var(--text); font-weight: 500; }
</style>
