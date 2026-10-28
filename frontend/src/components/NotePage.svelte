<script>
  import { cubicOut } from 'svelte/easing';
  import { app } from '../state.svelte.js';
  import Editor from './Editor.svelte';
  import Icon from './Icon.svelte';
  import NoteMenu from './NoteMenu.svelte';
  import PeopleField from './PeopleField.svelte';
  import RecordControl from './RecordControl.svelte';

  let { note } = $props();
  let scroller;
  let sheet = $state();
  let title = $state();
  let editor = $state();

  const SAVE_LABELS = { pending: 'Modificata', saving: 'Salvataggio…', saved: 'Salvata' };

  // cambio di nota: il contenuto entra con una breve dissolvenza (niente animazione in uscita)
  function enter() {
    return { duration: app.animations ? 160 : 0, easing: cubicOut,
             css: (t) => `opacity: ${t}; transform: translateY(${(1 - t) * 6}px)` };
  }

  $effect(() => {
    if (title && app.focus?.target === 'title') {
      app.focus = null;
      title.focus();
    }
  });

  function titleKeydown(e) {
    if (e.key === 'Enter' || (e.key === 'ArrowDown' && title.selectionStart === title.value.length)) {
      e.preventDefault();
      editor?.focus();
    }
  }

  // clic nello spazio vuoto sotto il testo: si scrive in fondo alla nota
  function backgroundDown(e) {
    if (e.target === scroller || e.target === sheet) {
      e.preventDefault();
      editor?.focus();
    }
  }
</script>

<section class="page">
  <header class="topbar">
    <div class="crumb">
      <Icon name={note.icon} size={15} />
      <span>{note.typeLabel}</span>
      {#if note.project}<span class="sep">/</span><span class="project">#{note.project}</span>{/if}
    </div>
    <div class="tools">
      <div class="save" class:visible={app.saveState !== 'idle'} data-state={app.saveState}>
        <span class="dot"></span>{SAVE_LABELS[app.saveState] ?? ''}
      </div>
      <RecordControl />
      <NoteMenu />
    </div>
  </header>

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="scroll" bind:this={scroller} onmousedown={backgroundDown}>
    {#key note.key}
      <article class="sheet" bind:this={sheet} in:enter>
        <textarea class="note-title" rows="1" bind:this={title} value={note.title} spellcheck="false"
                  placeholder={note.type === 'meeting' ? 'Titolo del meeting' : 'Senza titolo'}
                  oninput={(e) => app.edit('title', e.currentTarget.value.replace(/\n/g, ' '))}
                  onkeydown={titleKeydown}></textarea>

        {#if note.type !== 'daily'}
          <div class="props">
            <div class="label"><Icon name="calendar" size={15} />Data</div>
            <div class="value">{note.dateLabel}</div>
            <div class="label"><Icon name="users" size={15} />Partecipanti</div>
            <PeopleField people={note.people} suggestions={app.suggestions.people}
                         onchange={(people) => app.edit('people', people)} />
            <div class="label"><Icon name="hash" size={15} />Progetto</div>
            <div class="project-field">
              <span class="hash" class:empty={!note.project}>#</span>
              <input value={note.project} placeholder="Aggiungi progetto" spellcheck="false"
                     oninput={(e) => app.edit('project', e.currentTarget.value.replace(/^#/, '').replace(/\s/g, '-'))} />
            </div>
          </div>
        {/if}
        <div class="rule"></div>

        <div class="body">
          {#key note.rev}
            <Editor doc={note.body} bind:this={editor} />
          {/key}
          {#if app.empty}
            <div class="hints" aria-hidden="true">
              <div><span>@persona</span><span>#progetto</span><span>- [ ] azione due:AAAA-MM-GG</span><span>!decisione</span></div>
              <div><span><kbd>Ctrl+T</kbd> azione</span><span><kbd>Ctrl+D</kbd> decisione</span><span><kbd>Ctrl+Shift+H</kbd> ora</span></div>
            </div>
          {/if}
        </div>
      </article>
    {/key}
  </div>
</section>

<style>
  .page { display: flex; flex-direction: column; min-width: 0; height: 100%; background: var(--bg); }
  .topbar { flex: none; height: 52px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 12px 0 24px; }
  .tools { display: flex; align-items: center; gap: 4px; }
  .crumb { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 13.5px; min-width: 0; }
  .crumb .sep { color: var(--faint); }
  .crumb .project { color: var(--tag); }
  .save { display: flex; align-items: center; gap: 7px; margin-right: 8px; font-size: 12.5px; color: var(--faint); opacity: 0;
          transition: opacity var(--normal) var(--ease); }
  .save.visible { opacity: 1; }
  .save .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--faint); transition: background var(--normal) var(--ease); }
  .save[data-state='saved'] .dot { background: var(--success); }
  .save[data-state='saving'] .dot { background: var(--warning); }

  .scroll { flex: 1; overflow-y: auto; overflow-x: hidden; scrollbar-gutter: stable; }
  .sheet { max-width: 780px; margin: 0 auto; padding: 28px 56px 0; min-height: 100%; }

  .note-title {
    display: block; width: 100%; resize: none; border: 0; background: none; padding: 0; margin: 0 0 18px;
    font: 700 32px/1.25 var(--font-display); letter-spacing: -0.015em; color: var(--text);
    field-sizing: content; overflow: hidden;
  }
  .note-title::placeholder { color: var(--faint); }

  .props { display: grid; grid-template-columns: 150px 1fr; align-items: center; row-gap: 4px; margin-bottom: 14px; font-size: 14px; }
  .label { display: flex; align-items: center; gap: 9px; color: var(--muted); height: 32px; }
  .label :global(.icon) { color: var(--faint); }
  .value { padding: 0 2px; }
  .project-field { display: flex; align-items: center; }
  .project-field input { flex: 1; border: 0; background: none; padding: 4px 0; color: var(--tag); font-size: 14px; }
  .project-field input::placeholder { color: var(--faint); }
  .hash { color: var(--tag); padding-left: 2px; }
  .hash.empty { color: var(--faint); }

  .rule { height: 1px; background: var(--border); margin: 6px 0 20px; }

  .body { position: relative; }
  .hints { position: absolute; top: 46px; left: 0; right: 0; display: grid; gap: 10px; color: var(--faint); font-size: 13.5px; pointer-events: none; }
  .hints div { display: flex; flex-wrap: wrap; gap: 6px 20px; }
  kbd { font: 12px var(--font); padding: 1px 6px; border: 1px solid var(--border-strong); border-bottom-width: 2px; border-radius: 4px; color: var(--muted); }
</style>
