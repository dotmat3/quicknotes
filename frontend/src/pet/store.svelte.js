// Micio: preferenze, crocchette e oggetti della stanza. Tutto sta in config.json, chiave ui.pet.
// Le crocchette non si contano a parte: 5 per ogni azione completata da quando c'è Micio (lette dall'indice, quindi
// valgono anche quelle spuntate nell'editor, in Obsidian o da Claude), più quelle vinte al minigioco, meno le spese.
import { boot, call } from '../api.js';
import { savePrefs } from '../state/app.svelte.js';

const today = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const saved = boot.ui?.pet ?? {};

export const pet = $state({
  name: saved.name ?? '', // vuoto: si chiama Micio
  since: saved.since ?? today(),
  bonus: saved.bonus ?? 0,
  spent: saved.spent ?? 0,
  owned: saved.owned ?? {},
  placed: saved.placed ?? {},
  coat: saved.coat ?? '#F2B25E',
  scale: saved.scale ?? 3,
  out: saved.out ?? 'walk', // walk · play · off
  best: saved.best ?? 0,
  done: null, // azioni completate da `since`; null finché non le ha lette
  roomOpen: false,
});

export const PER_ACTION = 5;
export const NAME_MAX = 24;
// Il nome scelto, o Micio finché non gliene si dà uno.
export const petName = () => pet.name.trim() || 'Micio';
export const coins = () => Math.max(0, PER_ACTION * (pet.done ?? 0) + pet.bonus - pet.spent);

export function savePet() {
  const { name, since, bonus, spent, owned, placed, coat, scale, out, best } = $state.snapshot(pet);
  savePrefs({ pet: { name, since, bonus, spent, owned, placed, coat, scale, out, best } });
}
// Il primo giorno va ricordato subito: altrimenti a ogni avvio Micio ricomincerebbe da oggi.
if (!saved.since) savePet();

// Chi vuole sapere quando un'azione nuova è stata completata (il gatto festeggia).
const listeners = new Set();
export const onEarned = (fn) => (listeners.add(fn), () => listeners.delete(fn));

let checking = null;
// Rilegge le azioni completate. Si chiama dopo ogni salvataggio e quando l'indice cambia: costa una query.
export function petCheck() {
  clearTimeout(checking);
  checking = setTimeout(async () => {
    const n = await call('pet_done', { since: pet.since }, null).catch(() => null);
    if (n == null) return;
    const before = pet.done;
    pet.done = n;
    if (before != null && n > before) for (const fn of listeners) fn(n - before);
  }, 250);
}

export const COATS = [['Bianco', '#F6F4F0'], ['Rosso', '#F2B25E'], ['Crema', '#EAD7B7'], ['Grigio', '#9A9FAD'], ['Marrone', '#C98A5B'], ['Nero', '#3A3436'], ['Rosa', '#F2B0C4']];

// Gli occhi: scuri sui mantelli chiari, chiari su quelli scuri.
export function eyeFor(coat) {
  const n = parseInt(coat.replace('#', ''), 16);
  const lum = (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  return lum < 0.38 ? '#F4E9C8' : '#2B2A33';
}

// Gli oggetti della stanza: dove stanno (x in % della stanza, w in pixel dello sprite) e cosa ci fa Micio.
export const ITEMS = [
  { id: 'cuscino', name: 'Cuscino', price: 30, desc: 'Ci fa i pisolini', x: 16, w: 24, at: 'floor' },
  { id: 'ciotola', name: 'Ciotola', price: 10, desc: 'Sempre piena di crocchette', x: 30, w: 12, at: 'floor' },
  { id: 'gomitolo', name: 'Gomitolo', price: 15, desc: 'Ci gioca per ore', x: 44, w: 10, at: 'floor' },
  { id: 'tappeto', name: 'Tappeto', price: 45, desc: 'Più morbido del pavimento', x: 50, w: 44, at: 'rug' },
  { id: 'scatola', name: 'Scatola', price: 12, desc: 'Il regalo preferito', x: 60, w: 18, at: 'floor' },
  { id: 'pianta', name: 'Pianta', price: 25, desc: 'Da toccare con la zampa', x: 73, w: 12, at: 'floor' },
  { id: 'tiragraffi', name: 'Tiragraffi', price: 40, desc: 'Per farsi le unghie', x: 87, w: 14, at: 'floor' },
  { id: 'quadro', name: 'Quadro', price: 20, desc: 'Un paesaggio per la parete', x: 64, w: 18, at: 'wall' },
  { id: 'lampada', name: 'Lampada', price: 35, desc: 'Luce calda e un bersaglio', x: 38, w: 12, at: 'ceiling' },
];
