// Chiamate al backend. Tutto passa da qui, così la pagina non conosce percorsi né file.
import { invoke } from '@tauri-apps/api/core';

export const inTauri = '__TAURI_INTERNALS__' in window;

export const boot = window.__QN__ ?? { theme: 'grafite', ui: {}, today: null, today_iso: '2026-11-01' };

export async function call(command, args = {}, fallback) {
  if (!inTauri) return fallback;
  return invoke(command, args);
}

export async function listen(event, handler) {
  if (!inTauri) return () => {};
  const { listen: tauriListen } = await import('@tauri-apps/api/event');
  return tauriListen(event, (e) => handler(e.payload));
}

export function appReady() {
  if (inTauri) invoke('app_ready');
}
