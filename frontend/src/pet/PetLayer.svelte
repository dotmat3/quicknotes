<script>
  // Micio fuori dalla stanza: cammina o gioca in fondo alla finestra, sopra le schede. Il livello lascia passare i
  // clic, tranne sul gatto. Quando la vista Micio è aperta il gatto è nella stanza e qui non compare.
  import { onMount, untrack } from 'svelte';
  import { app } from '../state/app.svelte.js';
  import { brain } from './brain.svelte.js';
  import { PER_ACTION, coins, onEarned, pet, petCheck } from './store.svelte.js';
  import Cat from './Cat.svelte';

  $effect(() => {
    const ctx = pet.roomOpen ? 'room' : pet.out === 'off' ? 'off' : 'app';
    untrack(() => {
      if (brain.context !== 'game') brain.enter(ctx);
    });
  });

  onMount(() => {
    petCheck();
    return onEarned((n) => brain.cheer('festeggia', `Azione fatta! +${n * PER_ACTION} crocchette`));
  });

  function poke() {
    const msg = brain.context === 'room' ? `Miao! Hai ${coins()} crocchette.` : `Miao! Oggi ${app.counts.todayDone} di ${app.counts.todayTotal}.`;
    brain.cheer('ti saluta', msg);
  }
</script>

{#if brain.context === 'app'}
  <div class="layer" role="region" aria-label="Micio">
    <Cat onpoke={poke} />
  </div>
{/if}

<style>
  .layer { position: fixed; left: 0; right: 0; bottom: env(safe-area-inset-bottom, 0px); height: 0; z-index: 45; pointer-events: none; }
</style>
