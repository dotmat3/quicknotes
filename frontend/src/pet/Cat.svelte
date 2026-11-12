<script>
  // Micio: una sola immagine (il foglio già colorato) animata dalle classi di animazioni.js. 1em = un pixel dello
  // sprite, così la dimensione si cambia con font-size. Lo spostamento usa transform, che non ricalcola la pagina:
  // la pista è larga quanto il contenitore e la sua traslazione in % equivale alla posizione del gatto.
  import { onMount } from 'svelte';
  import { HEAD, injectCss } from './animazioni.js';
  import { brain } from './brain.svelte.js';
  import { eyeFor, pet, petName } from './store.svelte.js';
  import { sheetFor } from './tinta.js';

  let { bottom = '0px', onpoke } = $props();
  let track = $state();
  let sheet = $state('');

  injectCss();
  onMount(() => {
    brain.mover = track;
    return () => {
      if (brain.mover === track) brain.mover = null;
    };
  });

  $effect(() => {
    const coat = pet.coat;
    let alive = true;
    sheetFor(coat, eyeFor(coat)).then((url) => alive && (sheet = url));
    return () => (alive = false);
  });

  const a = $derived(brain.animClass);
  const edge = $derived(brain.x < 14 ? 'left' : brain.x > 86 ? 'right' : 'mid');
</script>

<div
  class="track"
  bind:this={track}
  style="bottom:calc({bottom} - {2 * pet.scale}px); transform:translateX({brain.x}%); transition:transform {brain.dur}ms {brain.ease}"
>
  <div class="cat" style="font-size:{pet.scale}px">
    {#if brain.bubble}
      <div class="bubble {edge}" role="status" style="bottom:{30 * pet.scale}px; --head:{HEAD * pet.scale}px">{brain.bubble}</div>
    {/if}
    {#if brain.hearts}
      <svg class="heart px" viewBox="0 0 7 6" aria-hidden="true" style="left:10em; bottom:24em; width:7em; height:6em"><path d="M1 0h2v1H1zM4 0h2v1H4zM0 1h7v2H0zM1 3h5v1H1zM2 4h3v1H2zM3 5h1v1H3z" fill="#F0956E" /></svg>
      <svg class="heart px" viewBox="0 0 7 6" aria-hidden="true" style="left:19em; bottom:20em; width:5em; height:4.3em; animation-delay:.45s"><path d="M1 0h2v1H1zM4 0h2v1H4zM0 1h7v2H0zM1 3h5v1H1zM2 4h3v1H2zM3 5h1v1H3z" fill="#E58F9E" /></svg>
    {/if}
    {#if brain.anim === 'sleep'}
      <svg class="z px" viewBox="0 0 4 4" aria-hidden="true" style="left:{brain.dir > 0 ? 24 : 6}em; bottom:12em; width:4em; height:4em"><path d="M0 0h4v1H0zM2 1h1v1H2zM1 2h1v1H1zM0 3h4v1H0z" fill="#8DB4F0" /></svg>
    {/if}
    <button class="cat-btn" type="button" aria-label="{petName()} {brain.act}. Clicca per salutarlo" onclick={onpoke}>
      <span class="shadow" aria-hidden="true"></span>
      <span class="arc {brain.arc}">
        <span class="flip" style="transform:scaleX({brain.dir}); transform-origin:{HEAD}em 50%">
          {#if sheet}<span class="sprite qn-a-{a}" style="background-image:url({sheet})"></span>{/if}
        </span>
      </span>
    </button>
  </div>
</div>

<style>
  .track { position: absolute; left: 0; width: 100%; height: 0; pointer-events: none; will-change: transform; }
  .cat { position: absolute; left: -16em; bottom: 0; width: 32em; height: 32em; }
  .cat-btn { position: absolute; inset: 0; padding: 0; border: 0; background: transparent; pointer-events: auto; cursor: pointer; }
  .cat-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: -6em; }
  .arc, .flip, .sprite { position: absolute; inset: 0; display: block; }
  .flip { transition: transform 0.12s steps(2); }
  .sprite { background-size: 1200% 900%; background-repeat: no-repeat; image-rendering: pixelated; }
  .shadow { position: absolute; left: 10em; bottom: 1em; width: 14em; height: 1.5em; background: rgba(0, 0, 0, 0.28); }
  .px { image-rendering: pixelated; shape-rendering: crispEdges; display: block; position: absolute; }
  .heart { animation: float 1.4s steps(8) infinite; }
  .z { animation: float 2.6s steps(10) infinite; }
  @keyframes float { 0% { opacity: 0; transform: translateY(1em); } 20% { opacity: 1; } 100% { opacity: 0; transform: translateY(-10em); } }
  /* La nuvoletta ha un suo font-size, quindi qui 1em non è più un pixel dello sprite: altezza e testa arrivano in px. */
  .bubble { position: absolute; width: max-content; max-width: 260px; padding: 7px 11px; background: #ECEAE4; color: #141518; font-size: 12.5px; line-height: 1.4; font-weight: 500; border: 2px solid #141518; box-shadow: 3px 3px 0 #141518; animation: pop 0.18s steps(3); }
  .bubble.mid { left: var(--head); translate: -50% 0; }
  .bubble.left { left: 0; }
  .bubble.right { right: 0; }
  @keyframes pop { from { transform: scale(0.6); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  @media (prefers-reduced-motion: reduce) {
    .track { transition: none !important; }
    .heart, .z, .bubble { animation: none; }
  }
</style>
