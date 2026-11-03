// Azioni: dati della bacheca e modifiche. Ogni modifica passa dal file e, se la nota è aperta,
// il testo nuovo arriva all'editor come differenza: resta annullabile.
import { call } from '../api.js';
import { refreshCounts, showToast } from './app.svelte.js';
import { docs, onExternalChange, save, saveAll } from './documents.svelte.js';

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
}

export const setDone = (item, done) =>
  mutate(item.note_id, () => call('set_action_done', { noteId: item.note_id, line: item.line, text: item.raw, done }));

export const completeAll = (item) =>
  mutate(item.note_id, () => call('complete_action', { noteId: item.note_id, line: item.line, text: item.raw }));

export const setField = (item, field, value, index) =>
  mutate(item.note_id, () => call('set_action_field', { noteId: item.note_id, line: item.line, text: item.raw, field, index, value }));

// Scadenza ed etichetta arrivano dal "+" di una colonna; il testo scritto ha la precedenza.
export async function addAction(text, due = null, tag = null) {
  try {
    const noteId = await call('add_action', { text, due, tag });
    await onExternalChange([noteId]);
  } catch (e) {
    showToast(String(e));
  }
  await Promise.all([loadBoard(), refreshCounts()]);
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
}
