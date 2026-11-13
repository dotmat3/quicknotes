// Documenti aperti: testo, salvataggio e viste. La stessa nota può stare in più gruppi.
import { tick } from 'svelte';
import { call, emit } from '../api.js';
import { app, showToast } from './app.svelte.js';
import { replacePage } from './layout.svelte.js';

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
    else {
      // Se cambiano i [[link]], cambiano anche le note collegate mostrate nell'intestazione.
      if (wikiLinks(text) !== wikiLinks(d.base)) d.note = await call('read_note', { id });
      // Python non annuncia i salvataggi dall'editor. Se sono cambiate le azioni o le intestazioni (che decidono
      // il progetto), contatori, viste aperte e Micio si aggiornano come per una modifica esterna.
      const changed = outline(text) !== outline(d.base);
      d.base = text;
      if (changed) emit('index-updated', 1);
    }
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

// Le righe che decidono azioni e progetti: le azioni (con il loro stato e i campi) e le intestazioni.
const outline = (text) => (text.match(/^(?:\s*[-*+] \[.\].*|#{1,6} .*)$/gm) ?? []).join('\n');
const wikiLinks = (text) => (text.match(/\[\[[^\]\n]+\]\]/g) ?? []).join('\n');

export async function saveAll() {
  await Promise.all(Object.keys(docs).map(save));
}

// La nota del giorno prende il nome dalla data; quella di oggi non si elimina.
export const canRename = (id) => !id.endsWith('-giornata');
export const canDelete = (id) => id !== app.today?.id;

// Le viste di una nota che non c'è più con quel nome: chiuse, perdono modalità e cronologia delle modifiche.
async function forget(id, newId) {
  const page = `note:${id}`;
  for (const key of Object.keys(modes)) {
    if (!key.endsWith(`:${page}`)) continue;
    if (newId) modes[`${key.slice(0, -page.length)}note:${newId}`] = modes[key];
    delete modes[key];
  }
  replacePage(page, newId ? `note:${newId}` : null);
  // L'editor chiuso conserva il suo stato solo dopo essere stato smontato.
  await tick();
  delete docs[id];
  for (const key of [...savedStates.keys()]) if (key.endsWith(`:${page}`)) savedStates.delete(key);
}

// Nuovo titolo e nuovo nome del file. Prima si salva tutto: anche le note con i link da aggiornare.
export async function renameNote(id, title) {
  title = title.trim();
  const d = docs[id];
  if (!title || title === d?.note.title) return;
  try {
    await saveAll();
    const r = await call('rename_note', { id, title });
    if (r.id === id) {
      if (d) d.note = await call('read_note', { id });
      app.titles[`note:${id}`] = title;
    } else {
      if (d) clearTimeout(d.timer);
      app.titles[`note:${r.id}`] = title;
      await forget(id, r.id);
    }
    if (r.relinked) showToast(`Rinominata. Link aggiornati in ${r.relinked === 1 ? 'una nota' : `${r.relinked} note`}.`);
  } catch (e) {
    showToast(`Rinomina non riuscita: ${e}`);
  }
}

// Chiede conferma e manda la nota nel Cestino, con le ultime modifiche salvate.
export async function askDelete(id) {
  const note = docs[id]?.note ?? (await call('read_note', { id }).catch(() => null));
  const title = note?.title ?? app.titles[`note:${id}`] ?? id;
  const cited = new Set((note?.links_in ?? []).map((l) => l.note_id)).size;
  app.confirm = {
    title: `Eliminare «${title}»?`,
    text: `La nota va nel Cestino, da dove si può ripristinare.${cited ? ` ${cited === 1 ? 'Una nota la cita' : `${cited} note la citano`}: quei link non porteranno più a niente.` : ''}`,
    ok: 'Elimina',
    run: () => deleteNote(id, title),
  };
}

async function deleteNote(id, title) {
  try {
    await save(id);
    const r = await call('delete_note', { id });
    const d = docs[id];
    if (d) {
      clearTimeout(d.timer);
      d.dirty = false;
    }
    await forget(id, null);
    showToast(r.recycled ? `«${title}» è nel Cestino.` : `«${title}» è in .quicknotes/cestino, nella cartella delle note.`);
  } catch (e) {
    showToast(`Eliminazione non riuscita: ${e}`);
  }
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
