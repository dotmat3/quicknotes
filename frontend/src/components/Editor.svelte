<script>
  import { onMount } from 'svelte';
  import { createEditor, focusEnd } from '../editor/setup.js';
  import { app } from '../state.svelte.js';

  const MESSAGES = {
    action: ['Azione aggiunta', 'check-square'],
    done: ['Azione completata', 'check'],
    decision: ['Decisione segnata', 'flag'],
    undecision: ['Decisione rimossa', 'flag'],
    time: ['Ora inserita', 'clock'],
  };

  let { doc } = $props();
  let host;
  let view = $state(null);

  onMount(() => {
    view = createEditor(host, {
      doc,
      onChange: (text) => app.setBody(text),
      onCommand: (kind) => app.showToast(...MESSAGES[kind]),
      getSuggestions: () => app.suggestions,
    });
    app.editorView = view;
    return () => {
      if (app.editorView === view) app.editorView = null;
      view.destroy();
    };
  });

  // richiesta di fuoco consumata qui, cosi' un editor ricreato dopo non la riprende
  $effect(() => {
    if (view && app.focus?.target === 'editor') {
      app.focus = null;
      focusEnd(view);
    }
  });

  export function focus() {
    view && focusEnd(view);
  }
</script>

<div class="editor" bind:this={host}></div>

<style>
  .editor { min-height: 100%; }
</style>
