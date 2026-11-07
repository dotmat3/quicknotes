// Il comportamento di Micio. Un solo gatto per tutta l'app: in giro sulle schede (contesto "app"), nella sua stanza
// ("room"), fermo durante il minigioco ("game") o nascosto ("off"). Ogni animazione finisce in una posa (seduto,
// in piedi, sdraiato) e prima di fare qualcosa il gatto passa per la transizione giusta: non cammina mai da seduto.
import { ONCE, POSE } from './animazioni.js';
import { ITEMS, pet } from './store.svelte.js';

class Brain {
  x = $state(40);
  dir = $state(1);
  dur = $state(0);
  ease = $state('linear');
  anim = $state('sit');
  alt = $state(false);
  arc = $state('');
  act = $state('si guarda intorno');
  bubble = $state('');
  hearts = $state(false);
  usingYarn = $state(false);
  context = $state('off');
  pose = 'sit';
  timers = [];
  last = '';
  mover = null; // l'elemento che si sposta: serve per fermarlo dov'è davvero

  get reduce() {
    return matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
  get animClass() {
    return this.anim + (ONCE[this.anim] && this.alt ? 'b' : '');
  }

  after(ms, fn) {
    this.timers.push(setTimeout(fn, ms));
  }
  clear() {
    this.timers.forEach((t) => clearTimeout(t));
    this.timers = [];
  }

  // Entra in un contesto: da capo, in un punto a caso.
  enter(context) {
    if (this.context === context) return;
    this.clear();
    this.context = context;
    this.x = 20 + Math.random() * 60;
    this.dur = 0;
    this.anim = 'sit';
    this.pose = 'sit';
    this.arc = '';
    this.bubble = '';
    this.hearts = false;
    this.usingYarn = false;
    if (context === 'app' || context === 'room') this.after(900, () => this.next());
  }

  // Dov'è davvero ora, anche a metà di una camminata: la pista è larga quanto il contenitore, quindi la sua
  // traslazione divisa per la larghezza è la posizione in %.
  stopHere() {
    const el = this.mover;
    if (!el?.isConnected) return;
    const w = el.clientWidth || 1;
    const t = new DOMMatrix(getComputedStyle(el).transform);
    this.x = (t.m41 / w) * 100;
    this.dur = 0;
  }

  set(anim, act, extra) {
    const once = !!ONCE[anim];
    if (once) this.alt = !this.alt;
    this.anim = anim;
    this.pose = POSE[anim];
    this.arc = anim === 'pounce' ? 'qn-arc-pounce' + (this.alt ? 'b' : '') : '';
    if (act) this.act = act;
    this.dur = 0;
    this.hearts = false;
    if (extra) Object.assign(this, extra);
  }

  toPose(target, cb) {
    const p = this.pose;
    if (p === target) return cb();
    if (target === 'stand') {
      if (p === 'lie') {
        this.set('getup');
        return this.after(ONCE.getup, () => { this.set('standup'); this.after(ONCE.standup, cb); });
      }
      this.set('standup');
      return this.after(ONCE.standup, cb);
    }
    if (target === 'sit') {
      if (p === 'stand') { this.set('sitdown'); return this.after(ONCE.sitdown, cb); }
      this.set('getup');
      return this.after(ONCE.getup, cb);
    }
    const down = () => { this.set('liedown'); this.after(ONCE.liedown, cb); };
    if (p === 'stand') { this.set('sitdown'); return this.after(ONCE.sitdown, down); }
    down();
  }

  // Cammina o corre fino a x (in % della larghezza), poi si ferma in piedi.
  goTo(x, msPerPct, anim, act, cb, ease) {
    this.toPose('stand', () => {
      const tx = Math.max(4, Math.min(96, x));
      const dx = tx - this.x;
      const dur = Math.max(450, Math.abs(dx) * msPerPct);
      if (Math.abs(dx) >= 0.5) this.dir = dx > 0 ? 1 : -1;
      this.set(anim, act);
      this.ease = ease || 'linear';
      this.dur = dur;
      this.x = tx;
      this.after(dur, () => { this.anim = 'stand'; this.dur = 0; cb(); });
    });
  }
  sitFor(anim, act, ms, then) { this.toPose('sit', () => { this.set(anim, act); this.after(ms, then || (() => this.next())); }); }
  standFor(act, ms) { this.toPose('stand', () => { this.set('stand', act); this.after(ms, () => this.next()); }); }
  nap(act, ms) {
    this.toPose('lie', () => {
      this.set('rest', act);
      this.after(1500, () => this.set('sleep', act));
      this.after(1500 + ms, () => {
        this.set('getup', 'si sveglia');
        this.after(ONCE.getup, () => { this.set('sit', 'si lecca una zampa'); this.after(1600, () => this.next()); });
      });
    });
  }
  pounce(act, then) {
    this.toPose('sit', () => {
      this.set('pounce', act);
      this.after(ONCE.pounce, () => { this.set('sit'); this.after(500, then || (() => this.next())); });
    });
  }
  yarn(act, ms, end) {
    this.toPose('sit', () => {
      this.set('yarn', act);
      this.after(ms, () => {
        if (end) end();
        this.set('getup');
        this.after(ONCE.getup, () => { this.set('sit'); this.after(600, () => this.next()); });
      });
    });
  }

  pick(opts) {
    const pool = opts.filter((o) => o[0] !== this.last);
    let r = Math.random() * pool.reduce((s, o) => s + o[1], 0);
    for (const o of pool) { r -= o[1]; if (r < 0) { this.last = o[0]; return o[0]; } }
    this.last = pool[0][0];
    return pool[0][0];
  }

  next() {
    this.clear();
    if (this.reduce) { this.set('sit', 'si riposa'); return; }
    if (this.context === 'room') return this.roomStep();
    if (this.context !== 'app') return;
    return pet.out === 'play' ? this.playStep() : this.appStep();
  }

  appStep() {
    const x = this.x;
    const k = this.pick([['walk', 30], ['sit', 12], ['stand', 8], ['tap', 8], ['pounce', 10], ['zoom', 8], ['nap', 8], ['yarn', 8]]);
    if (k === 'walk') return this.goTo(x < 50 ? 52 + Math.random() * 44 : 4 + Math.random() * 44, 260, 'walk', 'passeggia', () => this.next());
    if (k === 'zoom') return this.goTo(x < 50 ? 82 + Math.random() * 14 : 4 + Math.random() * 14, 80, 'run', 'corre all’impazzata', () => this.sitFor('sit', 'riprende fiato', 2400), 'ease-in-out');
    if (k === 'stand') return this.standFor('si guarda intorno', 3000);
    if (k === 'tap') return this.sitFor('tap', 'tocca qualcosa con la zampa', 2800);
    if (k === 'pounce') return this.pounce('balza su qualcosa');
    if (k === 'nap') return this.nap('fa un pisolino', 8000);
    if (k === 'yarn') return this.yarn('gioca col gomitolo', 5200);
    this.sitFor('sit', 'si siede', 3600);
  }
  playStep() {
    const k = this.pick([['yarn', 50], ['chase', 30], ['pounce', 20]]);
    if (k === 'yarn') return this.yarn('gioca col gomitolo', 7000);
    if (k === 'chase') return this.goTo(8 + Math.random() * 84, 85, 'run', 'rincorre il gomitolo', () => this.pounce('ci salta sopra'), 'ease-in-out');
    this.pounce('punta il gomitolo e balza');
  }

  roomStep() {
    const placed = ITEMS.filter((i) => pet.placed[i.id]);
    const opts = [['walk', 26], ['sit', 12], ['stand', 8], ['tap', 6], ['nap', 6], ['zoom', 6]];
    for (const it of placed) opts.push(['use:' + it.id, 16]);
    const k = this.pick(opts);
    if (k.startsWith('use:')) return this.useItem(ITEMS.find((i) => 'use:' + i.id === k));
    if (k === 'walk') return this.goTo(6 + Math.random() * 88, 200, 'walk', 'gira per la stanza', () => this.next());
    if (k === 'zoom') return this.goTo(this.x < 50 ? 90 : 10, 64, 'run', 'corre da una parete all’altra', () => this.sitFor('sit', 'riprende fiato', 2400), 'ease-in-out');
    if (k === 'stand') return this.standFor('si guarda intorno', 2800);
    if (k === 'tap') return this.sitFor('tap', 'gioca con la polvere', 2800);
    if (k === 'nap') return this.nap('dorme per terra', 6000);
    this.sitFor('sit', 'si siede', 3400);
  }
  useItem(it) {
    if (this.context !== 'room') return;
    this.clear();
    const near = it.id === 'tiragraffi' || it.id === 'pianta' ? it.x - 9 : it.x;
    this.goTo(near, 200, 'walk', 'va verso ' + it.name.toLowerCase(), () => {
      if (it.id === 'cuscino') return this.nap('dorme sul cuscino', 9000);
      if (it.id === 'tappeto') return this.nap('sonnecchia sul tappeto', 6000);
      if (it.id === 'gomitolo') {
        this.usingYarn = true;
        return this.yarn('gioca col gomitolo', 6000, () => (this.usingYarn = false));
      }
      if (it.id === 'tiragraffi') { this.dir = 1; return this.sitFor('tap', 'si fa le unghie', 3600); }
      if (it.id === 'ciotola') return this.sitFor('tap', 'pesca le crocchette con la zampa', 3200);
      if (it.id === 'pianta') { this.dir = 1; return this.sitFor('tap', 'tocca la pianta con la zampa', 2600); }
      if (it.id === 'scatola') return this.pounce('salta nella scatola', () => this.sitFor('sit', 'si è seduto nella scatola', 3000));
      if (it.id === 'lampada') return this.pounce('prova a prendere la luce', () => this.pounce('ci riprova'));
      this.sitFor('sit', 'guarda il quadro', 3200);
    });
  }

  // Festa: un balzo da seduto con i cuori e una nuvoletta.
  cheer(act, bubble) {
    if (this.context !== 'app' && this.context !== 'room') return;
    this.clear();
    this.stopHere();
    this.bubble = bubble;
    this.hearts = true;
    this.toPose('sit', () => {
      this.set('pounce', act, { bubble, hearts: true });
      this.after(ONCE.pounce + 1200, () => { this.set('sit'); this.bubble = ''; this.next(); });
    });
  }
}

export const brain = new Brain();
