<script>
  // Grafo di tutte le note, come in Obsidian: disposizione a forze su canvas, trascinamento,
  // zoom con la rotella, clic su un nodo per aprirlo. "Locale" mostra solo i dintorni dell'ultima nota aperta.
  import { onDestroy, onMount } from 'svelte';
  import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from 'd3-force';
  import { call, listen } from '../api.js';
  import { app, tagColor, theme } from '../state/app.svelte.js';
  import { openPage } from '../state/layout.svelte.js';

  let wrap = $state();
  let canvas = $state();
  let data = $state(null);
  let error = $state('');
  let query = $state('');
  let show = $state({ people: true, tags: true, daily: true, orphans: false });
  let depth = $state(1);

  let sim = null;
  let nodes = [];
  let links = [];
  let neighbors = new Map();
  let view = { k: 1, x: 0, y: 0 };
  let hover = null;
  let drag = null;
  // Finché l'utente non sposta o ingrandisce la vista, il grafo resta adattato al riquadro mentre si assesta.
  let auto = true;
  let frame = 0;
  const kept = new Map(); // posizioni conservate quando cambiano i filtri

  async function load() {
    try {
      data = await call('full_graph', {}, { nodes: [], edges: [] });
    } catch (e) {
      error = String(e);
    }
  }
  load();
  const off = listen('index-updated', load);
  onDestroy(() => {
    off.then((f) => f());
    sim?.stop();
    cancelAnimationFrame(frame);
  });

  const center = $derived(app.lastNote ? `note:${app.lastNote}` : app.today ? `note:${app.today.id}` : null);

  // Nodi e archi visibili con i filtri attuali.
  const visible = $derived.by(() => {
    if (!data) return { nodes: [], edges: [] };
    const keep = data.nodes.map((n) => (n.kind === 'person' ? show.people : n.kind === 'tag' ? show.tags : n.kind === 'daily' ? show.daily : true));
    let edges = data.edges.filter(([a, b]) => keep[a] && keep[b]);
    const deg = new Array(data.nodes.length).fill(0);
    for (const [a, b] of edges) deg[a]++, deg[b]++;
    let ids = data.nodes.map((_, i) => i).filter((i) => keep[i] && (show.orphans || deg[i] > 0 || data.nodes[i].page === center));
    if (app.graphLocal && center) {
      const start = data.nodes.findIndex((n) => n.page === center);
      const near = new Set(start >= 0 ? [start] : []);
      // Un livello alla volta: i vicini trovati in questo giro si allargano solo al giro dopo.
      for (let d = 0; d < depth; d++) {
        const ring = new Set(near);
        for (const [a, b] of edges) if (ring.has(a) || ring.has(b)) near.add(a), near.add(b);
      }
      ids = ids.filter((i) => near.has(i));
    }
    const set = new Set(ids);
    edges = edges.filter(([a, b]) => set.has(a) && set.has(b));
    return { nodes: ids.map((i) => ({ ...data.nodes[i], i, deg: deg[i] })), edges };
  });

  const counts = $derived({ notes: visible.nodes.filter((n) => n.kind === 'note' || n.kind === 'daily').length, edges: visible.edges.length });

  $effect(() => {
    const v = visible;
    if (canvas) rebuild(v);
  });

  // Ridisegna quando cambiano tema, ricerca o colori delle etichette.
  $effect(() => {
    theme.current;
    app.tagColors;
    query;
    schedule();
  });

  function rebuild(v) {
    for (const n of nodes) kept.set(n.page, { x: n.x, y: n.y, vx: n.vx, vy: n.vy });
    const index = new Map();
    nodes = v.nodes.map((n) => {
      const node = { ...n, r: radius(n), ...(kept.get(n.page) ?? {}) };
      index.set(n.i, node);
      return node;
    });
    links = v.edges.map(([a, b]) => ({ source: index.get(a), target: index.get(b) }));
    neighbors = new Map(nodes.map((n) => [n, new Set()]));
    for (const l of links) neighbors.get(l.source).add(l.target), neighbors.get(l.target).add(l.source);
    sim?.stop();
    const strength = nodes.length > 600 ? -40 : -90;
    sim = forceSimulation(nodes)
      .force('link', forceLink(links).distance(46).strength(0.4))
      .force('charge', forceManyBody().strength(strength).distanceMax(420))
      .force('x', forceX(0).strength(0.04))
      .force('y', forceY(0).strength(0.04))
      .force('collide', forceCollide((n) => n.r + 3))
      .on('tick', schedule);
    if (kept.size) sim.alpha(0.5);
  }

  function radius(n) {
    if (n.page === center) return 7;
    return Math.min(3 + Math.sqrt(n.deg) * 1.1, 14);
  }

  function css(name) {
    return getComputedStyle(wrap).getPropertyValue(name).trim();
  }

  function colorOf(n, c) {
    if (n.page === center) return c.accent;
    if (n.kind === 'person') return c.person;
    if (n.kind === 'tag') return tagColor(n.id);
    return n.kind === 'daily' ? c.faint : c.muted;
  }

  function fit() {
    if (!nodes.length || !canvas) return;
    let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
    for (const n of nodes) (x0 = Math.min(x0, n.x)), (y0 = Math.min(y0, n.y)), (x1 = Math.max(x1, n.x)), (y1 = Math.max(y1, n.y));
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const k = Math.min(nodes.length < 40 ? 2.2 : 1.4, Math.max(0.05, Math.min(w / (x1 - x0 + 80), h / (y1 - y0 + 80))));
    view = { k, x: w / 2 - ((x0 + x1) / 2) * k, y: h / 2 - ((y0 + y1) / 2) * k };
  }

  function schedule() {
    if (!frame) frame = requestAnimationFrame(draw);
  }

  function draw() {
    frame = 0;
    if (!canvas || !wrap) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    if (auto) fit();
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const c = { accent: css('--accent'), person: css('--person'), muted: css('--muted'), faint: css('--faint'), line: css('--border3'), text: css('--text2'), lit: css('--subtle') };
    const q = query.trim().toLowerCase();
    const match = (n) => !q || n.label.toLowerCase().includes(q);
    const focus = hover ?? null;
    const near = focus ? neighbors.get(focus) : null;
    const lit = (n) => (focus ? n === focus || near.has(n) : match(n));

    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.k, view.k);
    ctx.lineWidth = 1 / view.k;
    for (const l of links) {
      const on = focus && (l.source === focus || l.target === focus);
      ctx.globalAlpha = focus ? (on ? 0.9 : 0.08) : q ? (match(l.source) && match(l.target) ? 0.6 : 0.08) : 0.5;
      ctx.strokeStyle = on ? c.accent : c.line;
      ctx.beginPath();
      ctx.moveTo(l.source.x, l.source.y);
      ctx.lineTo(l.target.x, l.target.y);
      ctx.stroke();
    }
    for (const n of nodes) {
      ctx.globalAlpha = lit(n) ? 1 : 0.15;
      ctx.fillStyle = colorOf(n, c);
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    // Etichette in pixel dello schermo: sempre leggibili. Si vedono avvicinandosi, oppure sui nodi in evidenza.
    // Più nodi ci sono, più bisogna avvicinarsi perché compaiano tutte.
    const labelZoom = nodes.length > 400 ? 2.2 : nodes.length > 120 ? 1.6 : 0.6;
    ctx.font = '12px Geist, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const n of nodes) {
      const strong = focus ? n === focus || near.has(n) : q ? match(n) : n.page === center;
      if (!strong && (view.k < labelZoom || (focus && !lit(n)))) continue;
      ctx.globalAlpha = strong || !focus ? (lit(n) ? 1 : 0.3) : 0.3;
      ctx.fillStyle = n === focus ? c.accent : c.text;
      const sx = n.x * view.k + view.x;
      const sy = (n.y + n.r) * view.k + view.y + 4;
      if (sx < -100 || sx > w + 100 || sy < -20 || sy > h + 20) continue;
      ctx.fillText(n.label.length > 40 ? `${n.label.slice(0, 39)}…` : n.label, sx, sy);
    }
    ctx.globalAlpha = 1;
  }

  const toWorld = (e) => {
    const r = canvas.getBoundingClientRect();
    return { x: (e.clientX - r.left - view.x) / view.k, y: (e.clientY - r.top - view.y) / view.k, sx: e.clientX, sy: e.clientY };
  };
  const nodeAt = (p) => sim?.find(p.x, p.y, 18 / view.k) ?? null;

  function down(e) {
    if (e.button !== 0) return;
    const p = toWorld(e);
    const n = nodeAt(p);
    drag = { n, sx: p.sx, sy: p.sy, vx: view.x, vy: view.y, moved: false };
    if (n) (n.fx = n.x), (n.fy = n.y);
    canvas.setPointerCapture(e.pointerId);
  }

  function move(e) {
    const p = toWorld(e);
    if (drag) {
      if (Math.abs(p.sx - drag.sx) + Math.abs(p.sy - drag.sy) > 4) drag.moved = true;
      if (!drag.moved) return;
      if (drag.n) {
        auto = false;
        drag.n.fx = p.x;
        drag.n.fy = p.y;
        sim.alphaTarget(0.25).restart();
      } else {
        view = { ...view, x: drag.vx + p.sx - drag.sx, y: drag.vy + p.sy - drag.sy };
        auto = false;
        schedule();
      }
      return;
    }
    const n = nodeAt(p);
    if (n !== hover) {
      hover = n;
      canvas.style.cursor = n ? 'pointer' : 'grab';
      schedule();
    }
  }

  function up(e) {
    if (!drag) return;
    const { n, moved } = drag;
    drag = null;
    if (n) {
      n.fx = n.fy = null;
      sim.alphaTarget(0);
      if (!moved) openPage(n.page, n.kind === 'note' || n.kind === 'daily' ? n.label : undefined);
    }
    canvas.releasePointerCapture?.(e.pointerId);
  }

  function wheel(e) {
    e.preventDefault();
    const r = canvas.getBoundingClientRect();
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    const k = Math.min(6, Math.max(0.08, view.k * Math.exp(-e.deltaY * 0.0015)));
    view = { k, x: mx - ((mx - view.x) * k) / view.k, y: my - ((my - view.y) * k) / view.k };
    auto = false;
    schedule();
  }

  onMount(() => {
    const ro = new ResizeObserver(schedule);
    ro.observe(wrap);
    canvas.addEventListener('wheel', wheel, { passive: false });
    // Usato dalle prove: dove si trova a schermo il nodo di una pagina.
    canvas.qnNodePosition = (page) => {
      const n = nodes.find((x) => x.page === page);
      const r = canvas.getBoundingClientRect();
      return n ? { x: r.left + n.x * view.k + view.x, y: r.top + n.y * view.k + view.y } : null;
    };
    return () => ro.disconnect();
  });

  function setLocal(on) {
    app.graphLocal = on;
    auto = true;
  }
</script>

<div class="head">
  <div>
    <h1>Grafo</h1>
    <p class="sub">{counts.notes} note · {counts.edges} collegamenti{#if app.graphLocal} · attorno all'ultima nota aperta{/if}</p>
  </div>
  <div class="right">
  <button class="btn fit" onclick={() => { auto = true; schedule(); }}>Adatta</button>
  <div class="seg" role="radiogroup" aria-label="Estensione del grafo">
    <button role="radio" aria-checked={!app.graphLocal} class:on={!app.graphLocal} onclick={() => setLocal(false)}>Tutto</button>
    <button role="radio" aria-checked={app.graphLocal} class:on={app.graphLocal} onclick={() => setLocal(true)}>Locale</button>
  </div>
  </div>
</div>

<div class="tools">
  <input class="filter" type="search" placeholder="Evidenzia…" aria-label="Evidenzia i nodi" bind:value={query} />
  {#if app.graphLocal}
    <label class="opt">Profondità <select bind:value={depth} onchange={() => (auto = true)}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></label>
  {/if}
  {#each [['people', 'Persone'], ['tags', 'Etichette'], ['daily', 'Note del giorno'], ['orphans', 'Note isolate']] as [k, label] (k)}
    <label class="opt"><input type="checkbox" bind:checked={show[k]} onchange={() => (auto = true)} />{label}</label>
  {/each}
</div>

{#if error}
  <p class="sub">{error}</p>
{/if}
<div class="canvas" bind:this={wrap}>
  <canvas bind:this={canvas} aria-label="Grafo delle note: usa l'elenco qui sotto con la tastiera" onpointerdown={down} onpointermove={move} onpointerup={up} onpointerleave={() => { if (!drag && hover) { hover = null; schedule(); } }}></canvas>
  {#if data && !visible.nodes.length}
    <p class="empty">Nessun collegamento da mostrare. Scrivi @persone, #etichette o [[link]] nelle note.</p>
  {/if}
</div>
<ul class="sr" aria-label="Nodi del grafo">
  {#each visible.nodes as n (n.page)}
    <li><button onclick={() => openPage(n.page, n.kind === 'note' || n.kind === 'daily' ? n.label : undefined)}>{n.label}</button></li>
  {/each}
</ul>

<style>
  .head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
  .sub { margin: 6px 0 14px; font-size: 13.5px; color: var(--subtle); }
  .right { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
  .seg { display: flex; padding: 2px; border-radius: 9px; background: var(--raised); border: 1px solid var(--border); }
  .seg button { height: 28px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .seg button.on { background: var(--border2); color: var(--text); }
  .tools { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; margin-bottom: 10px; }
  .filter { width: 200px; height: 30px; padding: 0 10px; border: 1px solid var(--border2); border-radius: 8px; background: var(--raised); color: var(--text); font: inherit; font-size: 13px; outline: none; }
  .filter:focus { border-color: var(--accent); }
  .opt { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
  .opt input { accent-color: var(--accent); margin: 0; }
  .opt select { height: 26px; border: 1px solid var(--border2); border-radius: 6px; background: var(--raised); color: var(--text); font: inherit; font-size: 12.5px; }
  .canvas { position: relative; height: max(420px, calc(100vh - 290px)); border-radius: 12px; border: 1px solid var(--border); background-color: var(--sunk); background-image: radial-gradient(var(--dots) 1px, transparent 1px); background-size: 20px 20px; overflow: hidden; }
  canvas { display: block; width: 100%; height: 100%; cursor: grab; touch-action: none; }
  .empty { position: absolute; left: 0; right: 0; top: 45%; text-align: center; font-size: 13px; color: var(--subtle); }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; margin: 0; padding: 0; }
</style>
