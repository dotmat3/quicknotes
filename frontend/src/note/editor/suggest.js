// Suggerimenti mentre si scrive, come in VS Code: aiutano a scrivere la sintassi delle note e dicono
// subito se il formato è giusto (una data valida, il nome di una lingua, una struttura completa).
import { syntaxTree } from '@codemirror/language';
import { PRIORITIES, dueLabel, isoToday } from './rules.js';

const CODE = new Set(['InlineCode', 'CodeText', 'FencedCode', 'CodeBlock']);
const DAYS = ['domenica', 'lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato'];

function inCode(ctx) {
  for (let n = syntaxTree(ctx.state).resolveInner(ctx.pos, -1); n; n = n.parent) if (CODE.has(n.name)) return true;
  return false;
}

// Il cursore finisce dove il testo indica `$0`, come negli snippet di VS Code.
function snippet(text) {
  return (view, _c, from, to) => {
    const at = text.indexOf('$0');
    const insert = text.replace('$0', '');
    view.dispatch({ changes: { from, to, insert }, selection: { anchor: from + (at < 0 ? insert.length : at) }, userEvent: 'input.complete' });
  };
}

const plus = (base, n) => new Date(base.getFullYear(), base.getMonth(), base.getDate() + n);
const capital = (s) => s[0].toUpperCase() + s.slice(1);

function dateOption(d, name, boost = 0) {
  const iso = isoToday(d);
  return { label: iso, displayLabel: name, detail: `${iso} · ${dueLabel(iso).label}`, type: 'date', boost };
}

// due:, entro:, scadenza: e done: propongono date; una data scritta a mano viene controllata.
export function dates(ctx) {
  const m = ctx.matchBefore(/\b(?:due|entro|scadenza|done)\s*:\s*[\d-]*/i);
  if (!m || inCode(ctx)) return null;
  const typed = m.text.slice(m.text.indexOf(':') + 1).trimStart();
  const from = m.to - typed.length;
  const now = new Date();
  let options;
  if (/^done/i.test(m.text)) {
    options = [dateOption(now, 'Oggi', 2), dateOption(plus(now, -1), 'Ieri', 1)];
  } else {
    options = [dateOption(now, 'Oggi', 9), dateOption(plus(now, 1), 'Domani', 8), dateOption(plus(now, 2), 'Dopodomani', 7)];
    for (let i = 3; i <= 7; i++) options.push(dateOption(plus(now, i), capital(DAYS[plus(now, i).getDay()]), 7 - i));
    options.push(dateOption(plus(now, 14), 'Fra due settimane', -1), dateOption(new Date(now.getFullYear(), now.getMonth() + 1, 0), 'Fine del mese', -2));
  }
  if (typed) {
    const full = /^\d{4}-\d{2}-\d{2}$/.test(typed);
    const d = full ? new Date(`${typed}T00:00`) : null;
    if (d && !Number.isNaN(d.getTime()) && isoToday(d) === typed) {
      return { from, filter: false, options: [{ label: typed, displayLabel: `✓ ${capital(DAYS[d.getDay()])} ${d.getDate()}`, detail: `data valida · ${dueLabel(typed).label}`, type: 'date' }] };
    }
    options = options.filter((o) => o.label.startsWith(typed));
    if (!options.length) {
      const hint = full ? { displayLabel: 'Data inesistente', detail: 'controlla giorno e mese' } : { displayLabel: 'Formato AAAA-MM-GG', detail: `per esempio ${isoToday(plus(now, 1))}` };
      return { from, filter: false, options: [{ label: typed, ...hint, type: 'invalid' }] };
    }
  }
  return { from, filter: false, options };
}

// prio:, priorità: e priority: propongono alta, media e bassa.
const PRIO_OPTIONS = PRIORITIES.map(([name, label, arrow], i) => ({ label: name, displayLabel: `${arrow} ${label}`, detail: 'priorità dell’azione', type: 'keyword', boost: -i }));

export function priority(ctx) {
  // Un controllo veloce prima della regola completa: questa fonte gira a ogni tasto.
  const before = ctx.state.sliceDoc(Math.max(0, ctx.pos - 20), ctx.pos);
  if (!before.includes(':')) return null;
  const m = ctx.matchBefore(/(?:prio|priorit[àa]|priority)\s*:\s*[a-zà]*/i);
  if (!m || /[\p{L}\p{N}_]/u.test(ctx.state.sliceDoc(m.from - 1, m.from)) || inCode(ctx)) return null;
  const typed = m.text.slice(m.text.indexOf(':') + 1).trimStart();
  return { from: m.to - typed.length, options: PRIO_OPTIONS, validFor: /^[a-zà]*$/i };
}

// ! a inizio parola propone !decisione.
export function decision(ctx) {
  const m = ctx.matchBefore(/(?:^|\s)!\p{L}*/u);
  if (!m || inCode(ctx)) return null;
  const word = m.text.slice(m.text.indexOf('!'));
  if (!'!decisione'.startsWith(word.toLowerCase()) || word === '!decisione') return null;
  return { from: m.to - word.length, options: [{ label: '!decisione', detail: 'segna la riga come decisione · Ctrl D', type: 'keyword' }] };
}

// - [ a inizio riga: azione da fare o fatta.
export function task(ctx) {
  const m = ctx.matchBefore(/^\s*[-*+] \[[ xX]?/);
  if (!m || inCode(ctx)) return null;
  return {
    from: m.from + m.text.indexOf('['),
    filter: false,
    options: [
      { label: '[ ] ', displayLabel: 'Azione da fare', detail: '- [ ] testo @persona #etichetta due:… prio:alta', type: 'keyword' },
      { label: '[x] ', displayLabel: 'Azione fatta oggi', detail: `- [x] testo done:${isoToday()}`, type: 'keyword', apply: snippet(`[x] $0 done:${isoToday()}`) },
    ],
  };
}

const LANGS = ['python', 'javascript', 'typescript', 'json', 'bash', 'sql', 'rust', 'html', 'css', 'markdown', 'yaml', 'java', 'go', 'c', 'cpp', 'csharp', 'php', 'xml'];

// ``` a inizio riga propone la lingua del blocco di codice e lo chiude.
export function fence(ctx) {
  const m = ctx.matchBefore(/^\s*```[\w+#-]*/);
  if (!m || ctx.state.doc.lineAt(ctx.pos).to !== ctx.pos) return null;
  return {
    from: m.from + m.text.indexOf('```') + 3,
    options: [
      ...LANGS.map((lang, i) => ({ label: lang, detail: 'blocco di codice con i colori', type: 'type', boost: -i / 100, apply: snippet(`${lang}\n$0\n\`\`\``) })),
      { label: 'testo', displayLabel: 'Senza lingua', detail: 'blocco a larghezza fissa', type: 'type', boost: -1, apply: snippet('\n$0\n```') },
    ],
  };
}

const TABLE = '| Colonna$0 | Colonna |\n| --- | --- |\n|  |  |';

// | a inizio riga propone una tabella completa.
export function table(ctx) {
  const m = ctx.matchBefore(/^\|/);
  if (!m || inCode(ctx) || ctx.state.doc.lineAt(ctx.pos).text !== '|') return null;
  return {
    from: m.from,
    filter: false,
    options: [{ label: '| Tabella |', displayLabel: 'Tabella con due colonne', detail: 'intestazione, separatore e una riga', type: 'keyword', apply: snippet(TABLE) }],
  };
}

const STRUCTURES = [
  ['Azione', '- [ ] testo @persona #etichetta due:… prio:alta', '- [ ] $0'],
  ['Sotto-attività', 'rientrata sotto un’azione · Tab', '    - [ ] $0'],
  ['Decisione', 'testo !decisione · Ctrl D', '$0 !decisione'],
  ['Titolo di sezione', '## Titolo', '## $0'],
  ['Avviso', '> [!NOTE] e gli altri tipi di GitHub', '> [!NOTE]\n> $0'],
  ['Tabella', '| a | b | con intestazione', TABLE],
  ['Blocco di codice', '```lingua', '```$0\n\n```'],
  ['Link a una nota', '[[Titolo della nota]]', '[[$0]]'],
  ['Nota a piè di pagina', 'riferimento [^1] e testo in fondo', '[^1]\n\n[^1]: $0'],
  ['Elenco puntato', '- voce', '- $0'],
  ['Citazione', '> testo', '> $0'],
  ['Linea di separazione', '---', '---\n$0'],
];

// / a inizio riga, oppure Ctrl+Spazio su una riga vuota: le strutture che si possono scrivere.
export function structures(ctx) {
  const line = ctx.state.doc.lineAt(ctx.pos);
  const slash = ctx.matchBefore(/^\s*\/[\p{L} -]*/u);
  const empty = ctx.explicit && !line.text.slice(0, ctx.pos - line.from).trim();
  if ((!slash && !empty) || inCode(ctx)) return null;
  return {
    from: slash ? slash.from + slash.text.indexOf('/') : ctx.pos,
    options: STRUCTURES.map(([name, detail, text], i) => ({ label: `/${name.toLowerCase()}`, displayLabel: name, detail, type: 'keyword', boost: -i / 100, apply: snippet(text) })),
  };
}

export const SUGGESTIONS = [dates, priority, decision, task, fence, table, structures];
