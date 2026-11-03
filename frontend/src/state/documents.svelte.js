// Documenti aperti: testo, salvataggio e viste. La stessa nota può stare in più gruppi.
import { call } from '../api.js';
import { showToast } from './app.svelte.js';

export const docs = $state({});

// Vista per gruppo e stato conservato per (gruppo, scheda): annulla e cursore sopravvivono al cambio di scheda.
export const views = new Map();
export const savedStates = new Map();

// Modalità di ogni (gruppo, scheda): anteprima viva se manca.
export const MODES = [
  ['live', 'Anteprima viva'],
  ['source', 'Sorgente'],
  ['split', 'Affiancata'],
  ['preview', 'Anteprima'],
];
export const modes = $state({});

export function setMode(key, mode) {
  if (mode === 'live') delete modes[key];
  else modes[key] = mode;
}

const SAVE_DELAY = 350;

export async function loadDoc(id) {
  if (docs[id]) return docs[id];
  const note = await call('read_note', { id });
  docs[id] ??= { id, text: note.body, base: note.body, note, saving: false, dirty: false, timer: null };
  return docs[id];
}

export function setText(id, text) {
  const d = docs[id];
  if (!d || d.text === text) return;
  d.text = text;
  d.dirty = true;
  clearTimeout(d.timer);
  d.timer = setTimeout(() => save(id), SAVE_DELAY);
}

export async function save(id) {
  const d = docs[id];
  if (!d || !d.dirty) return;
  // Un solo salvataggio per volta: quello che resta riparte alla fine.
  if (d.saving) return;
  clearTimeout(d.timer);
  d.saving = true;
  d.dirty = false;
  const text = d.text;
  try {
    const res = await call('save_note', { id, base: d.base, body: text });
    if (res.status === 'conflict') await resolveConflict(id, text, res.disk);
    else d.base = text;
  } catch (e) {
    d.dirty = true;
    showToast(`Salvataggio non riuscito: ${e}`);
  } finally {
    d.saving = false;
  }
  if (d.dirty) setTimeout(() => save(id), 0);
}

// Il file è cambiato fuori dall'app mentre c'erano modifiche: il testo dell'utente resta in una nota a parte.
async function resolveConflict(id, mine, disk) {
  const copy = await call('save_conflict', { id, body: mine });
  const d = docs[id];
  d.base = disk;
  d.text = disk;
  applyToViews(id, disk);
  showToast(`La nota è cambiata fuori dall'app. Il tuo testo è in «${copy.title}».`);
}

export async function saveAll() {
  await Promise.all(Object.keys(docs).map(save));
}

let applyToViews = () => {};
export function setApplyToViews(fn) {
  applyToViews = fn;
}

// Modifiche esterne segnalate dal backend.
export async function onExternalChange(ids) {
  for (const id of ids) {
    const d = docs[id];
    if (!d) continue;
    try {
      const note = await call('read_note', { id });
      d.note = note;
      if (note.body === d.text || note.body === d.base) continue;
      if (d.dirty || d.saving) continue; // Lo gestisce il controllo al salvataggio.
      d.base = note.body;
      d.text = note.body;
      applyToViews(id, note.body);
    } catch {
      // La nota è stata eliminata: la scheda resta aperta con l'ultimo testo.
    }
  }
}
