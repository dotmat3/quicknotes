<script>
  import { app } from '../state.svelte.js';
  import Icon from './Icon.svelte';

  const THEMES = [['auto', 'monitor', 'Come il sistema'], ['light', 'sun', 'Chiaro'], ['dark', 'moon', 'Scuro']];
  const main = $derived(app.nav.filter((n) => !n.group));
  const projects = $derived(app.nav.filter((n) => n.group === 'Progetti'));
</script>

{#snippet item(n)}
  <button class="item" class:active={app.view === n.key} onclick={() => app.selectView(n.key)}>
    <Icon name={n.icon} size={17} />
    <span class="label">{n.label}</span>
    {#if n.count}<span class="count" class:alert={n.alert}>{n.count}</span>{/if}
  </button>
{/snippet}

<nav class="sidebar">
  <div class="brand">
    <span class="logo"><Icon name="notes" size={15} stroke={2.2} /></span>
    QuickNotes
  </div>

  <button class="new" onclick={() => app.newDraft('meeting')}>
    <span class="plus"><Icon name="plus" size={14} stroke={2.4} /></span>
    Nuovo meeting
    <span class="kbd">Ctrl+N</span>
  </button>

  <div class="group">
    {#each main as n (n.key)}{@render item(n)}{/each}
  </div>

  {#if projects.length}
    <div class="heading">Progetti</div>
    <div class="group">
      {#each projects as n (n.key)}{@render item(n)}{/each}
    </div>
  {/if}

  <div class="footer">
    <div class="themes" role="radiogroup" aria-label="Aspetto">
      {#each THEMES as [mode, icon, label] (mode)}
        <button role="radio" aria-checked={app.theme === mode} class:on={app.theme === mode} title={label}
                onclick={() => app.setTheme(mode)}><Icon name={icon} size={15} /></button>
      {/each}
    </div>
  </div>
</nav>

<style>
  .sidebar { height: 100%; display: flex; flex-direction: column; background: var(--sidebar); padding: 14px 10px 12px; overflow-y: auto; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 650; font-size: 14.5px; padding: 2px 8px 14px; }
  .logo { width: 24px; height: 24px; border-radius: 7px; display: grid; place-items: center; color: #fff;
          background: linear-gradient(160deg, #e0745a, var(--accent)); box-shadow: 0 1px 2px rgb(0 0 0 / 0.15); }

  .new {
    display: flex; align-items: center; gap: 10px; height: 38px; padding: 0 10px 0 8px; margin-bottom: 14px;
    border-radius: 9px; background: var(--surface); border: 1px solid var(--border); font-weight: 600;
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.04); transition: border-color var(--fast) var(--ease), background var(--fast) var(--ease);
  }
  .new:hover { border-color: var(--border-strong); }
  .new:active { background: var(--hover); }
  .plus { width: 22px; height: 22px; border-radius: 6px; display: grid; place-items: center; background: var(--accent-soft); color: var(--accent); }
  .kbd { margin-left: auto; font-size: 11.5px; font-weight: 400; color: var(--faint); }

  .group { display: flex; flex-direction: column; gap: 1px; }
  .item {
    position: relative; display: flex; align-items: center; gap: 11px; height: 34px; padding: 0 10px;
    border-radius: 8px; color: var(--muted); text-align: left; transition: background var(--fast) var(--ease), color var(--fast) var(--ease);
  }
  .item:hover { background: var(--hover); color: var(--text); }
  .item.active { background: var(--selected); color: var(--text); font-weight: 600; }
  .item.active::before { content: ''; position: absolute; left: -4px; top: 9px; bottom: 9px; width: 3px; border-radius: 2px; background: var(--accent); }
  .label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .count { font-size: 12px; font-weight: 500; color: var(--faint); font-variant-numeric: tabular-nums; }
  .count.alert { color: var(--on-accent); background: var(--danger); border-radius: 999px; padding: 0 6px; line-height: 18px; font-weight: 600; }

  .heading { font-size: 11.5px; font-weight: 650; letter-spacing: 0.06em; text-transform: uppercase; color: var(--faint); padding: 18px 10px 6px; }

  .footer { margin-top: auto; padding: 12px 4px 0; }
  .themes { display: inline-flex; gap: 2px; padding: 3px; border-radius: 9px; background: var(--hover); }
  .themes button { width: 30px; height: 26px; border-radius: 6px; display: grid; place-items: center; color: var(--faint);
                   transition: background var(--fast) var(--ease), color var(--fast) var(--ease); }
  .themes button:hover { color: var(--text); }
  .themes button.on { background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgb(0 0 0 / 0.08); }
</style>
