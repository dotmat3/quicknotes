// Prova nell'app vera: immagini incollate e trascinate nella nota, salvate in images/ con il tag Markdown,
// mostrate nell'anteprima viva e in Anteprima; il server locale serve solo immagini della cartella delle note.
// L'ultimo passaggio usa gli appunti veri di Windows e un Ctrl V vero: sostituisce il contenuto degli appunti
// e per qualche secondo il PC non va usato. Va usata con le note di demo-note.mjs.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { Win } from './win.mjs';

// La prova chiede apposta file che il server deve rifiutare (404) e incolla un falso PNG, che rifiuta (400).
export const expectedErrors = [/status of 404 \(Not Found\)/, /status of 400 \(Bad Request\)/];

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page, { notes, work }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const month = join(notes, String(now.getFullYear()), p(now.getMonth() + 1));
  const daily = join(month, `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}-giornata.md`);
  const read = () => readFileSync(daily, 'utf8');
  const images = () => {
    try {
      return readdirSync(join(month, 'images'));
    } catch {
      return [];
    }
  };
  const until = async (fn, ms = 3000) => {
    for (const end = Date.now() + ms; Date.now() < end; await page.waitForTimeout(80)) if (await fn()) return true;
    return false;
  };

  // Un'immagine vera disegnata nella pagina, incollata o lasciata cadere come farebbe il sistema.
  const send = (type, { w = 40, h = 30, text = '', bytes = null, at = null } = {}) =>
    page.evaluate(async ({ type, w, h, text, bytes, at }) => {
      let blob;
      if (bytes) blob = new Blob([new Uint8Array(bytes)], { type: 'image/png' });
      else {
        const c = Object.assign(document.createElement('canvas'), { width: w, height: h });
        const g = c.getContext('2d');
        g.fillStyle = '#d33';
        g.fillRect(0, 0, w, h);
        blob = await new Promise((r) => c.toBlob(r, 'image/png'));
      }
      const dt = new DataTransfer();
      dt.items.add(new File([blob], 'immagine.png', { type: 'image/png' }));
      if (text) dt.setData('text/plain', text);
      const target = document.querySelector('.cm-content');
      if (type === 'paste') target.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
      else {
        const r = at ?? target.getBoundingClientRect();
        const el = at ? document.elementFromPoint(at.x, at.y) : target;
        const opts = { dataTransfer: dt, bubbles: true, cancelable: true, clientX: at ? at.x : r.left + 20, clientY: at ? at.y : r.bottom - 10 };
        el.dispatchEvent(new DragEvent('dragover', opts));
        el.dispatchEvent(new DragEvent('drop', opts));
      }
    }, { type, w, h, text, bytes, at });

  await page.waitForSelector('.cm-content');
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nSchermata: ');

  // Incolla: il file va in images/ e nella nota resta solo il tag.
  await send('paste');
  assert(await until(() => /Schermata: !\[\]\(images\/\d{4}-\d\d-\d\d-\d{6}\.png\)/.test(read())), 'incollando, la nota riceve il tag ![](images/…png)');
  const first = images()[0];
  assert(images().length === 1 && readFileSync(join(month, 'images', first)).subarray(0, 4).toString('latin1') === '\x89PNG', `il file è un PNG vero in images/ accanto alla nota: ${first}`);

  // Fuori dalla riga del cursore il tag diventa l'immagine, caricata dal server locale.
  await page.keyboard.press('Enter');
  await page.keyboard.type('riga dopo');
  await page.waitForSelector('.cm-image img');
  assert(await until(() => page.locator('.cm-image img').first().evaluate((i) => i.complete && i.naturalWidth === 40)), 'l\'anteprima viva mostra l\'immagine, 40×30');
  const src = await page.locator('.cm-image img').first().getAttribute('src');
  const origin = await page.evaluate(() => window.__QN__.fileOrigin);
  assert(src.startsWith(origin) && src.endsWith(`/images/${first}`), `servita dalla cartella delle note: ${src}`);
  await page.keyboard.press('ArrowUp');
  await page.keyboard.press('End');
  await page.waitForTimeout(150);
  assert((await page.locator('.cm-activeLine, .cm-line').filter({ hasText: '![](images/' }).count()) === 1, 'con il cursore sulla riga torna il testo del tag');

  // Testo semplice negli appunti insieme all'immagine (una tabella da Word): vince il testo.
  await page.keyboard.press('Control+End');
  await page.keyboard.press('Enter');
  await send('paste', { text: 'solo testo' });
  await page.waitForTimeout(400);
  assert(images().length === 1, 'con testo semplice negli appunti non si salva nessuna immagine');

  // Un file che si spaccia per PNG viene rifiutato, senza lasciare file.
  await send('paste', { bytes: [...Buffer.from('MZ questo non è un PNG')] });
  assert(await until(async () => (await page.locator('.toast').count()) && (await page.locator('.toast').innerText()).includes('Immagine non salvata')), 'un falso PNG viene rifiutato con un avviso');
  assert(images().length === 1 && !read().includes('MZ'), 'e non lascia file né testo');

  // Trascinamento nell'editor, e fuori: la pagina dell'app non se ne va.
  await send('drop', { w: 64, h: 16 });
  assert(await until(() => images().length === 2 && (read().match(/!\[\]\(images\//g) ?? []).length === 2), 'trascinata nell\'editor, l\'immagine si salva e il tag va nella nota');
  const side = await page.locator('.side, aside, nav').first().boundingBox();
  await send('drop', { at: { x: side.x + 20, y: side.y + 200 } });
  await page.waitForTimeout(400);
  assert(page.url().startsWith('http://127.0.0.1:') && images().length === 2, 'un\'immagine lasciata fuori dall\'editor non apre il file al posto dell\'app');

  // Il server serve solo immagini vere dentro la cartella delle note.
  writeFileSync(join(work, 'fuori.png'), readFileSync(join(month, 'images', first)));
  const rel = `${now.getFullYear()}/${p(now.getMonth() + 1)}`;
  const status = await page.evaluate(async (urls) => Promise.all(urls.map((u) => fetch(u).then((r) => r.status, () => 0))), [
    `${origin}${rel}/images/${first}`,
    `${origin}${rel}/${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}-giornata.md`,
    `${origin}${rel}/images/%2E%2E/%2E%2E/%2E%2E/%2E%2E/fuori.png`,
    `${origin}C:/Windows/win.ini`,
    origin.replace(/\/[^/]+\/qnfile\/$/, '/altro-prefisso/qnfile/') + `${rel}/images/${first}`,
  ]);
  assert(status[0] === 200 && status.slice(1).every((s) => s === 404), `si legge l'immagine; non la nota, né un file fuori dalla cartella, né un file di sistema, né senza il prefisso segreto: ${status.join(', ')}`);

  // Anteprima: stessa immagine; un indirizzo web resta un segnaposto, senza connessioni.
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\n![logo](https://example.com/logo.png)');
  await page.waitForTimeout(700);
  await page.keyboard.press('Control+k');
  await page.locator('.dialog .field input').fill('> Anteprima');
  await page.locator('.dialog .row .label', { hasText: /^Modalità della nota: Anteprima$/ }).click();
  await page.waitForSelector('.pv img.pv-img');
  assert(await until(() => page.locator('.pv img.pv-img').evaluateAll((l) => l.length === 2 && l.every((i) => i.complete && i.naturalWidth > 0))), 'l\'Anteprima mostra le due immagini');
  assert((await page.locator('.pv .pv-embed', { hasText: 'logo' }).count()) === 1, 'un\'immagine dal web resta un segnaposto');
  await page.keyboard.press('Control+k');
  await page.locator('.dialog .field input').fill('> Anteprima viva');
  await page.locator('.dialog .row .label', { hasText: /^Modalità della nota: Anteprima viva$/ }).click();

  // Appunti veri di Windows e Ctrl V vero, come dopo uno screenshot.
  const win = new Win();
  try {
    await win.call("Add-Type -AssemblyName System.Windows.Forms, System.Drawing; $b = New-Object Drawing.Bitmap 50, 20; [Windows.Forms.Clipboard]::SetImage($b)");
    await win.keys('ctrl+alt+d');
    await page.waitForTimeout(600);
    await page.locator('.cm-content').click();
    await page.keyboard.press('Control+End');
    await page.keyboard.press('Enter');
    await win.keys('ctrl+v');
    assert(await until(() => images().length === 3 && (read().match(/!\[\]\(images\//g) ?? []).length === 3, 5000), 'con gli appunti veri di Windows, Ctrl V salva l\'immagine e scrive il tag');
  } finally {
    win.close();
  }
}
