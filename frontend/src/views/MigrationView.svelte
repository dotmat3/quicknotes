<script>
  import { call } from '../api.js';
  import { loadBoard } from '../state/actions.svelte.js';
  import { app, refreshCounts, showToast } from '../state/app.svelte.js';
  import { onExternalChange, saveAll } from '../state/documents.svelte.js';
  import { openAt, openPage } from '../state/layout.svelte.js';
  import Icon from '../shell/Icon.svelte';

  // Porta le note scritte prima dei progetti al formato nuovo. Si vede tutto prima: progetti proposti dalle
  // note, righe da cambiare regola per regola. Nulla si scrive finché non si preme Applica, e prima si copia la cartella.
  let plan = $state(null);
  let error = $state('');
  let busy = $state(false);
  let result = $state(null);
  // Scelte: per progetto (chiave proposta) { on, title, status, areas }, per riga l'id.
  let picks = $state({});
  let chosen = $state(new Set());
  let expanded = $state({});

  async function load() {
    try {
      plan = await call('migration_plan');
      error = '';
    } catch (e) {
      error = String(e);
      return;
    }
    picks = Object.fromEntries(plan.projects.map((p) => [p.key, { on: p.selected, title: p.title, status: p.status, areas: p.areas.filter((a) => a.selected).map((a) => a.name) }]));
    const rules = new Set(plan.rules.filter((r) => r.default).map((r) => r.key));
    chosen = new Set(plan.edits.filter((e) => rules.has(e.rule)).map((e) => e.id));
  }
  load();

  // Le righe "etichetta ripetuta" valgono solo se il loro progetto esiste o viene creato.
  const projectKeys = $derived(new Set([...(plan?.existing ?? []).map((p) => p.key), ...Object.entries(picks).filter(([, v]) => v.on).map(([k]) => k)]));
  const valid = (e) => !e.project || projectKeys.has(e.project);
  const selectedEdits = $derived((plan?.edits ?? []).filter((e) => chosen.has(e.id) && valid(e)));
  const selectedProjects = $derived(Object.entries(picks).filter(([, v]) => v.on && v.title.trim()));
  const files = $derived(new Set(selectedEdits.map((e) => e.rel)).size);
  const nothing = $derived(plan && !plan.projects.length && !plan.edits.length);

  function toggle(id) {
    const next = new Set(chosen);
    next.has(id) ? next.delete(id) : next.add(id);
    chosen = next;
  }

  function toggleRule(rule, on) {
    const next = new Set(chosen);
    for (const e of plan.edits) if (e.rule === rule) on ? next.add(e.id) : next.delete(e.id);
    chosen = next;
  }

  function toggleArea(key, name) {
    const p = picks[key];
    p.areas = p.areas.includes(name) ? p.areas.filter((a) => a !== name) : [...p.areas, name];
  }

  const ruleEdits = (rule) => plan.edits.filter((e) => e.rule === rule);
  const ruleOn = (rule) => ruleEdits(rule).filter((e) => chosen.has(e.id)).length;
  const when = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : '—');
  const SOURCES = { heading: 'intestazione dei daily', tag: 'etichetta' };

  function ask() {
    const n = selectedProjects.length;
    app.confirm = {
      title: 'Applicare la migrazione?',
      text: `Prima si copia tutta la cartella delle note, accanto a lei (${plan.root}-copia-…). Poi si ${n ? `creano ${n} ${n === 1 ? 'progetto' : 'progetti'} e si ` : ''}cambiano ${selectedEdits.length} ${selectedEdits.length === 1 ? 'riga' : 'righe'} in ${files} ${files === 1 ? 'nota' : 'note'}.`,
      ok: 'Applica',
      run: apply,
    };
  }

  async function apply() {
    busy = true;
    // Le modifiche in sospeso nell'editor vanno scritte prima: ogni riga si confronta con il file.
    await saveAll();
    const choices = {
      projects: selectedProjects.map(([key, v]) => {
        const p = plan.projects.find((x) => x.key === key);
        // Se il titolo è cambiato, quello trovato nelle note resta come alias: le intestazioni continuano a valere.
        const aliases = v.title.trim() !== p.title ? [p.title] : [];
        return { title: v.title.trim(), from_key: key, status: v.status, areas: v.areas, aliases };
      }),
      edits: selectedEdits.map((e) => ({ id: e.id, before: e.before })),
    };
    try {
      result = await call('migration_apply', { choices });
      await onExternalChange(result.changed);
      await Promise.all([refreshCounts(), loadBoard()]);
      await load();
    } catch (e) {
      showToast(String(e));
    }
    busy = false;
  }
</script>

<div class="head">
  <div class="kicker">Migrazione</div>
  <h1>Porta le note al formato con progetti</h1>
  <p class="sum">Stati delle azioni, note di progetto, etichette ripetute. Rivedi la proposta: nulla cambia finché non premi Applica, e prima si fa una copia della cartella.</p>
</div>

{#if result}
  <div class="done" role="status">
    <Icon name="check" size={16} />
    <div class="grow">
      <strong>Fatto.</strong> {result.projects.length} {result.projects.length === 1 ? 'progetto creato' : 'progetti creati'}, {result.applied} {result.applied === 1 ? 'riga cambiata' : 'righe cambiate'}{result.skipped.length ? `, ${result.skipped.length} saltate perché cambiate nel frattempo` : ''}.
      {#if result.backup}<div class="mono path">Copia: {result.backup}</div>{/if}
    </div>
    {#if result.backup}<button class="btn" onclick={() => call('open_backup').catch((e) => showToast(String(e)))}>Apri la copia</button>{/if}
    <button class="btn" onclick={() => openPage('view:agenda')}>Agenda</button>
  </div>
{/if}

{#if error}
  <p class="none">{error}</p>
{:else if !plan}
  <p class="none">Leggo le note…</p>
{:else if nothing}
  <p class="none">Niente da migrare in {plan.notes} note{plan.existing.length ? `: i progetti ${plan.existing.map((p) => p.title).join(', ')} esistono già` : ''}.</p>
{:else}
  <section class="step">
    <h2><span class="num">1</span>Progetti da creare <span class="n mono">{selectedProjects.length} di {plan.projects.length}</span></h2>
    <p class="hint">Proposti dalle intestazioni dei daily e dalle etichette usate fuori da un progetto. Ognuno diventa una nota in <span class="mono">progetti/</span>; le aree sono le etichette usate nelle sue azioni.</p>
    {#if plan.existing.length}<p class="hint">Già presenti: {plan.existing.map((p) => p.title).join(', ')}.</p>{/if}
    {#each plan.projects as p (p.key)}
      {@const v = picks[p.key]}
      <div class="proj" class:off={!v.on}>
        <input type="checkbox" aria-label="Crea il progetto {p.title}" bind:checked={picks[p.key].on} />
        <div class="grow">
          <div class="line">
            <input class="title" type="text" aria-label="Titolo del progetto" bind:value={picks[p.key].title} disabled={!v.on} />
            <select aria-label="Stato di {p.title}" bind:value={picks[p.key].status} disabled={!v.on}>
              <option value="attivo">Attivo</option><option value="pausa">In pausa</option><option value="chiuso">Chiuso</option>
            </select>
          </div>
          <div class="meta">{p.actions} {p.actions === 1 ? 'azione' : 'azioni'} ({p.open} aperte){p.lines ? ` · ${p.lines} ${p.lines === 1 ? 'riga' : 'righe'} di log` : ''} in {p.notes} {p.notes === 1 ? 'nota' : 'note'} · ultima {when(p.last)} · da {p.sources.map((s) => SOURCES[s]).join(' e ')}{p.idle_days > 30 ? ` · ferma da ${p.idle_days} giorni` : ''}</div>
          {#if p.areas.length}
            <div class="areas" role="group" aria-label="Aree di {p.title}">
              <span class="al">Aree</span>
              {#each p.areas as a (a.name)}
                <button class="chip" class:on={v.areas.includes(a.name)} aria-pressed={v.areas.includes(a.name)} disabled={!v.on} onclick={() => toggleArea(p.key, a.name)}>{a.name}<span class="mono c">{a.count}</span></button>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    {:else}
      <p class="hint">Nessun progetto da proporre.</p>
    {/each}
  </section>

  <section class="step">
    <h2><span class="num">2</span>Righe da cambiare <span class="n mono">{selectedEdits.length} di {plan.edits.length}</span></h2>
    <p class="hint">Cambia solo il segno nella casella o l’etichetta indicata: il resto della riga, il frontmatter e gli a capo restano com’erano.</p>
    {#each plan.rules as r (r.key)}
      {@const list = ruleEdits(r.key)}
      <div class="rule">
        <label class="rule-head">
          <input type="checkbox" checked={list.length > 0 && ruleOn(r.key) === list.length} indeterminate={ruleOn(r.key) > 0 && ruleOn(r.key) < list.length} disabled={!list.length} onchange={(e) => toggleRule(r.key, e.target.checked)} />
          <span class="grow"><span class="rt">{r.title}</span> <span class="mono n">{ruleOn(r.key)} di {list.length}</span><span class="rd">{r.description}{r.default ? '' : ' Non attiva di default.'}</span></span>
        </label>
        {#each expanded[r.key] ? list : list.slice(0, 6) as e (e.id)}
          <div class="edit" class:off={!valid(e)}>
            <input type="checkbox" aria-label="Cambia la riga {e.line} di {e.note_title}" checked={chosen.has(e.id) && valid(e)} disabled={!valid(e)} onchange={() => toggle(e.id)} />
            <div class="grow">
              <button class="where" onclick={() => openAt(`note:${e.note_id}`)}>{e.note_title} <span class="mono">· riga {e.line}</span></button>
              <div class="diff mono"><span class="del">{e.before.trim()}</span><span class="ins">{e.after.trim()}</span></div>
              {#if !valid(e)}<div class="warn">Vale solo se crei il progetto {e.project}.</div>{/if}
            </div>
          </div>
        {/each}
        {#if list.length > 6}
          <button class="more" onclick={() => (expanded[r.key] = !expanded[r.key])}>{expanded[r.key] ? 'Mostra meno' : `Mostra tutte (${list.length})`}</button>
        {/if}
      </div>
    {/each}
  </section>

  <div class="finish">
    <span class="grow sum2">{selectedProjects.length} {selectedProjects.length === 1 ? 'progetto' : 'progetti'} · {selectedEdits.length} {selectedEdits.length === 1 ? 'riga' : 'righe'} in {files} {files === 1 ? 'nota' : 'note'}. Prima si copia la cartella delle note.</span>
    <button class="btn primary" disabled={busy || (!selectedProjects.length && !selectedEdits.length)} onclick={ask}><Icon name="check" size={14} />{busy ? 'Applico…' : 'Applica'}</button>
  </div>
{/if}

<style>
  .head { margin-bottom: 14px; }
  .kicker { font-size: 12.5px; color: var(--subtle); }
  .sum { margin: 6px 0 0; max-width: 720px; font-size: 13.5px; line-height: 1.5; color: var(--subtle); }
  .done { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; margin: 10px 0 6px; padding: 12px 14px; border-radius: 12px; border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent); background: color-mix(in srgb, var(--accent) 8%, transparent); font-size: 13.5px; }
  .path { margin-top: 2px; font-size: 11.5px; color: var(--subtle); overflow-wrap: anywhere; }
  .step { margin-top: 22px; }
  h2 { display: flex; align-items: center; gap: 10px; margin: 0 0 6px; font-size: 15px; font-weight: 600; }
  .num { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--border2); font-size: 11.5px; color: var(--muted); }
  .n { font-size: 12px; font-weight: 400; color: var(--subtle); }
  .hint { margin: 0 0 8px; font-size: 12.5px; color: var(--subtle); }
  .proj { display: flex; gap: 12px; align-items: flex-start; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); }
  .proj + .proj { margin-top: 8px; }
  .proj.off { opacity: 0.6; }
  input[type='checkbox'] { flex: none; width: 16px; height: 16px; margin-top: 3px; accent-color: var(--accent); }
  .grow { flex: 1; min-width: 0; }
  .line { display: flex; flex-wrap: wrap; gap: 8px; }
  .title { flex: 1 1 220px; min-width: 0; height: 32px; padding: 0 10px; border: 1px solid var(--border2); border-radius: 8px; background: var(--surface); color: var(--text); font: inherit; font-size: 14px; font-weight: 600; }
  select { height: 32px; padding: 0 8px; border: 1px solid var(--border2); border-radius: 8px; background: var(--raised); color: var(--text); font: inherit; font-size: 12.5px; }
  .meta { margin-top: 6px; font-size: 12px; color: var(--subtle); }
  .areas { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
  .al { font-size: 12px; color: var(--subtle); }
  .chip { display: flex; align-items: center; gap: 5px; height: 26px; padding: 0 10px; border: 1px dashed var(--border3); border-radius: 999px; background: transparent; color: var(--muted); font-size: 12px; }
  .chip.on { border-style: solid; background: var(--border2); color: var(--text); }
  .c { font-size: 10.5px; opacity: 0.7; }
  .rule { margin-top: 10px; padding: 10px 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); }
  .rule-head { display: flex; gap: 12px; align-items: flex-start; cursor: pointer; }
  .rt { font-size: 14px; font-weight: 600; }
  .rd { display: block; margin-top: 2px; font-size: 12.5px; color: var(--subtle); }
  .edit { display: flex; gap: 12px; align-items: flex-start; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); }
  .edit.off { opacity: 0.55; }
  .where { padding: 0; border: 0; background: transparent; color: var(--muted); font-size: 12.5px; text-align: left; }
  .where:hover { color: var(--text); }
  .diff { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; font-size: 12px; }
  .diff span { padding: 2px 8px; border-radius: 5px; white-space: pre-wrap; overflow-wrap: anywhere; }
  .del { background: color-mix(in srgb, var(--late) 10%, transparent); color: var(--muted); text-decoration: line-through; }
  .ins { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--text); }
  .warn { margin-top: 4px; font-size: 12px; color: var(--subtle); }
  .more { margin-top: 8px; padding: 0; border: 0; background: transparent; color: var(--muted); font-size: 12.5px; }
  .finish { position: sticky; bottom: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-top: 20px; padding: 12px 0; background: var(--surface); border-top: 1px solid var(--border); }
  .sum2 { font-size: 13px; color: var(--muted); }
  .btn:disabled { opacity: 0.5; }
  .none { padding: 40px 0; text-align: center; color: var(--subtle); }
</style>
