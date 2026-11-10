<script>
  import { onDestroy } from 'svelte';
  import { call, listen } from '../api.js';
  import { app } from '../state/app.svelte.js';
  import { openAt, openPage } from '../state/layout.svelte.js';
  import { isoToday } from '../note/editor/rules.js';
  import Icon from '../shell/Icon.svelte';

  const MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'];
  const DOWS = ['domenica', 'lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato'];
  const DOWS3 = ['Dom', 'Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab'];
  const KINDS = {
    note: ['Nota', 'var(--muted)', 'color-mix(in srgb, var(--muted) 12%, transparent)'],
    due: ['Scadenza', 'var(--text)', 'color-mix(in srgb, var(--text) 8%, transparent)'],
    plan: ['Pianificata', 'var(--accent)', 'color-mix(in srgb, var(--accent) 14%, transparent)'],
    late: ['In ritardo', 'var(--late)', 'color-mix(in srgb, var(--late) 14%, transparent)'],
    done: ['Fatta', 'var(--faint)', 'transparent'],
    dec: ['Decisione', 'var(--dec)', 'color-mix(in srgb, var(--dec) 13%, transparent)'],
    rec: ['Registrazione', 'var(--muted)', 'color-mix(in srgb, var(--muted) 12%, transparent)'],
  };
  // Nella legenda note e registrazioni hanno lo stesso colore, come nella tavola Home.
  const LEGEND = [['due', 'Scadenza'], ['plan', 'Pianificata'], ['late', 'In ritardo'], ['dec', 'Decisione'], ['note', 'Nota o registrazione'], ['done', 'Fatta']];
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  const today = isoToday();
  const now = new Date();
  let mode = $state('mese');
  let year = $state(now.getFullYear());
  let month = $state(now.getMonth());
  let sel = $state(today);
  let days = $state({});
  // Solo le note, le decisioni e le azioni di un progetto.
  let project = $state('');

  const parse = (iso) => new Date(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)));
  const selDate = $derived(parse(sel));

  const cells = $derived.by(() => {
    if (mode === 'settimana') {
      const back = (selDate.getDay() + 6) % 7;
      return Array.from({ length: 7 }, (_, i) => new Date(selDate.getFullYear(), selDate.getMonth(), selDate.getDate() - back + i));
    }
    const first = new Date(year, month, 1);
    const lead = (first.getDay() + 6) % 7;
    const count = Math.ceil((lead + new Date(year, month + 1, 0).getDate()) / 7) * 7;
    return Array.from({ length: count }, (_, i) => new Date(year, month, 1 - lead + i));
  });

  async function load() {
    days = await call('calendar_data', { from: isoToday(cells[0]), to: isoToday(cells[cells.length - 1]), project: project || null }, {});
  }
  $effect(() => {
    cells;
    project;
    load();
  });
  const off = listen('index-updated', load);
  onDestroy(() => off.then((f) => f()));

  const eventsOf = (key) => days[key]?.events ?? [];
  const selEvents = $derived(eventsOf(sel));
  const selDaily = $derived(days[sel]?.daily);

  function shift(n) {
    if (mode === 'settimana') {
      const d = new Date(selDate.getFullYear(), selDate.getMonth(), selDate.getDate() + 7 * n);
      sel = isoToday(d);
    } else {
      const d = new Date(year, month + n, 1);
      year = d.getFullYear();
      month = d.getMonth();
    }
  }

  function goToday() {
    year = now.getFullYear();
    month = now.getMonth();
    sel = today;
  }

  async function openDaily(key) {
    const n = await call('daily_note', { date: key, delta: 0 });
    openPage(`note:${n.id}`, n.title);
  }

  const openEvent = (e) => e.note_id && openAt(`note:${e.note_id}`, e.line);
  const prevName = $derived(mode === 'settimana' ? 'Settimana prima' : cap(MONTHS[(month + 11) % 12]));
  const nextName = $derived(mode === 'settimana' ? 'Settimana dopo' : cap(MONTHS[(month + 1) % 12]));
  const title = $derived.by(() => {
    if (mode !== 'settimana') return cap(MONTHS[month]);
    const a = cells[0];
    const b = cells[6];
    return a.getMonth() === b.getMonth() ? `${a.getDate()}–${b.getDate()} ${MONTHS[b.getMonth()]}` : `${a.getDate()} ${MONTHS[a.getMonth()].slice(0, 3)} – ${b.getDate()} ${MONTHS[b.getMonth()].slice(0, 3)}`;
  });
  const shownYear = $derived(mode === 'settimana' ? cells[0].getFullYear() : year);
  const todayInView = $derived(today >= isoToday(cells[0]) && today <= isoToday(cells[cells.length - 1]) && (mode === 'settimana' || (year === now.getFullYear() && month === now.getMonth())));
</script>

<div class="top">
  <div class="nav">
    <button class="step" aria-label={mode === 'settimana' ? 'Settimana precedente' : 'Mese precedente'} onclick={() => shift(-1)}><Icon name="left" size={14} />{prevName}</button>
    <h1>{title} <span class="year">{shownYear}</span></h1>
    <button class="step" aria-label={mode === 'settimana' ? 'Settimana successiva' : 'Mese successivo'} onclick={() => shift(1)}>{nextName}<Icon name="right" size={14} /></button>
  </div>
  {#if !todayInView}<button class="btn" onclick={goToday}>Torna a oggi</button>{/if}
  {#if app.counts.projects?.length}
    <select class="proj" aria-label="Progetto" bind:value={project}>
      <option value="">Tutti i progetti</option>
      {#each app.counts.projects as p (p.key)}<option value={p.key}>{p.title}</option>{/each}
    </select>
  {/if}
  <div class="seg" role="radiogroup" aria-label="Periodo">
    {#each [['mese', 'Mese'], ['settimana', 'Settimana']] as [v, label] (v)}
      <button role="radio" aria-checked={mode === v} class:on={mode === v} onclick={() => (mode = v)}>{label}</button>
    {/each}
  </div>
</div>

<div class="body">
  {#if mode === 'settimana'}
    <div class="week">
      {#each cells as d (d.getTime())}
        {@const key = isoToday(d)}
        {@const ev = eventsOf(key)}
        <div class="wrow" class:today={key === today}>
          <button class="wday" aria-label="{DOWS[d.getDay()]} {d.getDate()} {MONTHS[d.getMonth()]}" onclick={() => (sel = key)}><span class="dow">{DOWS3[d.getDay()]}</span><span class="num" class:dim={!ev.length && !days[key]?.daily}>{d.getDate()}</span></button>
          <div class="witems">
            {#each ev as e, i (i)}
              <button class="witem" onclick={() => openEvent(e)}><span class="sw" style="background:{KINDS[e.kind][1]}"></span>{#if e.kind === 'rec'}<Icon name="mic" size={14} style="color:var(--muted)" />{/if}<span class="wt" class:strike={e.kind === 'done'} style="color:{e.kind === 'late' ? 'var(--late)' : e.kind === 'done' ? 'var(--faint)' : 'var(--text)'}">{e.text}</span><span class="wk">{KINDS[e.kind][0]}</span></button>
            {:else}
              <span class="nothing">Niente in programma</span>
            {/each}
          </div>
          {#if days[key]?.daily}<button class="btn small" onclick={() => openDaily(key)}>Nota del giorno</button>{/if}
        </div>
      {/each}
    </div>
  {:else}
    <div class="month-wrap">
      <div class="grid">
        {#each ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'] as d (d)}<div class="dow-head">{d}</div>{/each}
        {#each cells as d, i (d.getTime())}
          {@const key = isoToday(d)}
          {@const ev = eventsOf(key)}
          <button class="cell" class:off={d.getMonth() !== month} class:sel={key === sel} class:top-line={i >= 7} class:left-line={i % 7} aria-pressed={key === sel} aria-label="{d.getDate()} {MONTHS[d.getMonth()]}{ev.length ? `, ${ev.length} elementi` : ''}{days[key]?.daily ? ', nota del giorno' : ''}" onclick={() => (sel = key)}>
            <span class="cell-head"><span class="cnum mono" class:today={key === today}>{d.getDate()}</span>{#if days[key]?.daily}<span class="ddot" title="Nota del giorno"></span>{/if}</span>
            {#each ev.slice(0, 3) as e, j (j)}
              <span class="chip" class:strike={e.kind === 'done'} style="color:{KINDS[e.kind][1]};background:{KINDS[e.kind][2]}">{#if e.kind === 'rec'}<Icon name="mic" size={11} style="vertical-align:-1px;margin-right:3px" />{/if}{e.text}</span>
            {/each}
            {#if ev.length > 3}<span class="more">+{ev.length - 3} altri</span>{/if}
          </button>
        {/each}
      </div>
      <div class="legend">
        {#each LEGEND as [k, label] (k)}
          <span class="leg"><span class="lsw" style="background:{KINDS[k][2]};border:1px solid {KINDS[k][1]}"></span>{label}</span>
        {/each}
      </div>
    </div>
    <aside class="side" aria-label="Giorno selezionato">
      <div class="side-dow">{sel === today ? 'Oggi · ' : ''}{DOWS[selDate.getDay()]}</div>
      <div class="side-title">{selDate.getDate()} {MONTHS[selDate.getMonth()]} {selDate.getFullYear()}</div>
      {#if selDaily}
        <button class="btn primary wide" onclick={() => openDaily(sel)}>Apri la nota del giorno</button>
      {:else}
        <button class="btn wide" onclick={() => openDaily(sel)}><Icon name="plus" size={14} />Crea la nota del giorno</button>
      {/if}
      <div class="side-list">
        {#each selEvents as e, i (i)}
          <button class="side-item" onclick={() => openEvent(e)}>{#if e.kind === 'rec'}<Icon name="mic" size={14} style="flex:none;margin-top:3px;color:var(--muted)" />{:else}<span class="sw top" style="background:{KINDS[e.kind][1]}"></span>{/if}<span class="grow"><span class="sl">{e.text}</span><span class="sk">{KINDS[e.kind][0]}</span></span></button>
        {:else}
          <p class="nothing">Niente in questo giorno.</p>
        {/each}
      </div>
    </aside>
  {/if}
</div>

<style>
  .top { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; margin-bottom: 16px; }
  .nav { display: flex; align-items: center; gap: 4px; flex: 1 1 420px; min-width: 0; }
  .step { display: flex; align-items: center; gap: 4px; height: 32px; padding: 0 8px; border: 0; border-radius: 8px; background: transparent; color: var(--subtle); font-size: 13px; }
  .step:hover { background: var(--hover); }
  h1 { margin: 0 8px; font-size: 26px !important; white-space: nowrap; }
  .year { font-weight: 400; color: var(--subtle); }
  .proj { height: 32px; max-width: 200px; padding: 0 8px; border: 1px solid var(--border2); border-radius: 8px; background: var(--raised); color: var(--text); font: inherit; font-size: 12.5px; }
  .seg { display: flex; padding: 2px; border-radius: 9px; background: var(--raised); border: 1px solid var(--border); }
  .seg button { height: 28px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .seg button.on { background: var(--border2); color: var(--text); }
  .body { display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start; }
  .month-wrap { flex: 999 1 560px; min-width: 0; }
  .grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; background: var(--card); }
  .dow-head { padding: 8px 10px; font-size: 11.5px; color: var(--subtle); border-bottom: 1px solid var(--border); }
  .cell { display: flex; flex-direction: column; justify-content: flex-start; align-items: stretch; min-width: 0; height: 112px; padding: 6px; border: 0; text-align: left; vertical-align: top; overflow: hidden; background: transparent; color: inherit; }
  .cell.top-line { border-top: 1px solid var(--border); }
  .cell.left-line { border-left: 1px solid var(--border); }
  .cell.off { background: var(--sunk); }
  .cell.sel { background: var(--raised); box-shadow: inset 0 0 0 1px var(--border3); }
  .cell-head { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
  .cnum { display: inline-flex; align-items: center; justify-content: center; min-width: 24px; height: 24px; padding: 0 4px; border-radius: 12px; font-size: 12.5px; color: var(--text); }
  .cell.off .cnum { color: var(--faint); }
  .cnum.today { background: var(--accent); color: var(--on-accent) !important; font-weight: 600; }
  .ddot { width: 5px; height: 5px; border-radius: 50%; background: var(--faint); }
  .chip { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; padding: 1px 6px; border-radius: 5px; font-size: 11.5px; line-height: 1.5; }
  .strike { text-decoration: line-through; }
  .more { display: block; padding: 0 4px; font-size: 11px; color: var(--subtle); }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 10px; font-size: 11.5px; color: var(--subtle); }
  .leg { display: flex; align-items: center; gap: 6px; }
  .lsw { width: 10px; height: 10px; border-radius: 3px; }
  .side { flex: 1 1 260px; min-width: 0; padding: 16px; border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .side-dow { font-size: 12px; color: var(--subtle); }
  .side-title { font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
  .wide { width: 100%; justify-content: center; height: 34px; margin-top: 12px; font-size: 13px; }
  .side-list { margin-top: 16px; display: flex; flex-direction: column; gap: 2px; }
  .side-item { display: flex; align-items: flex-start; gap: 10px; width: 100%; padding: 7px 4px; border: 0; border-radius: 6px; background: transparent; color: var(--text); font-size: 13.5px; text-align: left; }
  .side-item:hover { background: var(--hover); }
  .sw { flex: none; width: 8px; height: 8px; border-radius: 2px; }
  .sw.top { margin-top: 6px; }
  .grow { flex: 1; min-width: 0; }
  .sl, .sk { display: block; }
  .sk { font-size: 11.5px; color: var(--subtle); }
  .nothing { margin: 0; font-size: 13px; color: var(--faint); }
  .week { flex: 1 1 100%; min-width: 0; border: 1px solid var(--border); border-radius: 12px; background: var(--card); overflow: hidden; }
  .wrow { display: flex; align-items: flex-start; gap: 16px; padding: 16px 18px; }
  .wrow + .wrow { border-top: 1px solid var(--border); }
  .wrow.today { background: color-mix(in srgb, var(--accent) 5%, transparent); }
  .wday { flex: none; width: 76px; padding: 0; border: 0; background: transparent; color: inherit; text-align: left; }
  .dow { display: block; font-size: 12px; color: var(--subtle); }
  .wrow.today .dow, .wrow.today .num { color: var(--accent); }
  .num { display: block; font-size: 22px; font-weight: 600; line-height: 1.2; }
  .num.dim { color: var(--faint); }
  .witems { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; padding-top: 2px; }
  .witem { display: flex; align-items: center; gap: 10px; width: 100%; padding: 0; border: 0; background: transparent; font-size: 14px; text-align: left; }
  .wt { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .wk { flex: none; font-size: 12px; color: var(--faint); }
  .btn.small { flex: none; height: 28px; font-size: 12px; color: var(--muted); }
</style>
