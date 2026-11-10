// Prova Agenda, Progetto, Revisione e i nuovi stati nell'app vera, sulle note di scripts/demo-progetti.mjs.
// Ogni modifica deve ritrovarsi corretta nei file.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

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
  const hub = join(notes, 'progetti', 'llm-training.md');
  const nav = (name) => page.locator('nav[aria-label="Sezioni"] button', { hasText: name }).first();
  const settle = () => page.waitForTimeout(700);

  await page.waitForSelector('.cm-content');

  // ---- Agenda
  await nav('Agenda').click();
  await page.waitForSelector('.sec');
  await settle();
  const titles = await page.locator('.sec-title').allInnerTexts();
  for (const t of ['Oggi', 'In corso', 'In attesa', 'Domande', 'Prossimi 7 giorni', 'Da smistare']) assert(titles.includes(t), `Agenda ha la sezione ${t}`);
  const agendaText = await page.locator('article').innerText();
  assert(!agendaText.includes('Task EKM fermo') && !agendaText.includes('Rivedere il parser'), 'EKM è in pausa: non compare in Agenda');
  const inbox = page.locator('section.sec[aria-label="Da smistare"]');
  assert((await inbox.locator('.act', { hasText: 'Lanciare dedup e filtri' }).count()) === 2, 'i task del daily di 6 giorni fa sono da smistare');
  assert((await page.locator('section.sec[aria-label="Oggi"] .act', { hasText: 'Scrivere il report' }).count()) === 1, 'scheduled: di oggi va in Oggi');

  await inbox.locator('.act', { hasText: 'Comprare il toner' }).getByRole('button', { name: 'Domani' }).click();
  await settle();
  assert(read(dailyPath(-6)).includes(`- [ ] Comprare il toner scheduled:${iso(day(1))}\n`), 'Domani scrive scheduled: nel file');
  assert((await page.locator('section.sec[aria-label="Prossimi 7 giorni"] .act', { hasText: 'Comprare il toner' }).count()) === 1, 'e l’azione passa in Prossimi 7 giorni');

  await page.locator('section.sec[aria-label="Da smistare"] .act', { hasText: 'Lanciare dedup e filtri' }).first().getByRole('button', { name: 'Stato' }).click();
  await page.locator('.pop .opt', { hasText: 'In corso' }).click();
  await settle();
  assert(read(dailyPath(-6)).includes('- [/] Lanciare dedup e filtri\n'), 'lo stato In corso scrive [/]');

  const question = page.locator('.act', { hasText: 'Usare bf16' }).first();
  await question.getByRole('button', { name: 'Sposta nel progetto' }).click();
  await page.locator('.pop .opt', { hasText: 'LLM Training' }).click();
  await page.locator('.pop input').fill('eval');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1200);
  assert(read(hub).includes('### eval\n- [?] Usare bf16 per il training?\n'), 'Sposta nel progetto: l’azione va nella nota del progetto, sotto ### eval');
  assert(read(hub).includes('areas: [dedup, filter, eval]') || read(hub).includes('- eval'), 'l’area nuova entra nel frontmatter');
  assert(read(dailyPath(-6)).includes('- ↗ Usare bf16 per il training? → [[llm-training|LLM Training]]'), 'nel daily resta il rimando');

  // ---- Barra laterale e Progetto
  const side = page.locator('aside[aria-label="Navigazione"]');
  assert((await side.locator('.proj-row', { hasText: 'LLM Training' }).count()) === 1, 'la barra laterale elenca i progetti attivi');
  await side.getByRole('button', { name: /In pausa o chiusi/ }).click();
  assert((await side.locator('.area-row', { hasText: 'EKM' }).count()) === 1, 'EKM è tra i progetti in pausa');
  await side.locator('.proj-row', { hasText: 'LLM Training' }).click();
  await page.waitForSelector('h1:has-text("LLM Training")');
  await settle();
  const heads = await page.locator('article h2').allInnerTexts();
  assert(['dedup', 'filter', 'Domande'].every((a) => heads.some((h) => h.startsWith(a))), `il progetto è diviso per area, con le domande a parte: ${heads.join(' | ')}`);
  assert((await page.locator('.rows .act', { hasText: 'Usare bf16' }).count()) === 1, 'la domanda spostata compare nel progetto');
  assert(heads.some((h) => h.startsWith('Log dei daily')), 'c’è il log dei daily');
  assert((await page.locator('article', { hasText: 'Lanciato il job dedup' }).count()) === 1, 'il log mostra le righe del daily');
  await page.getByRole('button', { name: /Archivia fatte/ }).click();
  await page.waitForTimeout(1000);
  const archive = join(notes, 'progetti', 'llm-training.archivio.md');
  assert(existsSync(archive) && read(archive).includes('- [x] Filtro lingua'), 'Archivia fatte sposta le chiuse nell’archivio');
  assert(!read(hub).includes('Filtro lingua'), 'e le toglie dalla nota del progetto');

  // ---- Revisione
  await nav('Revisione').click();
  await page.waitForSelector('.step');
  await settle();
  await page.locator('.step-head', { hasText: 'Madri con tutte le figlie chiuse' }).click();
  const mother = page.locator('.step', { hasText: 'Madri con tutte le figlie chiuse' }).locator('.act', { hasText: 'Rilanciare finepdfs' });
  assert((await mother.count()) === 1, 'Rilanciare finepdfs è tra le madri da chiudere');
  await mother.getByRole('button', { name: 'Chiudi', exact: true }).click();
  await settle();
  assert(read(dailyPath(-1)).includes(`- [x] Rilanciare finepdfs done:${iso(day(0))}`), 'Chiudi la segna come fatta');
  await page.locator('.step-head', { hasText: 'Possibili duplicati' }).click();
  assert((await page.locator('.step', { hasText: 'Possibili duplicati' }).locator('.act', { hasText: 'Lanciare dedup e filtri' }).count()) === 2, 'Lanciare dedup e filtri è tra i duplicati');
  await page.locator('.step-head', { hasText: 'Progetti in pausa' }).click();
  assert((await page.locator('.step', { hasText: 'Progetti in pausa' }).locator('.proj', { hasText: 'EKM' }).count()) === 1, 'EKM è tra i progetti in pausa con task aperti');
  assert((await nav('Revisione').locator('.dot').count()) === 1, 'prima della revisione la barra laterale la ricorda');
  await page.getByRole('button', { name: 'Fine revisione' }).click();
  await page.waitForTimeout(1200);
  assert((await nav('Revisione').locator('.dot').count()) === 0, 'dopo Fine revisione l’avviso sparisce');
  assert((await page.locator('.cm-content', { hasText: 'Annullate: 1' }).count()) >= 1, 'si apre la nota della revisione con il riepilogo');

  // ---- Editor: i segni degli stati e il menu
  await nav('Oggi').click();
  await page.waitForTimeout(800);
  const editor = page.locator('.cm-content').last();
  assert((await editor.locator('.cm-task-box.st-cancelled').count()) === 1, 'l’editor disegna [-] come annullata');
  await editor.locator('.cm-line', { hasText: 'Scrivere il report' }).locator('.cm-task-box').click({ button: 'right' });
  await page.locator('.cm-status-menu').waitFor();
  await page.locator('.cm-status-item', { hasText: 'In attesa' }).click();
  await page.waitForTimeout(1500);
  assert(read(dailyPath(0)).includes('- [w] Scrivere il report'), 'tasto destro sulla casella: lo stato scelto va nel file');
  assert((await editor.locator('.cm-task-box.st-waiting').count()) === 1, 'e la casella mostra In attesa');

  // ---- Azioni: raggruppamento per stato e filtro per progetto
  await nav('Azioni').click();
  await page.waitForSelector('.column');
  assert((await page.locator('button[role=radio][aria-checked=true]', { hasText: 'Progetto' }).count()) === 1, 'Azioni parte raggruppata per progetto');
  await page.locator('button[role=radio]', { hasText: 'Stato' }).click();
  await settle();
  const cols = await page.locator('.col-title').allInnerTexts();
  assert(['Da fare', 'In corso', 'In attesa', 'Domande'].every((c) => cols.includes(c)), `colonne per stato: ${cols.join(', ')}`);
  await page.getByRole('button', { name: /^Filtri/ }).click();
  await page.locator('.fpanel .fsec', { hasText: 'Progetto' }).locator('.fchip', { hasText: 'LLM Training' }).click();
  await settle();
  const cards = await page.locator('.column .act .text').allInnerTexts();
  assert(cards.length > 0 && cards.every((t) => !t.includes('toner') && !t.includes('Laura')), 'il filtro per progetto lascia solo le sue azioni');
  assert((await page.locator('.column .act', { hasText: 'Rilanciare dedup fineweb_edu' }).count()) === 0, 'le annullate senza progetto restano fuori');

  // ---- Aggiunta rapida: con un progetto tra i filtri l'azione va nella sua nota; #progetto/area si completa.
  await page.getByRole('button', { name: /^Nuova azione/ }).click();
  const qa = page.getByRole('dialog', { name: 'Nuova azione' });
  assert((await qa.locator('.foot').innerText()).includes('Finisce in LLM Training'), 'il progetto filtrato è il posto di partenza');
  await page.keyboard.type('Valutare MinHash');
  await page.keyboard.press('Enter');
  await settle();
  assert(/## Prossime azioni\n- \[ \] Valutare MinHash\n/.test(read(hub)), 'senza area va in testa a Prossime azioni del progetto');
  await page.keyboard.type('Provare la soglia 0.8 #llm');
  await qa.locator('.sugg [role=option]', { hasText: '#llm-training' }).first().waitFor();
  await page.keyboard.press('Tab');
  await page.keyboard.type('ded');
  await page.keyboard.press('Tab');
  const typed = await qa.getByRole('combobox', { name: 'Testo della nuova azione' }).inputValue();
  assert(typed === 'Provare la soglia 0.8 #llm-training/dedup ', `i suggerimenti completano progetto e area (${typed})`);
  assert((await qa.locator('.foot').innerText()).includes('LLM Training › dedup'), 'il piede mostra progetto e area');
  await page.keyboard.press('Shift+Enter');
  await settle();
  assert(/### dedup\n(?:.*\n)*?- \[ \] Provare la soglia 0\.8\n/.test(read(hub)) && !read(hub).includes('0.8 #llm'), 'va sotto ### dedup, senza l\'etichetta del progetto');
  assert((await qa.count()) === 0, 'Maiusc Invio aggiunge e chiude');
  assert(!read(dailyPath(0)).includes('Valutare MinHash') && !read(dailyPath(0)).includes('soglia 0.8'), 'niente nella nota di oggi');

  await page.getByRole('button', { name: 'Togli i filtri' }).click();
  await page.getByRole('button', { name: /^Filtri/ }).click();
  await page.locator('button[role=radio]', { hasText: 'Scadenza' }).click();

  // ---- Da Agenda ad Azioni: ogni sezione apre Azioni con il suo filtro, e il progetto scelto resta.
  await nav('Agenda').click();
  await page.waitForSelector('.sec');
  await settle();
  const inAgenda = Number(await page.locator('.sec[aria-label="In attesa"] .sec-head .n2').innerText());
  await page.getByRole('button', { name: 'In attesa: tutte in Azioni' }).click();
  await page.waitForSelector('.columns');
  await settle();
  const chips = await page.locator('.active .achip').allInnerTexts();
  assert(chips.length === 1 && chips[0].includes('In attesa'), `il filtro della sezione arriva in Azioni (${chips.join(' | ')})`);
  const waitingCards = await page.locator('.columns .act').count();
  assert(waitingCards >= inAgenda && inAgenda > 0, `Azioni le mostra tutte: ${waitingCards}, Agenda ${inAgenda}`);
  await nav('Agenda').click();
  await page.waitForSelector('.sec');
  await page.locator('.chips .chip', { hasText: 'LLM Training' }).click();
  await settle();
  await page.getByRole('button', { name: /^Prossimi 7 giorni: tutte in Azioni|^Oggi: tutte in Azioni|^Da smistare: tutte in Azioni/ }).first().click();
  await page.waitForSelector('.columns');
  await settle();
  const chips2 = await page.locator('.active .achip').allInnerTexts();
  assert(chips2.some((c) => c.includes('LLM Training')), `con un progetto scelto in Agenda il filtro lo porta con sé (${chips2.join(' | ')})`);
  await page.getByRole('button', { name: 'Togli i filtri' }).click();
}
