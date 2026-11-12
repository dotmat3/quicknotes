<script>
  import { app, tagColor } from '../state/app.svelte.js';
  import { openAt } from '../state/layout.svelte.js';
  import { call } from '../api.js';
  import { completeAll, loadBoard, setDone, setScheduled, setStatus } from '../state/actions.svelte.js';
  import { docs, onExternalChange, save } from '../state/documents.svelte.js';
  import ActionText from './ActionText.svelte';
  import StatusBox from './StatusBox.svelte';
  import { PRIORITIES, statusLabel } from '../note/editor/rules.js';
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

  const LEVEL_LOOK = {
    late: 'background:color-mix(in srgb, var(--late) 14%, transparent);color:var(--late)',
    soon: 'background:var(--border2);color:var(--text)',
    normal: 'background:var(--border2);color:var(--muted)',
  };
  const dueLook = $derived(LEVEL_LOOK[item.due_level] ?? LEVEL_LOOK.normal);
  const schedLook = $derived(item.since_days ? LEVEL_LOOK.late : 'background:color-mix(in srgb, var(--accent) 14%, transparent);color:var(--text)');
  const STATUS_COLOR = { doing: 'var(--accent)', waiting: 'var(--person)', question: 'var(--dec)' };
  // L'etichetta solo se è scritta nella riga: quando manca, il server mette lì il progetto, che ha la sua pillola.
  const tag = $derived(item.tag && (item.raw ?? '').toLowerCase().includes(`#${item.tag}`) ? item.tag : null);
  const tc = $derived(tag ? tagColor(tag) : null);
  const prio = $derived(PRIORITIES.find(([p]) => p === item.priority));
  const PRIO_COLOR = { alta: 'var(--late)', media: 'var(--accent)', bassa: 'var(--muted)' };
  const where = $derived(item.project ? `${item.project}${item.area ? ` / ${item.area}` : ''}` : '');
  const key = (kind, idx = 0) => `${item.note_id}:${item.line}:${kind}:${idx}`;
  const aria = (label) => `${label} · ${item.text}`;
  const openNote = () => openAt(`note:${item.note_id}`, item.line, app.titles[`note:${item.note_id}`] ?? item.note_title);
</script>

<div class="act" class:card class:faded={card && closed} class:stale={item.stale}>
  <div class="head">
    <StatusBox {status} label={item.text} onclick={toggle} oncontextmenu={statusMenu} />
    <div class="main">
      {#if item.parent}<div class="parent">↳ {item.parent}</div>{/if}
      <div class="text"><ActionText text={item.text} done={closed} /></div>
      {#if item.description}<div class="desc">{item.description}</div>{/if}

      {#if closed}
        <div class="static">
          {#if status === 'cancelled'}<span>annullata</span>{/if}
          {#if prio}<span>{prio[2]} {prio[0]}</span>{/if}
          {#if tag}<span style="color:var(--faint)">#{tag}</span>{/if}
          {#if item.done_on || item.due_label}<span class="mono">{item.done_on ?? item.due_label}</span>{/if}
        </div>
      {:else}
        <div class="pills">
          {#if status !== 'todo'}
            <button class="pl" style="background:color-mix(in srgb, {STATUS_COLOR[status]} 14%, transparent);color:{STATUS_COLOR[status]}" aria-label={aria(`Stato ${statusLabel(status)}`)} aria-haspopup="dialog" aria-expanded={popKey === key('status')} onclick={(e) => pop(e, item, 'status', 0)}>{statusLabel(status) + (item.waiting_days ? ` · ${item.waiting_days} gg` : '')}</button>
          {/if}
          {#if prio}
            <button class="pl" style="background:color-mix(in srgb, {PRIO_COLOR[prio[0]]} 14%, transparent);color:{PRIO_COLOR[prio[0]]}" aria-label={aria(`Priorità ${prio[0]}`)} aria-haspopup="dialog" aria-expanded={popKey === key('priority')} onclick={(e) => pop(e, item, 'priority', 0)}>{prio[2]} {prio[1]}</button>
          {/if}
          {#if item.scheduled_label}
            <button class="pl" style={schedLook} title="Il giorno in cui farla (scheduled:)" aria-label={aria(`Da fare ${item.scheduled_label}`)} aria-haspopup="dialog" aria-expanded={popKey === key('scheduled')} onclick={(e) => pop(e, item, 'scheduled', 0)}>{`◷ ${item.scheduled_label}${item.since_days ? ` · da ${item.since_days} gg` : ''}`}</button>
          {/if}
          {#if item.due_label}
            <button class="pl" style={dueLook} title="Scadenza (due:)" aria-label={aria(`Scadenza ${item.due_label}`)} aria-haspopup="dialog" aria-expanded={popKey === key('due')} onclick={(e) => pop(e, item, 'due', 0)}>{item.due_label}</button>
          {/if}
          {#each item.people as w, i (w)}
            <button class="pl" style="background:color-mix(in srgb, var(--person) 14%, transparent);color:var(--person)" aria-label={aria(`Persona ${w}`)} aria-haspopup="dialog" aria-expanded={popKey === key('person', i)} onclick={(e) => pop(e, item, 'person', i)}>@{w}</button>
          {/each}
          {#if tag}
            <button class="pl" style="background:color-mix(in srgb, {tc} 14%, transparent);color:{tc}" aria-label={aria(`Etichetta ${tag}`)} aria-haspopup="dialog" aria-expanded={popKey === key('tag')} onclick={(e) => pop(e, item, 'tag', 0)}>#{tag}</button>
          {/if}
          {#if where && where !== tag}
            <button class="pl" style="background:var(--border2);color:var(--muted)" title="Progetto e area" aria-label={aria(`Progetto ${where}`)} aria-haspopup="dialog" aria-expanded={popKey === key('move')} onclick={(e) => pop(e, item, 'move', 0)}><Icon name="folder" size={11} style="vertical-align:-1px;margin-right:3px" />{where}</button>
          {/if}
          {#if item.description}
            <button class="pl" style="background:var(--border2);color:var(--muted)" aria-label={aria('Modifica la descrizione')} aria-haspopup="dialog" aria-expanded={popKey === key('description')} onclick={(e) => pop(e, item, 'description', 0)}>Descrizione</button>
          {/if}
        </div>
      {/if}

      {#if item.subs.length}
        <div class="subs">
          <button class="progress" aria-expanded={subsOpen} onclick={() => (subsOpen = !subsOpen)}>
            <Icon name="right" size={12} style="transition:transform .12s;transform:rotate({subsOpen ? 90 : 0}deg)" />
            <span class="mono">{nDone} di {item.subs.length}</span>
            <span class="track" aria-hidden="true"><span style="width:{(nDone / item.subs.length) * 100}%"></span></span>
          </button>
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
          {#if !closed && !left}
            <button class="mini all" onclick={() => setDone(item, true)}>Tutte fatte · Chiudi l’azione</button>
          {/if}
        </div>
      {/if}

      {#if !quick}
        <div class="foot">
          <button class="src" onclick={openNote}>
            <Icon name="note" size={12} /><span class="clip">{item.note_title}</span>
          </button>
          <!-- Un solo pulsante per priorità, stato, date, persone, etichetta, progetto e descrizione: sta nella riga
               della nota, quindi non allunga la scheda. -->
          {#if !closed}
            <button class="more" aria-label={aria('Dettagli: priorità, stato, scadenza…')} title="Priorità, stato, scadenza, persona, etichetta, progetto, descrizione" aria-haspopup="dialog" aria-expanded={popKey === key('add')} onclick={(e) => pop(e, item, 'add', 0)}><Icon name="plus" size={13} /></button>
          {/if}
        </div>
      {:else}
        <!-- Agenda e Revisione: la nota a sinistra (cliccandola si apre), le azioni rapide a destra sulla stessa
             riga, visibili al passaggio del mouse o con la tastiera. -->
        <div class="foot">
          <button class="src" title="Apri la nota" onclick={openNote}>
            <Icon name="note" size={12} /><span class="clip">{item.note_title + (item.age_days > 1 ? ` · da ${item.age_days} gg` : '')}</span>
          </button>
          {#if !closed}
            <div class="quick" role="group" aria-label={aria('Azioni rapide')}>
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
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .act { padding: 12px 14px; }
  .act.card { padding: 10px 12px; border-radius: 10px; background: var(--raised); border: 1px solid var(--border2); }
  .act.stale { box-shadow: inset 3px 0 0 var(--late); }
  .faded { opacity: 0.75; }
  .head { display: flex; gap: 12px; align-items: flex-start; }
  .card .head { gap: 10px; }
  .main { flex: 1; min-width: 0; }
  .parent { font-size: 12px; color: var(--subtle); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .text { font-size: 14.5px; line-height: 1.5; }
  .card .text { font-size: 13.5px; line-height: 1.45; }
  .desc { margin-top: 2px; font-size: 13px; line-height: 1.45; color: var(--muted); white-space: pre-line; }
  .card .desc { font-size: 12.5px; }
  .pills { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
  .pl { height: 26px; padding: 0 9px; border: 0; border-radius: 999px; font-size: 12px; white-space: nowrap; }
  .pills:not(:has(*)) { display: none; }
  .foot { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
  .foot .src { flex: 1; min-width: 0; margin-top: 0; }
  .clip { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .more { flex: none; display: grid; place-items: center; width: 22px; height: 22px; padding: 0; border: 1px dashed var(--border3); border-radius: 6px; background: transparent; color: var(--muted); opacity: 0; }
  .more:hover, .more[aria-expanded='true'] { border-style: solid; background: var(--hover); color: var(--text); }
  /* Il + compare al passaggio del mouse o con la tastiera; sugli schermi a tocco resta sempre. */
  .act:hover .more, .act:focus-within .more, .more[aria-expanded='true'] { opacity: 1; }
  @media (hover: none) { .more { opacity: 1; } }
  .quick { flex: none; display: flex; gap: 2px; opacity: 0; }
  .act:hover .quick, .act:focus-within .quick, .quick:has([aria-expanded='true']) { opacity: 1; }
  @media (hover: none) { .quick { opacity: 1; } }
  .q { display: flex; align-items: center; height: 22px; padding: 0 7px; border: 0; border-radius: 6px; background: transparent; color: var(--muted); font-size: 11.5px; }
  .q.icon { width: 22px; padding: 0; justify-content: center; }
  .q:hover, .q[aria-expanded='true'] { background: var(--hover); color: var(--text); }
  .static { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 3px; font-size: 12px; color: var(--subtle); }
  .subs { margin-top: 8px; }
  .progress { display: flex; align-items: center; gap: 8px; width: 100%; padding: 0; border: 0; background: transparent; color: var(--muted); font-size: 12px; text-align: left; }
  .track { flex: 1; height: 4px; border-radius: 2px; background: var(--border2); overflow: hidden; }
  .track span { display: block; height: 100%; background: var(--accent); }
  .sublist { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; font-size: 13.5px; }
  .card .sublist { padding-top: 8px; border-top: 1px solid var(--border2); font-size: 12.5px; }
  .sub { display: flex; gap: 8px; align-items: flex-start; }
  .subtext { flex: 1; min-width: 0; line-height: 1.4; }
  .due { flex: none; font-size: 11.5px; color: var(--subtle); }
  .warn { margin-top: 8px; padding: 8px 10px; border-radius: 8px; background: var(--hover); font-size: 12.5px; }
  .warn-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .mini { height: 28px; padding: 0 10px; border: 1px solid var(--border3); border-radius: 6px; background: transparent; font-size: 12px; }
  .mini.primary { border: 0; background: var(--accent); color: var(--on-accent); }
  .mini.all { margin-top: 8px; }
  .card .mini.all { width: 100%; }
  .src { display: flex; align-items: center; gap: 4px; margin-top: 8px; padding: 0; border: 0; background: transparent; color: var(--subtle); font-size: 12px; text-align: left; }
  .src:hover { color: var(--muted); }
</style>
