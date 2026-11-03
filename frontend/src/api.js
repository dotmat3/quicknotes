// Chiamate al backend Python. Tutto passa da qui, così la pagina non conosce percorsi né file.
// Aperta nel browser senza Python (npm run dev), ogni chiamata restituisce il suo valore di ripiego.

export const boot = window.__QN__ ?? { theme: 'grafite', ui: {}, today: null, today_iso: '2026-11-01' };

// Python inietta `backend: 'py'` nei dati d'avvio. `window.pywebview.api` arriva dopo la pagina.
export const hasBackend = boot.backend === 'py';

const ready = hasBackend
  ? new Promise((resolve) => {
      if (window.pywebview?.api?.invoke) resolve();
      else window.addEventListener('pywebviewready', () => resolve(), { once: true });
    })
  : null;

// Python risponde sempre { ok } oppure { err } con un messaggio da mostrare.
async function invoke(command, args) {
  await ready;
  let res;
  try {
    res = await window.pywebview.api.invoke(command, args);
  } catch (e) {
    throw e?.message ?? String(e);
  }
  if (res && 'err' in res) throw res.err;
  return res?.missing ? undefined : res?.ok;
}

export async function call(command, args = {}, fallback) {
  if (!hasBackend) return fallback;
  const value = await invoke(command, args);
  return value === undefined ? fallback : value;
}

// Eventi da Python: `window.__qnEmit(nome, dati)`.
const handlers = new Map();
window.__qnEmit = (event, payload) => {
  for (const handler of handlers.get(event) ?? []) handler(payload);
};

export async function listen(event, handler) {
  if (!handlers.has(event)) handlers.set(event, new Set());
  handlers.get(event).add(handler);
  return () => handlers.get(event).delete(handler);
}

export function appReady() {
  if (hasBackend) invoke('app_ready', {});
}

// Le immagini delle note arrivano dal server locale di Python, solo se sono dentro la cartella delle note.
export const fileOrigin = boot.fileOrigin ?? '/qnfile/';

// I byte di un'immagine incollata, così come sono. Restituisce il percorso da scrivere nel tag Markdown.
export async function saveImage(noteId, bytes) {
  if (!hasBackend) throw 'Nessun backend';
  const res = await fetch(`${fileOrigin}?note=${encodeURIComponent(noteId)}`, { method: 'POST', body: bytes });
  const text = await res.text();
  if (!res.ok) throw text;
  return text;
}
