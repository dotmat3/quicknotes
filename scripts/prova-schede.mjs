// Prova trascinamento delle schede, disposizione ricordata e uscita con salvataggio.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page, { notes }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const iso = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
  const daily = join(notes, String(now.getFullYear()), p(now.getMonth() + 1), `${iso}-giornata.md`);

  await page.waitForSelector('.cm-content');
  await page.getByRole('button', { name: 'Calendario' }).first().click();
  await page.waitForSelector('.grid');
  await page.getByRole('button', { name: 'Persone', exact: false }).first().click();
  await page.waitForTimeout(150);
  const tabs = () => page.locator('.tab .clip').allInnerTexts();
  assert((await tabs()).length === 3, `tre schede aperte: ${(await tabs()).join(', ')}`);

  // Riordino: Persone prima di Calendario.
  await page.locator('.tab', { hasText: 'Persone' }).dragTo(page.locator('.tab', { hasText: 'Calendario' }));
  await page.waitForTimeout(150);
  const order = await tabs();
  assert(order.indexOf('Persone') < order.indexOf('Calendario'), `il trascinamento riordina: ${order.join(', ')}`);

  // Divisione: Calendario sul bordo destro apre un secondo gruppo.
  const box = await page.locator('.scroll').first().boundingBox();
  const tab = await page.locator('.tab', { hasText: 'Calendario' }).boundingBox();
  await page.mouse.move(tab.x + 40, tab.y + 15);
  await page.mouse.down();
  await page.mouse.move(tab.x + 80, tab.y + 60, { steps: 4 });
  await page.mouse.move(box.x + box.width - 40, box.y + box.height / 2, { steps: 8 });
  await page.waitForTimeout(150);
  assert((await page.locator('.preview.right').count()) === 1, 'sul bordo destro compare l\'anteprima');
  await page.mouse.up();
  await page.waitForTimeout(250);
  assert((await page.locator('main.pane').count()) === 2, 'lasciando la scheda si crea un secondo gruppo');
  assert((await page.locator('main.pane').nth(1).locator('.tab .clip').allInnerTexts()).join() === 'Calendario', 'la scheda è passata al nuovo gruppo');

  // Scheda chiusa e riaperta.
  await page.locator('.tab', { hasText: 'Persone' }).getByRole('button', { name: /^Chiudi/ }).click();
  await page.waitForTimeout(100);
  assert(!(await tabs()).includes('Persone'), 'la scheda si chiude');
  await page.keyboard.press('Control+Shift+T');
  await page.waitForTimeout(150);
  assert((await tabs()).includes('Persone'), 'Ctrl Shift T la riapre');

  // La disposizione va nella configurazione: scripts/prova-riavvio.mjs controlla che torni dopo un riavvio.
  await page.waitForTimeout(700);

  // L'uscita salva le modifiche ancora in sospeso prima di chiudere.
  await page.getByRole('tab', { name: /Oggi/ }).click();
  await page.waitForSelector('.cm-content');
  await page.locator('.cm-content').first().click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('testo prima di uscire');
  await page.evaluate(() => {
    window.__TAURI_INTERNALS__.invoke('plugin:event|emit', { event: 'flush-and-close', payload: null }).catch(() => {});
  });
  await new Promise((r) => setTimeout(r, 900));
  assert(readFileSync(daily, 'utf8').includes('testo prima di uscire'), 'all\'uscita il testo in sospeso è nel file');
}
