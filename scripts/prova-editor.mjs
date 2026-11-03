// Prova l'editor nell'app vera: scrittura, salvataggio, spunta con done:, modifica esterna, divisione.
import { appendFileSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page, { notes }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const iso = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
  const file = join(notes, String(now.getFullYear()), p(now.getMonth() + 1), `${iso}-giornata.md`);

  await page.waitForSelector('.cm-content');
  const editor = page.locator('.cm-content').first();
  await editor.click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('- [ ] Chiamare @Marco per la cucina #casa due:2030-01-02\n', { delay: 2 });
  await page.keyboard.press('Shift+Home');
  await page.keyboard.press('Delete');
  await page.keyboard.type('Testo finale con @Giulia');
  await page.waitForTimeout(900);
  let text = readFileSync(file, 'utf8');
  assert(text.includes('- [ ] Chiamare @Marco per la cucina #casa due:2030-01-02'), 'il testo scritto arriva nel file');
  assert(text.startsWith('---\n'), 'il frontmatter resta');

  await page.locator('.cm-task-box').first().click();
  await page.waitForTimeout(800);
  text = readFileSync(file, 'utf8');
  assert(text.includes(`- [x] Chiamare @Marco per la cucina #casa due:2030-01-02 done:${iso}`), 'la spunta scrive [x] e done:');
  assert((await page.locator('.pill', { hasText: 'di 1 azioni' }).count()) === 1, 'l\'intestazione conta le azioni');

  await page.keyboard.press('Control+z');
  await page.waitForTimeout(800);
  assert(!readFileSync(file, 'utf8').includes('done:'), 'annulla toglie anche done:');

  appendFileSync(file, 'Riga scritta fuori dall\'app\n');
  await page.waitForTimeout(1200);
  assert((await editor.innerText()).includes('Riga scritta fuori dall\'app'), 'una modifica esterna compare nell\'editor');

  await page.keyboard.press('Control+Alt+\\');
  await page.waitForTimeout(600);
  assert((await page.locator('main.pane').count()) === 2, 'Ctrl Alt \\ divide in due gruppi');
  assert((await page.locator('.cm-content').count()) === 2, 'la stessa nota è aperta in entrambi');
  const second = page.locator('.cm-content').nth(1);
  await second.click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type(' sincronizzata');
  await page.waitForTimeout(200);
  assert((await page.locator('.cm-content').nth(0).innerText()).includes('sincronizzata'), 'scrivere in un gruppo aggiorna l\'altro subito');
  await page.waitForTimeout(800);
  assert(readFileSync(file, 'utf8').includes('sincronizzata'), 'anche il testo sincronizzato viene salvato');

  await page.keyboard.press('Control+z');
  await page.waitForTimeout(800);
  assert(!(await page.locator('.cm-content').nth(0).innerText()).includes('sincronizzata'), 'annulla si propaga all\'altra vista');

  // Tornando su una scheda già aperta, quello che si scrive deve continuare a salvarsi.
  await page.keyboard.press('Control+\\');
  await page.keyboard.press('Control+\\');
  await page.getByRole('button', { name: 'Calendario' }).first().click();
  await page.waitForSelector('.grid');
  await page.getByRole('tab', { name: /Oggi/ }).last().click();
  await page.waitForTimeout(300);
  await page.locator('.cm-content').last().click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type(' dopo il ritorno');
  await page.waitForTimeout(800);
  assert(readFileSync(file, 'utf8').includes('dopo il ritorno'), 'tornando su una scheda il testo continua a salvarsi');

  // Il mouse sulla striscia compressa apre il pannello.
  await page.keyboard.press('Control+\\');
  await page.waitForTimeout(150);
  await page.locator('nav .btn[aria-label="Azioni"]').hover();
  await page.waitForTimeout(150);
  assert((await page.locator('.fly .item').count()) === 3, 'sulla striscia il pannello di Azioni ha tre voci');
  await page.mouse.move(800, 500);
  await page.waitForTimeout(100);
  assert((await page.locator('.fly').count()) === 0, 'il pannello si chiude uscendo');
  await page.keyboard.press('Control+\\');

  writeFileSync(`${notes}/.ultimo.txt`, readdirSync(join(notes, String(now.getFullYear()))).join(','));
}
