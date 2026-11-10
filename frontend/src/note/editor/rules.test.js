import { describe, expect, it } from 'vitest';
import { ACTION, PRIO, SCHEDULED, diff, dueLabel, isoToday, noteStats, prioName, prioRank, statusOfMark, withChecked, withStatus } from './rules.js';

describe('withChecked', () => {
  it('spunta e riapre come il nucleo Python', () => {
    expect(withChecked('  - [ ] A due:2026-01-01', '2026-11-03')).toBe('  - [x] A due:2026-01-01 done:2026-11-03');
    expect(withChecked('* [X] A done:2026-11-03', null)).toBe('* [ ] A');
    expect(withChecked('testo', null)).toBe('testo');
  });
});

describe('dueLabel', () => {
  const now = new Date(2026, 10, 1);
  it('usa le stesse etichette del nucleo', () => {
    expect(dueLabel('2026-10-30', now)).toEqual({ label: '30 ott', level: 'late' });
    expect(dueLabel('2026-11-01', now)).toEqual({ label: 'oggi', level: 'soon' });
    expect(dueLabel('2026-11-02', now)).toEqual({ label: 'domani', level: 'soon' });
    expect(dueLabel('2026-11-04', now)).toEqual({ label: 'mer 4 nov', level: 'normal' });
  });
  it('isoToday usa la data locale', () => {
    expect(isoToday(now)).toBe('2026-11-01');
  });
});

describe('noteStats', () => {
  it('conta solo le azioni di primo livello e ignora il codice', () => {
    const s = noteStats('- [x] A @Marco\n    - [ ] figlia @Elena\n- [ ] B\n```\n- [ ] no @No\n```\n');
    expect(s.done).toBe(1);
    expect(s.total).toBe(2);
    expect(s.people).toEqual(['Marco', 'Elena']);
  });
});

describe('diff', () => {
  it('trova la parte cambiata', () => {
    expect(diff('abcdef', 'abXdef')).toEqual({ from: 2, to: 3, insert: 'X' });
    expect(diff('abc', 'abc')).toEqual({ from: 3, to: 3, insert: '' });
    expect(diff('', 'x')).toEqual({ from: 0, to: 0, insert: 'x' });
  });
});

describe('priorità', () => {
  it('riconosce le stesse forme del nucleo Python', () => {
    const found = (t) => [...t.matchAll(PRIO)].map((m) => prioName(m[1]));
    expect(found('- [ ] A prio:alta #x')).toEqual(['alta']);
    expect(found('- [ ] B Priorità: Media due:2026-01-01')).toEqual(['media']);
    expect(found('- [ ] C priority:low')).toEqual(['bassa']);
    expect(found('- [ ] D prio:urgente xprio:alta prio:altissima')).toEqual([]);
    expect([null, 'bassa', 'media', 'alta'].map(prioRank)).toEqual([3, 2, 1, 0]);
  });
});

describe('stati', () => {
  it('riconosce i sei segni come il nucleo Python', () => {
    const marks = ['- [ ] a', '- [/] a', '- [w] a', '- [?] a', '- [-] a', '- [x] a', '- [X] a'].map((l) => statusOfMark(ACTION.exec(l)[2]));
    expect(marks).toEqual(['todo', 'doing', 'waiting', 'question', 'cancelled', 'done', 'done']);
    expect(ACTION.test('- [!] a')).toBe(false);
  });
  it('withStatus scrive done: solo per fatta e annullata', () => {
    expect(withStatus('  - [ ] A due:2026-11-14', 'cancelled', '2026-11-10')).toBe('  - [-] A due:2026-11-14 done:2026-11-10');
    expect(withStatus('- [x] A done:2026-11-09', 'waiting', '2026-11-10')).toBe('- [w] A');
    expect(withStatus('- [ ] A', 'doing', '2026-11-10')).toBe('- [/] A');
  });
  it('le annullate non contano nei numeri della nota', () => {
    const s = noteStats('- [x] A\n- [-] B\n- [/] C\n- [?] D\n');
    expect([s.done, s.total]).toEqual([1, 3]);
  });
  it('scheduled:', () => {
    expect([...'- [ ] A scheduled:2026-11-12 due:2026-11-14'.matchAll(SCHEDULED)].map((m) => m[1])).toEqual(['2026-11-12']);
  });
});
