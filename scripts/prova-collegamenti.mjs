// Prova nell'app vera: note collegate dalla pillola, grafo completo e locale, barra del titolo.
// Va usata con le note di demo-note.mjs.
import { execSync, spawn } from 'node:child_process';
import { join, resolve } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

const h1 = (page) => page.locator('h1').first().innerText();

export default async function (page, { notes, work }) {
  await page.waitForSelector('.cm-content');

  // La pillola dei collegamenti apre le note collegate.
  const pill = page.locator('.pills .pill', { hasText: /collegament/ });
  assert((await pill.innerText()) === '1 collegamento', 'la nota di oggi ha un collegamento verso la riunione');
  await pill.click();
  const pop = page.getByRole('dialog', { name: 'Note collegate' });
  assert((await pop.locator('.lp-head').allInnerTexts()).join() === 'Collega a', 'il riquadro elenca le note citate');
  await pop.getByRole('button', { name: /Riunione budget Q4/ }).click();
  await page.waitForFunction(() => document.querySelector('h1')?.innerText === 'Riunione budget Q4');
  assert(true, 'un clic apre la nota collegata');
  await page.locator('.pills .pill', { hasText: /collegament/ }).click();
  const back = page.getByRole('dialog', { name: 'Note collegate' });
  assert((await back.locator('.lp-head').allInnerTexts()).join() === 'Citata in', 'nella riunione la nota di oggi compare tra quelle che la citano');
  assert((await back.locator('.lp-hint').first().innerText()).includes('Vedi'), 'con la riga che la cita');
  await page.keyboard.press('Escape');
  assert((await page.getByRole('dialog', { name: 'Note collegate' }).count()) === 0, 'Esc chiude il riquadro');

  // Un [[link]] scritto ora aggiorna la pillola dopo il salvataggio.
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nVedi anche [[Requisiti e architettura]]');
  await page.waitForTimeout(900);
  assert((await page.locator('.pills .pill', { hasText: /collegament/ }).innerText()) === '2 collegamenti', 'un link nuovo aggiorna i collegamenti');

  // Grafo completo: tutte le note, persone ed etichette; clic su un nodo apre la nota.
  await page.getByRole('button', { name: 'Grafo', exact: false }).first().click();
  await page.waitForSelector('canvas');
  await page.waitForTimeout(1500);
  const labels = await page.locator('.sr button').allInnerTexts();
  assert(['Riunione budget Q4', 'Requisiti e architettura', '@Giulia', '#casa'].every((l) => labels.includes(l)), `il grafo contiene tutte le note, persone ed etichette (${labels.length} nodi)`);
  assert((await page.locator('.sub').first().innerText()).match(/\d+ note · \d+ collegamenti/), 'il conteggio di note e collegamenti');
  await page.getByRole('checkbox', { name: 'Persone' }).uncheck();
  await page.waitForTimeout(200);
  assert(!(await page.locator('.sr button').allInnerTexts()).includes('@Giulia'), 'si possono nascondere le persone');
  await page.getByRole('checkbox', { name: 'Persone' }).check();
  await page.getByRole('radio', { name: 'Locale' }).click();
  await page.waitForTimeout(300);
  const local = await page.locator('.sr button').allInnerTexts();
  assert(local.includes('Riunione budget Q4') && local.includes('Requisiti e architettura') && local.length < labels.length, `il grafo locale parte dall'ultima nota aperta (${local.length} nodi)`);
  await page.getByRole('radio', { name: 'Tutto' }).click();
  await page.waitForTimeout(2500);
  const at = await page.locator('canvas').evaluate((c) => c.qnNodePosition('note:requisiti-e-architettura'));
  await page.mouse.move(at.x, at.y);
  await page.waitForTimeout(100);
  await page.mouse.down();
  await page.mouse.up();
  await page.waitForFunction(() => document.querySelector('h1')?.innerText === 'Requisiti e architettura');
  assert(true, 'un clic su un nodo del grafo apre la nota');

  // Barra del titolo.
  assert((await page.locator('.titlebar .title').innerText()) === 'Requisiti e architettura — QuickNotes', 'la barra del titolo mostra la scheda attiva');
  const width = () => page.evaluate(() => [window.outerWidth, screen.availWidth]);
  const [w0] = await width();
  await page.getByRole('button', { name: 'Ingrandisci' }).click();
  await page.waitForTimeout(600);
  const [w1, avail] = await width();
  assert(w1 >= avail - 2 && (await page.getByRole('button', { name: 'Ripristina' }).count()) === 1, `Ingrandisci occupa lo schermo (${w0} → ${w1} di ${avail})`);
  await page.getByRole('button', { name: 'Ripristina' }).click();
  await page.waitForTimeout(600);
  assert((await width())[0] === w0, 'Ripristina torna alla larghezza di prima');

  const env = { ...process.env, QUICKNOTES_DIR: notes, QUICKNOTES_CONFIG_DIR: process.env.QN_CFG ?? join(work, 'cfg') };
  const reopen = () => new Promise((done) => spawn(resolve('target/release/quicknotes.exe'), [], { env, stdio: 'ignore' }).on('exit', done));
  await page.getByRole('button', { name: 'Riduci a icona' }).click();
  await page.waitForTimeout(600);
  // Windows porta le finestre ridotte a icona fuori dallo schermo, verso -32000.
  const minimized = () => page.evaluate(() => window.screenX < -10000);
  assert(await minimized(), 'Riduci a icona riduce la finestra');
  await reopen();
  await page.waitForTimeout(600);
  assert(!(await minimized()) && (await page.evaluate(() => document.visibilityState)) === 'visible', 'una seconda istanza la riporta in primo piano');
  // Lo chiede a Windows: la pagina non si accorge di essere nascosta. Con la finestra nascosta, la finestra
  // principale del processo diventa quella interna del plugin di istanza singola.
  const shown = () => execSync('powershell -NoProfile -Command "(Get-Process quicknotes).MainWindowTitle"', { encoding: 'utf8' }).split(/\r?\n/).includes('QuickNotes');
  assert(shown(), 'prima di chiudere la finestra è visibile');
  await page.getByRole('button', { name: 'Chiudi', exact: true }).click();
  await page.waitForTimeout(600);
  assert(!shown(), 'Chiudi nasconde la finestra, come la X di sistema');
  await reopen();
  await page.waitForTimeout(600);
  assert(shown() && (await h1(page)) === 'Requisiti e architettura', 'e riaprendola il lavoro è dove era');
}
