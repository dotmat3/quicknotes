<script>
  // Conferma prima di un'azione che toglie qualcosa, come eliminare una nota. Invio conferma, Esc annulla.
  import { app } from '../state/app.svelte.js';

  const ask = app.confirm;
  const back = document.activeElement;

  function close(ok) {
    app.confirm = null;
    if (back?.isConnected) back.focus();
    if (ok) ask.run();
  }

  function onKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close(false);
    } else if (e.key === 'Tab') {
      // Il fuoco resta dentro la finestra.
      const buttons = [...e.currentTarget.querySelectorAll('button')];
      const i = buttons.indexOf(document.activeElement);
      e.preventDefault();
      buttons[(i + (e.shiftKey ? -1 : 1) + buttons.length) % buttons.length].focus();
    }
  }
</script>

<div class="dim"></div>
<button class="outside" aria-label="Annulla" tabindex="-1" onclick={() => close(false)}></button>
<div class="box" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-text" tabindex="-1" onkeydown={onKey}>
  <h2 id="confirm-title">{ask.title}</h2>
  <p id="confirm-text">{ask.text}</p>
  <div class="buttons">
    <button class="btn" onclick={() => close(false)}>Annulla</button>
    <button class="btn primary danger" onclick={() => close(true)} {@attach (el) => el.focus()}>{ask.ok}</button>
  </div>
</div>

<style>
  .dim { position: fixed; inset: 0; z-index: 54; background: rgba(8, 8, 10, 0.55); }
  .outside { position: fixed; inset: 0; z-index: 55; padding: 0; border: 0; background: transparent; cursor: default; }
  .box { position: fixed; top: 30%; left: 50%; transform: translate(-50%, -30%); z-index: 56; width: 420px; max-width: calc(100% - 32px); padding: 20px 20px 16px; border-radius: 14px; background: var(--raised); border: 1px solid var(--border3); box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6); }
  h2 { font-size: 16px; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
  p { margin-top: 8px; font-size: 13px; line-height: 1.5; color: var(--muted); }
  .buttons { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
  .btn.danger { background: var(--late); color: #fff; }
</style>
