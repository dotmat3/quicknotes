<script>
  import { tagColor } from '../state/app.svelte.js';
  import { openPage } from '../state/layout.svelte.js';
  import { MENTION, TAG } from '../note/editor/rules.js';

  // `pick(kind, arg, event)`: dentro una riga d'azione il clic su @persona o #etichetta apre il pannello per
  // cambiarla (che porta anche alla pagina); senza, il clic apre direttamente la pagina.
  let { text, done = false, pick = null } = $props();

  function open(e, p) {
    if (pick && pick(p.kind, p.arg, e)) return;
    openPage(p.kind === 'person' ? `person:${p.arg}` : `tag:${p.arg.toLowerCase()}`);
  }

  // Il testo con @persone e #etichette cliccabili. Le posizioni vengono dalle stesse regole dell'editor.
  const parts = $derived.by(() => {
    const found = [
      ...[...text.matchAll(MENTION)].map((m) => ({ kind: 'person', at: m.index, raw: m[0], arg: m[1] })),
      ...[...text.matchAll(TAG)].map((m) => ({ kind: 'tag', at: m.index, raw: m[0], arg: m[1] })),
    ].sort((a, b) => a.at - b.at);
    const out = [];
    let pos = 0;
    for (const f of found) {
      if (f.at > pos) out.push({ kind: 'text', raw: text.slice(pos, f.at) });
      out.push(f);
      pos = f.at + f.raw.length;
    }
    if (pos < text.length) out.push({ kind: 'text', raw: text.slice(pos) });
    return out;
  });
</script>

<span class:done>
  {#each parts as p, i (i)}
    {#if p.kind === 'person'}
      <button class="link" style="color:{done ? 'inherit' : 'var(--person)'}" title={pick ? `Cambia o apri @${p.arg}` : `Apri @${p.arg}`} aria-label={pick ? `Persona ${p.arg}` : undefined} onclick={(e) => open(e, p)}>{p.raw}</button>
    {:else if p.kind === 'tag'}
      <button class="tag chip" style="color:{done ? 'inherit' : tagColor(p.arg)}" title={pick ? `Cambia o apri ${p.raw}` : `Apri ${p.raw}`} aria-label={pick ? `Etichetta ${p.arg}` : undefined} onclick={(e) => open(e, p)}>{p.raw}</button>
    {:else}{p.raw}{/if}
  {/each}
</span>

<style>
  .done { color: var(--subtle); text-decoration: line-through; }
  .link { display: inline; padding: 0; border: 0; background: transparent; font: inherit; text-decoration: inherit; }
  /* L'etichetta è la stessa mini pillola del progetto e delle date (.chip in app.css): stessa altezza e stessa
     linea di base, così le pillole di una riga stanno allineate. */
  .tag { background: transparent; text-decoration: inherit; }
  .tag:hover { background: color-mix(in srgb, currentColor 10%, transparent); }
</style>
