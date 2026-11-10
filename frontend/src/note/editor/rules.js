// Regole del testo, uguali a quelle del nucleo Python (quicknotes/parser.py ed edit.py).
const W = '\\p{L}\\p{N}_';
export const MENTION = new RegExp(`(?<![${W}.@])@([${W}][${W}\\-.]*[${W}]|[${W}])`, 'gu');
export const TAG = new RegExp(`(?<![${W}/#&])#([\\p{L}_][${W}\\-/]*)`, 'gu');
export const DUE = /\b(?:due|entro|scadenza)\s*:\s*(\d{4}-\d{2}-\d{2})/giu;
export const DONE = /\bdone\s*:\s*(\d{4}-\d{2}-\d{2})/giu;
// `scheduled:` è il giorno in cui farla; `due:` resta la scadenza.
export const SCHEDULED = /\bscheduled\s*:\s*(\d{4}-\d{2}-\d{2})/giu;
export const PRIO = /(?<![\p{L}\p{N}_])(?:prio|priorit[àa]|priority)\s*:\s*(alta|media|bassa|high|medium|low)(?![\p{L}\p{N}_])/giu;
// Le tre priorità, dalla più alta: nome scritto nel file, etichetta e freccia.
export const PRIORITIES = [
  ['alta', 'Alta', '↑'],
  ['media', 'Media', '→'],
  ['bassa', 'Bassa', '↓'],
];
const PRIO_NAMES = { high: 'alta', medium: 'media', low: 'bassa' };
export function prioName(value) {
  const v = String(value ?? '').toLowerCase();
  return PRIO_NAMES[v] ?? (PRIORITIES.some(([p]) => p === v) ? v : null);
}
// Per ordinare: alta 0, media 1, bassa 2, nessuna 3.
export const prioRank = (p) => {
  const i = PRIORITIES.findIndex(([name]) => name === p);
  return i < 0 ? PRIORITIES.length : i;
};
export const prioArrow = (p) => PRIORITIES.find(([name]) => name === p)?.[2] ?? '';
export const DECISION =/!(?:decisione|decision|dec)(?![\p{L}\p{N}_])/giu;
export const WIKI = /(!?)\[\[([^\]\n|]+)(?:\|([^\]\n]*))?\]\]/g;
export const ACTION = /^(\s*)[-*+]\s+\[( |x|X|\/|w|W|\?|-)\]\s*(.*)$/;
// I sei stati: nome scritto nel modello, segno nella casella, etichetta, colore.
export const STATUSES = [
  ['todo', ' ', 'Da fare', 'var(--faint)'],
  ['doing', '/', 'In corso', 'var(--accent)'],
  ['waiting', 'w', 'In attesa', 'var(--person)'],
  ['question', '?', 'Domanda', 'var(--dec)'],
  ['cancelled', '-', 'Annullata', 'var(--faint)'],
  ['done', 'x', 'Fatta', 'var(--accent)'],
];
export const CLOSED = ['done', 'cancelled'];
export const statusOfMark = (mark) => STATUSES.find(([, m]) => m === String(mark).toLowerCase())?.[0] ?? 'todo';
export const markOfStatus = (status) => STATUSES.find(([s]) => s === status)?.[1] ?? ' ';
export const statusLabel = (status) => STATUSES.find(([s]) => s === status)?.[2] ?? status;
export const ALERT_LABELS = { NOTE: 'Nota', TIP: 'Suggerimento', IMPORTANT: 'Importante', WARNING: 'Avvertenza', CAUTION: 'Attenzione' };
export const ALERT_DESCRIPTIONS = {
  NOTE: 'Informazioni utili anche a una lettura veloce',
  TIP: 'Un modo migliore o più semplice di fare qualcosa',
  IMPORTANT: 'Necessario per raggiungere l’obiettivo',
  WARNING: 'Richiede attenzione immediata per evitare problemi',
  CAUTION: 'Rischi o conseguenze negative di un’azione',
};
export const FOOTNOTE = /\[\^([^\]\s]+)\](:?)/g;

// Icona di un avviso: una maschera CSS, così non serve SVG nell'HTML.
export function alertIcon(kind) {
  const el = document.createElement('span');
  el.className = `qn-ai qn-ai-${kind.toLowerCase()}`;
  el.setAttribute('aria-hidden', 'true');
  return el;
}

const MONTHS = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
const DAYS = ['dom', 'lun', 'mar', 'mer', 'gio', 'ven', 'sab'];

export function isoToday(now = new Date()) {
  const p = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}

// Come dates.rs: «30 ott» se è passata, «oggi», «domani», altrimenti «lun 2 nov».
export function dueLabel(iso, now = new Date()) {
  const [y, m, d] = iso.split('-').map(Number);
  const due = new Date(y, m - 1, d);
  if (Number.isNaN(due.getTime())) return { label: iso, level: 'normal' };
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((due - today) / 86400000);
  if (days < 0) return { label: `${d} ${MONTHS[m - 1]}`, level: 'late' };
  if (days === 0) return { label: 'oggi', level: 'soon' };
  if (days === 1) return { label: 'domani', level: 'soon' };
  return { label: `${DAYS[due.getDay()]} ${d} ${MONTHS[m - 1]}`, level: 'normal' };
}

// Come edit.py, with_checked: casella e data di completamento cambiano insieme.
export function withChecked(line, doneOn) {
  return withStatus(line, doneOn ? 'done' : 'todo', doneOn);
}

// Come edit.py, with_status: fatta e annullata prendono `done:` con il giorno, gli altri stati lo tolgono.
export function withStatus(line, status, day) {
  const m = ACTION.exec(line);
  if (!m) return line;
  const at = line.indexOf('[', m[1].length);
  let out = line.slice(0, at) + `[${markOfStatus(status)}]` + line.slice(at + 3);
  const indent = out.slice(0, out.length - out.trimStart().length);
  out = indent + out.replace(DONE, '').trim().replace(/[ \t]{2,}/g, ' ');
  return CLOSED.includes(status) && day ? `${out} done:${day}` : out;
}

// Numeri per l'intestazione, a ogni modifica. Contano solo le azioni di primo livello.
export function noteStats(text) {
  let done = 0;
  let total = 0;
  let inFence = false;
  let topIndent = null;
  const people = new Map();
  for (const line of text.split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    for (const m of line.matchAll(MENTION)) if (!people.has(m[1].toLowerCase())) people.set(m[1].toLowerCase(), m[1]);
    const a = ACTION.exec(line);
    if (a && a[3].trim()) {
      const w = a[1].replace(/\t/g, '    ').length;
      if (topIndent !== null && w > topIndent) continue;
      topIndent = w;
      // Le annullate non contano: come nel nucleo, fatte sono solo le [x].
      if (a[2] === '-') continue;
      total += 1;
      if (a[2].toLowerCase() === 'x') done += 1;
    } else if (line.trim() && !/^\s/.test(line)) {
      topIndent = null;
    }
  }
  return { done, total, people: [...people.values()] };
}

// Prefisso e suffisso comuni: a CodeMirror arriva solo la differenza, così la modifica resta annullabile.
export function diff(a, b) {
  let start = 0;
  const max = Math.min(a.length, b.length);
  while (start < max && a.charCodeAt(start) === b.charCodeAt(start)) start++;
  let endA = a.length;
  let endB = b.length;
  while (endA > start && endB > start && a.charCodeAt(endA - 1) === b.charCodeAt(endB - 1)) {
    endA--;
    endB--;
  }
  return { from: start, to: endA, insert: b.slice(start, endB) };
}
