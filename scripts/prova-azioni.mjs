// Prova la vista Azioni nell'app vera: ogni modifica deve ritrovarsi corretta nel file.
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
  const dir = join(notes, String(now.getFullYear()), p(now.getMonth() + 1));
  const daily = join(dir, `${iso}-giornata.md`);
  const read = () => readFileSync(daily, 'utf8');

  await page.waitForSelector('.cm-content');
  await page.getByRole('button', { name: 'Azioni', exact: false }).first().click();
  await page.waitForSelector('.column');
  await page.waitForTimeout(300);
  const titles = await page.locator('.col-title').allInnerTexts();
  assert(titles.includes('In ritardo') && titles.includes('Oggi e domani') && titles.includes('Senza scadenza'), `colonne presenti: ${titles.join(', ')}`);

  const card = page.locator('.act', { hasText: 'Richiamare' }).first();
  await card.getByRole('button', { name: /^Persona Marco/ }).click();
  await page.locator('.pop input').fill('Elena');
  await page.locator('.pop .opt', { hasText: '@Elena' }).click();
  await page.waitForTimeout(500);
  assert(read().includes('- [ ] Richiamare @Elena per il preventivo'), 'la persona si sostituisce dentro la frase');

  const moved = page.locator('.act', { hasText: 'Provare il modello' }).first();
  await moved.hover();
  await moved.getByRole('button', { name: /^Aggiungi una scadenza/ }).click();
  await page.locator('.pop .opt', { hasText: 'Domani' }).click();
  await page.waitForTimeout(500);
  assert(/Whisper sulle registrazioni lunghe #quicknotes due:\d{4}-\d{2}-\d{2}/.test(read()), 'la scadenza va nel file, dopo l\'etichetta');
  const soon = page.locator('.column[aria-label="Oggi e domani"]');
  assert((await soon.locator('.act', { hasText: 'Provare il modello' }).count()) === 1, 'la scheda passa nella colonna giusta');

  const withDesc = page.locator('.act', { hasText: 'Provare il modello' }).first();
  await withDesc.hover();
  await withDesc.getByRole('button', { name: /^Aggiungi una descrizione/ }).click();
  await page.locator('.pop textarea').fill('Usare la riunione del budget');
  await page.keyboard.press('Control+Enter');
  await page.waitForTimeout(500);
  assert(read().includes('\n    Usare la riunione del budget\n'), 'la descrizione è una riga rientrata');

  const mother = page.locator('.act', { hasText: 'Mandare a' }).first();
  assert((await mother.locator('.progress').innerText()).includes('1 di 3'), 'la madre mostra l\'avanzamento');
  await mother.getByRole('checkbox', { name: /^Mandare/ }).click();
  await page.waitForTimeout(150);
  assert((await mother.getByRole('alert').innerText()).includes('Restano 2 aperte'), 'chiudere una madre con figlie aperte chiede conferma');
  await mother.getByRole('button', { name: 'Completa tutte' }).click();
  await page.waitForTimeout(600);
  const text = read();
  assert(text.includes(`- [x] Mandare a @Giulia la bozza del budget Q4 #lavoro-q4`) && text.includes(`- [x] Confrontare con @Elena le voci del terzo trimestre done:${iso}`), 'Completa tutte chiude madre e figlie con una data');

  await page.locator('.new input').fill('Nuova azione di prova @Marco');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(500);
  assert(read().includes('## Priorità\n- [ ] Nuova azione di prova @Marco'), 'la nuova azione finisce nella nota di oggi, sezione Priorità');

  // L'editor della nota aperta riceve le modifiche fatte dalla bacheca.
  await page.getByRole('tab', { name: /Oggi/ }).click();
  await page.waitForSelector('.cm-content');
  await page.waitForTimeout(300);
  assert((await page.locator('.cm-content').innerText()).includes('Richiamare @Elena'), 'l\'editor mostra il testo cambiato dalla bacheca');
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('fine prova');
  await page.waitForTimeout(800);
  assert(read().endsWith('fine prova') && read().includes('Richiamare @Elena'), 'scrivendo dopo non si perde nulla');

  await page.getByRole('button', { name: 'Azioni', exact: false }).first().click();
  await page.waitForSelector('.columns');
  await page.waitForTimeout(400);
  await page.locator('button[role=radio]', { hasText: 'Elenco' }).click();
  await page.waitForTimeout(150);
  assert((await page.locator('.rows .act').count()) > 0, 'la vista Elenco mostra le azioni');
  await page.locator('button[role=radio]', { hasText: 'Bacheca' }).click();
}
