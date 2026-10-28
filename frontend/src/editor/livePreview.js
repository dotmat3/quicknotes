// Anteprima viva del Markdown, come in Obsidian: i marcatori spariscono fuori dalla riga del cursore,
// le azioni hanno caselle cliccabili, @persone e #tag sono evidenziati, scadenze e decisioni diventano etichette.
import { syntaxTree } from '@codemirror/language';
import { Decoration, EditorView, ViewPlugin, WidgetType } from '@codemirror/view';
import { dueBadge } from './dates.js';

// stesse regole di quicknotes/parser.py (\w di Python = lettere, cifre e _ Unicode)
const W = '\\p{L}\\p{N}_';
const MENTION = new RegExp(`(?<![${W}.@])@([${W}][${W}\\-.]*[${W}]|[${W}])`, 'gu');
const TAG = new RegExp(`(?<![${W}/#&])#(\\p{L}[${W}\\-/]*)`, 'gu');
const DUE = /(?:due|entro|scadenza)\s*:\s*(\d{4}-\d{2}-\d{2})/giu;
const DECISION = /!(?:decisione|decision|dec)(?![\p{L}\p{N}_])/giu;
const SKIP_NODES = new Set(['InlineCode', 'URL', 'CodeText', 'FencedCode', 'CodeBlock', 'Autolink']);

const ICON_CHECK = '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>';
const ICON_FLAG = '<svg viewBox="0 0 24 24"><path d="M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.33 2q2 0 3.67-.8a1 1 0 0 1 1.4.9v9.8a1 1 0 0 1-.6.9A8 8 0 0 1 15.33 16c-2.33 0-4.33-2-7.33-2a6 6 0 0 0-4 1.5"/></svg>';
const ICON_CAL = '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>';

// ------------------------------------------------------------------ widget
class CheckboxWidget extends WidgetType {
  constructor(checked) {
    super();
    this.checked = checked;
  }
  eq(other) {
    return other.checked === this.checked;
  }
  toDOM(view) {
    const box = document.createElement('span');
    box.className = 'cm-task-box';
    box.setAttribute('role', 'checkbox');
    box.innerHTML = ICON_CHECK;
    this.updateDOM(box);
    box.addEventListener('mousedown', (e) => {
      e.preventDefault();
      toggleTaskAt(view, view.posAtDOM(box));
    });
    return box;
  }
  // stessa casella, stato diverso: si aggiorna sul posto cosi' la transizione CSS si vede
  updateDOM(dom) {
    dom.classList.toggle('checked', this.checked);
    dom.setAttribute('aria-checked', String(this.checked));
    return true;
  }
  ignoreEvent() {
    return true;
  }
}

class BulletWidget extends WidgetType {
  eq() {
    return true;
  }
  toDOM() {
    const el = document.createElement('span');
    el.className = 'cm-bullet';
    el.innerHTML = '<span></span>';
    return el;
  }
}

class BadgeWidget extends WidgetType {
  constructor(kind, label, level = '') {
    super();
    this.kind = kind;
    this.label = label;
    this.level = level;
  }
  eq(other) {
    return other.kind === this.kind && other.label === this.label && other.level === this.level;
  }
  toDOM() {
    const el = document.createElement('span');
    el.className = `cm-badge cm-badge-${this.kind} ${this.level}`;
    el.innerHTML = (this.kind === 'due' ? ICON_CAL : ICON_FLAG) + `<span></span>`;
    el.lastChild.textContent = this.label;
    return el;
  }
}

const bullet = Decoration.replace({ widget: new BulletWidget() });
const hide = Decoration.replace({});
const lineDeco = (cls) => Decoration.line({ class: cls });
const mark = (cls) => Decoration.mark({ class: cls });

export function toggleTaskAt(view, pos) {
  const line = view.state.doc.lineAt(pos);
  const m = /\[( |x|X)\]/.exec(line.text.slice(pos - line.from));
  if (!m) return false;
  const at = pos + m.index + 1;
  view.dispatch({ changes: { from: at, to: at + 1, insert: m[1] === ' ' ? 'x' : ' ' }, userEvent: 'input.toggle' });
  return true;
}

// ------------------------------------------------------------------ costruzione
function activeLines(state) {
  const lines = new Set();
  if (!state.facet(EditorView.editable)) return lines;
  for (const r of state.selection.ranges) {
    const first = state.doc.lineAt(r.from).number;
    const last = state.doc.lineAt(r.to).number;
    for (let n = first; n <= last; n++) lines.add(n);
  }
  return lines;
}

function build(view, focused) {
  const { state } = view;
  const doc = state.doc;
  const active = focused ? activeLines(state) : new Set();
  const isActive = (pos) => active.has(doc.lineAt(pos).number);
  const decos = [];
  const atomic = [];
  const tree = syntaxTree(state);
  const codeLines = new Set();

  const replace = (from, to, deco = hide, isAtomic = false) => {
    if (to <= from) return;
    decos.push(deco.range(from, to));
    if (isAtomic) atomic.push(deco.range(from, to));
  };
  const spaceAfter = (pos) => (doc.sliceString(pos, pos + 1) === ' ' ? pos + 1 : pos);

  for (const { from, to } of view.visibleRanges) {
    tree.iterate({
      from, to,
      enter: (node) => {
        const name = node.name;
        if (name === 'FencedCode' || name === 'CodeBlock') {
          for (let pos = node.from; pos <= node.to;) {
            const line = doc.lineAt(pos);
            codeLines.add(line.number);
            decos.push(lineDeco('cm-codeblock').range(line.from));
            pos = line.to + 1;
          }
          if (name === 'FencedCode' && !isActive(node.from)) {
            node.node.getChildren('CodeMark').forEach((m) => decos.push(mark('cm-fence-mark').range(m.from, m.to)));
          }
          return false;
        }
        const heading = /^ATXHeading(\d)$/.exec(name);
        if (heading) {
          decos.push(lineDeco(`cm-h cm-h${heading[1]}`).range(doc.lineAt(node.from).from));
          const m = node.node.getChild('HeaderMark');
          if (m && !isActive(node.from)) replace(m.from, spaceAfter(m.to));
          return;
        }
        if (name === 'ListMark') {
          const line = doc.lineAt(node.from);
          const task = node.node.nextSibling;
          const taskMark = task?.name === 'Task' ? task.getChild('TaskMarker') : null;
          if (taskMark) {
            const checked = /x/i.test(doc.sliceString(taskMark.from, taskMark.to));
            decos.push(lineDeco(checked ? 'cm-task cm-task-done' : 'cm-task').range(line.from));
            replace(node.from, spaceAfter(taskMark.to), Decoration.replace({ widget: new CheckboxWidget(checked) }), true);
          } else if (/^[-*+]$/.test(doc.sliceString(node.from, node.to)) && doc.sliceString(node.to, node.to + 1) === ' ') {
            decos.push(lineDeco('cm-li').range(line.from));
            replace(node.from, node.to + 1, bullet, true);
          } else {
            decos.push(mark('cm-ol-mark').range(node.from, node.to));
          }
          return;
        }
        if (name === 'QuoteMark') {
          decos.push(lineDeco('cm-quote').range(doc.lineAt(node.from).from));
          if (!isActive(node.from)) replace(node.from, spaceAfter(node.to));
          return;
        }
        if (name === 'HorizontalRule') {
          decos.push(lineDeco('cm-hr').range(doc.lineAt(node.from).from));
          if (!isActive(node.from)) replace(node.from, node.to);
          return;
        }
        if (name === 'EmphasisMark' || name === 'StrikethroughMark') {
          if (!isActive(node.from)) replace(node.from, node.to);
          return;
        }
        if (name === 'InlineCode') {
          decos.push(mark('cm-inline-code').range(node.from, node.to));
          if (!isActive(node.from)) node.node.getChildren('CodeMark').forEach((m) => replace(m.from, m.to));
          return false;
        }
        if (name === 'Link') {
          const marks = node.node.getChildren('LinkMark');
          if (marks.length >= 2 && marks[0].to < marks[1].from) {
            decos.push(mark('cm-link').range(marks[0].to, marks[1].from));
            if (!isActive(node.from)) {
              replace(node.from, marks[0].to);
              replace(marks[1].from, node.to);
            }
          }
          return false;
        }
      },
    });

    // persone, tag, scadenze e decisioni: riga per riga, fuori dal codice
    for (let pos = from; pos <= to;) {
      const line = doc.lineAt(pos);
      pos = line.to + 1;
      if (codeLines.has(line.number)) continue;
      const text = line.text;
      const skip = (i) => {
        for (let n = tree.resolveInner(line.from + i, 1); n; n = n.parent) if (SKIP_NODES.has(n.name)) return true;
        return false;
      };
      const lineActive = active.has(line.number);
      const done = /^\s*[-*+]\s+\[[xX]\]/.test(text);
      for (const m of text.matchAll(MENTION)) {
        if (!skip(m.index)) decos.push(mark('cm-mention').range(line.from + m.index, line.from + m.index + m[0].length));
      }
      for (const m of text.matchAll(TAG)) {
        if (!skip(m.index)) decos.push(mark('cm-tag').range(line.from + m.index, line.from + m.index + m[0].length));
      }
      for (const m of text.matchAll(DUE)) {
        if (skip(m.index)) continue;
        const a = line.from + m.index;
        const b = a + m[0].length;
        if (lineActive) decos.push(mark('cm-due-raw').range(a, b));
        else {
          const [label, level] = dueBadge(m[1]);
          replace(a, b, Decoration.replace({ widget: new BadgeWidget('due', label, done ? 'done' : level) }));
        }
      }
      let decided = false;
      for (const m of text.matchAll(DECISION)) {
        if (skip(m.index)) continue;
        decided = true;
        const a = line.from + m.index;
        const b = a + m[0].length;
        if (lineActive) decos.push(mark('cm-decision-raw').range(a, b));
        else replace(a, b, Decoration.replace({ widget: new BadgeWidget('decision', 'Decisione') }));
      }
      if (decided) decos.push(lineDeco('cm-decision').range(line.from));
    }
  }
  return { decorations: Decoration.set(decos, true), atomic: Decoration.set(atomic, true) };
}

export const livePreview = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.focused = view.hasFocus;
      Object.assign(this, build(view, this.focused));
    }
    update(u) {
      if (u.focusChanged) this.focused = u.view.hasFocus;
      if (u.docChanged || u.viewportChanged || u.selectionSet || u.focusChanged ||
          syntaxTree(u.startState) !== syntaxTree(u.state)) {
        Object.assign(this, build(u.view, this.focused));
      }
    }
  },
  {
    decorations: (p) => p.decorations,
    provide: (plugin) => EditorView.atomicRanges.of((view) => view.plugin(plugin)?.atomic ?? Decoration.none),
  },
);
