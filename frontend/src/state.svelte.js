// Stato dell'app: vista, elenchi, nota aperta, salvataggio automatico, modifiche esterne,
// registrazione ed eventi mandati da Python (window.qnEvent).
import { call } from './api.js';
import { clock } from './editor/dates.js';

const SAVE_DELAY = 600;
const SEARCH_DELAY = 150;
const POLL_INTERVAL = 2000;
const RECORDING_TICK = 120;

let drafts = 0;

class AppState {
  nav = $state([]);
  view = $state('all');
  search = $state('');
  notes = $state([]);
  actions = $state([]);
  note = $state(null);          // nota aperta: payload di Python + key (stabile) e rev (contenuto ricaricato)
  saveState = $state('idle');   // idle | pending | saving | saved
  theme = $state('auto');
  animations = $state(true);
  hasTray = $state(false);
  toast = $state(null);         // { text, icon, id }
  dialog = $state(null);        // { title, text, accept, reject, danger, cancellable, resolve }
  focus = $state(null);         // { target: 'title' | 'editor' | 'search', n }
  empty = $state(true);         // la nota aperta non ha testo (si mostrano i suggerimenti di scrittura)
  recording = $state(null);     // { noteId, elapsed, level } durante la registrazione
  transcription = $state(null); // { percent } durante la trascrizione
  suggestions = { people: [], projects: [] };
  editorView = null;            // editor CodeMirror della nota aperta (per aggiungere testo in fondo)

  body = '';                    // testo dell'editor (non reattivo: cambia a ogni tasto)
  dirty = false;
  #saving = Promise.resolve();
  #saveTimer = 0;
  #searchTimer = 0;
  #toastTimer = 0;
  #recTimer = 0;
  #focusN = 0;

  get paneTitle() {
    const item = this.nav.find((n) => n.key === this.view);
    if (!item) return 'Tutte le note';
    return this.view.startsWith('project:') ? `#${item.label}` : item.label;
  }

  async start() {
    window.qnEvent = (name, data) => this.#event(name, data);
    window.qnPending = () => (this.dirty ? this.#payload() : null);  // letto da Python alla chiusura
    const boot = await call('bootstrap');
    this.theme = boot.theme;
    this.animations = boot.animations;
    this.hasTray = boot.hasTray;
    this.nav = boot.nav;
    this.#load(boot.note);
    this.refreshList();
    this.refreshSuggestions();
    if (boot.recording?.recording) this.#watchRecording(boot.recording);
    if (boot.notice) this.showToast(boot.notice, 'x');
    if (boot.command !== 'show') this.#event('command', boot.command);
    setInterval(() => this.#poll(), POLL_INTERVAL);
    window.addEventListener('blur', () => this.save());
    document.addEventListener('visibilitychange', () => document.hidden && this.save());
  }

  #event(name, data) {
    if (name === 'command') {
      if (data === 'new') this.newDraft('meeting');
      else if (data === 'daily') this.openDaily();
      else if (data === 'record') this.toggleRecording();
      else if (data === 'flush') this.save();
    } else if (name === 'append') {
      this.appendTo(data.noteId, data.text, data.heading).then(() => this.showToast('Trascrizione aggiunta alla nota', 'check'));
    } else if (name === 'transcription') {
      this.transcription = data.active ? { percent: data.percent } : null;
    } else if (name === 'toast') {
      this.showToast(data.text, data.icon);
    } else if (name === 'dialog') {
      this.inform(data.title, data.text);
    }
  }

  // ------------------------------------------------------------ nota aperta
  #load(payload, focus = 'editor') {
    const sameNote = this.note && payload.id && this.note.id === payload.id;
    this.note = { ...payload, key: sameNote ? this.note.key : payload.id ?? `draft-${++drafts}`,
                  rev: (this.note?.rev ?? 0) + 1 };
    this.body = payload.body;
    this.empty = !payload.body.trim();
    this.dirty = false;
    this.saveState = 'idle';
    if (focus) this.requestFocus(focus);
  }

  requestFocus(target) {
    this.focus = { target, n: ++this.#focusN };
  }

  async open(id) {
    if (!id || id === this.note?.id) return;
    await this.save();
    const payload = await call('open', id);
    if (payload) this.#load(payload);
    else {
      this.showToast('Nota non trovata (forse eliminata)', 'x');
      this.refreshList();
    }
  }

  async openDaily() {
    await this.save();
    const payload = await call('daily');
    // gia' aperta: niente ricarica (si perderebbe cio' che si sta scrivendo), solo il fuoco
    if (payload.id === this.note?.id) this.requestFocus('editor');
    else this.#load(payload);
    this.refreshList();
  }

  async newDraft(type) {
    await this.save();
    this.#load(await call('draft', type), 'title');
  }

  edit(field, value) {
    if (!this.note || this.note[field] === value) return;
    this.note[field] = value;
    this.markDirty();
  }

  setBody(text) {
    this.body = text;
    const empty = !text.trim();
    if (empty !== this.empty) this.empty = empty;
    this.markDirty();
  }

  markDirty() {
    this.dirty = true;
    this.saveState = 'pending';
    clearTimeout(this.#saveTimer);
    this.#saveTimer = setTimeout(() => this.save(), SAVE_DELAY);
  }

  #payload() {
    const n = this.note;
    return { id: n.id, type: n.type, date: n.date, title: n.title, people: n.people.map((p) => p.name),
             project: n.project, body: this.body, mtime: n.mtime };
  }

  // I salvataggi sono in fila: uno alla volta, nell'ordine in cui sono chiesti.
  save(force = false) {
    clearTimeout(this.#saveTimer);
    this.#saving = this.#saving.then(() => this.#save(force)).catch((err) => {
      this.saveState = 'pending';
      this.showToast(`Salvataggio non riuscito: ${err?.message ?? err}`, 'x');
    });
    return this.#saving;
  }

  async #save(force) {
    if (!this.dirty || !this.note) return;
    const note = this.note;
    const data = this.#payload();
    this.dirty = false;
    this.saveState = 'saving';
    const res = await call('save', data, force);
    if (res.status === 'conflict') {
      this.dirty = true;
      this.saveState = 'pending';
      this.#askOverwrite(res.disk);
      return;
    }
    if (res.status === 'missing') {
      this.showToast('La nota è stata eliminata dal disco: salvataggio annullato', 'trash');
      return;
    }
    if (res.status === 'saved' && this.note === note) {
      // la bozza diventa un file: id e versione nuovi, stessa key (l'editor non si ricarica)
      note.id = res.note.id;
      note.mtime = res.note.mtime;
      if (!this.dirty) this.saveState = 'saved';
    }
    this.refreshList();
    this.refreshSuggestions();
  }

  async #askOverwrite(disk) {
    if (this.dialog) return;
    const overwrite = await this.ask({
      title: 'Nota modificata altrove',
      text: "Questa nota è stata modificata fuori dall'app (ad esempio da Claude). Vuoi sovrascriverla con la tua " +
            'versione, o ricaricare quella su disco?',
      accept: 'Sovrascrivi', reject: 'Ricarica', cancellable: false,
    });
    if (overwrite) {
      this.dirty = true;
      await this.save(true);
    } else if (this.note?.id === disk.id) {
      this.#load(disk, null);
    }
  }

  async #poll() {
    const n = this.note;
    if (!n?.id || this.dirty || this.saveState === 'saving' || this.dialog) return;
    const changed = await call('poll', n.id, n.mtime);
    if (changed && this.note === n && !this.dirty) {
      this.#load(changed, null);
      this.showToast('Aggiornata da modifiche esterne', 'external');
      this.refreshList();
    }
  }

  /** Aggiunge un blocco in fondo a una nota: nell'editor se e' aperta (resta annullabile), altrimenti su disco. */
  async appendTo(noteId, text, heading = null) {
    const block = (heading ? `### ${heading}\n` : '') + text.replace(/^\n+|\n+$/g, '');
    const view = this.editorView;
    if (noteId === this.note?.id && view) {
      const doc = view.state.doc;
      const end = doc.toString().trimEnd().length;
      view.dispatch({ changes: { from: end, to: doc.length, insert: (end ? '\n\n' : '') + block + '\n' },
                      userEvent: 'input.append' });
      await this.save();
    } else {
      await this.save();
      await call('append', noteId, text, heading);
      this.refreshList();
    }
  }

  // ------------------------------------------------------------ elenchi
  selectView(key) {
    this.view = key;
    if (key === 'today') this.openDaily();
    else this.refreshList();
  }

  setSearch(text) {
    this.search = text;
    clearTimeout(this.#searchTimer);
    this.#searchTimer = setTimeout(() => this.refreshList(), SEARCH_DELAY);
  }

  async refreshList() {
    const view = this.view;
    const search = this.search;
    const [items, nav] = await Promise.all([
      view === 'actions' ? call('actions', search) : call('notes', view, search),
      call('nav'),
    ]);
    if (view !== this.view || search !== this.search) return;  // risposta superata
    if (view === 'actions') this.actions = items;
    else this.notes = items;
    this.nav = nav;
  }

  async refreshSuggestions() {
    this.suggestions = await call('suggestions');
  }

  async completeAction(item) {
    if (item.done) return;
    item.done = true;
    if (item.noteId === this.note?.id) await this.save();
    const res = await call('complete_action', item.noteId, item.raw);
    if (res?.error) {
      item.done = false;
      this.showToast(res.error, 'x');
      return;
    }
    this.showToast('Azione completata', 'check');
    setTimeout(() => this.refreshList(), 650);  // la spunta resta visibile un attimo
    if (item.noteId === this.note?.id) this.#poll();
  }

  // ------------------------------------------------------------ registrazione
  async toggleRecording() {
    if (this.recording) return this.stopRecording();
    const note = this.note;
    if (!note) return;
    if (!note.id) {  // serve un file a cui collegare l'audio
      if (!note.title.trim()) note.title = `Meeting ${clock()}`;
      this.dirty = true;
    }
    await this.save();
    if (!note.id || this.note !== note) return;
    const res = await call('start_recording', note.id);
    if (res.error) return this.inform('Registrazione', res.error);
    this.#watchRecording(res);
  }

  #watchRecording(status) {
    this.recording = status;
    clearInterval(this.#recTimer);
    this.#recTimer = setInterval(async () => {
      const s = await call('recording_status');
      if (!s.recording) {
        clearInterval(this.#recTimer);
        this.recording = null;
      } else if (this.recording) {
        this.recording = s;
      }
    }, RECORDING_TICK);
  }

  async stopRecording() {
    clearInterval(this.#recTimer);
    this.recording = null;
    const res = await call('stop_recording');
    if (res) await this.appendTo(res.noteId, res.text);
  }

  // ------------------------------------------------------------ eliminazione e file
  async deleteNote() {
    const note = this.note;
    if (!note) return;
    if (!note.id) {  // bozza mai salvata: basta scartarla
      this.dirty = false;
      return this.openDaily();
    }
    if (this.recording?.noteId === note.id) {
      return this.inform('Elimina nota', 'Ferma la registrazione prima di eliminare la nota.');
    }
    const info = await call('delete_info', note.id);
    if (!info) return this.refreshList();
    const extra = info.audio === 1 ? ' insieme a una registrazione audio'
      : info.audio ? ` insieme a ${info.audio} registrazioni audio` : '';
    const ok = await this.ask({ title: `Eliminare «${info.title}»?`, accept: 'Sposta nel Cestino', danger: true,
                                text: `La nota viene spostata nel Cestino${extra}: potrai recuperarla da lì.` });
    if (!ok) return;
    clearTimeout(this.#saveTimer);  // le modifiche in sospeso non vanno salvate
    this.dirty = false;
    const ids = this.notes.map((n) => n.id);
    const i = ids.indexOf(note.id);
    const neighbor = i < 0 ? null : (ids[i + 1] ?? ids[i - 1] ?? null);
    let res = await call('delete_note', note.id, false);
    let what = 'spostata nel Cestino';
    if (res.status === 'no-trash') {
      const forever = await this.ask({ title: 'Cestino non disponibile', accept: 'Elimina definitivamente', danger: true,
                                       text: 'Il Cestino non è disponibile per questa cartella. Eliminare la nota definitivamente?' });
      if (!forever) return;
      res = await call('delete_note', note.id, true);
      what = 'eliminata';
    }
    this.showToast(`«${info.title}» ${what}`, 'trash');
    if (this.note === note) {
      if (neighbor) await this.open(neighbor);
      else await this.openDaily();
    }
    this.refreshList();
  }

  revealNote() {
    if (this.note?.id) call('reveal_note', this.note.id);
  }

  openFolder() {
    call('open_folder');
  }

  quit() {
    call('quit');
  }

  // ------------------------------------------------------------ dialog e avvisi
  /** Chiede conferma; risolve true (accept) o false (reject / Esc). */
  ask(spec) {
    return new Promise((resolve) => {
      this.dialog = { reject: 'Annulla', danger: false, cancellable: true, ...spec,
                      resolve: (ok) => { this.dialog = null; resolve(ok); } };
    });
  }

  inform(title, text) {
    return this.ask({ title, text, accept: 'OK', reject: null });
  }

  showToast(text, icon = 'check') {
    clearTimeout(this.#toastTimer);
    this.toast = { text, icon, id: Date.now() };
    this.#toastTimer = setTimeout(() => (this.toast = null), 2400);
  }

  setTheme(mode) {
    this.theme = mode;
    call('set_theme', mode);
  }
}

export const app = new AppState();
