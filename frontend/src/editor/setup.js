// Configurazione di CodeMirror per le note: Markdown con anteprima viva, comandi rapidi e completamento di @ e #.
import { autocompletion } from '@codemirror/autocomplete';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import { markdown, markdownLanguage } from '@codemirror/lang-markdown';
import { HighlightStyle, indentUnit, syntaxHighlighting } from '@codemirror/language';
import { EditorSelection, EditorState, Prec } from '@codemirror/state';
import { drawSelection, dropCursor, EditorView, keymap, placeholder } from '@codemirror/view';
import { tags as t } from '@lezer/highlight';
import { flashField, insertTime, markDecision, toggleAction } from './commands.js';
import { livePreview } from './livePreview.js';

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

// @ propone le persone gia' citate, # i progetti
function tokenCompletions(getSuggestions) {
  return (ctx) => {
    const m = ctx.matchBefore(/[@#][\p{L}\p{N}_\-./]*/u);
    if (!m) return null;
    const before = ctx.state.sliceDoc(m.from - 1, m.from);
    if (before && WORD.test(before)) return null;
    const { people, projects } = getSuggestions();
    const isPerson = m.text[0] === '@';
    const names = isPerson ? people : projects;
    if (!names.length) return null;
    return {
      from: m.from + 1,
      options: names.map((label) => ({ label, type: isPerson ? 'person' : 'project' })),
      validFor: /^[\p{L}\p{N}_\-./]*$/u,
    };
  };
}

/**
 * @param {HTMLElement} parent
 * @param {{ doc: string, onChange: (text: string) => void, onCommand: (kind: string) => void,
 *           getSuggestions: () => {people: string[], projects: string[]} }} opts
 */
export function createEditor(parent, { doc, onChange, onCommand, getSuggestions }) {
  const run = (cmd) => (view) => cmd(view, onCommand);
  const state = EditorState.create({
    doc,
    selection: EditorSelection.cursor(doc.length),
    extensions: [
      history(),
      drawSelection(),
      dropCursor(),
      indentUnit.of('  '),
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({ spellcheck: 'true', lang: 'it', 'aria-label': 'Testo della nota' }),
      markdown({ base: markdownLanguage }),
      syntaxHighlighting(highlight),
      livePreview,
      flashField,
      autocompletion({ override: [tokenCompletions(getSuggestions)], icons: false }),
      placeholder('Inizia a scrivere…'),
      Prec.high(keymap.of([
        { key: 'Mod-t', run: run(toggleAction), preventDefault: true },
        { key: 'Mod-d', run: run(markDecision), preventDefault: true },
        { key: 'Mod-Shift-h', run: run(insertTime), preventDefault: true },
      ])),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      EditorView.updateListener.of((u) => u.docChanged && onChange(u.state.doc.toString())),
    ],
  });
  return new EditorView({ state, parent });
}

export function focusEnd(view) {
  view.focus();
  view.dispatch({ selection: EditorSelection.cursor(view.state.doc.length), scrollIntoView: true });
}
