// Il foglio sprite colorato, preparato una volta per mantello: corpo moltiplicato per il colore, occhi del colore
// adatto al mantello, dettagli originali. Il gatto diventa così una sola immagine, senza maschere né fusioni da
// ricalcolare a ogni fotogramma.
import corpoUrl from './sprite/gatto-corpo.png';
import dettagliUrl from './sprite/gatto-dettagli.png';
import occhiUrl from './sprite/gatto-occhi.png';

const load = (src) =>
  new Promise((ok, ko) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = ko;
    img.src = src;
  });

let images = null;
const cache = new Map();

export async function sheetFor(coat, eye) {
  const key = coat + eye;
  if (cache.has(key)) return cache.get(key);
  images ??= Promise.all([load(corpoUrl), load(dettagliUrl), load(occhiUrl)]);
  const [corpo, dettagli, occhi] = await images;
  const w = corpo.naturalWidth, h = corpo.naturalHeight;
  const layer = (img, paint) => {
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    const g = c.getContext('2d');
    g.drawImage(img, 0, 0);
    paint(g);
    g.globalCompositeOperation = 'destination-in';
    g.drawImage(img, 0, 0);
    return c;
  };
  const body = layer(corpo, (g) => { g.globalCompositeOperation = 'multiply'; g.fillStyle = coat; g.fillRect(0, 0, w, h); });
  const eyes = layer(occhi, (g) => { g.globalCompositeOperation = 'source-in'; g.fillStyle = eye; g.fillRect(0, 0, w, h); });
  const out = document.createElement('canvas');
  out.width = w;
  out.height = h;
  const g = out.getContext('2d');
  g.drawImage(body, 0, 0);
  g.drawImage(eyes, 0, 0);
  g.drawImage(dettagli, 0, 0);
  const url = out.toDataURL('image/png');
  cache.set(key, url);
  return url;
}
