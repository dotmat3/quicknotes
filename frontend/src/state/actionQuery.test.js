import { describe, expect, it } from 'vitest';
import { NONE, emptyFilters, filterCount, keyOf, matchItem, parseDay, parseQuery, parseQuick, tokenAt } from './actionQuery.js';

// Martedì 10 novembre 2026.
const NOW = new Date(2026, 10, 10, 9, 30);
const TODAY = '2026-11-10';
const PROJECTS = [
  { key: 'llm-training', title: 'LLM Training', aliases: ['LLM'], areas: ['dedup', 'filter'] },
  { key: 'casa', title: 'Casa', aliases: [], areas: [] },
];

const item = (over = {}) => ({
  text: 'Valutare MinHash', raw: '- [ ] Valutare MinHash', note_title: 'LLM Training', note_type: 'project', is_daily: false,
  project: 'llm-training', area: 'dedup', topics: ['dedup'], tag: 'llm-training', people: ['Marco'], priority: 'alta',
  status: 'todo', closed: false, due: '2026-11-12', group: 'week', scheduled: null, description: '', subs: [], ...over,
});

describe('keyOf', () => {
  it('come projects.key_of', () => {
    expect(keyOf('LLM Training')).toBe('llm-training');
    expect(keyOf('#Città  Nuova')).toBe('citta-nuova');
    expect(keyOf('  ')).toBe('');
  });
});

describe('parseDay', () => {
  it('parole, giorni della settimana, scarti e date', () => {
    expect(parseDay('oggi', NOW)).toBe('2026-11-10');
    expect(parseDay('Domani', NOW)).toBe('2026-11-11');
    expect(parseDay('venerdì', NOW)).toBe('2026-11-13');
    expect(parseDay('mar', NOW)).toBe('2026-11-17');
    expect(parseDay('+3', NOW)).toBe('2026-11-13');
    expect(parseDay('+2s', NOW)).toBe('2026-11-24');
    expect(parseDay('20/11', NOW)).toBe('2026-11-20');
    expect(parseDay('5/1', NOW)).toBe('2027-01-05');
    expect(parseDay('2026-12-01', NOW)).toBe('2026-12-01');
    expect(parseDay('31/02', NOW)).toBe(null);
    expect(parseDay('marzo', NOW)).toBe(null);
  });
});

describe('parseQuick', () => {
  it('progetto, area, scadenza e priorità escono dal testo', () => {
    expect(parseQuick('Valutare MinHash #llm/dedup @Marco entro:ven !alta', PROJECTS, NOW)).toEqual({
      text: 'Valutare MinHash @Marco', project: 'llm-training', area: 'dedup', due: '2026-11-13', scheduled: null, priority: 'alta',
    });
  });
  it('un’etichetta che non è un progetto e una data sconosciuta restano nel testo', () => {
    const r = parseQuick('Comprare pile #spesa entro:presto pianifica:domani prio:bassa', PROJECTS, NOW);
    expect(r).toMatchObject({ text: 'Comprare pile #spesa entro:presto', project: null, scheduled: '2026-11-11', priority: 'bassa' });
  });
  it('solo il primo progetto', () => {
    expect(parseQuick('A #casa #llm', PROJECTS, NOW)).toMatchObject({ text: 'A #llm', project: 'casa', area: null });
  });
});

describe('parseQuery e matchItem', () => {
  it('riconosce le condizioni scritte', () => {
    expect(parseQuery('#llm/dedup -@giulia !alta stato:attesa "due parole" entro:settimana')).toEqual([
      { neg: false, kind: 'tag', value: 'llm/dedup' },
      { neg: true, kind: 'person', value: 'giulia' },
      { neg: false, kind: 'prio', value: 'alta' },
      { neg: false, kind: 'status', value: 'attesa' },
      { neg: false, kind: 'text', value: 'due parole' },
      { neg: false, kind: 'due', value: 'settimana' },
    ]);
  });
  it('filtra con testo, progetto, persone, stato e scadenza', () => {
    const m = (q, over) => matchItem(item(over), emptyFilters(), parseQuery(q), TODAY);
    expect(m('minhash')).toBe(true);
    expect(m('MINHÄSH')).toBe(true);
    expect(m('#llm-training/dedup @mar !alta')).toBe(true);
    expect(m('#llm-training/filter')).toBe(false);
    expect(m('-@marco')).toBe(false);
    expect(m('stato:corso', { status: 'doing' })).toBe(true);
    expect(m('stato:aperte', { status: 'waiting' })).toBe(true);
    expect(m('entro:settimana')).toBe(true);
    expect(m('entro:oggi')).toBe(false);
    expect(m('entro:15/11')).toBe(true);
    expect(m('!nessuna')).toBe(false);
    expect(m('nota:training')).toBe(true);
  });
  it('filtri a scelta multipla: basta una scelta per filtro, servono tutti i filtri', () => {
    const f = { ...emptyFilters(), projects: ['casa', 'llm-training'], priorities: ['alta', NONE], sources: ['project'] };
    expect(matchItem(item(), f, [], TODAY)).toBe(true);
    expect(matchItem(item({ priority: null }), f, [], TODAY)).toBe(true);
    expect(matchItem(item({ priority: 'bassa' }), f, [], TODAY)).toBe(false);
    expect(matchItem(item({ is_daily: true }), f, [], TODAY)).toBe(false);
    expect(matchItem(item({ project: null, tag: null }), { ...emptyFilters(), projects: [NONE] }, [], TODAY)).toBe(true);
    expect(matchItem(item(), { ...emptyFilters(), due: ['planned'] }, [], TODAY)).toBe(false);
    expect(filterCount(f)).toBe(5);
  });
  it('le scelte con le regole di Agenda: da fare oggi, prossimi 7 giorni, da smistare', () => {
    const due = (d, over) => matchItem(item(over), { ...emptyFilters(), due: [d] }, [], TODAY);
    expect(due('today', { due: TODAY })).toBe(true);
    expect(due('today', { due: null, scheduled: '2026-11-08' })).toBe(true);
    expect(due('today')).toBe(false);
    expect(due('next7')).toBe(true);
    expect(due('next7', { due: '2026-11-17' })).toBe(true);
    expect(due('next7', { due: '2026-11-18' })).toBe(false);
    expect(due('next7', { due: TODAY })).toBe(false);
    const inbox = (over) => matchItem(item(over), { ...emptyFilters(), sources: ['inbox'] }, [], TODAY);
    expect(inbox({ inbox: true, note_type: 'daily', is_daily: true })).toBe(true);
    expect(inbox({ note_type: 'inbox' })).toBe(true);
    expect(inbox()).toBe(false);
  });
});

describe('tokenAt', () => {
  it('la parola con # o @ prima del cursore', () => {
    expect(tokenAt('Chiamare @Ma', 12)).toEqual({ sigil: '@', value: 'Ma', start: 9 });
    expect(tokenAt('#llm/de', 7)).toEqual({ sigil: '#', value: 'llm/de', start: 0 });
    expect(tokenAt('mail a@b', 8)).toBe(null);
  });
});
