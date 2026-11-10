// Azioni: dati della bacheca e modifiche. Ogni modifica passa dal file e, se la nota è aperta,
// il testo nuovo arriva all'editor come differenza: resta annullabile.
import { call } from '../api.js';
import { refreshCounts, showToast } from './app.svelte.js';
import { docs, onExternalChange, save, saveAll } from './documents.svelte.js';
import { petCheck } from '../pet/store.svelte.js';

// `version` cresce a ogni ricarica: le pagine che mostrano azioni (etichetta) si ricaricano con la bacheca.
export const board = $state({ items: [], open: 0, late: 0, done_this_week: 0, week_number: 0, loaded: false, version: 0 });

export async function loadBoard() {
  Object.assign(board, await call('action_board', {}, {}), { loaded: true, version: board.version + 1 });
}

async function mutate(noteId, fn) {
  // Le modifiche in sospeso vanno scritte prima, altrimenti la riga attesa non corrisponde.
  if (docs[noteId]) await save(noteId);
  try {
    await fn();
  } catch (e) {
    showToast(String(e));
  }
  await onExternalChange([noteId]);
  await Promise.all([loadBoard(), refreshCounts()]);
  petCheck();
}

export const setDone = (item, done) =>
  mutate(item.note_id, () => call('set_action_done', { noteId: item.note_id, line: item.line, text: item.raw, done }));

export const completeAll = (item) =>
  mutate(item.note_id, () => call('complete_action', { noteId: item.note_id, line: item.line, text: item.raw }));

export const setField = (item, field, value, index) =>
  mutate(item.note_id, () => call('set_action_field', { noteId: item.note_id, line: item.line, text: item.raw, field, index, value }));

export const setStatus = (item, status) =>
  mutate(item.note_id, () => call('set_action_status', { noteId: item.note_id, line: item.line, text: item.raw, status }));

// `value`: una data AAAA-MM-GG, 'oggi', 'domani' oppure null per togliere `scheduled:`.
export const setScheduled = (item, value) =>
  mutate(item.note_id, () => call('set_scheduled', { noteId: item.note_id, line: item.line, text: item.raw, value }));

// Sposta l'azione nella nota del progetto, sotto l'area. Cambiano due note: si ricaricano entrambe.
export async function moveAction(item, project, area) {
  if (docs[item.note_id]) await save(item.note_id);
  let res = null;
  try {
    res = await call('move_action', { noteId: item.note_id, line: item.line, text: item.raw, target: project, section: area || null });
    showToast(`Spostata in ${res.title}${area ? ` · ${area}` : ''}`);
  } catch (e) {
    showToast(String(e));
  }
  await onExternalChange(res?.ids ?? [item.note_id]);
  await Promise.all([loadBoard(), refreshCounts()]);
  return res;
}

export async function archiveDone(project) {
  await saveAll();
  try {
    const res = await call('archive_done', { project });
    await onExternalChange(res.ids);
    showToast(res.archived ? (res.archived === 1 ? '1 azione archiviata' : `${res.archived} azioni archiviate`) : 'Niente da archiviare');
  } catch (e) {
    showToast(String(e));
  }
  await Promise.all([loadBoard(), refreshCounts()]);
}

export async function addProjectAction(project, text, area) {
  try {
    const noteId = await call('add_project_action', { project, text, area: area || null });
    await onExternalChange([noteId]);
  } catch (e) {
    showToast(String(e));
  }
  await Promise.all([loadBoard(), refreshCounts()]);
}

export async function setProjectStatus(project, status) {
  await saveAll();
  try {
    const res = await call('set_project_status', { project, status });
    await onExternalChange([res.id]);
  } catch (e) {
    showToast(String(e));
  }
  await Promise.all([loadBoard(), refreshCounts()]);
}

export async function createProject(name, areas = []) {
  try {
    const res = await call('create_project', { name, aliases: [], areas });
    await refreshCounts();
    return res;
  } catch (e) {
    showToast(String(e));
    return null;
  }
}

// Scadenza, etichetta e priorità arrivano dal "+" di una colonna; il testo scritto ha la precedenza.
export async function addAction(text, due = null, tag = null, priority = null) {
  try {
    const noteId = await call('add_action', { text, due, tag, priority });
    await onExternalChange([noteId]);
  } catch (e) {
    showToast(String(e));
  }
  await Promise.all([loadBoard(), refreshCounts()]);
  petCheck();
}

// Aggiunta rapida della vista Azioni: nella nota del progetto, sotto l'area, oppure in "Da smistare".
// Restituisce { id, title, project, area } oppure null se non è andata.
export async function quickAction({ text, project = null, area = null, due = null, priority = null, scheduled = null }) {
  let res = null;
  try {
    res = await call('quick_action', { text, project, area, due, priority, scheduled });
    await onExternalChange([res.id]);
  } catch (e) {
    showToast(String(e));
  }
  await Promise.all([loadBoard(), refreshCounts()]);
  petCheck();
  return res;
}

export async function postponeLate() {
  // Le modifiche in sospeso vanno scritte prima: ogni riga viene confrontata con il file.
  await saveAll();
  try {
    const { moved, ids } = await call('postpone_late');
    await onExternalChange(ids);
    showToast(moved === 1 ? '1 azione spostata a domani' : `${moved} azioni spostate a domani`);
  } catch (e) {
    showToast(String(e));
  }
  await Promise.all([loadBoard(), refreshCounts()]);
  petCheck();
}
