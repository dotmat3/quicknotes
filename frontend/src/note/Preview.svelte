<script>
  // Anteprima della nota: si ridisegna poco dopo l'ultima modifica, senza rallentare la scrittura.
  import { onDestroy } from 'svelte';
  import { previewClick, renderMarkdown } from './preview.js';
  import { tagColor } from '../state/app.svelte.js';

  let { text, notePath = '', onOpen } = $props();

  let host = $state();
  let timer = null;
  let drawn = false;

  function draw(t) {
    host.replaceChildren(...renderMarkdown(t, tagColor, notePath).childNodes);
    drawn = true;
  }

  $effect(() => {
    const t = text;
    if (!host) return;
    clearTimeout(timer);
    if (!drawn) draw(t);
    else timer = setTimeout(() => draw(t), 120);
  });

  onDestroy(() => clearTimeout(timer));
</script>

<!-- I clic arrivano dai link dentro l'anteprima, che sono già raggiungibili con la tastiera. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<div class="pv preview" role="document" aria-label="Anteprima della nota" bind:this={host} onclick={(e) => previewClick(e, host, onOpen)}></div>

<style>
  .preview { padding-bottom: 40vh; }
</style>
