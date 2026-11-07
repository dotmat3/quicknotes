// Prova nell'app vera: la priorità delle azioni, dalla bacheca e dall'editor. Va usata con le note di demo-note.mjs.
// Uso: node scripts/demo-note.mjs <cartella> && node scripts/cdp.mjs <cartella> <foto.png> scripts/prova-priorita.mjs
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

function files(root, prefix = '') {
  return readdirSync(join(root, prefix), { withFileTypes: true }).flatMap((e) =>
    e.name.startsWith('.') ? [] : e.isDirectory() ? files(root, `${prefix}${e.name}/`) : e.name.endsWith('.md') ? [`${prefix}${e.name}`] : [],
  );
}

const until = async (fn, ms = 4000) => {
  for (const end = Date.now() + ms; Date.now() < end; await new Promise((r) => setTimeout(r, 80))) if (await fn()) return true;
  return false;
};

export default async function (page, { notes }) {
  await page.waitForSelector('.cm-content');
  const daily = join(notes, files(notes).find((f) => f.endsWith('-giornata.md')));
  const dailyText = () => readFileSync(daily, 'utf8');

  await page.getByRole('button', { name: 'Azioni', exact: false }).first().click();
  const late = page.getByRole('region', { name: 'In ritardo' });
  await late.locator('.act').first().waitFor();
  const lateTexts = () => late.locator('.act .text').allInnerTexts();
  assert((await lateTexts())[0].startsWith('Aggiornare con'), 'senza priorità vale la scadenza: prima la più vecchia');

  // + priorità → Alta: la riga nel file cambia e la scheda sale in cima alla colonna.
  const marco = late.locator('.act', { hasText: 'Richiamare @Marco' });
  await marco.hover();
  await marco.getByRole('button', { name: /Aggiungi una priorità/ }).click();
  const pop = page.getByRole('dialog', { name: 'Priorità' });
  assert((await pop.locator('.opt').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ').trim()).join(' | ') === '↑ Alta | → Media | ↓ Bassa | Nessuna', 'il popover propone alta, media, bassa e nessuna');
  await pop.getByRole('button', { name: /Alta/ }).click();
  assert(await until(() => dailyText().includes('- [ ] Richiamare @Marco per il preventivo della cucina #casa prio:alta due:')), 'nel file la priorità va prima della scadenza');
  await page.waitForFunction(() => document.querySelector('[aria-label="In ritardo"] .act .text')?.innerText.startsWith('Richiamare'));
  assert(true, 'con priorità alta passa in cima alla colonna, prima di una scadenza più vecchia');
  assert((await marco.getByRole('button', { name: /Priorità alta/ }).innerText()) === '↑ Alta', 'la pillola mostra la priorità');
  assert(!(await marco.locator('.text').innerText()).includes('prio:'), 'nel testo della scheda non compare prio:');

  // Raggruppata per priorità, il + di una colonna crea l'azione con quella priorità.
  await page.getByRole('radio', { name: 'Priorità' }).click();
  assert((await page.getByRole('region', { name: '↑ Alta' }).locator('.act .text').allInnerTexts()).some((t) => t.startsWith('Richiamare')), 'raggruppando per priorità la scheda sta nella colonna Alta');
  await page.getByRole('button', { name: 'Aggiungi a → Media' }).click();
  await page.getByRole('textbox', { name: 'Nuova azione in → Media' }).fill('Ordinare i toner');
  await page.keyboard.press('Enter');
  assert(await until(() => dailyText().includes('- [ ] Ordinare i toner prio:media')), 'il + della colonna Media scrive prio:media');
  await page.getByRole('region', { name: '→ Media' }).locator('.act', { hasText: 'Ordinare i toner' }).waitFor();
  assert(true, 'la nuova azione compare nella colonna Media');
  await page.keyboard.press('Escape');

  // Nessuna: la priorità sparisce dal file.
  const toner = page.getByRole('region', { name: '→ Media' }).locator('.act', { hasText: 'Ordinare i toner' });
  await toner.getByRole('button', { name: /Priorità media/ }).click();
  await page.getByRole('dialog', { name: 'Priorità' }).getByRole('button', { name: 'Nessuna' }).click();
  assert(await until(() => dailyText().includes('- [ ] Ordinare i toner\n')), 'Nessuna toglie prio: dal file');
  await page.getByRole('radio', { name: 'Scadenza' }).click();

  // Nell'editor: prio:alta diventa un'etichetta colorata e prio: propone i valori.
  await page.locator('.tab-main', { hasText: 'Oggi ·' }).click();
  await page.waitForSelector('.cm-prio.alta');
  assert((await page.locator('.cm-prio.alta').first().innerText()) === '↑ alta', "nell'editor prio:alta si vede come ↑ alta");
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\n- [ ] Provare la stampante prio:');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  const opts = await page.locator('.cm-tooltip-autocomplete li').allInnerTexts();
  assert(['↑ Alta', '→ Media', '↓ Bassa'].every((o) => opts.some((t) => t.includes(o))), 'prio: propone alta, media e bassa');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  assert(await until(() => dailyText().includes('- [ ] Provare la stampante prio:media')), 'il suggerimento scelto finisce nel file');
}
