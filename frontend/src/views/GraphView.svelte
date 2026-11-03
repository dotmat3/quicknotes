<script>
  import { call } from '../api.js';
  import { app, tagColor } from '../state/app.svelte.js';
  import { openPage } from '../state/layout.svelte.js';

  let graph = $state(null);
  let error = $state('');

  $effect(() => {
    if (!app.today) return;
    call('graph_data', { id: app.today.id }).then((g) => (graph = g), (e) => (error = String(e)));
  });

  // Il centro al centro, gli altri in cerchio. Le percentuali seguono la dimensione del riquadro.
  const placed = $derived.by(() => {
    if (!graph) return [];
    const others = graph.nodes.length - 1;
    return graph.nodes.map((n, i) => {
      if (i === 0) return { ...n, x: 50, y: 50 };
      const a = ((i - 1) / Math.max(others, 1)) * 2 * Math.PI - Math.PI / 2;
      return { ...n, x: 50 + 38 * Math.cos(a), y: 50 + 38 * Math.sin(a) };
    });
  });

  function color(n) {
    if (n.kind === 'center') return 'var(--accent)';
    if (n.kind === 'person') return 'var(--person)';
    if (n.kind === 'tag') return tagColor(n.id);
    return 'var(--muted)';
  }
</script>

<h1>Grafo</h1>
<p class="sub">Collegamenti attorno alla nota di oggi</p>
{#if error}
  <p class="sub">{error}</p>
{:else if graph}
  <div class="canvas">
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      {#each graph.edges as [a, b], i (i)}
        <line x1={placed[a].x} y1={placed[a].y} x2={placed[b].x} y2={placed[b].y} />
      {/each}
    </svg>
    {#each placed as n (n.page)}
      <button class="node" style="left:{n.x}%;top:{n.y}%" aria-label={n.label} onclick={() => openPage(n.page)}>
        <span class="dot" class:big={n.kind === 'center'} style="background:{color(n)}" aria-hidden="true"></span>
        <span class="label">{n.label}</span>
      </button>
    {/each}
    {#if graph.nodes.length === 1}
      <p class="empty">La nota di oggi non ha ancora collegamenti. Scrivi @persone, #etichette o [[link]].</p>
    {/if}
  </div>
{/if}

<style>
  .sub { margin: 6px 0 16px; font-size: 13.5px; color: var(--subtle); }
  .canvas { position: relative; height: 480px; border-radius: 12px; border: 1px solid var(--border); background-color: var(--sunk); background-image: radial-gradient(var(--dots) 1px, transparent 1px); background-size: 20px 20px; overflow: hidden; }
  svg { position: absolute; inset: 0; width: 100%; height: 100%; }
  line { stroke: var(--border3); stroke-width: 0.3; }
  .node { position: absolute; transform: translate(-50%, -50%); padding: 6px; border: 0; background: transparent; }
  .dot { display: block; width: 12px; height: 12px; border-radius: 50%; }
  .dot.big { width: 16px; height: 16px; }
  .label { position: absolute; top: 100%; left: 50%; transform: translateX(-50%); white-space: nowrap; font-size: 12px; color: var(--text2); }
  .empty { position: absolute; left: 0; right: 0; bottom: 24px; text-align: center; font-size: 13px; color: var(--subtle); }
</style>
