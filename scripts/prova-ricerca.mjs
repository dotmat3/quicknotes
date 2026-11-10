// Prova nell'app vera: Ctrl K con tipi di risultato, anteprima, trascrizioni, Apri a lato e solo comandi;
// registrazioni nel Calendario; scheda Note e registrazione delle Impostazioni.
// Va usata con le note di demo-note.mjs.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page, { cfg }) {
  const rows = () => page.locator('.dialog .row').allInnerTexts();
  // La riga evidenziata nel gruppo attivo, che con più gruppi ha il bordo acceso.
  const flashLine = async () => {
    const sel = `${(await page.locator('main.pane').count()) > 1 ? 'main.pane.lit' : 'main.pane'} .cm-line.cm-flash`;
    await page.waitForSelector(sel, { timeout: 3000 });
    return page.locator(sel).first().innerText();
  };
  await page.waitForSelector('.cm-content');

  // Ctrl K: tutti i tipi insieme, con i conteggi.
  await page.keyboard.press('Control+k');
  await page.locator('.dialog .field input').fill('tranche');
  await page.waitForSelector('.dialog .row.transcript');
  const tabs = await page.locator('.dialog [role="tab"]').allInnerTexts();
  assert(tabs.some((t) => t.startsWith('Trascrizioni')) && tabs.some((t) => t.startsWith('Decisioni')), `tipi di risultato con i conteggi: ${tabs.join(' | ')}`);
  const heads = await page.locator('.dialog .head').allInnerTexts();
  assert(heads.map((h) => h.toLowerCase()).join(',').includes('note,decisioni,trascrizioni'), `risultati divisi in gruppi: ${heads.join(', ')}`);
  const t = (await rows()).find((r) => r.includes('12:40'));
  assert(t && t.includes('Riunione budget Q4') && t.includes('Trascrizione 15:02') && t.includes('tre tranche'), `la riga della trascrizione con nota, ora e minutaggio: ${t?.replace(/\s+/g, ' ')}`);

  // Anteprima del primo risultato, con le parole evidenziate.
  await page.waitForSelector('.pane .phead h2');
  assert((await page.locator('.pane .phead h2').innerText()) === 'Riunione budget Q4', 'il riquadro mostra la nota scelta');
  await page.waitForSelector('.pane .content mark');
  assert((await page.locator('.pane .content mark').first().innerText()).toLowerCase() === 'tranche', 'e la parola cercata è evidenziata');

  // Solo le trascrizioni, con Tab; Invio apre la nota sulla riga.
  for (let i = 0; i < 6 && !(await page.locator('.dialog [role="tab"][aria-selected="true"]').innerText()).startsWith('Trascrizioni'); i++) await page.keyboard.press('Tab');
  assert((await page.locator('.dialog .row').count()) === (await page.locator('.dialog .row.transcript').count()), 'Tab passa al tipo Trascrizioni, che mostra solo quelle');
  await page.keyboard.press('Enter');
  assert((await flashLine()).includes('tre tranche mensili'), 'Invio apre la nota sulla riga della trascrizione');
  assert((await page.locator('main.pane .tab.on .clip').first().innerText()) === 'Riunione budget Q4', 'nella scheda attiva');

  // Un'azione: scadenza in ritardo, poi Alt Invio la apre in un altro gruppo.
  await page.keyboard.press('Control+k');
  await page.locator('.dialog .field input').fill('foglio costi');
  await page.waitForSelector('.dialog .row.action');
  assert((await page.locator('.dialog .row.action .due.late').count()) === 1, 'l\'azione in ritardo ha la scadenza in rosso');
  const groups = await page.locator('main.pane').count();
  const actionIndex = (await page.locator('.dialog .row').evaluateAll((els) => els.findIndex((e) => e.classList.contains('action'))));
  for (let i = 0; i < actionIndex; i++) await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Alt+Enter');
  await page.waitForTimeout(300);
  assert((await page.locator('main.pane').count()) === groups + 1, 'Alt Invio apre a lato, in un nuovo gruppo');
  const actionLine = await flashLine().catch(() => 'nessuna');
  assert(actionLine.includes('Aggiornare con @Giulia'), `sulla riga dell'azione: ${actionLine}`);

  // Solo comandi con >.
  await page.keyboard.press('Control+k');
  await page.locator('.dialog .field input').fill('> layout');
  await page.waitForTimeout(150);
  const cmds = await rows();
  assert(cmds.length >= 2 && cmds.every((r) => r.startsWith('Layout')), `> mostra solo i comandi: ${cmds.map((r) => r.split('\n')[0]).join(' | ')}`);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(200);

  // Copia [[link]] dal riquadro.
  await page.keyboard.press('Control+k');
  await page.locator('.dialog .field input').fill('preventivi fornitori');
  await page.waitForSelector('.pane .actions');
  await page.locator('.pane button', { hasText: 'Copia [[link]]' }).click();
  await page.waitForTimeout(150);
  assert((await page.locator('.toast').innerText()).includes('[[riunione-budget-q4|Riunione budget Q4]]'), 'Copia [[link]] copia il link alla nota');
  await page.keyboard.press('Escape');

  // Calendario: la registrazione nel giorno della riunione.
  await page.keyboard.press('Control+3');
  await page.waitForSelector('.grid');
  const chip = page.locator('.cell .chip', { hasText: 'Registrazione 15:02 (18:40)' });
  if (!(await chip.count())) {
    await page.getByRole('button', { name: 'Mese precedente' }).click();
    await page.waitForTimeout(300);
  }
  assert((await chip.count()) === 1, 'il Calendario mostra la registrazione nel giorno della nota');
  assert((await page.locator('.legend').innerText()).includes('Nota o registrazione'), 'la legenda come nella tavola Home');
  await chip.click();
  await page.locator('.side-item', { hasText: 'Registrazione 15:02' }).click();
  const recLine = await flashLine().catch(() => 'nessuna riga evidenziata');
  assert(recLine.includes('Registrazione 15:02'), `un clic apre la nota sulla riga della registrazione: ${recLine}`);

  // Impostazioni › Note e registrazione: le scelte finiscono in config.json.
  await page.keyboard.press('Control+,');
  await page.getByRole('tab', { name: 'Note e registrazione' }).click();
  await page.waitForSelector('text=Cartella delle note');
  await page.getByRole('radiogroup', { name: 'Modello di trascrizione' }).getByRole('radio', { name: 'medium' }).click();
  await page.getByRole('switch', { name: 'Conserva il file audio' }).click();
  await page.waitForTimeout(400);
  const config = JSON.parse(readFileSync(join(cfg, 'config.json'), 'utf8'));
  assert(config.whisper_model === 'medium' && config.keep_audio === false, `modello e file audio salvati: ${config.whisper_model}, ${config.keep_audio}`);
  assert((await page.getByRole('switch', { name: 'Minutaggio cliccabile' }).getAttribute('aria-checked')) === 'true', 'il minutaggio parte acceso');
}
