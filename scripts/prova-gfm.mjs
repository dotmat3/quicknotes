// Prova nell'app vera: GitHub Markdown (avvisi con icone e scelta del tipo, codice con i colori, note a piè di
// pagina, link nudi) e la manina sul testo che si apre con Ctrl+clic. Va usata con le note di demo-note.mjs.
import { appendFileSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

const EXTRA = `
\`\`\`python
def saluta(nome):
    return "ciao " + nome  # commento
\`\`\`

Documentazione: https://example.com/doc e la nota[^a].

[^a]: Spiegazione.
`;

export default async function (page, { notes }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const iso = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
  const file = join(notes, String(now.getFullYear()), p(now.getMonth() + 1), `${iso}-giornata.md`);
  const cursorOf = (sel) => page.locator(sel).first().evaluate((el) => getComputedStyle(el).cursor);

  await page.waitForSelector('.cm-content');
  appendFileSync(file, EXTRA);
  await page.waitForFunction(() => document.querySelector('.cm-content')?.innerText.includes('Spiegazione'));
  await page.locator('h1').first().click();
  await page.waitForTimeout(300);

  // Anteprima viva.
  assert((await page.locator('.cm-alert-title .qn-ai-note').count()) === 1, 'l\'avviso NOTE ha la sua icona');
  assert((await page.locator('.cm-code-lang').innerText()) === 'python', 'il blocco di codice mostra la lingua');
  await page.waitForFunction(() => document.querySelector('.cm-codeblock .tok-keyword'), null, { timeout: 5000 });
  assert(true, 'il codice nell\'editor ha i colori della sintassi');
  assert((await page.locator('.cm-fn').count()) >= 2, 'le note a piè di pagina sono evidenziate');
  const bare = page.locator('.cm-link[data-href="https://example.com/doc"]');
  assert((await bare.count()) === 1 && (await cursorOf('.cm-link[data-href="https://example.com/doc"]')) === 'pointer', 'un indirizzo nudo è un link, con la manina');

  // La manina su @ e # solo tenendo premuto Ctrl.
  const mention = '.cm-mention[data-person="Giulia"]';
  await page.locator(mention).first().hover();
  assert((await cursorOf(mention)) !== 'pointer', 'senza Ctrl, su @Giulia il cursore resta quello del testo');
  await page.keyboard.down('Control');
  await page.mouse.move(5, 5);
  await page.locator(mention).first().hover();
  assert((await cursorOf(mention)) === 'pointer', 'con Ctrl premuto, su @Giulia compare la manina');
  await page.keyboard.up('Control');
  await page.mouse.move(6, 6);
  assert((await page.evaluate(() => document.documentElement.classList.contains('qn-ctrl'))) === false, 'lasciando Ctrl la manina sparisce');
  assert((await cursorOf('.cm-wiki')) === 'pointer', 'un [[link]] reso ha sempre la manina');

  // Scrivendo > [! compare l'elenco dei tipi di avviso.
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\n> [!');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  const opts = await page.locator('.cm-tooltip-autocomplete li').allInnerTexts();
  assert(opts.length === 5 && opts[3].includes('Avvertenza') && opts[0].includes('Informazioni utili'), `cinque tipi con nome e descrizione: ${opts.map((o) => o.split('\n')[0]).join(', ')}`);
  assert((await page.locator('.cm-tooltip-autocomplete .qn-ai').count()) === 5, 'ogni tipo ha la sua icona');
  await page.keyboard.type('WA');
  await page.waitForTimeout(150);
  assert((await page.locator('.cm-tooltip-autocomplete li').count()) === 1, 'scrivendo si restringe l\'elenco');
  await page.keyboard.press('Enter');
  await page.keyboard.type('Non spegnere durante la registrazione');
  await page.waitForTimeout(800);
  assert(readFileSync(file, 'utf8').includes('> [!WARNING]\n> Non spegnere durante la registrazione'), 'Invio scrive il blocco e si continua sulla riga dopo');

  // Sorgente: colori dei segni e Ctrl+clic.
  await page.getByRole('button', { name: 'Altre opzioni' }).click();
  await page.getByRole('menuitemradio', { name: 'Sorgente' }).click();
  await page.waitForTimeout(300);
  assert((await page.locator('.cm-alert-mark.cm-alert-warning').count()) === 1, 'in Sorgente il segno dell\'avviso ha il suo colore');
  assert((await page.locator('.cm-source [data-person="Marco"][data-needs-ctrl]').count()) >= 1, 'in Sorgente @persone si aprono con Ctrl+clic');
  assert((await page.locator('.modebar .gfm').innerText()) === 'GitHub Markdown', 'la barra delle modalità dice che il formato è GitHub Markdown');
  await page.locator('.cm-source [data-person="Marco"]').first().click({ modifiers: ['Control'] });
  await page.waitForFunction(() => document.querySelector('h1')?.innerText.includes('@Marco'));
  assert(true, 'Ctrl+clic su @Marco in Sorgente apre la persona');
  await page.getByRole('tab', { name: /Oggi/ }).click();
  await page.waitForSelector('.modebar');

  // Anteprima: icone, lingua e colori del codice.
  await page.locator('.modebar button', { hasText: /^Anteprima$/ }).click();
  await page.waitForSelector('.preview');
  assert((await page.locator('.preview .pv-alert-warning .qn-ai-warning').count()) === 1 && (await page.locator('.preview .pv-alert-warning .pv-alert-title').innerText()) === 'Avvertenza', 'in Anteprima l\'avviso ha icona ed etichetta come nel design');
  assert((await page.locator('.preview .pv-code-lang').innerText()) === 'python', 'in Anteprima il codice mostra la lingua');
  await page.waitForFunction(() => document.querySelector('.preview pre .tok-keyword') && document.querySelector('.preview pre .tok-string') && document.querySelector('.preview pre .tok-comment'), null, { timeout: 5000 });
  assert(true, 'in Anteprima il codice ha parole chiave, stringhe e commenti colorati');
  assert((await page.locator('.preview a[data-href="https://example.com/doc"]').count()) === 1, 'in Anteprima l\'indirizzo nudo è un link');
  assert((await cursorOf('.preview .pv-mention')) === 'pointer', 'in Anteprima @persone hanno la manina e si aprono con un clic');
}
