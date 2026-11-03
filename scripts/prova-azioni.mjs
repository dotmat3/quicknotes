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
  assert((await page.locator('.list-group[aria-label="In ritardo"] button', { hasText: 'Sposta a domani' }).count()) === 1, 'in Elenco il gruppo In ritardo ha Sposta a domani');
  await page.locator('button[role=radio]', { hasText: 'Bacheca' }).click();
  await page.waitForSelector('.columns');

  // Il "+" di una colonna dà la sua scadenza; raggruppando per progetto, la sua etichetta.
  await page.getByRole('button', { name: 'Aggiungi a Oggi e domani' }).click();
  await page.locator('.col-new').fill('Dalla colonna @Marco');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(600);
  assert(read().includes(`- [ ] Dalla colonna @Marco due:${iso}\n`), 'il + di Oggi e domani scrive la scadenza di oggi');
  assert((await page.locator('.column[aria-label="Oggi e domani"] .act', { hasText: 'Dalla colonna' }).count()) === 1, 'la nuova azione compare nella sua colonna');
  await page.keyboard.press('Escape');
  assert((await page.getByRole('button', { name: 'Aggiungi a In ritardo' }).count()) === 0, 'In ritardo non ha il +');
  await page.locator('button[role=radio]', { hasText: 'Progetto' }).click();
  await page.getByRole('button', { name: 'Aggiungi a #casa' }).click();
  await page.locator('.col-new').fill('Dal progetto');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(600);
  assert(read().includes('- [ ] Dal progetto #casa\n'), 'il + di un progetto scrive la sua etichetta');
  await page.keyboard.press('Escape');
  await page.locator('button[role=radio]', { hasText: 'Scadenza' }).click();

  // Sposta a domani: tutte le azioni in ritardo, anche in altre note.
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const isoTomorrow = `${tomorrow.getFullYear()}-${p(tomorrow.getMonth() + 1)}-${p(tomorrow.getDate())}`;
  const lateCol = page.locator('.column[aria-label="In ritardo"]');
  const nLate = await lateCol.locator('.act').count();
  await lateCol.getByRole('button', { name: 'Sposta a domani' }).click();
  await page.waitForTimeout(900);
  assert(nLate >= 2 && (await page.locator('.column[aria-label="In ritardo"] .act').count()) === 0, `Sposta a domani svuota In ritardo (${nLate} azioni)`);
  assert(read().includes(`- [ ] Richiamare @Elena per il preventivo della cucina #casa due:${isoTomorrow}`), 'nella nota del giorno la scadenza diventa domani');
  assert(readFileSync(join(dir, 'riunione-budget-q4.md'), 'utf8').includes(`#lavoro-q4 due:${isoTomorrow}`), 'anche nelle altre note');
  assert((await page.locator('.toast').innerText()).includes('spostate a domani'), 'un avviso dice quante azioni sono state spostate');

  // Pagina etichetta: spunta e pillole come in bacheca.
  await page.keyboard.press('Control+k');
  await page.locator('.dialog input').fill('#casa');
  await page.waitForTimeout(200);
  await page.locator('.dialog .row', { hasText: '#casa' }).first().click();
  await page.waitForSelector('button:has-text("Colore")');
  await page.waitForTimeout(300);
  const tagAct = page.locator('.act', { hasText: 'Dal progetto' });
  assert((await tagAct.count()) === 1, 'la pagina etichetta mostra le azioni come schede');
  await tagAct.hover();
  await tagAct.getByRole('button', { name: /^Aggiungi una scadenza/ }).click();
  await page.locator('.pop .opt', { hasText: 'Domani' }).click();
  await page.waitForTimeout(600);
  assert(read().includes(`- [ ] Dal progetto #casa due:${isoTomorrow}`), 'una pillola nella pagina etichetta scrive nel file');
  assert((await page.locator('.act', { hasText: 'Dal progetto' }).getByRole('button', { name: /^Scadenza domani/ }).count()) === 1, 'e la pagina si aggiorna');
  await page.locator('.act', { hasText: 'Dal progetto' }).getByRole('checkbox').click();
  await page.waitForTimeout(600);
  assert(read().includes(`- [x] Dal progetto #casa due:${isoTomorrow} done:${iso}`), 'la spunta nella pagina etichetta scrive done:');
  assert((await page.locator('.act', { hasText: 'Dal progetto' }).count()) === 0, 'l\'azione fatta esce dalle aperte');
}
