// Tabelle nell'anteprima viva. Sono decorazioni a blocco, che CodeMirror accetta solo da uno StateField.
// Con il cursore dentro la tabella si vede il testo grezzo.
import { syntaxTree } from '@codemirror/language';
import { StateField } from '@codemirror/state';
import { Decoration, EditorView, WidgetType } from '@codemirror/view';
import { renderMarkdown } from '../preview.js';

// Blocchi che non possono contenere una tabella: non serve scendere nei loro figli.
const LEAVES = new Set(['Paragraph', 'FencedCode', 'CodeBlock', 'ATXHeading1', 'ATXHeading2', 'ATXHeading3', 'ATXHeading4', 'ATXHeading5', 'ATXHeading6', 'HTMLBlock', 'SetextHeading1', 'SetextHeading2']);

class TableWidget extends WidgetType {
  constructor(source, tagColor) {
    super();
    this.source = source;
    this.tagColor = tagColor;
  }
  eq(other) {
    return other.source === this.source;
  }
  toDOM() {
    const wrap = document.createElement('div');
    wrap.className = 'cm-table pv';
    wrap.append(...renderMarkdown(this.source, this.tagColor).childNodes);
    return wrap;
  }
  // Il clic arriva all'editor: porta il cursore nella tabella, o apre @, # e [[link]].
  ignoreEvent() {
    return false;
  }
}

function build(state, tagColor) {
  const decos = [];
  const ranges = state.selection.ranges;
  syntaxTree(state).iterate({
    enter: (node) => {
      if (LEAVES.has(node.name)) return false;
      if (node.name !== 'Table') return undefined;
      const from = state.doc.lineAt(node.from).from;
      const to = state.doc.lineAt(node.to).to;
      if (!ranges.some((r) => r.to >= from && r.from <= to)) {
        decos.push(Decoration.replace({ widget: new TableWidget(state.sliceDoc(from, to), tagColor), block: true }).range(from, to));
      }
      return false;
    },
  });
  return Decoration.set(decos);
}

export function tables(tagColor) {
  return StateField.define({
    create: (state) => build(state, tagColor),
    update: (decos, tr) => (tr.docChanged || tr.selection || syntaxTree(tr.startState) !== syntaxTree(tr.state) ? build(tr.state, tagColor) : decos),
    provide: (field) => EditorView.decorations.from(field),
  });
}
