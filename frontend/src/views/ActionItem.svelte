<script>
  import { app, tagColor } from '../state/app.svelte.js';
  import { openAt } from '../state/layout.svelte.js';
  import { call } from '../api.js';
  import { completeAll, loadBoard, setDone, setScheduled, setStatus } from '../state/actions.svelte.js';
  import { docs, onExternalChange, save } from '../state/documents.svelte.js';
  import ActionText from './ActionText.svelte';
  import StatusBox from './StatusBox.svelte';
  import { PRIORITIES, TAG, statusLabel } from '../note/editor/rules.js';
  import Icon from '../shell/Icon.svelte';

  // `pop` apre il popover unico della vista: sta fuori dalle colonne, che lo taglierebbero.
  // `quick`: 'agenda' o 'review' mostrano i pulsanti rapidi (Oggi, Domani, stato, sposta, apri la nota).
  let { item, card = false, pop, popKey, quick = null } = $props();

  let subsOpen = $state(true);
  let warn = $state(false);

  const nDone = $derived(item.subs.filter((s) => s.closed ?? s.done).length);
  const left = $derived(item.subs.length - nDone);
  const closed = $derived(item.closed ?? item.done);
  const status = $derived(item.status ?? (item.done ? 'done' : 'todo'));

  function toggle() {
    if (closed) setStatus(item, 'todo');
    else if (left) {
      warn = true;
      subsOpen = true;
    } else {
      setDone(item, true);
    }
  }

  async function toggleSub(s) {
    if (docs[item.note_id]) await save(item.note_id);
    await call('set_action_done', { noteId: item.note_id, line: s.line, text: s.raw, done: !(s.closed ?? s.done) });
    await onExternalChange([item.note_id]);
    warn = false;
    await loadBoard();
  }

  function statusMenu(e) {
    e.preventDefault();
    pop(e, item, 'status', 0);
  }

  // Le mini pillole hanno solo il bordo, nel colore del testo; la priorità alta è l'unica piena (in app.css).
  const LEVEL_LOOK = { late: 'color:var(--late)', soon: 'color:var(--text)', normal: '' };
  const dueLook = $derived(LEVEL_LOOK[item.due_level] ?? '');
  const schedLook = $derived(item.since_days ? LEVEL_LOOK.late : 'color:var(--text)');
  // Le etichette scritte nella riga sono già pillole nel testo. Il progetto ha la sua pillola solo quando non è
  // scritto (viene dall'intestazione o dalla nota), e senza l'area se anche l'area è già un'etichetta del testo.
  const tag = $derived(item.tag && (item.raw ?? '').toLowerCase().includes(`#${item.tag}`) ? item.tag : null);
  const prio = $derived(PRIORITIES.find(([p]) => p === item.priority));
  const written = $derived([...(item.raw ?? '').matchAll(TAG)].map((m) => m[1].toLowerCase()));
  const areaWritten = $derived(!!item.area && written.some((t) => t === item.area.toLowerCase() || t.endsWith(`/${item.area.toLowerCase()}`)));
  const where = $derived(item.project && !item.project_in_text ? `${item.project}${item.area && !areaWritten ? ` / ${item.area}` : ''}` : '');
  const pc = $derived(item.project ? tagColor(item.project) : null);
  // Le sotto-azioni: un segmento per ognuna fino a 8, oltre una barra continua.
  const segments = $derived(item.subs.length <= 8 ? item.subs.map((s) => s.closed ?? s.done) : null);
  const key = (kind, idx = 0) => `${item.note_id}:${item.line}:${kind}:${idx}`;
  const aria = (label) => `${label} · ${item.text}`;
  const source = $derived(quick && item.age_days > 1 ? `${item.note_title} · da ${item.age_days} gg` : item.note_title);
  // @persona e #etichetta nel titolo fanno da pillola: il clic apre il pannello per cambiarle o toglierle.
  function pickToken(kind, arg, e) {
    if (closed) return false;
    if (kind === 'person') {
      const i = item.people.findIndex((w) => w.toLowerCase() === arg.toLowerCase());
      if (i < 0) return false;
      pop(e, item, 'person', i);
      return true;
    }
    if (!tag || arg.toLowerCase() !== tag.toLowerCase()) return false;
    pop(e, item, 'tag', 0);
    return true;
  }
  const openNote = () => openAt(`note:${item.note_id}`, item.line, app.titles[`note:${item.note_id}`] ?? item.note_title);
</script>

<div class="act" class:card class:faded={card && closed} class:stale={item.stale}>
  <div class="head">
    <StatusBox {status} label={item.text} onclick={toggle} oncontextmenu={statusMenu} />
    <div class="main">
      {#if item.parent}<div class="parent">↳ {item.parent}</div>{/if}
      <!-- Titolo e mini pillole sulla stessa riga: vanno a capo solo se il titolo è lungo. -->
      <div class="text">
        <ActionText text={item.text} done={closed} pick={pickToken} />
        {#if closed}
          {#if status === 'cancelled'}<span class="chip neutral">annullata</span>{/if}
          {#if item.done_on || item.due_label}<span class="chip mono neutral">{item.done_on ?? item.due_label}</span>{/if}
        {:else}
          {#if prio}
            <button class="chip prio-{prio[0]}" aria-label={aria(`Priorità ${prio[0]}`)} aria-haspopup="dialog" aria-expanded={popKey === key('priority')} onclick={(e) => pop(e, item, 'priority', 0)}>{prio[2]} {prio[1]}</button>
          {/if}
          {#if status === 'waiting'}
            <button class="chip" style="color:var(--person)" title="Stato: in attesa" aria-label={aria(`Stato ${statusLabel(status)}`)} aria-haspopup="dialog" aria-expanded={popKey === key('status')} onclick={(e) => pop(e, item, 'status', 0)}>in attesa{item.waiting_days ? ` · ${item.waiting_days} gg` : ''}</button>
          {/if}
          {#if item.scheduled_label}
            <button class="chip mono" class:neutral={!item.since_days} style={schedLook} title="Il giorno in cui farla (scheduled:)" aria-label={aria(`Da fare ${item.scheduled_label}`)} aria-haspopup="dialog" aria-expanded={popKey === key('scheduled')} onclick={(e) => pop(e, item, 'scheduled', 0)}><Icon name="clock" size={11} />{`${item.scheduled_label}${item.since_days ? ` · da ${item.since_days} gg` : ''}`}</button>
          {/if}
          {#if item.due_label}
            <button class="chip mono" class:neutral={!dueLook} style={dueLook} title="Scadenza (due:)" aria-label={aria(`Scadenza ${item.due_label}`)} aria-haspopup="dialog" aria-expanded={popKey === key('due')} onclick={(e) => pop(e, item, 'due', 0)}>{item.due_label}</button>
          {/if}
          {#if where}
            <button class="chip" style="color:{pc}" title="Progetto e area" aria-label={aria(`Progetto ${where}`)} aria-haspopup="dialog" aria-expanded={popKey === key('move')} onclick={(e) => pop(e, item, 'move', 0)}><Icon name="folder" size={11} />{where}</button>
          {/if}
          {#if item.subs.length}
            <button class="chip neutral" title="Sotto-azioni" aria-label={aria(`Sotto-azioni: ${nDone} fatte su ${item.subs.length}`)} aria-expanded={subsOpen} onclick={() => (subsOpen = !subsOpen)}>
              {#if segments}
                <span class="segs" aria-hidden="true">{#each segments as on, i (i)}<span class:on></span>{/each}</span>
              {:else}
                <span class="track" aria-hidden="true"><span style="width:{(nDone / item.subs.length) * 100}%"></span></span>
              {/if}
              <span>{nDone}/{item.subs.length}</span>
            </button>
            {#if !left}
              <button class="chip" style="color:var(--accent)" onclick={() => setDone(item, true)}>Tutte fatte · chiudi</button>
            {/if}
          {/if}
          {#if item.description}
            <button class="chip neutral" aria-label={aria('Modifica la descrizione')} aria-haspopup="dialog" aria-expanded={popKey === key('description')} onclick={(e) => pop(e, item, 'description', 0)}>Descrizione</button>
          {/if}
        {/if}
        <button class="src" title="Apri la nota" onclick={openNote}><Icon name="note" size={11} /><span class="clip">{source}</span></button>
      </div>
      {#if item.description}<div class="desc">{item.description}</div>{/if}

      {#if item.subs.length && (subsOpen || (warn && !closed && left))}
        <div class="subs">
          {#if subsOpen}
            <div class="sublist">
              {#each item.subs as s (s.line)}
                <div class="sub">
                  <StatusBox small status={s.status ?? (s.done ? 'done' : 'todo')} label={s.text} onclick={() => toggleSub(s)} />
                  <span class="subtext"><ActionText text={s.text} done={s.closed ?? s.done} /></span>
                  {#if s.due_label}<span class="mono due">{s.due_label}</span>{/if}
                </div>
              {/each}
            </div>
          {/if}
          {#if warn && !closed && left}
            <div class="warn" role="alert">
              Restano {left} aperte.
              <div class="warn-actions">
                <button class="mini primary" onclick={() => { warn = false; completeAll(item); }}>Completa tutte</button>
                <button class="mini" onclick={() => (warn = false)}>Annulla</button>
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>

  <!-- I comandi compaiono sopra la riga al passaggio del mouse o con la tastiera: non occupano una riga loro. -->
  {#if !closed}
    {#if !quick}
      <div class="tools">
        <!-- Un solo pulsante per priorità, stato, date, persone, etichetta, progetto e descrizione. -->
        <button class="q icon" aria-label={aria('Dettagli: priorità, stato, scadenza…')} title="Priorità, stato, scadenza, persona, etichetta, progetto, descrizione" aria-haspopup="dialog" aria-expanded={popKey === key('add')} onclick={(e) => pop(e, item, 'add', 0)}><Icon name="plus" size={13} /></button>
      </div>
    {:else}
      <div class="tools" role="group" aria-label={aria('Azioni rapide')}>
        <button class="q" onclick={() => setScheduled(item, 'oggi')}>Oggi</button>
        <button class="q" onclick={() => setScheduled(item, 'domani')}>Domani</button>
        <button class="q" aria-haspopup="dialog" aria-expanded={popKey === key('status')} onclick={(e) => pop(e, item, 'status', 0)}>Stato</button>
        {#if quick === 'review'}
          <button class="q" onclick={() => setStatus(item, 'cancelled')}>Annulla</button>
          <button class="q" onclick={() => (left ? completeAll(item) : setDone(item, true))}>Chiudi</button>
        {/if}
        <button class="q icon" aria-label="Sposta nel progetto" title="Sposta nel progetto" aria-haspopup="dialog" aria-expanded={popKey === key('move')} onclick={(e) => pop(e, item, 'move', 0)}><Icon name="move" size={12} /></button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .act { position: relative; padding: 10px 14px; }
  .act.card { padding: 9px 12px; border-radius: 10px; background: var(--raised); border: 1px solid var(--border2); }
  .act.stale { box-shadow: inset 3px 0 0 var(--late); }
  .faded { opacity: 0.75; }
  .head { display: flex; gap: 12px; align-items: flex-start; }
  .card .head { gap: 10px; }
  .main { flex: 1; min-width: 0; }
  .parent { font-size: 12px; color: var(--subtle); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .text { font-size: 14.5px; line-height: 1.6; }
  .card .text { font-size: 13.5px; line-height: 1.55; }
  .text .chip, .text .src { margin-left: 6px; }
  .desc { margin-top: 2px; font-size: 13px; line-height: 1.45; color: var(--muted); white-space: pre-line; }
  .card .desc { font-size: 12.5px; }
  .segs { display: inline-flex; gap: 2px; }
  .segs span { width: 8px; height: 5px; border-radius: 1.5px; background: var(--border3); }
  .segs span.on { background: var(--accent); }
  .track { width: 44px; height: 5px; border-radius: 3px; background: var(--border3); overflow: hidden; }
  .track span { display: block; height: 100%; background: var(--accent); }
  .src { display: inline-flex; align-items: center; gap: 4px; max-width: 260px; padding: 0; border: 0; background: transparent; color: var(--subtle); font-size: 12px; vertical-align: middle; }
  .src:hover { color: var(--muted); }
  .clip { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tools { position: absolute; top: 6px; right: 8px; z-index: 1; display: flex; gap: 2px; padding: 2px; border-radius: 8px; background: var(--raised); border: 1px solid var(--border2); opacity: 0; }
  .card .tools { background: var(--hover); }
  .act:hover .tools, .act:focus-within .tools, .tools:has([aria-expanded='true']) { opacity: 1; }
  /* Sugli schermi a tocco i comandi restano sempre visibili, sotto la riga. */
  @media (hover: none) {
    .tools { position: static; width: fit-content; margin: 6px 0 0 30px; opacity: 1; }
  }
  .q { display: flex; align-items: center; height: 22px; padding: 0 7px; border: 0; border-radius: 6px; background: transparent; color: var(--muted); font-size: 11.5px; }
  .q.icon { width: 22px; padding: 0; justify-content: center; }
  .q:hover, .q[aria-expanded='true'] { background: var(--hover); color: var(--text); }
  .subs { margin-top: 6px; }
  .sublist { display: flex; flex-direction: column; gap: 6px; font-size: 13.5px; }
  .card .sublist { padding-top: 8px; border-top: 1px solid var(--border2); font-size: 12.5px; }
  .sub { display: flex; gap: 8px; align-items: flex-start; }
  .subtext { flex: 1; min-width: 0; line-height: 1.4; }
  .due { flex: none; font-size: 11.5px; color: var(--subtle); }
  .warn { margin-top: 8px; padding: 8px 10px; border-radius: 8px; background: var(--hover); font-size: 12.5px; }
  .warn-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .mini { height: 28px; padding: 0 10px; border: 1px solid var(--border3); border-radius: 6px; background: transparent; font-size: 12px; }
  .mini.primary { border: 0; background: var(--accent); color: var(--on-accent); }
</style>
