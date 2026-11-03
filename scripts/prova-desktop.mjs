// Prova nota rapida e salvataggio alla chiusura, guidando le pagine via CDP.
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
  await page.waitForTimeout(2200);

  // La finestra della nota rapida è stata creata in sottofondo.
  const pages = page.context().pages();
  const capture = pages.find((x) => x.url().includes('#capture'));
  assert(!!capture, 'la nota rapida è già pronta, nascosta');
  await capture.locator('textarea').fill('- [ ] Dalla nota rapida @Marco #casa due:2030-05-01');
  await capture.waitForTimeout(80);
  const chips = await capture.locator('.chip').allInnerTexts();
  assert(chips.some((c) => c.includes('azione')) && chips.includes('@Marco') && chips.includes('#casa'), `riconosce azione, persona ed etichetta: ${chips.join(', ')}`);
  await capture.screenshot({ path: process.env.QN_FOTO ? join(process.env.QN_FOTO, 'cattura.png') : undefined });
  await capture.keyboard.press('Control+Enter');
  await page.waitForTimeout(700);
  assert(readFileSync(daily, 'utf8').includes('## Priorità\n- [ ] Dalla nota rapida @Marco #casa due:2030-05-01'), 'il testo va nella nota del giorno, sezione Priorità');
  assert((await page.locator('.cm-content').innerText()).includes('Dalla nota rapida'), 'la nota aperta nell\'editor si aggiorna');

  // Un salvataggio in sospeso viene scritto appena la finestra si nasconde.
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('scritto prima di chiudere');
  await page.evaluate(() => {
    window.__TAURI_INTERNALS__.invoke('plugin:event|emit', { event: 'flush', payload: null });
  });
  await page.waitForTimeout(250);
  assert(readFileSync(daily, 'utf8').includes('scritto prima di chiudere'), 'l\'evento di chiusura salva subito, senza aspettare il ritardo');
}
