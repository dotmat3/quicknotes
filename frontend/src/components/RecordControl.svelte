<script>
  import { app } from '../state.svelte.js';
  import Icon from './Icon.svelte';

  // Pulsante "Registra"; durante la registrazione diventa una pillola con tempo, livello del microfono e stop.
  const BARS = 5;
  const rec = $derived(app.recording);
  const elsewhere = $derived(rec && rec.noteId !== app.note?.id);
</script>

<div class="wrap">
  {#if app.transcription}
    <div class="transcribing" title="Trascrizione in corso, in locale">
      <span class="spinner"></span>
      Trascrizione {app.transcription.percent}%
    </div>
  {/if}

  {#if rec}
    <button class="pill" onclick={() => app.toggleRecording()}
            title={elsewhere ? 'Registrazione in corso su un\'altra nota: clic per fermarla' : 'Ferma registrazione (Ctrl+Alt+R)'}>
      <span class="dot"></span>
      <span class="time">{rec.elapsed}</span>
      <span class="meter" aria-hidden="true">
        {#each { length: BARS } as _, i}
          <span style:transform="scaleY({Math.max(0.15, Math.min(1, rec.level * 1.6 - i * 0.18))})"></span>
        {/each}
      </span>
      <span class="stop"><Icon name="stop" size={12} /></span>
    </button>
  {:else}
    <button class="record" onclick={() => app.toggleRecording()} title="Registra e trascrivi (Ctrl+Alt+R)">
      <Icon name="mic" size={16} />
      Registra
    </button>
  {/if}
</div>

<style>
  .wrap { display: flex; align-items: center; gap: 8px; }
  .record { display: flex; align-items: center; gap: 7px; height: 32px; padding: 0 12px 0 10px; border-radius: 8px;
            color: var(--muted); font-size: 13.5px; transition: background var(--fast) var(--ease), color var(--fast) var(--ease); }
  .record:hover { background: var(--hover); color: var(--text); }

  .pill { display: flex; align-items: center; gap: 9px; height: 32px; padding: 0 6px 0 12px; border-radius: 999px;
          background: var(--danger-soft); color: var(--danger); font-size: 13.5px; font-weight: 600;
          transition: filter var(--fast) var(--ease); }
  .pill:hover { filter: brightness(0.97); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--danger); animation: pulse 1.4s ease-in-out infinite; }
  .time { font-variant-numeric: tabular-nums; min-width: 38px; }
  .meter { display: flex; align-items: center; gap: 2px; height: 14px; }
  .meter span { width: 3px; height: 14px; border-radius: 2px; background: currentColor; transform-origin: center;
                transition: transform 110ms linear; }
  .stop { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; background: var(--danger); color: var(--on-accent); }

  .transcribing { display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; border-radius: 999px;
                  background: var(--hover); color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
  .spinner { width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--border-strong); border-top-color: var(--accent);
             animation: spin 0.8s linear infinite; }

  @keyframes pulse { 50% { opacity: 0.35; } }
  @keyframes spin { to { transform: rotate(360deg); } }
  :global(:root[data-motion='off']) .dot, :global(:root[data-motion='off']) .spinner { animation-duration: 0s; }
</style>
