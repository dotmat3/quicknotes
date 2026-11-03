// Prova nell'app vera: note collegate dalla pillola, grafo completo e locale, titolo e finestra.
// Va usata con le note di demo-note.mjs.
import { spawn } from 'node:child_process';
import { join, resolve } from 'node:path';
import { Win } from './win.mjs';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

const h1 = (page) => page.locator('h1').first().innerText();

export default async function (page, { notes, work, pid }) {
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

  // Titolo della finestra: segue la scheda attiva.
  const win = new Win();
  const main = async () => (await win.windows(pid)).find((w) => w.title.endsWith('QuickNotes') && !w.title.includes('area di notifica'));
  const until = async (fn, ms = 4000) => {
    for (const end = Date.now() + ms; Date.now() < end; await new Promise((r) => setTimeout(r, 80))) if (await fn()) return true;
    return false;
  };
  try {
    assert(await until(async () => (await main())?.title === 'Requisiti e architettura — QuickNotes'), 'il titolo della finestra mostra la scheda attiva');

    const env = { ...process.env, QUICKNOTES_DIR: notes, QUICKNOTES_CONFIG_DIR: process.env.QN_CFG ?? join(work, 'cfg') };
    const python = resolve(process.env.QN_PYTHON ?? '.venv/Scripts/python.exe');
    const reopen = () => new Promise((done) => spawn(python, ['-m', 'quicknotes'], { env, stdio: 'ignore' }).on('exit', done));
    const WM_SYSCOMMAND = 0x0112;
    const SC_MINIMIZE = 0xf020;
    const WM_CLOSE = 0x0010;
    await win.post((await main()).hwnd, WM_SYSCOMMAND, SC_MINIMIZE, 0);
    assert(await until(async () => (await main())?.iconic), 'la finestra si riduce a icona');
    await reopen();
    assert(await until(async () => (await main())?.visible && !(await main()).iconic), 'una seconda istanza la riporta in primo piano');
    await win.post((await main()).hwnd, WM_CLOSE, 0, 0);
    assert(await until(async () => !(await main())?.visible), "la X nasconde la finestra nell'area di notifica");
    await reopen();
    assert(await until(async () => (await main())?.visible), 'riaprendo QuickNotes torna la finestra');
    assert((await h1(page)) === 'Requisiti e architettura', 'e il lavoro è dove era');
  } finally {
    win.close();
  }
}
