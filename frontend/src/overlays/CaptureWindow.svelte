<script>
  import { onMount } from 'svelte';
  import { boot, call, listen } from '../api.js';
  import { applyTheme, resolveTheme, tagHex } from '../theme/themes.js';
  import { ACTION, DUE, MENTION, TAG, dueLabel } from '../note/editor/rules.js';
  import Icon from '../shell/Icon.svelte';

  // La nota rapida è una finestra già pronta e nascosta: Ctrl Alt N la mostra all'istante.
  const ui = boot.ui ?? {};
  const theme = resolveTheme(ui.theme ?? boot.theme, ui.custom);
  applyTheme(theme);

  const SECTIONS = ['Priorità', 'Note', 'Trascrizioni'];
  let text = $state('');
  let section = $state('Priorità');
  let openAfter = $state(ui.captureOpen !== false);
  let today = $state(boot.today);
  let saving = $state(false);
  let error = $state('');
  let field = $state();

  const chips = $derived.by(() => {
    const out = [];
    if (text.split('\n').some((l) => ACTION.test(l))) out.push({ label: 'azione', look: 'plain', icon: true });
    for (const m of text.matchAll(MENTION)) out.push({ label: `@${m[1]}`, look: 'person' });
    for (const m of text.matchAll(TAG)) out.push({ label: `#${m[1]}`, color: tagHex(m[1], ui.tagColors, theme.dark) });
    for (const m of text.matchAll(DUE)) out.push({ label: `scade ${dueLabel(m[1]).label}`, look: 'plain' });
    return out;
  });

  const close = () => call('hide_capture');

  async function submit() {
    if (!text.trim() || saving) return;
    saving = true;
    error = '';
    try {
      await call('capture_save', { text, section, open: openAfter });
      text = '';
      close();
    } catch (e) {
      error = String(e);
    } finally {
      saving = false;
    }
  }

  function onKey(e) {
    if (e.key === 'Escape') close();
    else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      submit();
    }
  }

  onMount(() => {
    const off = listen('capture-open', async () => {
      today = (await call('today_info')) ?? today;
      field?.focus();
    });
    field?.focus();
    return () => off.then((f) => f());
  });

  const dayLabel = $derived(today?.short ?? '');
</script>

<svelte:window onkeydown={onKey} />

<div class="win">
  <div class="head pywebview-drag-region">
    <span class="pen"><Icon name="pen" /></span>
    <span class="title">Nota rapida</span>
    <kbd>Ctrl Alt N</kbd>
    <span class="grow"></span>
    <button class="icon-btn" aria-label="Chiudi" onclick={close}><Icon name="close" /></button>
  </div>

  <div class="dest">
    <span>Aggiungi a</span>
    <span class="box"><Icon name="today" size={14} style="color:var(--accent)" />Nota del giorno · {dayLabel}</span>
    <span>sezione</span>
    <select aria-label="Sezione" bind:value={section}>
      {#each SECTIONS as s (s)}<option>{s}</option>{/each}
    </select>
  </div>

  <textarea bind:this={field} bind:value={text} aria-label="Testo della nota rapida" placeholder="- [ ] Scrivi qui… @persona #etichetta due:2026-12-01" spellcheck="true" lang="it"></textarea>

  {#if chips.length}
    <div class="found">
      <div class="found-title">Riconosciuti</div>
      <div class="chips">
        {#each chips as c, i (i)}
          <span class="chip {c.look ?? ''}" style={c.color ? `color:${c.color};background:color-mix(in srgb, ${c.color} 14%, transparent)` : ''}>
            {#if c.icon}<Icon name="actions" size={12} />{/if}{c.label}
          </span>
        {/each}
      </div>
    </div>
  {/if}

  {#if error}<p class="err" role="alert">{error}</p>{/if}

  <div class="foot">
    <label class="open"><input type="checkbox" bind:checked={openAfter} />Apri dopo il salvataggio</label>
    <span class="grow"></span>
    <span class="esc"><kbd>Esc</kbd> chiudi</span>
    <button class="save" disabled={!text.trim() || saving} onclick={submit}>Salva<kbd>Ctrl ↵</kbd></button>
  </div>
</div>

<style>
  :global(body) { background: var(--raised); }
  .win { height: 100%; display: flex; flex-direction: column; background: var(--raised); color: var(--text); }
  .head { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border-bottom: 1px solid var(--border2); }
  .pen { display: flex; color: var(--accent); pointer-events: none; }
  .title { font-weight: 600; pointer-events: none; }
  kbd { padding: 1px 6px; border: 1px solid var(--border2); border-radius: 4px; color: var(--muted); pointer-events: none; }
  .grow { flex: 1; }
  .dest { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px 0; font-size: 13px; color: var(--muted); }
  .box { display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border: 1px solid var(--border2); border-radius: 6px; background: var(--surface); color: var(--text); }
  select { height: 28px; padding: 0 6px; border: 1px solid var(--border2); border-radius: 6px; background: var(--surface); color: var(--text); font: inherit; font-size: 13px; }
  textarea { flex: 1; min-height: 0; margin: 12px 16px 0; padding: 14px; border-radius: 10px; background: var(--surface); border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent); color: var(--text); font: inherit; font-size: 15px; line-height: 1.65; resize: none; outline: none; caret-color: var(--accent); }
  textarea::placeholder { color: var(--faint); }
  .found { padding: 12px 16px 0; }
  .found-title { margin-bottom: 6px; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--subtle); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; font-size: 12px; }
  .chip { display: flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; }
  .chip.plain { background: var(--hover); color: var(--text); }
  .chip.person { background: color-mix(in srgb, var(--person) 12%, transparent); color: var(--person); }
  .err { padding: 8px 16px 0; font-size: 13px; color: var(--late); }
  .foot { display: flex; align-items: center; gap: 10px; padding: 14px 16px; margin-top: 12px; border-top: 1px solid var(--border2); background: var(--card); }
  .open { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
  .open input { width: 16px; height: 16px; accent-color: var(--accent); }
  .esc { font-size: 12px; color: var(--subtle); }
  .esc kbd { padding: 0; border: 0; }
  .save { display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 14px; border: 0; border-radius: 8px; background: var(--accent); color: var(--on-accent); font-size: 13px; font-weight: 600; }
  .save:disabled { opacity: 0.5; cursor: default; }
  .save kbd { padding: 0; border: 0; color: inherit; opacity: 0.75; }
</style>
