// Le animazioni di Micio, calibrate nel Banco animazioni. Sprite: Cat Pack di Glem (octopusinkus.itch.io),
// versione gratuita; il gatto nero è diviso in tre livelli (corpo da tingere, dettagli, occhi).
// Fotogramma: [colonna, riga, dx, dy] in pixel dello sprite; dy positivo alza, dx positivo va verso dove guarda.
export const ANIMS = {
  sit: {"it": "seduto", "frames": [[0, 0, 0, 0], [1, 0, 0, 0], [2, 0, 0, 0], [3, 0, 0, 0], [4, 0, 0, 0], [5, 0, 0, 0], [6, 0, 0, 0], [7, 0, 0, 0], [8, 0, 0, 0]], "ms": 1500, "loop": true, "pose": "sit"},
  standup: {"it": "si alza", "frames": [[0, 1, 0, 0], [1, 1, 0, 0], [2, 1, 0, 1], [3, 1, 0, 1], [4, 1, 0, 1]], "ms": 500, "loop": false, "pose": "stand"},
  sitdown: {"it": "si siede", "frames": [[4, 1, 0, 1], [3, 1, 0, 1], [2, 1, 0, 1], [1, 1, 0, 0], [0, 1, 0, 0]], "ms": 500, "loop": false, "pose": "sit"},
  stand: {"it": "in piedi fermo", "frames": [[4, 1, 0, 1]], "ms": 1000, "loop": true, "pose": "stand"},
  pounce: {"it": "balzo da seduto", "frames": [[0, 2, 0, 0], [1, 2, 0, 0], [2, 2, 0, 0], [3, 2, 0, 0], [4, 2, 0, 0], [5, 2, 0, 0], [6, 2, 0, 1], [7, 2, 0, 2], [8, 2, 0, 2], [9, 2, 0, 0], [10, 2, 0, 0]], "ms": 1100, "loop": false, "pose": "sit"},
  tap: {"it": "zampa allungata", "frames": [[3, 3, 0, 0], [4, 3, 0, 0], [5, 3, 0, 1], [4, 3, 0, 0]], "ms": 800, "loop": true, "pose": "sit"},
  liedown: {"it": "si sdraia", "frames": [[0, 4, 0, 0], [1, 4, 0, 0], [2, 4, 0, 0], [3, 4, 0, 0], [4, 4, 0, 0], [5, 4, 0, 0], [6, 4, 0, 0], [7, 4, 0, 0]], "ms": 900, "loop": false, "pose": "lie"},
  getup: {"it": "si rialza", "frames": [[7, 4, 0, 0], [6, 4, 0, 0], [5, 4, 0, 0], [4, 4, 0, 0], [3, 4, 0, 0], [2, 4, 0, 0], [1, 4, 0, 0], [0, 4, 0, 0]], "ms": 900, "loop": false, "pose": "sit"},
  rest: {"it": "sdraiato sveglio", "frames": [[6, 4, 0, 0], [6, 4, 0, 0], [6, 4, 0, 0], [7, 4, 0, 0]], "ms": 2000, "loop": true, "pose": "lie"},
  sleep: {"it": "dorme", "frames": [[8, 4, 0, 0], [9, 4, 0, 0]], "ms": 2200, "loop": true, "pose": "lie"},
  walk: {"it": "cammina", "frames": [[0, 5, 0, 0], [1, 5, 0, 0], [2, 5, 0, 0], [3, 5, 0, 0], [4, 5, 0, 0], [5, 5, 0, 0], [6, 5, 0, 0], [7, 5, 0, 0], [8, 5, 0, 0], [9, 5, 0, 0]], "ms": 2000, "loop": true, "pose": "stand"},
  run: {"it": "corre", "frames": [[1, 6, -2, 0], [2, 6, -2, 0], [3, 6, -2, 0], [4, 6, -2, 0], [5, 6, -2, 0], [6, 6, -2, 0], [7, 6, -2, 0], [8, 6, -2, 0], [9, 6, -2, 0]], "ms": 1200, "loop": true, "pose": "stand"},
  yarn: {"it": "gomitolo", "frames": [[0, 7, 0, 0], [1, 7, 0, 0], [2, 7, 0, 0], [3, 7, 0, 0], [4, 7, 0, 0], [5, 7, 0, 0], [6, 7, 0, 0], [7, 7, 0, 0], [8, 7, 0, 0], [9, 7, 0, 0], [10, 7, 0, 0]], "ms": 1200, "loop": true, "pose": "lie"},
};

// Posa in cui finisce ogni animazione e durata di quelle che si fanno una volta sola.
export const POSE = Object.fromEntries(Object.entries(ANIMS).map(([k, a]) => [k, a.pose]));
export const ONCE = Object.fromEntries(Object.entries(ANIMS).filter(([, a]) => !a.loop).map(([k, a]) => [k, a.ms]));

// Colonna dell'occhio: il gatto si specchia attorno alla testa, così girandosi non salta.
export const HEAD = 18.5;

const pos = (c, r) => `${((c * 100) / 11).toFixed(4)}% ${r * 12.5}%`;
const decl = ([c, r, dx = 0, dy = 0]) => {
  const p = pos(c, r);
  return `background-position:${p};-webkit-mask-position:${p};mask-position:${p};translate:${dx}em ${-dy}em`;
};

// Le regole dei fotogrammi, una volta sola per tutta la pagina. Le animazioni "una volta" hanno un secondo nome
// (suffisso b): cambiando nome a ogni uso ripartono anche quando si ripetono di fila.
let injected = false;
export function injectCss() {
  if (injected) return;
  injected = true;
  const out = [];
  for (const [name, a] of Object.entries(ANIMS)) {
    const fr = a.frames;
    const steps = [...fr, fr[fr.length - 1]].map((f, i) => `${+((i * 100) / fr.length).toFixed(3)}%{${decl(f)}}`).join('');
    for (const v of a.loop ? [''] : ['', 'b']) {
      out.push(`@keyframes qn-k-${name}${v}{${steps}}`);
      out.push(`.qn-a-${name}${v}{${decl(fr[0])};animation:qn-k-${name}${v} ${a.ms / 1000}s step-end ${a.loop ? 'infinite' : '1 forwards'}}`);
    }
  }
  for (const v of ['', 'b']) {
    out.push(`@keyframes qn-arc-pounce${v}{0%,52%{transform:translateY(0)}66%{transform:translateY(-8em)}80%,100%{transform:translateY(0)}}`);
    out.push(`.qn-arc-pounce${v}{animation:qn-arc-pounce${v} ${ANIMS.pounce.ms / 1000}s ease-in-out 1}`);
  }
  out.push('@media (prefers-reduced-motion: reduce){[class*="qn-a-"],[class*="qn-arc-"]{animation:none!important}}');
  const style = document.createElement('style');
  style.dataset.qn = 'micio';
  style.textContent = out.join('\n');
  document.head.append(style);
}
