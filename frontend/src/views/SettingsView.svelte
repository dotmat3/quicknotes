<script>
  import { call } from '../api.js';
  import { app, savePrefs, setTheme, showToast, tagColor, theme } from '../state/app.svelte.js';
  import { applyLayout, layout, openPage } from '../state/layout.svelte.js';
  import { TAG_PALETTE, THEMES, applyTheme, resolveTheme, tagColorId } from '../theme/themes.js';
  import { VIEWS } from '../shell/nav.js';
  import Icon from '../shell/Icon.svelte';
  import SettingRow from './SettingRow.svelte';

  const TABS = [['aspetto', 'Aspetto'], ['navigazione', 'Navigazione'], ['azioni', 'Azioni'], ['etichette', 'Etichette'], ['note', 'Note e registrazione'], ['claude', 'Claude'], ['info', 'Informazioni']];
  const tab = $derived(app.settingsTab ?? 'aspetto');

  let tags = $state([]);
  let claude = $state(null);
  let notes = $state(null);
  let dragKey = $state(null);
  let copied = $state('');
  let info = $state(null); // { version, releases, autostart }

  $effect(() => {
    if (tab === 'etichette') call('all_tags', {}, []).then((t) => (tags = t));
    if (tab === 'claude' && !claude) call('claude_config').then((c) => (claude = c));
    if (tab === 'note' && !notes) call('notes_settings').then((n) => (notes = n));
    if (tab === 'info' && !info) call('app_info', {}, null).then((i) => (info = i));
  });

  async function setAutostart(on) {
    try {
      await call('set_autostart', { on });
      info.autostart = on;
    } catch (e) {
      showToast(String(e));
    }
  }

  // Le scelte della registrazione vanno in config.json con le chiavi della versione precedente.
  async function setNotes(field, key, value) {
    const before = notes[field];
    notes[field] = value;
    try {
      await call('set_notes_setting', { key, value });
    } catch (e) {
      notes[field] = before;
      showToast(String(e));
    }
  }

  const W3 = [['leggibile', 'Leggibile'], ['ampia', 'Ampia'], ['intera', 'Intera']];

  function set(key, value) {
    app[key] = value;
    savePrefs();
  }

  const themeCards = $derived([
    { id: 'auto', name: 'Automatico', sub: 'segue il sistema', t: resolveTheme('auto').t, accent: resolveTheme('auto').accent },
    ...Object.entries(THEMES).map(([id, th]) => ({ id, name: th.name, sub: th.dark ? 'scuro' : 'chiaro', t: th.t, accent: th.accent })),
    { id: 'custom', name: 'Personalizzato', sub: 'i tuoi colori', t: resolveTheme('custom', app.custom).t, accent: resolveTheme('custom', app.custom).accent },
  ]);
  const isAuto = (id) => !['custom', ...Object.keys(THEMES)].includes(id);
  const selectedTheme = $derived(isAuto(app.themeId) ? 'auto' : app.themeId);

  function setCustom(key, value) {
    const cur = resolveTheme(app.themeId, app.custom);
    app.custom = { base: cur.dark ? 'scuro' : 'chiaro', accent: cur.accent, chrome: cur.t.chrome, surface: cur.t.surface, text: cur.t.text, ...(app.custom ?? {}), [key]: value };
    app.themeId = 'custom';
    applyTheme(resolveTheme('custom', app.custom));
    savePrefs();
  }

  function pickTheme(id) {
    if (id === 'custom' && !app.custom) setCustom('base', theme.current.dark ? 'scuro' : 'chiaro');
    else setTheme(id);
  }

  function reorder(from, to) {
    if (!from || from === to) return;
    const o = app.viewOrder.filter((k) => k !== from);
    const at = o.indexOf(to);
    o.splice(app.viewOrder.indexOf(from) < app.viewOrder.indexOf(to) ? at + 1 : at, 0, from);
    set('viewOrder', o);
  }

  function pickTag(tag, id) {
    app.tagColors = { ...app.tagColors, [tag]: id };
    savePrefs();
  }

  function reset() {
    Object.assign(app, { custom: null, side: 'open', showPins: true, noteW: 'leggibile', viewW: 'intera', actView: 'bacheca', actGroup: 'scadenza', boardDone: true, tagColors: {} });
    setTheme('auto');
  }

  async function copy(key, text) {
    await navigator.clipboard.writeText(text);
    copied = key;
    setTimeout(() => (copied = ''), 1500);
  }

  const layoutKey = $derived(layout.groups.length === 1 ? '1' : `${layout.groups.length}${layout.dir === 'col' ? 'r' : 'c'}`);
</script>

{#snippet seg(label, options, current, pick)}
  <div class="seg" role="radiogroup" aria-label={label}>
    {#each options as [v, text] (v)}
      <button role="radio" aria-checked={current === v} class:on={current === v} onclick={() => pick(v)}>{text}</button>
    {/each}
  </div>
{/snippet}

{#snippet toggle(label, on, flip)}
  <button class="switch" class:on role="switch" aria-checked={on} aria-label={label} onclick={flip}><span></span></button>
{/snippet}

<div class="head"><h1>Impostazioni</h1><button class="btn" onclick={reset}>Ripristina predefiniti</button></div>

<div class="tabs" role="tablist" aria-label="Categorie">
  {#each TABS as [k, label] (k)}
    <button role="tab" aria-selected={tab === k} class:on={tab === k} onclick={() => (app.settingsTab = k)}>{label}</button>
  {/each}
</div>

{#if tab === 'aspetto'}
  <section>
    <h2>Tema <span class="note">Si applica subito a tutta l’app</span></h2>
    <div class="themes" role="radiogroup" aria-label="Tema">
      {#each themeCards as c (c.id)}
        <button class="theme" class:on={selectedTheme === c.id} role="radio" aria-checked={selectedTheme === c.id} onclick={() => pickTheme(c.id)}>
          <span class="prev" aria-hidden="true" style="background:{c.t.chrome};border-color:{c.t.border}">
            <span class="pside"><i style="background:{c.accent};width:9px;height:9px;border-radius:3px"></i><i style="background:{c.t.muted};opacity:.55;height:4px;width:80%;border-radius:2px"></i><i style="background:{c.t.muted};opacity:.35;height:4px;width:60%;border-radius:2px"></i></span>
            <span class="pmain" style="background:{c.t.surface};border-color:{c.t.border}"><i style="background:{c.t.text};height:5px;width:55%;border-radius:2px"></i><i style="background:{c.t.muted};opacity:.6;height:4px;width:85%;border-radius:2px"></i><i style="background:{c.accent};opacity:.85;height:8px;width:34%;border-radius:4px"></i></span>
          </span>
          <span class="tname"><span class="grow"><b>{c.name}</b><small>{c.sub}</small></span>{#if selectedTheme === c.id}<Icon name="check" style="color:var(--accent)" />{/if}</span>
        </button>
      {/each}
    </div>
    {#if app.themeId === 'custom'}
      <div class="box custom">
        {#each [['accent', 'Accento', resolveTheme('custom', app.custom).accent], ['chrome', 'Sfondo', resolveTheme('custom', app.custom).t.chrome], ['surface', 'Contenuto', resolveTheme('custom', app.custom).t.surface], ['text', 'Testo', resolveTheme('custom', app.custom).t.text]] as [k, label, val] (k)}
          <label class="row"><span class="rtext rl">{label}</span><input type="color" value={val} onchange={(e) => setCustom(k, e.target.value)} /><span class="mono hex">{val.toUpperCase()}</span></label>
        {/each}
      </div>
    {/if}
  </section>
  <section>
    <h2>Aspetto</h2>
    <div class="box">
      <SettingRow label="Larghezza delle note" desc="Note del giorno e documenti.">{@render seg('Larghezza delle note', W3, app.noteW, (v) => set('noteW', v))}</SettingRow>
      <SettingRow label="Larghezza delle viste" desc="Calendario, Azioni, Persone e Grafo.">{@render seg('Larghezza delle viste', W3, app.viewW, (v) => set('viewW', v))}</SettingRow>
    </div>
  </section>
{:else if tab === 'navigazione'}
  <section>
    <h2>Barra laterale</h2>
    <div class="box">
      <SettingRow label="Stato" desc="Espansa è il predefinito. Si cambia anche con Ctrl \.">{@render seg('Stato', [['open', 'Espansa'], ['closed', 'Compressa']], app.side, (v) => set('side', v))}</SettingRow>
      <SettingRow label="Mostra i preferiti" desc="Note, persone ed etichette segnate con la stella.">{@render toggle('Mostra i preferiti', app.showPins, () => set('showPins', !app.showPins))}</SettingRow>
    </div>
  </section>
  <section>
    <h2>Viste in barra laterale <span class="note">Trascina per riordinare · le nascoste restano in Ctrl K</span></h2>
    <div class="box" role="list">
      <div class="vrow fixed" role="listitem"><Icon name="today" /><span class="grow">Oggi</span><span class="vfix">fissa</span></div>
      {#each app.viewOrder as k (k)}
        {@const on = app.viewVis[k]}
        <div class="vrow" role="listitem" draggable="true" ondragstart={() => (dragKey = k)} ondragover={(e) => e.preventDefault()} ondrop={() => { reorder(dragKey, k); dragKey = null; }} ondragend={() => (dragKey = null)} class:dragging={dragKey === k}>
          <Icon name={VIEWS[k].icon} style={on ? 'color:var(--muted)' : 'color:var(--faint2)'} />
          <span class="grow" class:off={!on}>{VIEWS[k].label}</span>
          <button class="icon-btn" aria-pressed={!on} aria-label={(on ? 'Nascondi ' : 'Mostra ') + VIEWS[k].label} onclick={() => set('viewVis', { ...app.viewVis, [k]: !on })}><Icon name={on ? 'eye' : 'eyeOff'} /></button>
        </div>
      {/each}
    </div>
  </section>
  <section>
    <h2>Schede</h2>
    <div class="box">
      <SettingRow label="Disposizione" desc="Puoi anche trascinare una scheda sul bordo di un gruppo.">{@render seg('Disposizione', [['1', 'Un gruppo'], ['2c', 'Due colonne'], ['3c', 'Tre colonne'], ['2r', 'Due righe']], layoutKey, (v) => applyLayout(Number(v[0]), v[1] === 'r' ? 'col' : v[1] === 'c' ? 'row' : layout.dir))}</SettingRow>
    </div>
  </section>
{:else if tab === 'azioni'}
  <section>
    <h2>Azioni</h2>
    <div class="box">
      <SettingRow label="Vista predefinita" desc="Bacheca a colonne oppure elenco unico.">{@render seg('Vista predefinita', [['bacheca', 'Bacheca'], ['elenco', 'Elenco']], app.actView, (v) => set('actView', v))}</SettingRow>
      <SettingRow label="Raggruppa per" desc="">{@render seg('Raggruppa per', [['scadenza', 'Scadenza'], ['progetto', 'Progetto']], app.actGroup, (v) => set('actGroup', v))}</SettingRow>
      <SettingRow label="Colonna “Fatte” nella bacheca" desc="Le azioni spuntate passano in una colonna a parte.">{@render toggle('Colonna Fatte', app.boardDone, () => set('boardDone', !app.boardDone))}</SettingRow>
    </div>
  </section>
{:else if tab === 'etichette'}
  <section>
    <h2>Colori delle etichette <span class="note">Le tinte si adattano al tema · i file delle note non cambiano</span></h2>
    <div class="box">
      {#each tags as t (t)}
        <div class="trow">
          <button class="chip" style="background:color-mix(in srgb, {tagColor(t)} 14%, transparent);color:{tagColor(t)}" onclick={() => openPage(`tag:${t}`)}>#{t}</button>
          <span class="grow"></span>
          <div class="colors" role="radiogroup" aria-label="Colore di #{t}">
            {#each Object.entries(TAG_PALETTE) as [id, [dark, light, label]] (id)}
              {@const c = theme.current.dark ? dark : light}
              {@const on = tagColorId(t, app.tagColors) === id}
              <button class="color" class:on role="radio" aria-checked={on} aria-label={label} title={label} style="background:{c};--c:{c}" onclick={() => pickTag(t, id)}>
                {#if on}<Icon name="check" size={13} style="stroke-width:3;color:{theme.current.dark ? '#141518' : '#fff'}" />{/if}
              </button>
            {/each}
          </div>
        </div>
      {:else}
        <p class="empty">Le etichette scritte con #nome compaiono qui.</p>
      {/each}
    </div>
  </section>
{:else if tab === 'note' && notes}
  <section>
    <h2>Nota del giorno</h2>
    <div class="box">
      <SettingRow label="Cartella delle note" desc={notes.notesDir}><button class="btn" onclick={() => call('open_notes_folder')}>Apri la cartella</button></SettingRow>
      <SettingRow label="Note del giorno" desc="Una per giorno, creata quando serve."><span class="mono value">AAAA/MM/AAAA-MM-GG-giornata.md</span></SettingRow>
      <SettingRow label="Sezioni" desc="Nota rapida e nuove azioni scrivono nella loro sezione, creata solo quando serve."><span class="value">Priorità · Note · Trascrizioni</span></SettingRow>
    </div>
  </section>
  <section>
    <h2>Registrazione <span class="note">La registrazione arriva con la prossima tappa: queste scelte sono già salvate</span></h2>
    <div class="box">
      <SettingRow label="Modello di trascrizione" desc="Più grande è il modello, più è preciso e lento.">{@render seg('Modello di trascrizione', [['base', 'base'], ['small', 'small'], ['medium', 'medium']], notes.whisperModel, (v) => setNotes('whisperModel', 'whisper_model', v))}</SettingRow>
      <SettingRow label="Lingua" desc="">{@render seg('Lingua', [['it', 'Italiano'], ['en', 'Inglese'], ['auto', 'Automatica']], notes.language, (v) => setNotes('language', 'language', v))}</SettingRow>
      <SettingRow label="Conserva il file audio" desc="Il WAV resta accanto alla nota. Se la trascrizione non riesce resta comunque.">{@render toggle('Conserva il file audio', notes.keepAudio, () => setNotes('keepAudio', 'keep_audio', !notes.keepAudio))}</SettingRow>
      <SettingRow label="Minutaggio cliccabile" desc="Ogni paragrafo trascritto comincia con [mm:ss], che fa ripartire l’audio da lì.">{@render toggle('Minutaggio cliccabile', notes.timestamps, () => setNotes('timestamps', 'transcript_timestamps', !notes.timestamps))}</SettingRow>
    </div>
  </section>
{:else if tab === 'info' && info}
  <section>
    <h2>QuickNotes</h2>
    <div class="box">
      <SettingRow label="Versione" desc=""><span class="mono value">{info.version}</span></SettingRow>
      {#if info.releases}
        <SettingRow label="Versioni nuove" desc="Si scaricano a mano da GitHub. Sostituisci QuickNotes.exe con quello nuovo, ad app chiusa: le note restano dove sono.">
          <button class="btn" onclick={() => call('open_url', { url: info.releases })}>Apri le release</button>
        </SettingRow>
      {/if}
    </div>
  </section>
  <section>
    <h2>Avvio</h2>
    <div class="box">
      <SettingRow label="Avvia con Windows" desc="L’app parte nascosta nell’area di notifica, con Ctrl Alt N e Ctrl Alt D già pronti. Se sposti QuickNotes.exe, riattivalo.">{@render toggle('Avvia con Windows', info.autostart, () => setAutostart(!info.autostart))}</SettingRow>
    </div>
  </section>
{:else if tab === 'claude' && claude}
  <section>
    <h2>Claude (MCP)</h2>
    <p class="intro">Claude cerca e legge le note tramite il server <code>quicknotes-mcp</code>, che Claude stesso avvia quando serve. Copia una di queste configurazioni.</p>
    {#if !claude.exists}<p class="warn">Il file quicknotes-mcp.exe non è accanto all'app. Scaricalo dalla stessa release di GitHub e mettilo nella cartella di QuickNotes.exe.</p>{/if}
    <div class="code-head"><span>Claude Desktop</span><button class="btn" onclick={() => copy('desktop', claude.desktop)}>{copied === 'desktop' ? 'Copiato' : 'Copia'}</button></div>
    <pre>{claude.desktop}</pre>
    <div class="code-head"><span>Claude Code</span><button class="btn" onclick={() => copy('code', claude.code)}>{copied === 'code' ? 'Copiato' : 'Copia'}</button></div>
    <pre>{claude.code}</pre>
  </section>
{/if}

<style>
  .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; margin-bottom: 4px; }
  .head h1 { flex: 1 1 260px; }
  .tabs { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 18px; border-bottom: 1px solid var(--border); }
  .tabs button { height: 36px; padding: 0 12px; margin-bottom: -1px; border: 0; border-bottom: 2px solid transparent; background: transparent; font-size: 13.5px; color: var(--subtle); }
  .tabs button.on { border-bottom-color: var(--accent); color: var(--text); }
  section { margin-top: 26px; }
  h2 { margin: 0 0 10px; font-size: 15px; font-weight: 600; }
  .note { margin-left: 10px; font-size: 12.5px; font-weight: 400; color: var(--subtle); }
  .box { border-radius: 12px; border: 1px solid var(--border); background: var(--card); }
  .box > :global(* + *) { border-top: 1px solid var(--border); }
  .row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; padding: 14px 16px; }
  .rtext { flex: 1 1 240px; min-width: 0; }
  .rl { font-size: 14px; color: var(--text); }
  .seg { display: flex; flex-wrap: wrap; padding: 2px; border-radius: 9px; background: var(--raised); border: 1px solid var(--border); }
  .seg button { height: 28px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .seg button.on { background: var(--border2); color: var(--text); }
  .switch { flex: none; position: relative; width: 40px; height: 22px; padding: 0; border: 0; border-radius: 11px; background: var(--border3); }
  .switch span { position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: var(--muted); }
  .switch.on { background: var(--accent); }
  .switch.on span { left: 21px; background: var(--surface); }
  .themes { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
  .theme { display: flex; flex-direction: column; padding: 6px; border-radius: 12px; text-align: left; color: var(--text); background: var(--card); border: 1px solid var(--border2); }
  .theme.on { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .prev { display: flex; height: 70px; border-radius: 8px; overflow: hidden; border: 1px solid; }
  .prev i { display: block; }
  .pside { display: flex; flex-direction: column; gap: 5px; width: 30%; padding: 8px 7px; }
  .pmain { display: flex; flex-direction: column; gap: 5px; flex: 1; margin: 6px 6px 6px 0; padding: 8px; border-radius: 5px; border: 1px solid; }
  .tname { display: flex; align-items: center; gap: 6px; padding: 8px 4px 2px; }
  .grow { flex: 1; min-width: 0; }
  .tname b { display: block; font-size: 13.5px; font-weight: 500; }
  .tname small { display: block; font-size: 12px; color: var(--subtle); }
  .custom { margin-top: 12px; }
  .hex { font-size: 12px; color: var(--muted); }
  .value { font-size: 13px; color: var(--muted); }
  input[type='color'] { width: 26px; height: 24px; padding: 0; border: 0; background: transparent; cursor: pointer; }
  .vrow { display: flex; align-items: center; gap: 10px; height: 40px; padding: 0 6px 0 12px; font-size: 13.5px; cursor: grab; }
  .vrow.fixed { color: var(--subtle); cursor: default; padding-right: 12px; }
  .vrow.dragging { opacity: 0.45; }
  .off { color: var(--faint); text-decoration: line-through; }
  .vfix { font-size: 12px; color: var(--faint); }
  .trow { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px; padding: 12px 16px; }
  .chip { height: 24px; padding: 0 10px; border: 0; border-radius: 999px; font-size: 12px; }
  .colors { display: flex; flex-wrap: wrap; gap: 8px; }
  .color { flex: none; width: 24px; height: 24px; padding: 0; border: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
  .color.on { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--c); }
  .empty { margin: 0; padding: 14px 16px; font-size: 13.5px; color: var(--subtle); }
  .intro { margin-bottom: 14px; font-size: 14px; color: var(--text2); }
  .warn { margin-bottom: 14px; font-size: 13.5px; color: var(--late); }
  code { font-family: 'Geist Mono', monospace; font-size: 13px; }
  .code-head { display: flex; align-items: center; justify-content: space-between; margin: 16px 0 6px; font-size: 13.5px; }
  pre { margin: 0; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--sunk); font-family: 'Geist Mono', monospace; font-size: 12.5px; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
