// Vista Azioni: filtri avanzati e testo dell'aggiunta rapida. Funzioni pure, provate in actionQuery.test.js.
import { PRIORITIES, STATUSES, isoToday, prioName } from '../note/editor/rules.js';

// "Senza progetto", "nessuna area", "senza priorità": il valore vuoto dentro un filtro a scelta multipla.
export const NONE = '-';
export const FILTER_KEYS = ['projects', 'areas', 'statuses', 'priorities', 'people', 'due', 'sources'];
export const emptyFilters = () => Object.fromEntries(FILTER_KEYS.map((k) => [k, []]));

// Le scelte dei filtri che non dipendono dalle note.
// "Da fare oggi" e "Prossimi 7 giorni" seguono le regole delle sezioni di Agenda (scadenza o scheduled:).
export const DUE_CHOICES = [
  ['late', 'In ritardo'],
  ['today', 'Da fare oggi'],
  ['next7', 'Prossimi 7 giorni'],
  ['soon', 'Oggi e domani'],
  ['week', 'Questa settimana'],
  ['later', 'Più avanti'],
  ['none', 'Senza scadenza'],
  ['planned', 'Pianificate'],
];
export const SOURCE_CHOICES = [
  ['project', 'Note di progetto'],
  ['daily', 'Note del giorno'],
  ['inbox', 'Da smistare'],
  ['other', 'Altre note'],
];

// Per ogni sezione di Agenda, i filtri di Azioni che mostrano tutte le azioni di quel tipo.
export const AGENDA_FILTERS = {
  late: { due: ['late'] },
  today: { due: ['today'] },
  doing: { statuses: ['doing'] },
  waiting: { statuses: ['waiting'] },
  question: { statuses: ['question'] },
  next: { due: ['next7'] },
  inbox: { sources: ['inbox'] },
};

const addDays = (iso, n) => {
  const [y, m, d] = iso.split('-').map(Number);
  return isoToday(new Date(y, m - 1, d + n));
};

function dueChoice(item, choice, today) {
  const { due, scheduled } = item;
  switch (choice) {
    case 'planned': return !!scheduled;
    case 'today': return due === today || (!!scheduled && scheduled <= today);
    case 'next7': {
      const end = addDays(today, 7);
      return (!!due && due > today && due <= end) || (!!scheduled && scheduled > today && scheduled <= end);
    }
    default: return item.group === choice;
  }
}

// "Da smistare" è la regola di Agenda (calcolata dal server), più tutta la nota "Da smistare".
const sourceMatch = (item, s) => (s === 'inbox' ? !!item.inbox || item.note_type === 'inbox' : sourceOf(item) === s);

export const fold = (s) => String(s ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

// Come projects.key_of in Python: `LLM Training`, `llm-training` e `#llm-training` danno lo stesso valore.
export function keyOf(name) {
  const s = fold(String(name ?? '').trim().replace(/^#+/, ''));
  let out = '';
  let dash = false;
  for (const c of s) {
    if (/[a-z0-9]/.test(c)) {
      if (dash && out) out += '-';
      dash = false;
      out += c;
    } else if (c === '-' || c === '_' || /\s/.test(c)) dash = true;
  }
  return out.slice(0, 50).replace(/^-+|-+$/g, '');
}

export function sourceOf(item) {
  if (item.is_daily) return 'daily';
  if (item.note_type === 'inbox') return 'inbox';
  if (item.note_type === 'project') return 'project';
  return 'other';
}

// ---------------------------------------------------------------- ricerca scritta

// Parole riconosciute dopo `stato:`, `entro:` e `!`; il resto del testo si cerca in azione, nota e descrizione.
function statusesFor(v) {
  const words = { aperta: ['todo', 'doing', 'waiting', 'question'], aperte: ['todo', 'doing', 'waiting', 'question'], chiusa: ['done', 'cancelled'], chiuse: ['done', 'cancelled'] };
  if (words[v]) return words[v];
  return STATUSES.filter(([key, , label]) => key.startsWith(v) || fold(label).startsWith(v) || fold(label).split(' ').some((w) => w.length > 2 && w.startsWith(v))).map(([key]) => key);
}

const TOKEN = /(-?)(?:"([^"]*)"?|(\S+))/g;

/** Il testo del campo Filtra diviso in condizioni: `#progetto/area`, `@persona`, `!alta`, `stato:attesa`,
 *  `entro:settimana`, `nota:riunione`, parole e "frasi". Un `-` davanti esclude. */
export function parseQuery(q) {
  const terms = [];
  for (const m of String(q ?? '').matchAll(TOKEN)) {
    const neg = m[1] === '-';
    const raw = m[2] ?? m[3] ?? '';
    if (!raw) continue;
    if (m[2] !== undefined) {
      terms.push({ neg, kind: 'text', value: fold(raw) });
      continue;
    }
    const kv = raw.match(/^(stato|status|entro|scadenza|due|nota|prio|priorita|priorità|persona|progetto)\s*:\s*(.+)$/iu);
    if (kv) {
      const k = fold(kv[1]);
      const value = fold(kv[2]);
      const kind = { stato: 'status', status: 'status', entro: 'due', scadenza: 'due', due: 'due', nota: 'note', prio: 'prio', priorita: 'prio', persona: 'person', progetto: 'tag' }[k];
      terms.push({ neg, kind, value });
    } else if (raw.length > 1 && raw[0] === '#') terms.push({ neg, kind: 'tag', value: fold(raw.slice(1)) });
    else if (raw.length > 1 && raw[0] === '@') terms.push({ neg, kind: 'person', value: fold(raw.slice(1)) });
    else if (raw.length > 1 && raw[0] === '!') terms.push({ neg, kind: 'prio', value: fold(raw.slice(1)) });
    else terms.push({ neg, kind: 'text', value: fold(raw) });
  }
  return terms;
}

function dueMatch(item, v, today) {
  const tomorrow = isoToday(new Date(+new Date(`${today}T12:00`) + 86400000));
  switch (v) {
    case 'ritardo': case 'late': return item.group === 'late' && !item.closed;
    case 'oggi': return item.due === today;
    case 'domani': return item.due === tomorrow;
    case 'settimana': return item.group === 'soon' || item.group === 'week';
    case 'dopo': case 'avanti': case 'piu-avanti': return item.group === 'later';
    case 'nessuna': case 'senza': case 'no': return !item.due;
    case 'pianificata': case 'pianificate': return !!item.scheduled;
    default: {
      const day = parseDay(v, new Date(`${today}T12:00`));
      return !!(day && item.due && item.due <= day);
    }
  }
}

function termMatch(item, t, today) {
  const v = t.value;
  switch (t.kind) {
    case 'tag': {
      const [head, ...rest] = v.split('/');
      const area = rest.join('/');
      const proj = keyOf(head);
      const topics = (item.topics ?? []).map(fold);
      if (item.project && item.project === proj) return !area || fold(item.area) === area || topics.includes(area);
      return fold(item.raw).includes(`#${v}`) || topics.includes(v) || fold(item.tag) === v || fold(item.tag).startsWith(`${v}/`);
    }
    case 'person': return (item.people ?? []).some((p) => fold(p).startsWith(v));
    case 'prio': {
      if (['nessuna', 'senza', 'no'].includes(v)) return !item.priority;
      const name = prioName(v) ?? PRIORITIES.find(([p]) => p.startsWith(v))?.[0];
      return !!name && item.priority === name;
    }
    case 'status': return statusesFor(v).includes(item.status);
    case 'due': return dueMatch(item, v, today);
    case 'note': return fold(item.note_title).includes(v);
    default: {
      const hay = fold([item.text, item.note_title, item.description, item.project, item.area, ...(item.people ?? []).map((p) => `@${p}`), ...(item.subs ?? []).map((s) => s.text)].join(' '));
      return hay.includes(v);
    }
  }
}

/** L'azione passa se rispetta tutti i filtri scelti (dentro un filtro basta una delle scelte) e tutte le
 *  condizioni scritte. */
export function matchItem(item, f, terms = [], today = isoToday()) {
  if (f.projects?.length && !f.projects.some((p) => (p === NONE ? !item.project : item.project === p || item.tag === p || (item.tag ?? '').startsWith(`${p}/`)))) return false;
  if (f.areas?.length && !f.areas.some((a) => (a === NONE ? !item.area : item.area === a || (item.topics ?? []).includes(a)))) return false;
  if (f.statuses?.length && !f.statuses.includes(item.status)) return false;
  if (f.priorities?.length && !f.priorities.includes(item.priority ?? NONE)) return false;
  if (f.people?.length && !f.people.some((p) => (item.people ?? []).some((x) => fold(x) === fold(p)))) return false;
  if (f.due?.length && !f.due.some((d) => dueChoice(item, d, today))) return false;
  if (f.sources?.length && !f.sources.some((s) => sourceMatch(item, s))) return false;
  return terms.every((t) => termMatch(item, t, today) !== t.neg);
}

export const filterCount = (f) => FILTER_KEYS.reduce((n, k) => n + (f?.[k]?.length ?? 0), 0);

// ---------------------------------------------------------------- aggiunta rapida

const WEEKDAYS = ['dom', 'lun', 'mar', 'mer', 'gio', 'ven', 'sab'];

/** Un giorno scritto a parole: oggi, domani, dopodomani, lun…dom (il prossimo, mai oggi), +3, +2s, 20/11,
 *  20/11/2026, 2026-11-20. Restituisce AAAA-MM-GG oppure null. */
export function parseDay(word, now = new Date()) {
  const w = fold(word).trim();
  const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const plus = (n) => isoToday(new Date(base.getFullYear(), base.getMonth(), base.getDate() + n));
  if (!w) return null;
  if (w === 'oggi') return plus(0);
  if (w === 'domani') return plus(1);
  if (w === 'dopodomani') return plus(2);
  let m = w.match(/^\+(\d{1,3})([gs]?)$/);
  if (m) return plus(Number(m[1]) * (m[2] === 's' ? 7 : 1));
  const wd = WEEKDAYS.findIndex((d) => w.startsWith(d) && (w.length === 3 || /^(lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)$/.test(w)));
  if (wd >= 0) return plus(((wd - base.getDay() + 7) % 7) || 7);
  m = w.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return w;
  m = w.match(/^(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2}|\d{4}))?$/);
  if (m) {
    const [d, mo] = [Number(m[1]), Number(m[2])];
    let y = m[3] ? Number(m[3].length === 2 ? `20${m[3]}` : m[3]) : base.getFullYear();
    let date = new Date(y, mo - 1, d);
    if (date.getMonth() !== mo - 1 || date.getDate() !== d) return null;
    // Senza anno, una data già passata è quella dell'anno prossimo.
    if (!m[3] && date < base) date = new Date(++y, mo - 1, d);
    return isoToday(date);
  }
  return null;
}

/** Trova il progetto con quel nome, chiave o alias tra quelli della barra laterale. */
export function findProject(name, projects) {
  const k = keyOf(name);
  if (!k) return null;
  return projects.find((p) => p.key === k || keyOf(p.title) === k || (p.aliases ?? []).some((a) => keyOf(a) === k)) ?? null;
}

const QUICK = new RegExp(
  [
    String.raw`(?<![\p{L}\p{N}_])!(alta|media|bassa)(?![\p{L}\p{N}_])`,
    String.raw`(?<![\p{L}\p{N}_])(?:prio|priorit[àa])\s*:\s*(alta|media|bassa)(?![\p{L}\p{N}_])`,
    String.raw`(?<![\p{L}\p{N}_])(?:due|entro|scadenza)\s*:\s*(\S+)`,
    String.raw`(?<![\p{L}\p{N}_])(?:scheduled|pianifica)\s*:\s*(\S+)`,
    String.raw`(?<![\p{L}\p{N}_/#&])#([\p{L}_][\p{L}\p{N}_\-/]*)`,
  ].join('|'),
  'giu',
);

/** Il testo dell'aggiunta rapida: priorità (`!alta`), scadenza (`entro:venerdì`), giorno in cui farla
 *  (`pianifica:domani`) e progetto (`#progetto/area`) escono dal testo e diventano scelte; il resto resta. */
export function parseQuick(input, projects = [], now = new Date()) {
  const out = { text: '', project: null, area: null, due: null, scheduled: null, priority: null };
  const text = String(input ?? '').replace(QUICK, (all, p1, p2, due, sched, tag) => {
    if (p1 || p2) {
      out.priority = fold(p1 || p2);
      return '';
    }
    if (due || sched) {
      const day = parseDay(due || sched, now);
      if (!day) return all;
      out[due ? 'due' : 'scheduled'] = day;
      return '';
    }
    if (tag && !out.project) {
      const [head, ...rest] = tag.split('/');
      const p = findProject(head, projects);
      if (p) {
        out.project = p.key;
        out.area = keyOf(rest.join('/')) || null;
        return '';
      }
    }
    return all;
  });
  out.text = text.replace(/\s+/g, ' ').trim();
  return out;
}

/** La parola che si sta scrivendo prima del cursore, se comincia con `#` o `@`: per i suggerimenti. */
export function tokenAt(text, caret) {
  const m = String(text).slice(0, caret).match(/(?:^|\s)([#@])([^\s#@]*)$/u);
  return m ? { sigil: m[1], value: m[2], start: caret - m[2].length - 1 } : null;
}
