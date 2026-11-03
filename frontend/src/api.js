// Chiamate al backend. Tutto passa da qui, così la pagina non conosce percorsi né file.
// Due backend possibili: Tauri (Rust) e, nel branch di prova, pywebview (Python). Stessi nomi di comando.
import { invoke } from '@tauri-apps/api/core';

export const inTauri = '__TAURI_INTERNALS__' in window;

export const boot = window.__QN__ ?? { theme: 'grafite', ui: {}, today: null, today_iso: '2026-11-01' };

// pywebview: Python inietta `backend: 'py'` nei dati d'avvio. `window.pywebview.api` arriva dopo la pagina.
export const inPy = !inTauri && boot.backend === 'py';
export const hasBackend = inTauri || inPy;

const pyReady = inPy
  ? new Promise((resolve) => {
      if (window.pywebview?.api?.invoke) resolve();
      else window.addEventListener('pywebviewready', () => resolve(), { once: true });
    })
  : null;

// Python risponde sempre { ok } oppure { err } oppure { missing }: un comando non ancora portato in Python
// si comporta come nel browser senza backend, cioè restituisce il valore di ripiego.
async function pyCall(command, args) {
  await pyReady;
  let res;
  try {
    res = await window.pywebview.api.invoke(command, args);
  } catch (e) {
    throw e?.message ?? String(e);
  }
  if (res?.missing) return undefined;
  if (res && 'err' in res) throw res.err;
  return res?.ok;
}

export async function call(command, args = {}, fallback) {
  if (inTauri) return invoke(command, args);
  if (inPy) {
    const value = await pyCall(command, args);
    return value === undefined ? fallback : value;
  }
  return fallback;
}

// Eventi da Python: `window.__qnEmit(nome, dati)`.
const pyHandlers = new Map();
if (inPy) {
  window.__qnEmit = (event, payload) => {
    for (const handler of pyHandlers.get(event) ?? []) handler(payload);
  };
}

export async function listen(event, handler) {
  if (inPy) {
    if (!pyHandlers.has(event)) pyHandlers.set(event, new Set());
    pyHandlers.get(event).add(handler);
    return () => pyHandlers.get(event).delete(handler);
  }
  if (!inTauri) return () => {};
  const { listen: tauriListen } = await import('@tauri-apps/api/event');
  return tauriListen(event, (e) => handler(e.payload));
}

export function appReady() {
  if (inTauri) invoke('app_ready');
  else if (inPy) pyCall('app_ready', {});
}

// Le immagini delle note: Tauri le serve con il protocollo qnfile, Python con il suo server locale.
export const fileOrigin = inPy
  ? boot.fileOrigin
  : /Windows|Android/.test(navigator.userAgent)
    ? 'http://qnfile.localhost/'
    : 'qnfile://localhost/';

// I byte di un'immagine incollata, così come sono. Restituisce il percorso da scrivere nel tag Markdown.
export async function saveImage(noteId, bytes) {
  if (inTauri) return invoke('save_image', bytes, { headers: { 'x-note': encodeURIComponent(noteId) } });
  if (!inPy) throw 'Nessun backend';
  const res = await fetch(`${boot.fileOrigin}?note=${encodeURIComponent(noteId)}`, { method: 'POST', body: bytes });
  const text = await res.text();
  if (!res.ok) throw text;
  return text;
}
