// Prova nell'app vera: Guida (pulsante ?, F1, filtro), suggerimenti mentre si scrive, Indietro e Avanti
// con Alt e con i tasti laterali del mouse. Va usata con le note di demo-note.mjs.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

export default async function (page, { notes }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const iso = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  const file = join(notes, String(now.getFullYear()), p(now.getMonth() + 1), `${iso(now)}-giornata.md`);
  const read = () => readFileSync(file, 'utf8');
  const options = () => page.locator('.cm-tooltip-autocomplete li').allInnerTexts();
  const activeTab = () => page.locator('main.pane .tab.on .clip').first().innerText();

  await page.waitForSelector('.cm-content');

  // Guida.
  await page.getByRole('button', { name: /^Guida e comandi/ }).click();
  await page.waitForSelector('h1:text("Guida")');
  assert((await page.locator('section h2').count()) >= 5, 'il pulsante ? apre la guida con le sue sezioni');
  await page.getByRole('searchbox', { name: 'Cerca nella guida' }).fill('scheda chiudi');
  const rows = await page.locator('.row .what').allInnerTexts();
  assert(rows.length >= 1 && rows.every((r) => /chiud/i.test(r)), `il filtro trova i comandi: ${rows.join(' | ')}`);
  await page.keyboard.press('Control+w');
  await page.waitForTimeout(150);
  await page.keyboard.press('F1');
  await page.waitForSelector('h1:text("Guida")');
  assert(true, 'F1 apre la guida');
  await page.keyboard.press('Control+w');
  await page.waitForSelector('.cm-content');

  // Suggerimenti: date.
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\n- [');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  assert((await options()).some((o) => o.includes('Azione da fare')), '- [ propone l\'azione');
  await page.keyboard.press('Enter');
  await page.keyboard.type('Chiamare il fornitore due:');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  const dates = await options();
  assert(dates[0].includes('Oggi') && dates[1].includes('Domani') && dates.some((o) => o.includes('Fine del mese')), `due: propone le date: ${dates.slice(0, 3).map((o) => o.replace(/\s+/g, ' ')).join(' | ')}`);
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  // Il salvataggio arriva dopo una breve attesa: si guarda il file finché il testo c'è, fino a 3 secondi.
  let saved = false;
  for (let i = 0; i < 30 && !saved; i++, await page.waitForTimeout(100)) saved = read().includes(`- [ ] Chiamare il fornitore due:${iso(tomorrow)}`);
  assert(saved, 'scegliendo Domani si scrive la data nel formato giusto');
  await page.keyboard.type(' entro:2026-13');
  await page.waitForSelector('.cm-tooltip-autocomplete .cm-opt-invalid');
  assert((await options())[0].includes('Formato AAAA-MM-GG'), 'una data incompleta o sbagliata viene segnalata');
  await page.keyboard.type('-01');
  await page.waitForTimeout(150);
  assert((await options())[0].includes('Data inesistente'), 'il mese 13 non esiste');
  for (let i = 0; i < 10; i++) await page.keyboard.press('Backspace');
  await page.keyboard.type('2030-01-02');
  await page.waitForTimeout(150);
  assert((await options())[0].includes('✓') && (await options())[0].includes('Mercoledì'), `una data valida mostra il giorno: ${(await options())[0].replace(/\s+/g, ' ')}`);
  await page.keyboard.press('Escape');

  // Decisione, codice, strutture.
  await page.keyboard.type('\nScegliamo Rust !de');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  await page.keyboard.press('Enter');
  // Invio continua l'elenco: la riga nuova va svuotata, il blocco di codice parte da inizio riga.
  await page.keyboard.press('Enter');
  await page.keyboard.press('Shift+Home');
  await page.keyboard.press('Backspace');
  await page.keyboard.type('```py');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  assert((await options())[0].startsWith('python'), '``` propone le lingue');
  await page.keyboard.press('Enter');
  await page.keyboard.type('x = 1');
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\n/tab');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  assert((await options())[0].includes('Tabella'), '/ a inizio riga propone le strutture');
  await page.keyboard.press('Enter');
  await page.keyboard.type('Nome');
  await page.waitForTimeout(800);
  const text = read();
  assert(text.includes('Scegliamo Rust !decisione'), '!de si completa in !decisione');
  assert(text.includes('```python\nx = 1\n```'), 'il blocco di codice si chiude da solo');
  assert(text.includes('| ColonnaNome | Colonna |\n| --- | --- |\n|  |  |'), 'la tabella arriva completa, con il cursore nella prima cella');
  await page.locator('h1').first().click();
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Control+Space');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  assert((await options()).length >= 10, 'Ctrl Spazio su una riga vuota mostra le strutture');
  await page.keyboard.press('Escape');

  // Indietro e Avanti.
  await page.keyboard.press('Control+2');
  await page.waitForSelector('.grid');
  await page.keyboard.press('Control+3');
  await page.waitForSelector('.column');
  assert((await activeTab()) === 'Azioni', 'aperte Calendario e poi Azioni');
  await page.keyboard.press('Alt+ArrowLeft');
  await page.waitForTimeout(150);
  assert((await activeTab()) === 'Calendario', 'Alt ← torna al Calendario');
  await page.keyboard.press('Alt+ArrowRight');
  await page.waitForTimeout(150);
  assert((await activeTab()) === 'Azioni', 'Alt → va di nuovo ad Azioni');
  const cdp = await page.context().newCDPSession(page);
  const side = async (button) => {
    for (const type of ['mousePressed', 'mouseReleased']) await cdp.send('Input.dispatchMouseEvent', { type, x: 900, y: 500, button, clickCount: 1 });
    await page.waitForTimeout(200);
  };
  await side('back');
  assert((await activeTab()) === 'Calendario', 'il tasto laterale indietro torna al Calendario');
  await side('back');
  assert((await activeTab()).startsWith('Oggi'), 'e ancora indietro alla nota di oggi');
  await side('forward');
  assert((await activeTab()) === 'Calendario', 'il tasto laterale avanti va avanti');
  // Chiusa la scheda, Indietro la riapre, come in VS Code.
  await page.locator('.tab', { hasText: 'Calendario' }).click({ button: 'middle' });
  await page.waitForTimeout(150);
  assert((await activeTab()) === 'Azioni' && (await page.locator('.tab', { hasText: 'Calendario' }).count()) === 0, 'chiusa Calendario, resta Azioni');
  await page.keyboard.press('Alt+ArrowLeft');
  await page.waitForTimeout(150);
  assert((await activeTab()) === 'Calendario', 'Indietro riapre la scheda chiusa, come in VS Code');
  await page.keyboard.press('Alt+ArrowRight');
  await page.waitForTimeout(150);
  assert((await activeTab()) === 'Azioni', 'e Avanti torna ad Azioni');
  assert(page.url().startsWith('http://127.0.0.1:'), 'la pagina non ha lasciato l\'app');
}
