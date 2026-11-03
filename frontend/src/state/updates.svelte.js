// Aggiornamenti dell'app. All'avvio, dopo qualche secondo, si controlla se su GitHub c'è una versione più
// nuova; se c'è, la barra del titolo lo dice e Impostazioni › Informazioni la installa. Installare salva
// prima tutte le note: l'installer chiude l'app e la riapre aggiornata.
import { call, listen } from '../api.js';
import { app } from './app.svelte.js';
import { saveAll } from './documents.svelte.js';

export const updates = $state({
  info: null, // { version, updates, autostart }
  available: null, // { version, notes, date }
  checking: false,
  checked: false,
  error: '',
  installing: false,
  progress: null, // { done, total }
});

// Gli errori del plugin arrivano in inglese: i casi che si incontrano davvero diventano frasi chiare.
function explain(e, installing) {
  const text = String(e);
  if (/signature/i.test(text)) return 'Il pacchetto scaricato non ha la firma di QuickNotes: non è stato installato nulla.';
  if (/error sending request|dns|connect|timed out|network/i.test(text)) return 'GitHub non risponde: forse manca la connessione, o la rete aziendale lo blocca.';
  return `${installing ? 'Aggiornamento' : 'Controllo'} non riuscito: ${text}`;
}

export async function loadInfo() {
  updates.info = await call('app_info', {}, null);
  return updates.info;
}

export async function checkNow() {
  if (!updates.info?.updates || updates.checking) return;
  updates.checking = true;
  updates.error = '';
  try {
    updates.available = await call('check_update', {}, null);
  } catch (e) {
    updates.error = explain(e, false);
  } finally {
    updates.checking = false;
    updates.checked = true;
  }
}

// Controllo all'avvio, senza rallentarlo e senza avvisi se la rete non risponde.
export function checkLater() {
  setTimeout(async () => {
    const info = await loadInfo();
    if (info?.updates && app.autoUpdate !== false) await checkNow();
  }, 8000);
}

export async function install() {
  if (updates.installing) return;
  updates.installing = true;
  updates.error = '';
  const off = await listen('update-progress', (p) => (updates.progress = p));
  try {
    await saveAll();
    await call('install_update');
  } catch (e) {
    updates.error = explain(e, true);
    updates.installing = false;
    off();
  }
}
