// Prova nell'app vera: rinominare ed eliminare una nota. Va usata con le note di demo-note.mjs.
// Uso: node scripts/demo-note.mjs <cartella> && node scripts/cdp.mjs <cartella> <foto.png> scripts/prova-rinomina.mjs
// La nota eliminata finisce nel Cestino di Windows.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

// Tutti i file .md della cartella, con il percorso relativo.
function files(root, prefix = '') {
  return readdirSync(join(root, prefix), { withFileTypes: true }).flatMap((e) =>
    e.name.startsWith('.') ? [] : e.isDirectory() ? files(root, `${prefix}${e.name}/`) : e.name.endsWith('.md') ? [`${prefix}${e.name}`] : [],
  );
}

const h1 = (page) => page.locator('article h1').first().innerText();
const tabs = (page) => page.locator('.tab-main .clip').allInnerTexts();

export default async function (page, { notes }) {
  await page.waitForSelector('.cm-content');
  const daily = files(notes).find((f) => f.endsWith('-giornata.md'));

  // Si apre la riunione citata dalla nota di oggi e la si mette tra i preferiti.
  await page.locator('.pills .pill', { hasText: /collegament/ }).click();
  await page.getByRole('dialog', { name: 'Note collegate' }).getByRole('button', { name: /Riunione budget Q4/ }).click();
  await page.waitForFunction(() => document.querySelector('article h1')?.innerText === 'Riunione budget Q4');
  await page.getByRole('button', { name: 'Aggiungi ai preferiti' }).click();

  // La nota del giorno non si rinomina e quella di oggi non si elimina: il menu ⋯ non lo propone.
  await page.locator('.tab-main', { hasText: 'Oggi ·' }).click();
  await page.getByRole('button', { name: 'Altre opzioni' }).click();
  const dailyMenu = await page.getByRole('menu').innerText();
  assert(!dailyMenu.includes('Rinomina') && !dailyMenu.includes('Elimina'), 'la nota di oggi non si rinomina e non si elimina');
  await page.keyboard.press('Escape');
  await page.keyboard.press('F2');
  assert((await page.locator('.title-edit').count()) === 0, 'F2 sulla nota di oggi non fa nulla');

  // Doppio clic sul titolo e Esc: non cambia nulla.
  await page.locator('.tab-main', { hasText: 'Riunione budget Q4' }).click();
  await page.locator('article h1').dblclick();
  await page.locator('.title-edit').fill('Da non salvare');
  await page.keyboard.press('Escape');
  assert((await h1(page)) === 'Riunione budget Q4' && files(notes).some((f) => f.endsWith('/riunione-budget-q4.md')), 'Esc annulla la rinomina');

  // F2, nuovo titolo, Invio: cambiano titolo, scheda, file e il link nella nota di oggi.
  await page.locator('.cm-content').click();
  await page.keyboard.press('F2');
  const input = page.locator('.title-edit');
  assert((await input.inputValue()) === 'Riunione budget Q4', 'F2 apre il titolo da modificare');
  await input.fill('Budget Q4 con Giulia');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => document.querySelector('article h1')?.innerText === 'Budget Q4 con Giulia');
  await page.waitForTimeout(400);
  const all = files(notes);
  assert(all.some((f) => f.endsWith('/budget-q4-con-giulia.md')) && !all.some((f) => f.endsWith('/riunione-budget-q4.md')), 'il file prende il nuovo nome');
  assert((await tabs(page)).includes('Budget Q4 con Giulia'), 'la scheda mostra il nuovo titolo');
  assert((await page.locator('.crumb').innerText()).endsWith('budget-q4-con-giulia.md'), 'il percorso in alto è quello nuovo');
  assert(readFileSync(join(notes, daily), 'utf8').includes('[[budget-q4-con-giulia|Budget Q4 con Giulia]]'), 'il link nella nota di oggi è aggiornato sul disco');
  assert((await page.locator('.toast').innerText()).includes('Link aggiornati in una nota'), 'un avviso dice quante note sono cambiate');
  assert((await page.getByRole('button', { name: 'Togli dai preferiti' }).count()) === 1, 'resta tra i preferiti');
  await page.locator('.tab-main', { hasText: 'Oggi ·' }).click();
  await page.waitForFunction(() => document.querySelector('.cm-content')?.innerText.includes('Budget Q4 con Giulia'));
  assert(true, "la nota di oggi aperta nell'editor mostra il link nuovo");
  await page.locator('.pills .pill', { hasText: /collegament/ }).click();
  await page.getByRole('dialog', { name: 'Note collegate' }).getByRole('button', { name: /Budget Q4 con Giulia/ }).click();
  await page.waitForFunction(() => document.querySelector('article h1')?.innerText === 'Budget Q4 con Giulia');
  assert(true, 'il collegamento porta alla nota rinominata');

  // Rinomina dal menu ⋯ e conferma con un clic fuori.
  await page.getByRole('button', { name: 'Altre opzioni' }).click();
  await page.getByRole('menuitem', { name: /Rinomina/ }).click();
  await page.locator('.title-edit').fill('Budget Q4');
  await page.locator('.crumb').click();
  await page.waitForFunction(() => document.querySelector('article h1')?.innerText === 'Budget Q4');
  assert(files(notes).some((f) => f.endsWith('/budget-q4.md')), 'dal menu ⋯, con un clic fuori');

  // Elimina: chiede conferma; Annulla lascia la nota, Elimina la toglie da schede e preferiti.
  await page.getByRole('button', { name: 'Altre opzioni' }).click();
  await page.getByRole('menuitem', { name: 'Elimina la nota…' }).click();
  const dialog = page.getByRole('alertdialog');
  assert((await dialog.innerText()).includes('Eliminare «Budget Q4»?') && (await dialog.innerText()).includes('Una nota la cita'), 'la conferma dice chi cita la nota');
  await dialog.getByRole('button', { name: 'Annulla' }).click();
  assert(files(notes).some((f) => f.endsWith('/budget-q4.md')), 'Annulla non elimina');
  await page.locator('.tab-main', { hasText: 'Budget Q4' }).click({ button: 'right' });
  await page.getByRole('menuitem', { name: 'Elimina la nota…' }).click();
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => ![...document.querySelectorAll('.tab-main .clip')].some((t) => t.innerText === 'Budget Q4'));
  assert(!files(notes).some((f) => f.endsWith('/budget-q4.md')), 'il file non è più nella cartella delle note');
  assert(!existsSync(join(notes, '.quicknotes', 'cestino')), 'è andato nel Cestino di Windows, non nella cartella di riserva');
  assert((await page.locator('.toast').innerText()).includes('è nel Cestino'), "un avviso dice dov'è finita");
  assert(!(await page.locator('.sidebar, aside').first().innerText()).includes('Budget Q4'), 'non è più tra i preferiti');
  await page.keyboard.press('Control+Shift+T');
  await page.waitForTimeout(300);
  assert(!(await tabs(page)).includes('Budget Q4'), 'Riapri scheda chiusa non la riporta');
}
