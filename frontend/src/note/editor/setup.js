// Configurazione di CodeMirror per le note. È un blocco separato: la prima schermata non lo aspetta.
import { autocompletion, completionKeymap } from '@codemirror/autocomplete';
import { defaultKeymap, history, historyKeymap, indentLess, indentMore, isolateHistory } from '@codemirror/commands';
import { markdown, markdownKeymap, markdownLanguage } from '@codemirror/lang-markdown';
import { HighlightStyle, indentUnit, syntaxHighlighting } from '@codemirror/language';
import { highlightSelectionMatches, search, searchKeymap } from '@codemirror/search';
import { Annotation, Compartment, EditorSelection, EditorState, Facet, Prec, Transaction } from '@codemirror/state';
import { drawSelection, dropCursor, EditorView, keymap, lineNumbers, placeholder } from '@codemirror/view';
import { tags as t } from '@lezer/highlight';
import { livePreview, toggleTaskAt } from './livePreview.js';
import { ACTION, diff } from './rules.js';
import { tables } from './tables.js';
import './editor.css';

const PHRASES = {
  Find: 'Cerca',
  Replace: 'Sostituisci',
  next: 'Successivo',
  previous: 'Precedente',
  all: 'Tutti',
  'match case': 'Maiuscole',
  regexp: 'Espressione regolare',
  'by word': 'Parola intera',
  replace: 'Sostituisci',
  'replace all': 'Sostituisci tutti',
  close: 'Chiudi',
  'Go to line': 'Vai alla riga',
  go: 'Vai',
};

// Anteprima viva oppure testo grezzo con i numeri di riga (Sorgente e Affiancata).
const modeConf = new Compartment();
const modeKind = Facet.define({ combine: (v) => v[0] ?? 'live' });

function modeExtensions(kind, tagColor) {
  return kind === 'live'
    ? [modeKind.of('live'), livePreview(tagColor), tables(tagColor)]
    : [modeKind.of('source'), lineNumbers(), highlightSelectionMatches(), EditorView.editorAttributes.of({ class: 'cm-source' })];
}

export function setMode(view, mode, tagColor) {
  const kind = mode === 'live' ? 'live' : 'source';
  if (view.state.facet(modeKind) !== kind) view.dispatch({ effects: modeConf.reconfigure(modeExtensions(kind, tagColor)) });
}

const highlight = HighlightStyle.define([
  { tag: t.strong, class: 'tok-strong' },
  { tag: t.emphasis, class: 'tok-em' },
  { tag: t.strikethrough, class: 'tok-strike' },
  { tag: t.monospace, class: 'tok-code' },
  { tag: [t.link, t.url], class: 'tok-url' },
  { tag: [t.processingInstruction, t.contentSeparator], class: 'tok-mark' },
  { tag: t.quote, class: 'tok-quote' },
]);

const WORD = /[\p{L}\p{N}_.@#&/]/u;

// @ propone le persone, # le etichette, [[ le note. I dati si chiedono al backend quando servono.
function completions(suggest) {
  return async (ctx) => {
    const wiki = ctx.matchBefore(/\[\[[^\]\n]*/u);
    if (wiki) {
      const notes = await suggest('note', wiki.text.slice(2));
      return {
        from: wiki.from + 2,
        filter: false,
        options: notes.map((n) => ({ label: n.title, detail: n.date?.slice(0, 10), apply: `${n.id}|${n.title}]]` })),
      };
    }
    const m = ctx.matchBefore(/[@#][\p{L}\p{N}_\-./]*/u);
    if (!m) return null;
    const before = ctx.state.sliceDoc(m.from - 1, m.from);
    if (before && WORD.test(before)) return null;
    const names = await suggest(m.text[0] === '@' ? 'person' : 'tag', '');
    if (!names.length) return null;
    return { from: m.from + 1, options: names.map((label) => ({ label })), validFor: /^[\p{L}\p{N}_\-./]*$/u };
  };
}

function selectedLines(state) {
  const seen = new Map();
  for (const r of state.selection.ranges) {
    for (let pos = r.from; pos <= r.to; ) {
      const line = state.doc.lineAt(pos);
      seen.set(line.number, line);
      pos = line.to + 1;
    }
  }
  return [...seen.values()];
}

// Ctrl+T: trasforma la riga in azione; su un'azione, la spunta.
function toggleAction(view) {
  for (const line of selectedLines(view.state).reverse()) {
    if (ACTION.test(line.text)) toggleTaskAt(view, line.from);
    else {
      const [prefix, indent] = /^(\s*)((?:[-*+]|\d+[.)])\s+)?/.exec(line.text);
      view.dispatch({ changes: { from: line.from + indent.length, to: line.from + prefix.length, insert: '- [ ] ' }, userEvent: 'input.action' });
    }
  }
  return true;
}

// Ctrl+D: segna la riga come decisione, o toglie il segno.
function toggleDecision(view) {
  const re = /\s*!(?:decisione|decision|dec)(?![\p{L}\p{N}_])/iu;
  const lines = selectedLines(view.state);
  const marked = lines.every((l) => re.test(l.text));
  const changes = lines
    .map((line) => {
      const m = re.exec(line.text);
      if (marked) return { from: line.from + m.index, to: line.from + m.index + m[0].length };
      if (m) return null;
      const end = line.from + line.text.trimEnd().length;
      return { from: end, to: line.to, insert: ' !decisione' };
    })
    .filter(Boolean);
  view.dispatch({ changes, userEvent: 'input.decision' });
  return true;
}

function insertTime(view) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  view.dispatch(view.state.replaceSelection(`${p(now.getHours())}:${p(now.getMinutes())} `), { userEvent: 'input.time', scrollIntoView: true });
  return true;
}

// Le modifiche inoltrate tra le viste della stessa nota portano questa annotazione, per evitare rimbalzi.
const synced = Annotation.define();

export function createState(doc, { onChange, onOpen, tagColor, suggest }) {
  return EditorState.create({
    doc,
    selection: EditorSelection.cursor(doc.length),
    extensions: [
      history(),
      drawSelection(),
      dropCursor(),
      indentUnit.of('    '),
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({ spellcheck: 'true', lang: 'it', 'aria-label': 'Testo della nota' }),
      markdown({ base: markdownLanguage, addKeymap: false }),
      syntaxHighlighting(highlight),
      modeConf.of(modeExtensions('live', tagColor)),
      EditorState.phrases.of(PHRASES),
      search({ top: true }),
      autocompletion({ override: [completions(suggest)], icons: false }),
      placeholder('Inizia a scrivere…'),
      Prec.high(
        keymap.of([
          { key: 'Mod-t', run: toggleAction, preventDefault: true },
          { key: 'Mod-d', run: toggleDecision, preventDefault: true },
          { key: 'Mod-Shift-h', run: insertTime, preventDefault: true },
          { key: 'Tab', run: indentMore },
          { key: 'Shift-Tab', run: indentLess },
          ...markdownKeymap,
          ...completionKeymap,
        ]),
      ),
      keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap.filter((b) => b.key !== 'Mod-d')]),
      EditorView.domEventHandlers({
        mousedown(e) {
          const el = e.target.closest?.('[data-wiki],[data-href],[data-person],[data-tag]');
          if (!el) return false;
          // Mentre si scrive sulla riga serve Ctrl+clic; fuori basta un clic.
          const d = el.dataset;
          if (d.wiki === undefined && d.href === undefined && !(e.ctrlKey || e.metaKey)) return false;
          e.preventDefault();
          if (d.wiki !== undefined) onOpen('wiki', d.wiki);
          else if (d.href !== undefined) onOpen('url', d.href);
          else if (d.person) onOpen('person', d.person);
          else onOpen('tag', d.tag);
          return true;
        },
        // Un link nelle tabelle è un vero <a>: la pagina non deve mai seguirlo.
        click(e) {
          if (!e.target.closest?.('a')) return false;
          e.preventDefault();
          return true;
        },
      }),
      EditorView.updateListener.of((u) => {
        if (!u.docChanged) return;
        const fromPeer = u.transactions.some((tr) => tr.annotation(synced));
        onChange(u.state.doc.toString(), fromPeer ? null : u);
      }),
    ],
  });
}

export function createView(parent, state) {
  return new EditorView({ state, parent });
}

// Applica a una vista il testo aggiornato altrove: resta fuori dalla sua cronologia.
export function applyPeer(view, update) {
  update.changes.iterChanges(() => {});
  view.dispatch({ changes: update.changes, annotations: [synced.of(true), Transaction.addToHistory.of(false)] });
}

// Riallinea una vista a un testo arrivato da fuori (altra app, Claude). Resta annullabile.
export function applyText(view, text) {
  const cur = view.state.doc.toString();
  if (cur === text) return;
  view.dispatch({ changes: diff(cur, text), annotations: [synced.of(true), isolateHistory.of('full')] });
}

export function stateText(state) {
  return state.doc.toString();
}
