<script>
  // La finestra ha la cornice di Windows: qui resta solo il titolo, che segue la scheda attiva.
  import { call } from '../api.js';
  import { app } from '../state/app.svelte.js';
  import { focused } from '../state/layout.svelte.js';
  import { pageTitle } from './nav.js';

  const title = $derived.by(() => {
    const page = focused()?.active;
    return page ? `${pageTitle(page, app.titles)} — QuickNotes` : 'QuickNotes';
  });

  $effect(() => {
    document.title = title;
    call('set_title', { title });
  });
</script>
