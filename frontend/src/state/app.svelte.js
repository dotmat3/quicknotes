// Stato dell'app: preferenze, tema, barra laterale. Le preferenze vanno in config.json, chiave `ui`.
import { boot, call } from '../api.js';
import { applyTheme, resolveTheme, tagHex } from '../theme/themes.js';

const ui = boot.ui ?? {};

// Le viste aggiunte dopo che l'ordine è stato salvato vanno in fondo, tranne Agenda, che è la prima dopo Oggi,
// e Revisione, che segue Azioni.
function initialOrder(saved) {
  const order = [...new Set([...(saved ?? []), 'calendario', 'azioni', 'persone', 'grafo', 'micio'])];
  if (!order.includes('agenda')) order.unshift('agenda');
  if (!order.includes('revisione')) order.splice(order.indexOf('azioni') + 1, 0, 'revisione');
  return order;
}

// Prima della 0.6.0 i filtri erano un progetto, un'area e uno stato singoli.
function initialFilters(saved) {
  const f = { projects: [], areas: [], statuses: [], priorities: [], people: [], due: [], sources: [], ...(saved.actF ?? {}) };
  if (!saved.actF) {
    if (saved.actProject) f.projects = [saved.actProject];
    if (saved.actArea) f.areas = [saved.actArea];
    if (saved.actStatus) f.statuses = [saved.actStatus];
  }
  return f;
}

export const app = $state({
  themeId: ui.theme ?? boot.theme ?? 'auto',
  custom: ui.custom ?? null,
  side: ui.side ?? 'open',
  // Larghezza della barra laterale aperta, in pixel: si cambia trascinandone il bordo destro.
  sideW: ui.sideW ?? 240,
  showPins: ui.showPins !== false,
  favs: ui.favs ?? ['view:actions'],
  viewOrder: initialOrder(ui.viewOrder),
  viewVis: { agenda: true, calendario: true, azioni: true, revisione: true, persone: true, grafo: true, micio: true, ...(ui.viewVis ?? {}) },
  tagColors: ui.tagColors ?? {},
  noteW: ui.noteW ?? 'leggibile',
  viewW: ui.viewW ?? 'intera',
  actView: ui.actView ?? 'bacheca',
  // Dalla 0.6.0 Azioni parte raggruppata per progetto (Agenda è già la vista per scadenza): chi aveva salvato
  // un altro raggruppamento passa una volta a Progetto, poi vale la sua scelta (actGroupV ricorda il passaggio).
  actGroup: ui.actGroupV >= 2 ? (ui.actGroup ?? 'progetto') : 'progetto',
  boardDone: ui.boardDone !== false,
  // Filtri della vista Azioni, a scelta multipla (vedi state/actionQuery.js); il testo di Filtra non si ricorda.
  actF: initialFilters(ui),
  actQ: '',
  actPaused: ui.actPaused === true,
  // Viste salvate della vista Azioni: { name, f, q, paused }.
  actViews: ui.actViews ?? [],
  // Progetti aperti nell'albero della barra laterale.
  projOpen: ui.projOpen ?? {},
  lastReview: ui.lastReview ?? null,
  counts: { todayDone: 0, todayTotal: 0, open: 0, late: 0, people: 0, reviewDue: false, projects: [] },
  palette: false,
  paletteQuery: '',
  toast: '',
  titles: ui.titles ?? {},
  today: boot.today,
  // Ultima nota aperta e modalità del grafo: il grafo locale parte da quella nota.
  lastNote: null,
  graphLocal: false,
  // Riga da mostrare quando si apre una nota: { page, line }, presa dalla nota appena pronta.
  reveal: null,
  // La vista (gruppo:pagina) il cui titolo si sta rinominando.
  rename: null,
  // La finestra di conferma aperta: { title, text, ok, run }.
  confirm: null,
  // La casella "nuovo progetto" della barra laterale è aperta.
  newProject: false,
});

export const theme = {
  get current() {
    return resolveTheme(app.themeId, app.custom);
  },
};

export function tagColor(tag) {
  return tagHex(tag, app.tagColors, theme.current.dark);
}

export function setTheme(id) {
  app.themeId = id;
  applyTheme(resolveTheme(id, app.custom));
  savePrefs();
}

// Applicato prima del montaggio: la prima pittura ha già i colori giusti.
applyTheme(resolveTheme(app.themeId, app.custom));

// Con il tema Automatico segue il sistema anche mentre l'app è aperta.
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  applyTheme(resolveTheme(app.themeId, app.custom));
});

let timer;
const extra = {};

// Le altre parti dell'app (come la disposizione delle schede) aggiungono qui ciò che va ricordato.
export function savePrefs(more) {
  Object.assign(extra, more);
  clearTimeout(timer);
  timer = setTimeout(() => {
    const { themeId: theme, custom, side, sideW, showPins, favs, viewOrder, viewVis, tagColors, noteW, viewW, actView, actGroup, boardDone, titles } = app;
    const { actF, actPaused, actViews, projOpen, lastReview } = app;
    const { actProject, actWithAreas, actArea, actStatus, ...rest } = ui;
    call('save_ui', { ui: $state.snapshot({ ...rest, theme, custom, side, sideW, showPins, favs, viewOrder, viewVis, tagColors, noteW, viewW, actView, actGroup, actGroupV: 2, boardDone, titles, actF, actPaused, actViews, projOpen, lastReview, ...extra }) });
  }, 400);
}

export async function refreshCounts() {
  app.counts = await call('sidebar', {}, app.counts);
}

// L'avviso sparisce da solo: 4 secondi, di più se è lungo da leggere, al massimo 10. Con il mouse sopra resta.
let toastTimer;
const toastTime = (text) => Math.min(10000, Math.max(4000, text.length * 60));

export function showToast(text) {
  app.toast = text;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (app.toast = ''), toastTime(text));
}

export function holdToast(hold) {
  clearTimeout(toastTimer);
  if (!hold && app.toast) toastTimer = setTimeout(() => (app.toast = ''), 2000);
}

// Il link [[id|Titolo]] da incollare in un'altra nota. Se gli appunti non rispondono si passa da una casella nascosta.
export async function copyNoteLink(id, title) {
  const text = `[[${id}|${title ?? id}]]`;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = Object.assign(document.createElement('textarea'), { value: text });
    document.body.append(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }
  showToast(`Copiato: ${text}`);
}
