// Viste e preferiti condivisi da barra aperta e striscia compressa.

export const VIEWS = {
  calendario: { label: 'Calendario', page: 'view:calendar', icon: 'calendar' },
  azioni: { label: 'Azioni', page: 'view:actions', icon: 'actions' },
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

const VIEW_TITLES = { 'view:calendar': 'Calendario', 'view:actions': 'Azioni', 'view:people': 'Persone', 'view:graph': 'Grafo', 'view:micio': 'Micio', 'view:help': 'Guida', settings: 'Impostazioni' };

export function pageTitle(id, titles) {
  const kind = pageKind(id);
  if (titles[id]) return titles[id];
  if (kind === 'tag') return `#${pageArg(id)}`;
  if (kind === 'person') return `@${pageArg(id)}`;
  return VIEW_TITLES[id] ?? pageArg(id);
}

export function pageIcon(id, isDaily) {
  const kind = pageKind(id);
  if (kind === 'note') return isDaily ? 'today' : 'note';
  if (kind === 'person') return 'person';
  if (kind === 'tag') return 'hash';
  if (id === 'view:calendar') return 'calendar';
  if (id === 'view:actions') return 'actions';
  if (id === 'view:people') return 'person';
  if (id === 'view:graph') return 'graph';
  if (id === 'view:micio') return 'cat';
  if (id === 'view:help') return 'help';
  return 'settings';
}

// Icona e tipo di un preferito.
export function favInfo(id, todayId) {
  const kind = pageKind(id);
  if (kind === 'note') return pageArg(id) === todayId || pageArg(id).endsWith('-giornata') ? { icon: 'day', type: 'giorno' } : { icon: 'noteLines', type: 'nota' };
  if (kind === 'person') return { icon: 'person', type: 'persona' };
  if (kind === 'tag') return { icon: 'tag', type: 'etichetta' };
  if (id === 'view:calendar') return { icon: 'day', type: 'vista' };
  if (id === 'view:actions') return { icon: 'kanban', type: 'vista' };
  if (id === 'view:people') return { icon: 'group', type: 'vista' };
  if (id === 'view:help') return { icon: 'help', type: 'vista' };
  if (id === 'view:micio') return { icon: 'cat', type: 'vista' };
  return { icon: 'graph', type: 'vista' };
}
