// Anteprima viva del Markdown: i marcatori spariscono fuori dalla riga del cursore, le azioni hanno
// caselle cliccabili, @persone e #etichette sono evidenziate, scadenze e decisioni diventano etichette.
import { syntaxTree } from '@codemirror/language';
import { Decoration, EditorView, ViewPlugin, WidgetType } from '@codemirror/view';
import { ALERT_LABELS, DECISION, DONE, DUE, FOOTNOTE, MENTION, TAG, WIKI, alertIcon, dueLabel, isoToday, withChecked } from './rules.js';

const SKIP_NODES = new Set(['InlineCode', 'URL', 'CodeText', 'FencedCode', 'CodeBlock', 'Autolink']);
const ALERT = /^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$/i;

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
    box.innerHTML = '<svg viewBox="0 0 24 24"><path d="m5 12 5 5 9-10"/></svg>';
    this.updateDOM(box);
    box.addEventListener('mousedown', (e) => {
      e.preventDefault();
      toggleTaskAt(view, view.posAtDOM(box));
    });
    return box;
  }
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

class LabelWidget extends WidgetType {
  constructor(cls, label) {
    super();
    this.cls = cls;
    this.label = label;
  }
  eq(other) {
    return other.cls === this.cls && other.label === this.label;
  }
  toDOM() {
    const el = document.createElement('span');
    el.className = this.cls;
    el.textContent = this.label;
    return el;
  }
}

class AlertTitleWidget extends WidgetType {
  constructor(kind) {
    super();
    this.kind = kind;
  }
  eq(other) {
    return other.kind === this.kind;
  }
  toDOM() {
    const el = document.createElement('span');
    el.className = 'cm-alert-title';
    el.append(alertIcon(this.kind), ALERT_LABELS[this.kind]);
    return el;
  }
}

// Testo che si sta scrivendo: si apre con Ctrl+clic, e la manina compare solo tenendo premuto Ctrl.
const CTRL = { 'data-needs-ctrl': '' };

const bullet = Decoration.replace({ widget: new BulletWidget() });
const hide = Decoration.replace({});
const lineDeco = (cls) => Decoration.line({ class: cls });
const mark = (cls) => Decoration.mark({ class: cls });

export function toggleTaskAt(view, pos) {
  const line = view.state.doc.lineAt(pos);
  const done = /^\s*[-*+]\s+\[[xX]\]/.test(line.text);
  const next = withChecked(line.text, done ? null : isoToday());
  if (next === line.text) return false;
  view.dispatch({ changes: { from: line.from, to: line.to, insert: next }, userEvent: 'input.toggle' });
  return true;
}

function activeLines(state) {
  const lines = new Set();
  for (const r of state.selection.ranges) {
    const first = state.doc.lineAt(r.from).number;
    const last = state.doc.lineAt(r.to).number;
    for (let n = first; n <= last; n++) lines.add(n);
  }
  return lines;
}

function build(view, focused, tagColor) {
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
      from,
      to,
      enter: (node) => {
        const name = node.name;
        if (name === 'FencedCode' || name === 'CodeBlock') {
          for (let pos = node.from; pos <= node.to; ) {
            const line = doc.lineAt(pos);
            codeLines.add(line.number);
            decos.push(lineDeco('cm-codeblock').range(line.from));
            pos = line.to + 1;
          }
          if (name === 'FencedCode' && !isActive(node.from)) {
            // Fuori dal blocco i ``` spariscono e resta solo il nome della lingua, come nell'Anteprima.
            node.node.getChildren('CodeMark').forEach((m) => replace(m.from, m.to));
            const info = node.node.getChild('CodeInfo');
            if (info) decos.push(mark('cm-code-lang').range(info.from, info.to));
          }
          return false;
        }
        const heading = /^ATXHeading(\d)$/.exec(name);
        if (heading) {
          decos.push(lineDeco(`cm-h cm-h${heading[1]}`).range(doc.lineAt(node.from).from));
          const m = node.node.getChild('HeaderMark');
          if (m && !isActive(node.from)) replace(m.from, spaceAfter(m.to));
          return undefined;
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
          return undefined;
        }
        if (name === 'QuoteMark') {
          decos.push(lineDeco('cm-quote').range(doc.lineAt(node.from).from));
          if (!isActive(node.from)) replace(node.from, spaceAfter(node.to));
          return undefined;
        }
        if (name === 'HorizontalRule') {
          decos.push(lineDeco('cm-hr').range(doc.lineAt(node.from).from));
          if (!isActive(node.from)) replace(node.from, node.to);
          return undefined;
        }
        if (name === 'EmphasisMark' || name === 'StrikethroughMark') {
          if (!isActive(node.from)) replace(node.from, node.to);
          return undefined;
        }
        if (name === 'InlineCode') {
          decos.push(mark('cm-inline-code').range(node.from, node.to));
          if (!isActive(node.from)) node.node.getChildren('CodeMark').forEach((m) => replace(m.from, m.to));
          return false;
        }
        if (name === 'URL' && node.node.parent?.name !== 'Link' && node.node.parent?.name !== 'Image') {
          // Indirizzo scritto nudo, come su GitHub: è già un link.
          const active = isActive(node.from);
          decos.push(Decoration.mark({ class: 'cm-link', attributes: { 'data-href': doc.sliceString(node.from, node.to), ...(active ? CTRL : {}) } }).range(node.from, node.to));
          return false;
        }
        if (name === 'Link') {
          const marks = node.node.getChildren('LinkMark');
          if (marks.length >= 2 && marks[0].to < marks[1].from) {
            const url = node.node.getChild('URL');
            // Fuori dalla riga del cursore il link si apre con un clic, come i [[link]]; sulla riga con Ctrl+clic.
            const href = url ? { attributes: { 'data-href': doc.sliceString(url.from, url.to), ...(isActive(node.from) ? CTRL : {}) } } : {};
            decos.push(Decoration.mark({ class: 'cm-link', ...href }).range(marks[0].to, marks[1].from));
            if (!isActive(node.from)) {
              replace(node.from, marks[0].to);
              replace(marks[1].from, node.to);
            }
          }
          return false;
        }
        return undefined;
      },
    });

    let alertKind = null;
    for (let pos = from; pos <= to; ) {
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

      // Il rientro diventa margine: non viene barrato con la riga e allinea figlie e descrizioni.
      const indent = /^[ 	]+/.exec(text)?.[0];
      if (indent) {
        const inList = (() => {
          for (let n = tree.resolveInner(line.from + indent.length, 1); n; n = n.parent) if (n.name === 'ListItem') return true;
          return false;
        })();
        if (inList) {
          const levels = Math.ceil(indent.replace(/	/g, '    ').length / 4);
          const isItem = /^\s*(?:[-*+]|\d+[.)])\s/.test(text);
          decos.push(Decoration.line({ class: isItem ? '' : 'cm-desc', attributes: { style: `margin-left:${(isItem ? levels : Math.max(levels - 1, 0)) * 28 + (isItem ? 0 : 28)}px` } }).range(line.from));
          replace(line.from, line.from + indent.length, hide, true);
        }
      }

      const alert = ALERT.exec(text);
      if (alert) {
        alertKind = alert[1].toUpperCase();
        decos.push(lineDeco(`cm-alert cm-alert-${alertKind.toLowerCase()} cm-alert-head`).range(line.from));
        if (!lineActive) replace(line.from, line.to, Decoration.replace({ widget: new AlertTitleWidget(alertKind) }));
        continue;
      }
      if (alertKind && text.startsWith('>')) decos.push(lineDeco(`cm-alert cm-alert-${alertKind.toLowerCase()}`).range(line.from));
      else alertKind = null;

      for (const m of text.matchAll(MENTION)) {
        if (!skip(m.index)) decos.push(Decoration.mark({ class: 'cm-mention', attributes: { 'data-person': m[1], ...CTRL } }).range(line.from + m.index, line.from + m.index + m[0].length));
      }
      for (const m of text.matchAll(TAG)) {
        if (skip(m.index)) continue;
        const color = done ? undefined : `color:${tagColor(m[1])}`;
        decos.push(Decoration.mark({ class: 'cm-tag', attributes: { 'data-tag': m[1], ...CTRL, ...(color ? { style: color } : {}) } }).range(line.from + m.index, line.from + m.index + m[0].length));
      }
      for (const m of text.matchAll(WIKI)) {
        if (m[1] || skip(m.index)) continue;
        const a = line.from + m.index;
        const b = a + m[0].length;
        const label = (m[3] || m[2]).trim();
        if (lineActive) decos.push(Decoration.mark({ class: 'cm-wiki-raw', attributes: { 'data-wiki': m[2].trim(), ...CTRL } }).range(a, b));
        else replace(a, b, Decoration.replace({ widget: new WikiWidget(m[2].trim(), label) }));
      }
      for (const m of text.matchAll(FOOTNOTE)) {
        if (skip(m.index)) continue;
        decos.push(mark(m[2] && m.index === 0 ? 'cm-fn cm-fn-def' : 'cm-fn').range(line.from + m.index, line.from + m.index + m[0].length - m[2].length));
      }
      for (const m of text.matchAll(DUE)) {
        if (skip(m.index)) continue;
        const a = line.from + m.index;
        const b = a + m[0].length;
        if (lineActive) decos.push(mark('cm-date-raw').range(a, b));
        else {
          const { label, level } = dueLabel(m[1]);
          replace(a, b, Decoration.replace({ widget: new LabelWidget(`cm-due ${done ? 'done' : level}`, label) }));
        }
      }
      for (const m of text.matchAll(DONE)) {
        if (skip(m.index)) continue;
        const a = line.from + m.index;
        const b = a + m[0].length;
        if (lineActive) decos.push(mark('cm-date-raw').range(a, b));
        else replace(doc.sliceString(a - 1, a) === ' ' ? a - 1 : a, b);
      }
      for (const m of text.matchAll(DECISION)) {
        if (skip(m.index)) continue;
        const a = line.from + m.index;
        const b = a + m[0].length;
        if (lineActive) decos.push(mark('cm-decision').range(a, b));
        else replace(a, b, Decoration.replace({ widget: new LabelWidget('cm-decision', '!decisione') }));
      }
    }
  }
  return { decorations: Decoration.set(decos, true), atomic: Decoration.set(atomic, true) };
}

class WikiWidget extends WidgetType {
  constructor(target, label) {
    super();
    this.target = target;
    this.label = label;
  }
  eq(other) {
    return other.target === this.target && other.label === this.label;
  }
  toDOM() {
    const el = document.createElement('span');
    el.className = 'cm-wiki';
    el.dataset.wiki = this.target;
    el.textContent = this.label;
    return el;
  }
  ignoreEvent() {
    return false;
  }
}

export function livePreview(tagColor) {
  const plugin = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.focused = view.hasFocus;
        Object.assign(this, build(view, this.focused, tagColor));
      }
      update(u) {
        if (u.focusChanged) this.focused = u.view.hasFocus;
        if (u.docChanged || u.viewportChanged || u.selectionSet || u.focusChanged || syntaxTree(u.startState) !== syntaxTree(u.state)) {
          Object.assign(this, build(u.view, this.focused, tagColor));
        }
      }
    },
    {
      decorations: (p) => p.decorations,
      provide: (p) => EditorView.atomicRanges.of((view) => view.plugin(p)?.atomic ?? Decoration.none),
    },
  );
  return plugin;
}
