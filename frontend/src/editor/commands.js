// Comandi rapidi dell'editor (Ctrl+T azione, Ctrl+D decisione, Ctrl+Shift+H ora) e lampeggio della riga toccata.
import { StateEffect, StateField } from '@codemirror/state';
import { Decoration, EditorView } from '@codemirror/view';
import { clock } from './dates.js';

const ACTION_RE = /^(\s*)[-*+]\s+\[( |x|X)\]/;
const BULLET_RE = /^(\s*)((?:[-*+]|\d+[.)])\s+)?/;
const DECISION_RE = /\s*!(?:decisione|decision|dec)(?![\p{L}\p{N}_])/iu;

// ------------------------------------------------------------------ lampeggio
const flashEffect = StateEffect.define();
const clearFlash = StateEffect.define();

export const flashField = StateField.define({
  create: () => Decoration.none,
  update(decos, tr) {
    decos = decos.map(tr.changes);
    for (const e of tr.effects) {
      if (e.is(clearFlash)) decos = decos.update({ filter: (_f, _t, d) => d.spec.id !== e.value });
      if (e.is(flashEffect)) {
        const deco = Decoration.line({ class: 'cm-flash', id: e.value.id });
        decos = decos.update({ add: [deco.range(e.value.pos)], sort: true });
      }
    }
    return decos;
  },
  provide: (f) => EditorView.decorations.from(f),
});

let flashes = 0;

function flash(view, linePos) {
  const id = ++flashes;
  view.dispatch({ effects: flashEffect.of({ pos: linePos, id }) });
  setTimeout(() => view.dom.isConnected && view.dispatch({ effects: clearFlash.of(id) }), 700);
}

// righe toccate dalla selezione, ognuna una volta
function selectedLines(state) {
  const seen = new Map();
  for (const r of state.selection.ranges) {
    for (let pos = r.from; pos <= r.to;) {
      const line = state.doc.lineAt(pos);
      seen.set(line.number, line);
      pos = line.to + 1;
    }
  }
  return [...seen.values()];
}

// ------------------------------------------------------------------ comandi
export function toggleAction(view, notify) {
  const lines = selectedLines(view.state);
  const changes = [];
  let kind = 'action';
  for (const line of lines) {
    const task = ACTION_RE.exec(line.text);
    if (task) {
      const at = line.from + line.text.indexOf('[', task[1].length) + 1;
      const done = task[2] === ' ';
      changes.push({ from: at, to: at + 1, insert: done ? 'x' : ' ' });
      kind = done ? 'done' : 'action';
    } else {
      const [prefix, indent] = BULLET_RE.exec(line.text);
      changes.push({ from: line.from + indent.length, to: line.from + prefix.length, insert: '- [ ] ' });
    }
  }
  // il cursore all'inizio della riga deve finire dopo "- [ ] ", non prima
  const changeSet = view.state.changes(changes);
  view.dispatch({ changes: changeSet, selection: view.state.selection.map(changeSet, 1), userEvent: 'input.action' });
  lines.forEach((l) => flash(view, view.state.doc.line(l.number).from));
  notify?.(kind);
  return true;
}

export function markDecision(view, notify) {
  const lines = selectedLines(view.state);
  const marked = lines.every((l) => DECISION_RE.test(l.text));
  const changes = lines.map((line) => {
    const m = DECISION_RE.exec(line.text);
    if (marked) return { from: line.from + m.index, to: line.from + m.index + m[0].length };
    if (m) return { from: line.to, to: line.to };
    const end = line.from + line.text.trimEnd().length;
    return { from: end, to: line.to, insert: ' !decisione' };
  });
  view.dispatch({ changes, userEvent: 'input.decision' });
  lines.forEach((l) => flash(view, view.state.doc.line(l.number).from));
  notify?.(marked ? 'undecision' : 'decision');
  return true;
}

export function insertTime(view, notify) {
  view.dispatch(view.state.replaceSelection(`${clock()} `), { userEvent: 'input.time', scrollIntoView: true });
  flash(view, view.state.doc.lineAt(view.state.selection.main.head).from);
  notify?.('time');
  return true;
}
