<script>
  import { app, tagColor } from '../state/app.svelte.js';
  import { openPage } from '../state/layout.svelte.js';
  import { call } from '../api.js';
  import { completeAll, loadBoard, setDone } from '../state/actions.svelte.js';
  import { docs, onExternalChange, save } from '../state/documents.svelte.js';
  import ActionText from './ActionText.svelte';
  import Icon from '../shell/Icon.svelte';

  // `pop` apre il popover unico della vista: sta fuori dalle colonne, che lo taglierebbero.
  let { item, card = false, pop, popKey } = $props();

  let subsOpen = $state(true);
  let warn = $state(false);

  const nDone = $derived(item.subs.filter((s) => s.done).length);
  const left = $derived(item.subs.length - nDone);

  function toggle() {
    if (!item.done && left) {
      warn = true;
      subsOpen = true;
    } else {
      setDone(item, !item.done);
    }
  }

  async function toggleSub(s) {
    if (docs[item.note_id]) await save(item.note_id);
    await call('set_action_done', { noteId: item.note_id, line: s.line, text: s.raw, done: !s.done });
    await onExternalChange([item.note_id]);
    warn = false;
    await loadBoard();
  }

  const dueLook = $derived(item.due_level === 'late' ? 'background:color-mix(in srgb, var(--late) 14%, transparent);color:var(--late)' : item.due_level === 'soon' ? 'background:var(--border2);color:var(--text)' : 'background:var(--border2);color:var(--muted)');
  const tc = $derived(item.tag ? tagColor(item.tag) : null);
  const key = (kind, idx = 0) => `${item.note_id}:${item.line}:${kind}:${idx}`;
  const aria = (label) => `${label} · ${item.text}`;
</script>

<div class="act" class:card class:faded={card && item.done}>
  <div class="head">
    <button class="box" class:on={item.done} role="checkbox" aria-checked={item.done} aria-label={item.text} onclick={toggle}>
      {#if item.done}<Icon name="check" size={11} style="stroke-width:3" />{/if}
    </button>
    <div class="main">
      <div class="text"><ActionText text={item.text} done={item.done} /></div>
      {#if item.description}<div class="desc">{item.description}</div>{/if}

      {#if item.done}
        <div class="static">
          {#if item.tag}<span style="color:var(--faint)">#{item.tag}</span>{/if}
          {#if item.done_on || item.due_label}<span class="mono">{item.done_on ?? item.due_label}</span>{/if}
        </div>
      {:else}
        <div class="pills">
          {#if item.due_label}
            <button class="pl" style={dueLook} aria-label={aria(`Scadenza ${item.due_label}`)} aria-haspopup="dialog" aria-expanded={popKey === key('due')} onclick={(e) => pop(e, item, 'due', 0)}>{item.due_label}</button>
          {/if}
          {#each item.people as w, i (w)}
            <button class="pl" style="background:color-mix(in srgb, var(--person) 14%, transparent);color:var(--person)" aria-label={aria(`Persona ${w}`)} aria-haspopup="dialog" aria-expanded={popKey === key('person', i)} onclick={(e) => pop(e, item, 'person', i)}>@{w}</button>
          {/each}
          {#if item.tag}
            <button class="pl" style="background:color-mix(in srgb, {tc} 14%, transparent);color:{tc}" aria-label={aria(`Etichetta ${item.tag}`)} aria-haspopup="dialog" aria-expanded={popKey === key('tag')} onclick={(e) => pop(e, item, 'tag', 0)}>#{item.tag}</button>
          {/if}
          {#if item.description}
            <button class="pl" style="background:var(--border2);color:var(--muted)" aria-label={aria('Modifica la descrizione')} aria-haspopup="dialog" aria-expanded={popKey === key('description')} onclick={(e) => pop(e, item, 'description', 0)}>Descrizione</button>
          {/if}
          {#if !item.due_label}<button class="pl add" aria-label={aria('Aggiungi una scadenza')} aria-haspopup="dialog" aria-expanded={popKey === key('due')} onclick={(e) => pop(e, item, 'due', 0)}>+ scadenza</button>{/if}
          <button class="pl add" aria-label={aria('Aggiungi una persona')} aria-haspopup="dialog" aria-expanded={popKey === key('person', item.people.length)} onclick={(e) => pop(e, item, 'person', item.people.length)}>+ persona</button>
          {#if !item.tag}<button class="pl add" aria-label={aria('Aggiungi un’etichetta')} aria-haspopup="dialog" aria-expanded={popKey === key('tag')} onclick={(e) => pop(e, item, 'tag', 0)}>+ etichetta</button>{/if}
          {#if !item.description}<button class="pl add" aria-label={aria('Aggiungi una descrizione')} aria-haspopup="dialog" aria-expanded={popKey === key('description')} onclick={(e) => pop(e, item, 'description', 0)}>+ descrizione</button>{/if}
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
                  <button class="box small" class:on={s.done} role="checkbox" aria-checked={s.done} aria-label={s.text} onclick={() => toggleSub(s)}>
                    {#if s.done}<Icon name="check" size={10} style="stroke-width:3" />{/if}
                  </button>
                  <span class="subtext"><ActionText text={s.text} done={s.done} /></span>
                  {#if s.due_label}<span class="mono due">{s.due_label}</span>{/if}
                </div>
              {/each}
            </div>
          {/if}
          {#if warn && !item.done && left}
            <div class="warn" role="alert">
              Restano {left} aperte.
              <div class="warn-actions">
                <button class="mini primary" onclick={() => { warn = false; completeAll(item); }}>Completa tutte</button>
                <button class="mini" onclick={() => (warn = false)}>Annulla</button>
              </div>
            </div>
          {/if}
          {#if !item.done && !left}
            <button class="mini all" onclick={() => setDone(item, true)}>Tutte fatte · Chiudi l’azione</button>
          {/if}
        </div>
      {/if}

      <button class="src" onclick={() => openPage(`note:${item.note_id}`, app.titles[`note:${item.note_id}`] ?? item.note_title)}>
        <Icon name="note" size={12} />{item.note_title}
      </button>
    </div>
  </div>
</div>

<style>
  .act { padding: 12px 14px; }
  .act.card { padding: 10px 12px; border-radius: 10px; background: var(--raised); border: 1px solid var(--border2); }
  .faded { opacity: 0.75; }
  .head { display: flex; gap: 12px; align-items: flex-start; }
  .card .head { gap: 10px; }
  .box { flex: none; width: 18px; height: 18px; margin-top: 0.5px; padding: 0; border-radius: 5px; display: flex; align-items: center; justify-content: center; border: 1.5px solid var(--faint); background: transparent; }
  .box.on { border: 0; background: var(--accent); color: var(--on-accent); }
  .box.small { width: 15px; height: 15px; margin-top: 1px; border-radius: 4px; }
  .main { flex: 1; min-width: 0; }
  .text { font-size: 14.5px; line-height: 1.5; }
  .card .text { font-size: 13.5px; line-height: 1.45; }
  .desc { margin-top: 2px; font-size: 13px; line-height: 1.45; color: var(--muted); white-space: pre-line; }
  .card .desc { font-size: 12.5px; }
  .pills { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
  .pl { height: 26px; padding: 0 9px; border: 0; border-radius: 999px; font-size: 12px; white-space: nowrap; }
  .add { border: 1px dashed var(--border3); background: transparent; color: var(--muted); opacity: 0; }
  /* I + compaiono al passaggio del mouse o con la tastiera: con molte schede coprirebbero il contenuto. */
  .act:hover .add, .act:focus-within .add, .add[aria-expanded='true'] { opacity: 1; }
  @media (hover: none) { .add { opacity: 1; } }
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
