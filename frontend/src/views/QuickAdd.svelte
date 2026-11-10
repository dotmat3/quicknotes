<script>
  // Aggiunta rapida della vista Azioni (tasto N, "Nuova azione" o il "+" di una colonna). L'azione va nella nota
  // del progetto, sotto l'area, oppure in "Da smistare": mai nella nota di oggi. Invio aggiunge e resta aperto
  // per la successiva, Maiusc Invio aggiunge e chiude.
  import { onMount, tick, untrack } from 'svelte';
  import { app } from '../state/app.svelte.js';
  import { board, quickAction } from '../state/actions.svelte.js';
  import { fold, keyOf, parseDay, parseQuick, tokenAt } from '../state/actionQuery.js';
  import { PRIORITIES, dueLabel, isoToday } from '../note/editor/rules.js';
  import { openPage } from '../state/layout.svelte.js';
  import Icon from '../shell/Icon.svelte';

  let { preset = {}, close } = $props();

  // Le scelte di partenza valgono solo all'apertura.
  const start = untrack(() => ({ ...preset }));
  let text = $state(start.text ?? '');
  let project = $state(start.project ?? '');
  let area = $state(start.area ?? '');
  let due = $state(start.due ?? '');
  let priority = $state(start.priority ?? '');
  let added = $state([]);
  let busy = $state(false);
  let input = $state();
  let caret = $state(0);
  let sel = $state(0);
  let suggOff = $state(false);

  onMount(async () => {
    await tick();
    input?.focus();
    // Un testo che comincia con uno spazio (l'etichetta di una colonna, " #casa") si scrive davanti.
    const pos = text.startsWith(' ') ? 0 : text.length;
    input?.setSelectionRange(pos, pos);
    caret = pos;
  });

  const projects = $derived(app.counts.projects ?? []);
  const live = $derived(projects.filter((p) => p.status === 'attivo'));
  const parsed = $derived(parseQuick(text, projects));
  // Quello scritto nel testo vale più delle scelte sotto.
  const dest = $derived(parsed.project ?? (project || null));
  const destArea = $derived(parsed.project ? (parsed.area ?? (parsed.project === project ? area || null : null)) : dest ? area || null : null);
  const destDue = $derived(parsed.due ?? (due || null));
  const destPrio = $derived(parsed.priority ?? (priority || null));
  const destProject = $derived(projects.find((p) => p.key === dest));
  const areas = $derived(projects.find((p) => p.key === project)?.areas ?? []);
  const people = $derived.by(() => {
    const n = new Map();
    for (const i of board.items) for (const p of i.people ?? []) n.set(p, (n.get(p) ?? 0) + 1);
    return [...n].sort((a, b) => b[1] - a[1]).map(([p]) => p);
  });

  // Giorni proposti: oggi, domani, il prossimo venerdì (se non è domani) e lunedì prossimo.
  const today = isoToday();
  const DAYS = $derived.by(() => {
    const out = [['oggi', 'Oggi'], ['domani', 'Domani']];
    const fri = parseDay('ven');
    if (fri !== parseDay('domani')) out.push(['ven', 'Venerdì']);
    out.push(['lun', 'Lunedì']);
    return out.map(([w, label]) => [parseDay(w), label]);
  });

  // Suggerimenti per la parola con # o @ sotto il cursore.
  const token = $derived(suggOff ? null : tokenAt(text, caret));
  const sugg = $derived.by(() => {
    if (!token) return [];
    const v = fold(token.value);
    if (token.sigil === '@') {
      return people.filter((p) => fold(p).startsWith(v) || (v.length > 1 && fold(p).includes(v))).slice(0, 7).map((p) => ({ insert: `@${p}`, label: `@${p}`, hint: 'persona' }));
    }
    const [head, ...rest] = v.split('/');
    if (rest.length) {
      const p = projects.find((x) => x.key === keyOf(head) || keyOf(x.title) === keyOf(head) || (x.aliases ?? []).some((a) => keyOf(a) === keyOf(head)));
      if (!p) return [];
      const a = rest.join('/');
      return p.areas.filter((x) => x.startsWith(a)).slice(0, 7).map((x) => ({ insert: `#${p.key}/${x}`, label: `#${p.key}/${x}`, hint: `${p.title} · area` }));
    }
    const hit = (p) => !v || p.key.startsWith(v) || fold(p.title).includes(v) || (p.aliases ?? []).some((a) => fold(a).startsWith(v));
    return [...live, ...projects.filter((p) => p.status !== 'attivo')].filter(hit).slice(0, 7)
      .map((p) => ({ insert: `#${p.key}`, label: `#${p.key}`, hint: p.status === 'attivo' ? p.title : `${p.title} · ${p.status}`, areas: p.areas.length }));
  });
  $effect(() => {
    sugg;
    sel = 0;
  });

  function track() {
    caret = input?.selectionStart ?? text.length;
    suggOff = false;
  }

  async function accept(s) {
    const end = caret;
    const before = text.slice(0, token.start);
    const after = text.slice(end).replace(/^\S*/, '');
    // Un progetto con aree lascia la barra: si sceglie subito l'area.
    const piece = s.areas && !s.insert.includes('/') ? `${s.insert}/` : `${s.insert} `;
    text = `${before}${piece}${after.replace(/^\s+/, '')}`;
    await tick();
    const pos = before.length + piece.length;
    input.setSelectionRange(pos, pos);
    caret = pos;
  }

  async function submit(andClose) {
    const body = parsed.text;
    if (!body || busy) return;
    busy = true;
    const res = await quickAction({ text: body, project: dest, area: destArea, due: destDue, priority: destPrio, scheduled: parsed.scheduled });
    busy = false;
    if (!res) return;
    added = [{ text: body, where: whereLabel(res), id: res.id, title: res.title }, ...added].slice(0, 5);
    text = '';
    caret = 0;
    if (andClose) close();
    else input?.focus();
  }

  function whereLabel(r) {
    if (!r.project) return 'Da smistare';
    const p = projects.find((x) => x.key === r.project);
    return `${p?.title ?? r.project}${r.area ? ` › ${r.area}` : ''}`;
  }

  function onKey(e) {
    if (sugg.length) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        sel = (sel + (e.key === 'ArrowDown' ? 1 : -1) + sugg.length) % sugg.length;
        return;
      }
      // Con la parola già completa (@Marco scritto per intero) Invio aggiunge l'azione; Tab completa sempre.
      const complete = fold(sugg[sel].insert) === fold(`${token.sigil}${token.value}`);
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey && !complete)) {
        e.preventDefault();
        accept(sugg[sel]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        suggOff = true;
        return;
      }
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      submit(e.shiftKey);
    }
  }

  function setProject(v) {
    project = v;
    area = '';
    input?.focus();
  }

  const toggle = (cur, v) => (cur === v ? '' : v);
  const dueText = (d) => (d ? dueLabel(d).label : '');
</script>

<div class="dim"></div>
<button class="outside" aria-label="Chiudi l’aggiunta rapida" tabindex="-1" onclick={close}></button>
<div class="dialog" role="dialog" aria-modal="true" aria-label="Nuova azione">
  <div class="field">
    <span class="box" aria-hidden="true"></span>
    <input
      bind:this={input}
      bind:value={text}
      type="text"
      aria-label="Testo della nuova azione"
      role="combobox"
      aria-autocomplete="list"
      aria-controls="qa-sugg"
      aria-expanded={sugg.length > 0}
      placeholder="Cosa c’è da fare?  #progetto/area  @persona  entro:venerdì  !alta"
      onkeydown={onKey}
      oninput={track}
      onclick={track}
      onkeyup={(e) => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) track(); }}
    />
    {#if busy}<span class="busy" aria-hidden="true"></span>{/if}
  </div>

  {#if sugg.length}
    <div class="sugg" id="qa-sugg" role="listbox" aria-label="Suggerimenti">
      {#each sugg as s, i (s.insert)}
        <button role="option" aria-selected={i === sel} class:sel={i === sel} onmousedown={(e) => { e.preventDefault(); accept(s); }}>
          <span class="mono">{s.label}</span><span class="hint">{s.hint}</span>
        </button>
      {/each}
    </div>
  {/if}

  <div class="opts">
    <div class="opt">
      <span class="lbl">Dove</span>
      {#if parsed.project}
        <span class="chip on locked" title="Dal testo">#{parsed.project}{destArea ? `/${destArea}` : ''}</span>
      {:else}
        <select aria-label="Progetto" value={project} onchange={(e) => setProject(e.target.value)}>
          <option value="">Da smistare (nessun progetto)</option>
          {#each live as p (p.key)}<option value={p.key}>{p.title}</option>{/each}
          {#each projects.filter((p) => p.status !== 'attivo') as p (p.key)}<option value={p.key}>{p.title} ({p.status})</option>{/each}
        </select>
        {#if project}
          <select aria-label="Area" value={area} onchange={(e) => { area = e.target.value; input?.focus(); }}>
            <option value="">Senza area</option>
            {#each areas as a (a)}<option value={a}>{a}</option>{/each}
          </select>
        {/if}
      {/if}
    </div>
    <div class="opt">
      <span class="lbl">Scadenza</span>
      {#if parsed.due}
        <span class="chip on locked" title="Dal testo">{dueText(parsed.due)}</span>
      {:else}
        {#each DAYS as [d, label] (label)}
          <button class="chip" class:on={due === d} aria-pressed={due === d} onclick={() => { due = toggle(due, d); input?.focus(); }}>{label}</button>
        {/each}
        <input class="date" type="date" aria-label="Altra data" min={today} value={DAYS.some(([d]) => d === due) ? '' : due} onchange={(e) => (due = e.target.value)} />
      {/if}
    </div>
    <div class="opt">
      <span class="lbl">Priorità</span>
      {#if parsed.priority}
        <span class="chip on locked" title="Dal testo">{PRIORITIES.find(([p]) => p === parsed.priority)?.[2]} {parsed.priority}</span>
      {:else}
        {#each PRIORITIES as [p, label, arrow] (p)}
          <button class="chip prio-{p}" class:on={priority === p} aria-pressed={priority === p} onclick={() => { priority = toggle(priority, p); input?.focus(); }}>{arrow} {label}</button>
        {/each}
      {/if}
    </div>
  </div>

  {#if added.length}
    <ul class="added" aria-label="Appena aggiunte">
      {#each added as a, i (i + a.text)}
        <li><Icon name="check" size={13} /><span class="clip">{a.text}</span><button class="where" onclick={() => { openPage(`note:${a.id}`, a.title); close(); }}>{a.where}</button></li>
      {/each}
    </ul>
  {/if}

  <div class="foot">
    <span class="to">
      Finisce in <b>{destProject ? `${destProject.title}${destArea ? ` › ${destArea}` : ''}` : 'Da smistare'}</b>
      {#if destDue}<span class="sep">·</span>scade {dueText(destDue)}{/if}
      {#if parsed.scheduled}<span class="sep">·</span>da fare {dueText(parsed.scheduled)}{/if}
      {#if destPrio}<span class="sep">·</span>priorità {destPrio}{/if}
    </span>
    <span class="keys"><kbd>↵</kbd> aggiungi <kbd>⇧ ↵</kbd> e chiudi <kbd>Esc</kbd></span>
  </div>
</div>

<style>
  .dim { position: fixed; inset: 0; z-index: 50; background: rgba(8, 8, 10, 0.45); }
  .outside { position: fixed; inset: 0; z-index: 51; padding: 0; border: 0; background: transparent; cursor: default; }
  .dialog { position: fixed; top: 72px; left: 50%; transform: translateX(-50%); z-index: 52; display: flex; flex-direction: column; width: 640px; max-width: calc(100% - 32px); border-radius: 14px; background: var(--raised); border: 1px solid var(--border3); box-shadow: 0 30px 80px rgba(0, 0, 0, 0.55); }
  .field { position: relative; display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-bottom: 1px solid var(--border2); }
  .field input { flex: 1; min-width: 0; border: 0; outline: none; background: transparent; color: var(--text); font: inherit; font-size: 15.5px; }
  .field input::placeholder { color: var(--faint); }
  .box { flex: none; width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid var(--faint); }
  .busy { width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--border3); border-top-color: var(--accent); animation: spin 0.7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .sugg { display: flex; flex-direction: column; padding: 4px; border-bottom: 1px solid var(--border2); }
  .sugg button { display: flex; align-items: center; gap: 10px; height: 30px; padding: 0 10px; border: 0; border-radius: 7px; background: transparent; color: var(--text); font-size: 13px; text-align: left; }
  .sugg button.sel { background: var(--border2); }
  .sugg .hint { margin-left: auto; font-size: 12px; color: var(--subtle); }
  .mono { font-family: 'Geist Mono', monospace; font-size: 12.5px; }
  .opts { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; }
  .opt { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-height: 28px; }
  .lbl { width: 72px; font-size: 12px; color: var(--subtle); }
  .opt select, .date { height: 28px; max-width: 220px; padding: 0 6px; border: 1px solid var(--border2); border-radius: 7px; background: var(--surface); color: var(--text); font: inherit; font-size: 12.5px; }
  .date { color-scheme: light dark; }
  .chip { height: 26px; padding: 0 10px; border: 1px solid var(--border2); border-radius: 999px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .chip:hover { background: var(--hover); color: var(--text); }
  .chip.on { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--text); }
  .chip.locked { display: inline-flex; align-items: center; cursor: default; }
  .chip.prio-alta.on { border-color: var(--late); background: color-mix(in srgb, var(--late) 14%, transparent); }
  .added { margin: 0; padding: 4px 16px 10px; list-style: none; display: flex; flex-direction: column; gap: 2px; }
  .added li { display: flex; align-items: center; gap: 8px; min-height: 24px; font-size: 12.5px; color: var(--muted); }
  .added li :global(svg) { flex: none; color: var(--accent); }
  .clip { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .where { flex: none; margin-left: auto; height: 22px; padding: 0 8px; border: 0; border-radius: 6px; background: var(--hover); color: var(--subtle); font-size: 11.5px; }
  .where:hover { color: var(--text); }
  .foot { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding: 10px 16px; border-top: 1px solid var(--border2); font-size: 12px; color: var(--subtle); }
  .to b { color: var(--text); font-weight: 600; }
  .sep { margin: 0 6px; color: var(--faint); }
  .keys { margin-left: auto; display: flex; align-items: center; gap: 5px; }
  .keys kbd { margin-left: 6px; }
</style>
