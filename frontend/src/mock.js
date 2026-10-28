// Backend finto per provare l'interfaccia nel browser (npm run dev, poi http://localhost:5173/?mock).
import { person } from './people.js';

const today = new Date().toISOString().slice(0, 10);
const notes = [
  { id: `${today}-giornata`, type: 'daily', title: 'Giornata di oggi', date: today, people: [], project: '',
    body: '- 09:10 Chiamata con fornitore, confermati i tempi\n- [ ] Inviare mail di riepilogo a @Laura\n' },
  { id: 'kickoff', type: 'meeting', title: 'Kickoff cliente X', date: `${today}T10:00`, people: ['Marco', 'Laura'],
    project: 'clientex',
    body: '## Contesto\nDiscusso il budget del **Q4** con il cliente.\n\n- [ ] @Marco invia preventivo due:2026-10-31\n' +
          '- [x] @Laura prepara demo\n- Budget approvato a 50k !decisione\n\n> Il cliente vuole partire a gennaio.\n\n' +
          'Prossimi passi: rivedere i tempi con #design.\n' },
  { id: 'retro', type: 'note', title: 'Idee per la retro', date: '2026-10-20T16:30', people: [], project: '',
    body: 'Cose da migliorare:\n- stand-up più brevi\n- meno riunioni il venerdì\n' },
];
const typeInfo = { meeting: ['Meeting', 'users'], daily: ['Nota del giorno', 'sun'], note: ['Nota', 'pen'] };

const payload = (n) => ({ ...n, typeLabel: typeInfo[n.type][0], icon: typeInfo[n.type][1],
                          dateLabel: n.date.replace('T', ', '), people: n.people.map(person), mtime: 1 });

export const mockApi = {
  // ?mock&theme=light&open=kickoff: tema e nota iniziale dell'anteprima
  bootstrap: async () => {
    const q = new URLSearchParams(location.search);
    const first = notes.find((n) => n.id === q.get('open')) ?? notes[0];
    return { theme: q.get('theme') ?? 'auto', animations: true, hasTray: true, nav: await mockApi.nav(),
             note: payload(first), command: 'show', notice: '', recording: { recording: false } };
  },
  nav: async () => [
    { key: 'today', label: 'Oggi', icon: 'sun', count: 2 },
    { key: 'all', label: 'Tutte le note', icon: 'notes', count: notes.length },
    { key: 'meeting', label: 'Meeting', icon: 'users', count: 1 },
    { key: 'note', label: 'Note', icon: 'pen', count: 1 },
    { key: 'actions', label: 'Azioni', icon: 'check-square', count: 2 },
    { key: 'project:clientex', label: 'clientex', icon: 'hash', count: 1, group: 'Progetti' },
  ],
  notes: async (view, search) => notes
    .filter((n) => view === 'all' || view === n.type || (view === 'project:clientex' && n.project === 'clientex') || view === 'today')
    .filter((n) => !search || `${n.title} ${n.body}`.toLowerCase().includes(search.toLowerCase()))
    .map((n) => ({ id: n.id, title: n.title, when: n.date.length > 10 ? n.date.slice(11) : 'Oggi',
                   preview: n.body.replace(/[#*>\-[\]x]|!decisione|due:\S+/g, ' ').replace(/\s+/g, ' ').trim(),
                   section: n.date.startsWith(today) ? 'Oggi' : 'Ottobre', type: n.type, icon: typeInfo[n.type][1],
                   project: n.project, people: n.people })),
  actions: async () => [
    { key: 'a1', text: '@Marco invia preventivo', raw: '@Marco invia preventivo due:2026-10-31', due: '31 ott', level: '',
      noteId: 'kickoff', noteTitle: 'Kickoff cliente X', section: 'Prossimi 7 giorni' },
    { key: 'a2', text: 'Inviare mail di riepilogo a @Laura', raw: 'Inviare mail di riepilogo a @Laura', due: '', level: '',
      noteId: `${today}-giornata`, noteTitle: 'Giornata di oggi', section: 'Senza scadenza' },
  ],
  suggestions: async () => ({ people: ['Marco', 'Laura', 'Giulia'], projects: ['clientex', 'design'] }),
  open: async (id) => payload(notes.find((n) => n.id === id)),
  daily: async () => payload(notes[0]),
  draft: async (type) => payload({ id: null, type, title: '', date: `${today}T12:00`, people: [], project: '', body: '' }),
  save: async (data) => ({ status: 'saved', note: { ...data, id: data.id ?? `nuova-${Date.now()}`, mtime: 1 } }),
  poll: async () => null,
  complete_action: async () => ({}),
  set_theme: async () => {},
  titlebar: async () => {},
  append: async () => true,
  delete_info: async (id) => ({ id, title: notes.find((n) => n.id === id)?.title ?? id, audio: 0 }),
  delete_note: async () => ({ status: 'deleted' }),
  start_recording: async (noteId) => ({ recording: true, noteId, elapsed: '00:00', level: 0 }),
  stop_recording: async () => null,
  recording_status: async () => ({ recording: false }),
  reveal_note: async () => {},
  open_folder: async () => {},
  quit: async () => {},
};
