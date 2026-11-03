// Da usare dopo prova-schede.mjs con le stesse cartelle (QN_CFG): dopo un vero riavvio torna tutto.
const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page) {
  await page.waitForSelector('main.pane');
  await page.waitForTimeout(500);
  assert((await page.locator('main.pane').count()) === 2, 'dopo il riavvio tornano i due gruppi');
  const tabs = await page.locator('.tab .clip').allInnerTexts();
  assert(tabs.includes('Persone') && tabs.includes('Calendario'), `tornano le schede: ${tabs.join(', ')}`);
  await page.getByRole('tab', { name: /Oggi/ }).click();
  await page.waitForSelector('.cm-content');
  assert((await page.locator('.cm-content').first().innerText()).includes('testo prima di uscire'), 'torna il testo salvato all\'uscita');
}
