// Azioni: dati della bacheca e modifiche. Ogni modifica passa dal file e, se la nota è aperta,
// il testo nuovo arriva all'editor come differenza: resta annullabile.
import { call } from '../api.js';
import { refreshCounts, showToast } from './app.svelte.js';
import { docs, onExternalChange, save } from './documents.svelte.js';

export const board = $state({ items: [], open: 0, late: 0, done_this_week: 0, week_number: 0, loaded: false });

export async function loadBoard() {
  Object.assign(board, await call('action_board', {}, {}), { loaded: true });
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

export async function addAction(text) {
  const noteId = await call('add_action', { text });
  await onExternalChange([noteId]);
  await Promise.all([loadBoard(), refreshCounts()]);
}
