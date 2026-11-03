// Prova ricerca e viste nell'app vera, con le note di scripts/demo-note.mjs. Salva foto in QN_FOTO.
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page) {
  const shot = async (name) => {
    if (process.env.QN_FOTO) await page.screenshot({ path: join(process.env.QN_FOTO, `${name}.png`) });
  };
  await page.waitForSelector('.cm-content');

  await page.keyboard.press('Control+k');
  await page.waitForSelector('.dialog input');
  assert((await page.locator('.dialog .row').count()) > 3, 'Ctrl K senza testo mostra note recenti e viste');
  await page.keyboard.type('preventiv');
  await page.waitForTimeout(150);
  assert((await page.locator('.dialog .row').allInnerTexts()).some((t) => t.includes('preventivo')), 'la ricerca trova il testo nelle note');
  await page.locator('.dialog input').fill('budget #lavoro-q4');
  await page.waitForTimeout(150);
  assert((await page.locator('.dialog .row').first().innerText()).includes('Riunione budget Q4'), 'parole e filtri insieme');
  await shot('ricerca');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  assert((await page.locator('h1', { hasText: 'Riunione budget Q4' }).count()) === 1, 'Invio apre la nota');
  assert((await page.locator('.cm-content').innerText()).includes('Decisioni'), 'la nota si apre nell\'editor');

  await page.keyboard.press('Control+k');
  await page.locator('.dialog input').fill('@gi');
  await page.waitForTimeout(150);
  await page.locator('.dialog .row', { hasText: '@Giulia' }).first().click();
  await page.waitForSelector('.stats');
  assert((await page.locator('h1', { hasText: '@Giulia' }).count()) === 1, 'si apre la pagina persona');
  await shot('persona');

  await page.keyboard.press('Control+k');
  await page.locator('.dialog input').fill('#lavoro');
  await page.waitForTimeout(150);
  await page.locator('.dialog .row', { hasText: '#lavoro-q4' }).first().click();
  await page.waitForSelector('button:has-text("Colore")');
  await page.locator('button:has-text("Colore")').click();
  await page.getByRole('radio', { name: 'Corallo' }).click();
  await page.waitForTimeout(100);
  const color = await page.locator('h1').first().evaluate((e) => getComputedStyle(e).color);
  assert(color === 'rgb(161, 45, 34)' || color === 'rgb(242, 139, 125)', `il colore dell'etichetta cambia (${color})`);
  await shot('etichetta');

  await page.getByRole('button', { name: 'Calendario', exact: false }).first().click();
  await page.waitForSelector('.grid');
  await page.waitForTimeout(250);
  assert((await page.locator('.chip').count()) > 0, 'il calendario mostra eventi veri');
  await shot('calendario');
  await page.getByRole('radio', { name: 'Settimana' }).click();
  await page.waitForTimeout(250);
  assert((await page.locator('.wrow').count()) === 7, 'la vista settimana ha sette righe');

  await page.getByRole('button', { name: 'Persone', exact: false }).first().click();
  await page.waitForTimeout(250);
  assert((await page.locator('.row', { hasText: '@Marco' }).count()) === 1, 'l\'elenco persone contiene @Marco');

  await page.getByRole('button', { name: 'Grafo', exact: false }).first().click();
  await page.waitForSelector('.canvas');
  await page.waitForTimeout(250);
  assert((await page.locator('.sr button').count()) > 3, 'il grafo mostra note, persone ed etichette');
  await shot('grafo');

  await page.keyboard.press('Control+,');
  await page.waitForSelector('.themes');
  await page.getByRole('radio', { name: /Grafite/ }).click();
  await page.waitForTimeout(100);
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  assert(bg === 'rgb(23, 24, 27)', 'il tema Grafite si applica subito');
  await shot('impostazioni-grafite');
  for (const t of ['Navigazione', 'Azioni', 'Etichette', 'Claude']) {
    await page.getByRole('tablist', { name: 'Categorie' }).getByRole('tab', { name: t }).click();
    await page.waitForTimeout(120);
  }
  assert((await page.locator('pre').count()) === 2, 'la scheda Claude mostra la configurazione da copiare');

  await page.getByRole('tab', { name: /Oggi/ }).click();
  await page.waitForSelector('.cm-content');
  await page.waitForTimeout(200);
  await shot('oggi-grafite');
  await page.getByRole('button', { name: 'Azioni', exact: false }).first().click();
  await page.waitForSelector('.columns');
  await page.waitForTimeout(300);
  await shot('azioni-grafite');
}
