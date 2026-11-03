// Configurazione di CodeMirror per le note. È un blocco separato: la prima schermata non lo aspetta.
import { autocompletion, completionKeymap } from '@codemirror/autocomplete';
import { defaultKeymap, history, historyKeymap, indentLess, indentMore, isolateHistory } from '@codemirror/commands';
import { markdown, markdownKeymap, markdownLanguage } from '@codemirror/lang-markdown';
import { HighlightStyle, indentUnit, syntaxHighlighting, syntaxTree } from '@codemirror/language';
import { languages } from '@codemirror/language-data';
import { highlightSelectionMatches, search, searchKeymap } from '@codemirror/search';
import { Annotation, Compartment, EditorSelection, EditorState, Facet, Prec, StateEffect, StateField, Transaction } from '@codemirror/state';
import { Decoration, drawSelection, dropCursor, EditorView, keymap, lineNumbers, placeholder, ViewPlugin } from '@codemirror/view';
import { classHighlighter, tags as t } from '@lezer/highlight';
import { livePreview, toggleTaskAt } from './livePreview.js';
import { ACTION, ALERT_DESCRIPTIONS, ALERT_LABELS, FOOTNOTE, MENTION, TAG, WIKI, alertIcon, diff } from './rules.js';
import { SUGGESTIONS } from './suggest.js';
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

// Sorgente: il testo resta grezzo, ma @persone, #etichette e [[link]] si aprono con Ctrl+clic
// e i segni di avvisi e note a piè di pagina hanno il loro colore, come nella tavola Markdown.
const SOURCE_SKIP = new Set(['InlineCode', 'CodeText', 'FencedCode', 'CodeBlock', 'URL', 'Autolink']);
const ALERT_MARK = /^(\s*>\s*)(\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\])/i;

function sourceMarks(tagColor) {
  const build = (view) => {
    const decos = [];
    const tree = syntaxTree(view.state);
    for (const { from, to } of view.visibleRanges) {
      for (let pos = from; pos <= to; ) {
        const line = view.state.doc.lineAt(pos);
        pos = line.to + 1;
        const skip = (i) => {
          for (let n = tree.resolveInner(line.from + i, 1); n; n = n.parent) if (SOURCE_SKIP.has(n.name)) return true;
          return false;
        };
        const add = (m, cls, attrs) => {
          if (!skip(m.index)) decos.push(Decoration.mark({ class: cls, attributes: attrs }).range(line.from + m.index, line.from + m.index + m[0].length));
        };
        const alert = ALERT_MARK.exec(line.text);
        if (alert) decos.push(Decoration.mark({ class: `cm-alert-mark cm-alert-${alert[3].toLowerCase()}` }).range(line.from + alert[1].length, line.from + alert[0].length));
        for (const m of line.text.matchAll(MENTION)) add(m, 'cm-mention', { 'data-person': m[1], 'data-needs-ctrl': '' });
        for (const m of line.text.matchAll(TAG)) add(m, 'cm-tag', { 'data-tag': m[1], 'data-needs-ctrl': '', style: `color:${tagColor(m[1])}` });
        for (const m of line.text.matchAll(WIKI)) if (!m[1]) add(m, 'cm-src-wiki', { 'data-wiki': m[2].trim(), 'data-needs-ctrl': '' });
        for (const m of line.text.matchAll(FOOTNOTE)) add(m, 'cm-fn');
      }
      tree.iterate({
        from,
        to,
        enter: (n) => {
          if (n.name !== 'URL') return undefined;
          decos.push(Decoration.mark({ class: 'cm-src-url', attributes: { 'data-href': view.state.sliceDoc(n.from, n.to), 'data-needs-ctrl': '' } }).range(n.from, n.to));
          return false;
        },
      });
    }
    return Decoration.set(decos, true);
  };
  return ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = build(view);
      }
      update(u) {
        if (u.docChanged || u.viewportChanged || syntaxTree(u.startState) !== syntaxTree(u.state)) this.decorations = build(u.view);
      }
    },
    { decorations: (v) => v.decorations },
  );
}

// Scrivendo `> [!` compare l'elenco dei tipi di avviso, come in GitHub.
const ALERT_TYPES = ['NOTE', 'TIP', 'IMPORTANT', 'WARNING', 'CAUTION'];

function alertCompletions(ctx) {
  const m = ctx.matchBefore(/^\s*>\s?\[!\w*/);
  if (!m) return null;
  const from = m.from + m.text.indexOf('[!');
  return {
    from,
    filter: false,
    options: ALERT_TYPES.filter((k) => k.startsWith(m.text.slice(m.text.indexOf('[!') + 2).toUpperCase())).map((k) => ({
      label: `[!${k}]`,
      type: `alert-${k.toLowerCase()}`,
      alert: k,
      // Il blocco continua sulla riga dopo, dove si scrive il testo dell'avviso.
      apply: (view, _c, a, b) => {
        const insert = `[!${k}]\n> `;
        view.dispatch({ changes: { from: a, to: b, insert }, selection: { anchor: a + insert.length }, userEvent: 'input.complete' });
      },
    })),
  };
}

// Icona, nome e descrizione accanto a ogni tipo di avviso nell'elenco.
const alertOptionParts = [
  { position: 20, render: (c) => (c.alert ? alertIcon(c.alert) : null) },
  {
    position: 60,
    render: (c) => {
      if (!c.alert) return null;
      const el = document.createElement('span');
      el.className = 'cm-alert-option';
      const name = document.createElement('span');
      name.textContent = ALERT_LABELS[c.alert];
      const desc = document.createElement('span');
      desc.className = 'cm-alert-option-desc';
      desc.textContent = ALERT_DESCRIPTIONS[c.alert];
      el.append(name, desc);
      return el;
    },
  },
];

// Anteprima viva oppure testo grezzo con i numeri di riga (Sorgente e Affiancata).
const modeConf = new Compartment();
const modeKind = Facet.define({ combine: (v) => v[0] ?? 'live' });

function modeExtensions(kind, tagColor) {
  return kind === 'live'
    ? [modeKind.of('live'), livePreview(tagColor), tables(tagColor)]
    : [modeKind.of('source'), lineNumbers(), highlightSelectionMatches(), sourceMarks(tagColor), EditorView.editorAttributes.of({ class: 'cm-source' })];
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

// La riga mostrata aprendo una nota da Ctrl K o dal Calendario resta evidenziata per un attimo: il colore
// sfuma con un'animazione CSS, e la decorazione sparisce alla prima modifica o al primo clic.
const flash = StateEffect.define();
const flashField = StateField.define({
  create: () => Decoration.none,
  update(deco, tr) {
    for (const e of tr.effects) if (e.is(flash)) return e.value === null ? Decoration.none : Decoration.set([Decoration.line({ class: 'cm-flash' }).range(e.value)]);
    return tr.docChanged || tr.isUserEvent('select') ? Decoration.none : deco;
  },
  provide: (f) => EditorView.decorations.from(f),
});

export function revealLine(view, line) {
  const l = view.state.doc.line(Math.min(Math.max(1, line), view.state.doc.lines));
  view.dispatch({ selection: { anchor: l.from }, effects: [EditorView.scrollIntoView(l.from, { y: 'center' }), flash.of(l.from)] });
  setTimeout(() => unflash(view), 1600);
}

// Va spenta anche prima di conservare lo stato di una scheda nascosta, o resterebbe accesa al ritorno.
export function unflash(view) {
  if (view.state.field(flashField, false)?.size) view.dispatch({ effects: flash.of(null) });
}

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
      // Le lingue dei blocchi di codice si caricano solo quando compaiono nella nota.
      markdown({ base: markdownLanguage, addKeymap: false, codeLanguages: languages }),
      syntaxHighlighting(highlight),
      syntaxHighlighting(classHighlighter),
      modeConf.of(modeExtensions('live', tagColor)),
      EditorState.phrases.of(PHRASES),
      search({ top: true }),
      autocompletion({
        override: [alertCompletions, ...SUGGESTIONS, completions(suggest)],
        icons: false,
        addToOptions: alertOptionParts,
        optionClass: (c) => (c.type === 'invalid' ? 'cm-opt-invalid' : ''),
      }),
      placeholder('Inizia a scrivere…'),
      flashField,
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
          if (e.button !== 0) return false;
          const el = e.target.closest?.('[data-wiki],[data-href],[data-person],[data-tag]');
          if (!el) return false;
          // Il testo che si sta scrivendo si apre con Ctrl+clic; il contenuto reso con un clic.
          const d = el.dataset;
          if (d.needsCtrl !== undefined && !(e.ctrlKey || e.metaKey)) return false;
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
