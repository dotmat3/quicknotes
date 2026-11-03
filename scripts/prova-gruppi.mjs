// Prova i gruppi nell'app vera: divisore, ingrandimento, menu delle schede, chiusura di un gruppo, Ctrl 1…6 e Ctrl W.
// Va usata con le note di demo-note.mjs.
const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page) {
  await page.waitForSelector('.cm-content');
  const groups = page.locator('main.pane');
  const tabsOf = (i) => groups.nth(i).locator('.tab .clip').allInnerTexts();
  const box = async (i) => (await groups.nth(i).boundingBox()) ?? { width: 0 };

  // Ctrl 1…6 apre Oggi e le viste nell'ordine della barra.
  await page.keyboard.press('Control+2');
  await page.waitForSelector('.grid');
  await page.keyboard.press('Control+4');
  await page.waitForTimeout(200);
  const opened = await tabsOf(0);
  assert(opened.slice(1).join(',') === 'Calendario,Persone', `Ctrl 2 e Ctrl 4 aprono Calendario e Persone: ${opened.join(', ')}`);
  await page.keyboard.press('Control+1');
  await page.waitForTimeout(150);
  assert((await groups.nth(0).locator('.tab.on .clip').innerText()).startsWith('Oggi'), 'Ctrl 1 torna alla nota di oggi');

  // Divisione e divisore.
  await page.getByRole('button', { name: 'Dividi a destra' }).first().click();
  await page.waitForTimeout(300);
  assert((await groups.count()) === 2, 'il pulsante Dividi a destra crea un secondo gruppo');
  const before = [(await box(0)).width, (await box(1)).width];
  const split = await page.locator('.split').boundingBox();
  const div = await page.locator('.divider').boundingBox();
  await page.mouse.move(div.x + div.width / 2, div.y + div.height / 2);
  await page.mouse.down();
  await page.mouse.move(split.x + split.width * 0.3, div.y + div.height / 2, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(150);
  const after = [(await box(0)).width, (await box(1)).width];
  const ratio = after[0] / (after[0] + after[1]);
  assert(Math.abs(before[0] - before[1]) < 4 && ratio > 0.25 && ratio < 0.35, `il divisore ridimensiona i gruppi (${Math.round(ratio * 100)}% a sinistra)`);
  await page.locator('.divider').dblclick();
  await page.waitForTimeout(150);
  assert(Math.abs((await box(0)).width - (await box(1)).width) < 4, 'il doppio clic sul divisore pareggia i gruppi');

  // Ingrandimento.
  await groups.nth(1).getByRole('button', { name: 'Ingrandisci questo gruppo' }).click();
  await page.waitForTimeout(150);
  assert(!(await groups.nth(0).isVisible()) && (await box(1)).width > split.width * 0.95, 'Ingrandisci nasconde l\'altro gruppo');
  assert((await page.locator('.divider').count()) === 0, 'da ingrandito il divisore sparisce');
  await groups.nth(1).getByRole('button', { name: 'Ripristina i gruppi' }).click();
  await page.waitForTimeout(150);
  assert((await groups.nth(0).isVisible()) && (await page.locator('.divider').count()) === 1, 'Ripristina torna ai due gruppi');

  // Menu contestuale delle schede, nel primo gruppo.
  await groups.nth(0).locator('.tab', { hasText: 'Calendario' }).click({ button: 'right' });
  const menu = page.getByRole('menu', { name: /Calendario/ });
  assert((await menu.getByRole('menuitem').count()) === 9, 'il clic destro su una scheda apre il suo menu');
  await menu.getByRole('menuitem', { name: 'Chiudi quelle a destra' }).click();
  await page.waitForTimeout(150);
  assert(!(await tabsOf(0)).includes('Persone'), `Chiudi quelle a destra: ${(await tabsOf(0)).join(', ')}`);
  await groups.nth(0).locator('.tab', { hasText: 'Calendario' }).click({ button: 'right' });
  await page.getByRole('menuitem', { name: 'Sposta nel gruppo accanto' }).click();
  await page.waitForTimeout(150);
  assert((await tabsOf(1)).includes('Calendario') && !(await tabsOf(0)).includes('Calendario'), 'Sposta nel gruppo accanto');
  await groups.nth(0).locator('.tab').first().click({ button: 'right' });
  await page.getByRole('menuitem', { name: 'Riapri scheda chiusa' }).click();
  await page.waitForTimeout(150);
  assert((await page.locator('.tab', { hasText: 'Persone' }).count()) === 1, 'Riapri scheda chiusa dal menu');
  await groups.nth(0).locator('.tab').first().click({ button: 'right' });
  await page.keyboard.press('Escape').catch(() => {});
  await page.locator('.backdrop').click().catch(() => {});
  await page.waitForTimeout(100);
  assert((await page.locator('.tab-menu').count()) === 0, 'il menu si chiude con un clic fuori');

  // Chiusura di un gruppo: le schede passano al gruppo accanto.
  const all = [...(await tabsOf(0)), ...(await tabsOf(1))];
  await groups.nth(1).getByRole('button', { name: 'Chiudi il gruppo' }).click();
  await page.waitForTimeout(200);
  const left = await tabsOf(0);
  assert((await groups.count()) === 1 && all.every((t) => left.includes(t)), `Chiudi il gruppo sposta le schede: ${left.join(', ')}`);

  // Ctrl W chiude la scheda attiva.
  const n = left.length;
  await page.keyboard.press('Control+w');
  await page.waitForTimeout(150);
  assert((await tabsOf(0)).length === n - 1, 'Ctrl W chiude la scheda attiva');

  // Il tasto centrale chiude la scheda sotto il puntatore, anche se non è attiva.
  await page.keyboard.press('Control+3');
  await page.waitForTimeout(200);
  const before3 = await tabsOf(0);
  await groups.nth(0).locator('.tab', { hasText: before3.find((t) => t !== 'Azioni') }).click({ button: 'middle' });
  await page.waitForTimeout(150);
  const after3 = await tabsOf(0);
  assert(after3.length === before3.length - 1 && after3.includes('Azioni'), `il tasto centrale chiude la scheda: ${after3.join(', ')}`);

  // Il menu ⋯ compare solo dove ha voci utili.
  assert((await page.getByRole('button', { name: 'Altre opzioni' }).count()) === 0, 'nelle viste senza opzioni il pulsante ⋯ non c\'è');
  await page.keyboard.press('Control+4');
  await page.waitForSelector('main.pane .row');
  await page.locator('main.pane .row').first().click();
  await page.waitForSelector('.stats');
  await page.getByRole('button', { name: 'Altre opzioni' }).click();
  await page.getByRole('menuitem', { name: /^Cerca @/ }).click();
  await page.waitForSelector('.dialog .field input');
  assert((await page.locator('.dialog .field input').inputValue()).startsWith('@'), 'nella pagina persona il menu cerca la persona nelle note');
  await page.keyboard.press('Escape');
}
