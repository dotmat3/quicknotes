// Prova la migrazione dall'interfaccia, sulle note di scripts/demo-migrazione.mjs: proposta, scelte, conferma,
// copia della cartella e file cambiati solo dove scelto.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, basename } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page, { notes }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const day = (n) => new Date(now.getFullYear(), now.getMonth(), now.getDate() + n);
  const iso = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  const dailyPath = (n) => join(notes, String(day(n).getFullYear()), p(day(n).getMonth() + 1), `${iso(day(n))}-giornata.md`);
  const read = (path) => readFileSync(path, 'utf8');
  const before6 = read(dailyPath(-6));

  await page.waitForSelector('.cm-content');
  // La vista si apre da Ctrl K.
  await page.keyboard.press('Control+k');
  await page.keyboard.type('Migra le note');
  await page.waitForTimeout(400);
  await page.keyboard.press('Enter');
  await page.waitForSelector('article .proj');
  await page.waitForTimeout(400);

  const titles = await page.locator('article .proj input.title').evaluateAll((els) => els.map((e) => e.value));
  const row = (title) => page.locator('article .proj').nth(titles.indexOf(title));
  assert(titles.includes('LLM Training') && titles.includes('MBDA') && titles.includes('ekm'), `progetti proposti: ${titles.join(', ')}`);
  assert(!titles.includes('Varie'), '# Varie non è un progetto');
  assert(await row('LLM Training').locator('input[type=checkbox]').isChecked(), 'LLM Training parte scelto');
  assert(!(await row('MBDA').locator('input[type=checkbox]').isChecked()), 'MBDA (una sola nota) va scelto a mano');
  assert((await row('ekm').locator('select').inputValue()) === 'pausa', 'ekm, fermo da 40 giorni, si propone in pausa');

  await row('MBDA').locator('input[type=checkbox]').check();
  await row('ekm').locator('input.title').fill('EKM');
  await page.locator('.rule', { hasText: 'Etichette ripetute' }).locator('.rule-head input').check();
  await page.waitForTimeout(200);
  const summary = await page.locator('.sum2').innerText();
  assert(summary.startsWith('3 progetti'), `riepilogo: ${summary}`);
  assert(read(dailyPath(-6)) === before6, 'prima di Applica nessun file cambia');

  await page.getByRole('button', { name: 'Applica', exact: true }).click();
  await page.getByRole('alertdialog').getByRole('button', { name: 'Applica' }).click();
  await page.waitForSelector('.done', { timeout: 15000 });
  await page.waitForTimeout(800);
  assert((await page.locator('.done').innerText()).includes('3 progetti creati'), 'la pagina dice cosa è stato fatto');

  const after6 = read(dailyPath(-6));
  assert(after6.includes(`- [-] Rilanciare dedup fineweb_edu done:${iso(day(-5))}`), 'il task «Deprecato» diventa [-]');
  assert(after6.includes('- [?] Serve rifare i filtri? #filter'), 'la domanda diventa [?]');
  assert(after6.includes('- [ ] Lanciare dedup e filtri #dedup\n') && after6.includes('- Lanciato il job dedup\n'), 'l’etichetta ripetuta sotto # LLM Training sparisce');
  assert(after6.includes('- [ ] Comprare il toner\n'), 'le righe non scelte restano');
  const hub = read(join(notes, 'progetti', 'llm-training.md'));
  assert(hub.includes('type: project') && /areas:\n- (dedup|filter)\n- (dedup|filter)\n/.test(hub), 'la nota di progetto nasce con le aree');
  const ekm = read(join(notes, 'progetti', 'ekm.md'));
  assert(ekm.includes('title: EKM') && ekm.includes('status: pausa') && ekm.includes('- ekm'), 'il titolo cambiato resta, con il nome trovato come alias');
  assert(existsSync(join(notes, 'progetti', 'mbda.md')), 'anche MBDA, scelto a mano');
  const copies = readdirSync(dirname(notes)).filter((n) => n.startsWith(`${basename(notes)}-copia-`));
  assert(copies.length === 1 && read(join(dirname(notes), copies[0], ...dailyPath(-6).slice(notes.length + 1).split(/[\\/]/))) === before6, 'prima di scrivere si è copiata la cartella');

  assert((await page.locator('aside .proj-row', { hasText: 'LLM Training' }).count()) === 1, 'la barra laterale mostra i progetti nuovi');
  assert((await page.locator('article .proj').count()) === 0, 'dopo la migrazione non resta nulla da proporre');
  await page.getByRole('button', { name: 'Agenda' }).last().click();
  await page.waitForSelector('.sec');
  assert((await page.locator('.act', { hasText: 'Serve rifare i filtri' }).getByRole('checkbox', { name: /· Domanda$/ }).count()) === 1, 'in Agenda la domanda ha il suo stato');
}
