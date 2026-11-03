// Disposizione: gruppi di schede come in VS Code, fino a 4. La logica viene dalla tavola Home.
// Una scheda è l'id di una pagina: note:<id>, person:<nome>, tag:<nome>, view:<nome>, settings.
import { app, savePrefs } from './app.svelte.js';
import { boot } from '../api.js';

const saved = boot.ui?.layout;
const todayPage = boot.today ? `note:${boot.today.id}` : 'view:actions';

function initialGroups() {
  const groups = saved?.groups?.filter((g) => g.tabs?.length) ?? [];
  if (!groups.length) return [{ id: 'g1', tabs: [todayPage], active: todayPage }];
  return groups;
}

export const layout = $state({
  groups: initialGroups(),
  focus: saved?.focus ?? 'g1',
  dir: saved?.dir ?? 'row',
  sizes: saved?.sizes ?? {},
  max: null,
  seq: saved?.seq ?? 2,
  closed: [],
  drag: null,
  dropZone: null,
  dropTab: null,
  resize: null,
});
if (!layout.groups.some((g) => g.id === layout.focus)) layout.focus = layout.groups[0].id;

// All'avvio di un giorno nuovo la nota di oggi non è tra le schede ricordate: si apre e diventa attiva.
if (boot.today && !layout.groups.some((g) => g.tabs.includes(todayPage))) {
  const g = layout.groups.find((x) => x.id === layout.focus);
  g.tabs.push(todayPage);
  g.active = todayPage;
}

function persist() {
  const { groups, focus, dir, sizes, seq } = $state.snapshot(layout);
  savePrefs({ layout: { groups, focus, dir, sizes, seq } });
}

const group = (id) => layout.groups.find((g) => g.id === id);
export const focused = () => group(layout.focus) ?? layout.groups[0];

export function canSide(side) {
  const n = layout.groups.length;
  return n < 4 && (n === 1 || (layout.dir === 'row' ? side === 'left' || side === 'right' : side === 'top' || side === 'bottom'));
}

function afterChange(dropIfEmpty) {
  if (dropIfEmpty && layout.groups.length > 1) {
    layout.groups = layout.groups.filter((g) => g.id !== dropIfEmpty || g.tabs.length);
  }
  if (!group(layout.focus)) layout.focus = layout.groups[0].id;
  const ids = new Set(layout.groups.map((g) => g.id));
  for (const id of Object.keys(layout.sizes)) if (!ids.has(id) || layout.groups.length < 2) delete layout.sizes[id];
  if (layout.groups.length < 2) layout.max = null;
  layout.drag = layout.dropZone = layout.dropTab = null;
  persist();
  // Chiudere o spostare schede cambia la pagina visibile: anche quella entra nella cronologia.
  remember();
}

export function openPage(id, title) {
  const g = focused();
  if (title) app.titles[id] = title;
  if (!g.tabs.includes(id)) g.tabs.push(id);
  g.active = id;
  persist();
  remember();
}

// Apre una nota mostrando una riga: la nota la porta al centro appena l'editor è pronto.
export function openAt(id, line, title) {
  if (line) app.reveal = { page: id, line };
  openPage(id, title);
}

// "Apri a lato": nel gruppo accanto a quello attivo, o in un gruppo nuovo a destra.
export function openBeside(id, title, line) {
  const g = focused();
  if (layout.groups.length > 1) {
    const i = layout.groups.indexOf(g);
    layout.focus = (layout.groups[i + 1] ?? layout.groups[i - 1]).id;
    return openAt(id, line, title);
  }
  if (title) app.titles[id] = title;
  if (line) app.reveal = { page: id, line };
  splitTo(g.id, id, g.id, canSide('right') ? 'right' : 'bottom', true);
}

export function activate(groupId, id) {
  const g = group(groupId);
  g.active = id;
  layout.focus = groupId;
  persist();
  remember();
}

// Indietro e Avanti, come in VS Code: le pagine visitate, con il gruppo in cui erano.
// Tornando su una scheda chiusa, la si riapre.
const visits = { stack: [], at: -1 };

function remember() {
  const g = focused();
  if (!g?.active) return;
  const cur = visits.stack[visits.at];
  if (cur?.g === g.id && cur.page === g.active) return;
  visits.stack.splice(visits.at + 1);
  visits.stack.push({ g: g.id, page: g.active });
  if (visits.stack.length > 100) visits.stack.shift();
  visits.at = visits.stack.length - 1;
}

function go(delta) {
  const i = visits.at + delta;
  const e = visits.stack[i];
  if (!e) return false;
  const g = group(e.g) ?? focused();
  if (!g.tabs.includes(e.page)) g.tabs.push(e.page);
  g.active = e.page;
  layout.focus = g.id;
  visits.at = i;
  persist();
  return true;
}

export const goBack = () => go(-1);
export const goForward = () => go(1);

export function closeTabs(groupId, ids) {
  const g = group(groupId);
  if (!g || !ids.length) return;
  const before = [...g.tabs];
  g.tabs = g.tabs.filter((t) => !ids.includes(t));
  if (ids.includes(g.active)) {
    const i = before.indexOf(g.active);
    g.active = before.slice(i + 1).find((t) => !ids.includes(t)) ?? before.slice(0, i).reverse().find((t) => !ids.includes(t)) ?? null;
  }
  layout.closed.push(...ids);
  afterChange(groupId);
}

export function reopen() {
  const id = layout.closed.pop();
  if (id) openPage(id);
}

export function moveTab(fromId, id, toId, idx) {
  const from = group(fromId);
  const to = group(toId);
  if (!from || !to || !from.tabs.includes(id)) return afterChange();
  const fi = from.tabs.indexOf(id);
  if (from === to) {
    idx ??= from.tabs.length;
    from.tabs.splice(fi, 1);
    from.tabs.splice(idx > fi ? idx - 1 : idx, 0, id);
    from.active = id;
  } else {
    from.tabs.splice(fi, 1);
    if (from.active === id) from.active = from.tabs[Math.min(fi, from.tabs.length - 1)] ?? null;
    const ex = to.tabs.indexOf(id);
    if (ex >= 0) to.tabs.splice(ex, 1);
    to.tabs.splice(idx == null ? to.tabs.length : Math.min(idx, to.tabs.length), 0, id);
    to.active = id;
  }
  layout.focus = toId;
  afterChange(fromId);
}

export function splitTo(fromId, id, targetId, side, copy) {
  if (!id) return;
  if (!canSide(side)) {
    if (fromId !== targetId) moveTab(fromId, id, targetId, null);
    else afterChange();
    return;
  }
  if (layout.groups.length === 1) layout.dir = side === 'left' || side === 'right' ? 'row' : 'col';
  const from = group(fromId);
  const keep = copy || (fromId === targetId && from.tabs.length === 1);
  if (!keep) {
    const fi = from.tabs.indexOf(id);
    from.tabs.splice(fi, 1);
    if (from.active === id) from.active = from.tabs[Math.min(fi, from.tabs.length - 1)] ?? null;
  }
  const nid = `g${layout.seq++}`;
  const ti = layout.groups.findIndex((g) => g.id === targetId);
  layout.groups.splice(side === 'left' || side === 'top' ? ti : ti + 1, 0, { id: nid, tabs: [id], active: id });
  const w = layout.sizes[targetId] ?? 1;
  layout.sizes[targetId] = w / 2;
  layout.sizes[nid] = w / 2;
  layout.focus = nid;
  afterChange(keep ? null : fromId);
}

export function applyLayout(n, dir) {
  let gs = $state.snapshot(layout.groups);
  if (gs.length > n) {
    const kept = gs.slice(0, n);
    for (const g of gs.slice(n)) for (const t of g.tabs) if (!kept[n - 1].tabs.includes(t)) kept[n - 1].tabs.push(t);
    gs = kept;
  }
  while (gs.length < n) {
    const src = gs[gs.length - 1];
    gs.push({ id: `g${layout.seq++}`, tabs: src.active ? [src.active] : [], active: src.active });
  }
  layout.groups = gs;
  layout.dir = dir;
  layout.sizes = {};
  layout.max = null;
  afterChange();
}

export function closeGroup(id) {
  const i = layout.groups.findIndex((g) => g.id === id);
  const g = layout.groups[i];
  const nb = layout.groups[i - 1] ?? layout.groups[i + 1];
  for (const t of g.tabs) if (!nb.tabs.includes(t)) nb.tabs.push(t);
  nb.active ??= g.active;
  if (layout.sizes[nb.id]) layout.sizes[nb.id] += layout.sizes[id] ?? 1;
  layout.groups.splice(i, 1);
  layout.focus = nb.id;
  afterChange();
}

// Pesi relativi dei gruppi, sempre con somma pari al numero di gruppi.
export function weights() {
  const raw = layout.groups.map((g) => layout.sizes[g.id] ?? 1);
  const sum = raw.reduce((a, b) => a + b, 0) || 1;
  return layout.groups.length === 1 ? [1] : raw.map((w) => (w / sum) * layout.groups.length);
}

// `i` è l'indice del gruppo a destra del divisore, `pos` la posizione da 0 a 1 nella zona dei gruppi.
export function resizeAt(i, pos) {
  const w = weights();
  const total = w.reduce((a, b) => a + b, 0);
  const start = w.slice(0, i - 1).reduce((a, b) => a + b, 0) / total;
  const end = w.slice(0, i + 1).reduce((a, b) => a + b, 0) / total;
  const p = Math.max(start + 0.12, Math.min(end - 0.12, pos));
  layout.sizes[layout.groups[i - 1].id] = (p - start) * total;
  layout.sizes[layout.groups[i].id] = (end - p) * total;
}

export const saveLayout = persist;

// La pagina aperta all'avvio è il primo passo della cronologia.
remember();
