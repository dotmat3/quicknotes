// Viste e preferiti condivisi da barra aperta e striscia compressa.

export const VIEWS = {
  agenda: { label: 'Agenda', page: 'view:agenda', icon: 'agenda' },
  calendario: { label: 'Calendario', page: 'view:calendar', icon: 'calendar' },
  azioni: { label: 'Azioni', page: 'view:actions', icon: 'actions' },
  revisione: { label: 'Revisione', page: 'view:review', icon: 'review' },
  persone: { label: 'Persone', page: 'view:people', icon: 'people' },
  grafo: { label: 'Grafo', page: 'view:graph', icon: 'graph' },
  micio: { label: 'Micio', page: 'view:micio', icon: 'cat' },
};

export function pageKind(id) {
  if (id === 'settings') return 'settings';
  return id.slice(0, id.indexOf(':'));
}

export function pageArg(id) {
  return id.slice(id.indexOf(':') + 1);
}

const VIEW_TITLES = { 'view:agenda': 'Agenda', 'view:calendar': 'Calendario', 'view:actions': 'Azioni', 'view:review': 'Revisione', 'view:migration': 'Migrazione', 'view:people': 'Persone', 'view:graph': 'Grafo', 'view:micio': 'Micio', 'view:help': 'Guida', settings: 'Impostazioni' };

export function pageTitle(id, titles) {
  const kind = pageKind(id);
  if (titles[id]) return titles[id];
  if (kind === 'tag') return `#${pageArg(id)}`;
  if (kind === 'person') return `@${pageArg(id)}`;
  return VIEW_TITLES[id] ?? pageArg(id);
}

const VIEW_ICONS = { 'view:agenda': 'agenda', 'view:calendar': 'calendar', 'view:actions': 'actions', 'view:review': 'review', 'view:migration': 'move', 'view:people': 'person', 'view:graph': 'graph', 'view:micio': 'cat', 'view:help': 'help' };

export function pageIcon(id, isDaily) {
  const kind = pageKind(id);
  if (kind === 'note') return isDaily ? 'today' : 'note';
  if (kind === 'person') return 'person';
  if (kind === 'tag') return 'hash';
  if (kind === 'project') return 'folder';
  return VIEW_ICONS[id] ?? 'settings';
}

// Icona e tipo di un preferito.
export function favInfo(id, todayId) {
  const kind = pageKind(id);
  if (kind === 'note') return pageArg(id) === todayId || pageArg(id).endsWith('-giornata') ? { icon: 'day', type: 'giorno' } : { icon: 'noteLines', type: 'nota' };
  if (kind === 'person') return { icon: 'person', type: 'persona' };
  if (kind === 'tag') return { icon: 'tag', type: 'etichetta' };
  if (kind === 'project') return { icon: 'folder', type: 'progetto' };
  if (id === 'view:calendar' || id === 'view:agenda') return { icon: 'day', type: 'vista' };
  if (id === 'view:actions') return { icon: 'kanban', type: 'vista' };
  if (id === 'view:review') return { icon: 'review', type: 'vista' };
  if (id === 'view:people') return { icon: 'group', type: 'vista' };
  if (id === 'view:help') return { icon: 'help', type: 'vista' };
  if (id === 'view:micio') return { icon: 'cat', type: 'vista' };
  return { icon: 'graph', type: 'vista' };
}
