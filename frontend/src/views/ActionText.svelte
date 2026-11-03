<script>
  import { tagColor } from '../state/app.svelte.js';
  import { openPage } from '../state/layout.svelte.js';
  import { MENTION, TAG } from '../note/editor/rules.js';

  let { text, done = false } = $props();

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
      <button class="link" style="color:{done ? 'inherit' : 'var(--person)'}" title="Apri @{p.arg}" onclick={() => openPage(`person:${p.arg}`)}>{p.raw}</button>
    {:else if p.kind === 'tag'}
      <button class="link" style="color:{done ? 'inherit' : tagColor(p.arg)}" title="Apri {p.raw}" onclick={() => openPage(`tag:${p.arg.toLowerCase()}`)}>{p.raw}</button>
    {:else}{p.raw}{/if}
  {/each}
</span>

<style>
  .done { color: var(--subtle); text-decoration: line-through; }
  .link { display: inline; padding: 0; border: 0; background: transparent; font: inherit; text-decoration: inherit; }
</style>
