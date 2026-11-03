// Prova nell'app vera: tabelle, modalità della nota, Anteprima sanificata, link, Ctrl F e completamento.
// Va usata con le note di demo-note.mjs.
import { appendFileSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};

const EXTRA = `
| Persona | Compito |
|---|---|
| @Giulia | [[riunione-budget-q4|Riunione]] #lavoro-q4 |
| @Marco | preventivo due:2030-01-02 |

Vedi il [sito di esempio](https://example.com) e la nota[^1].

[^1]: Una nota a piè di pagina.

<img src=x onerror="window.__xss=1"><script>window.__xss=2</script>
[pericolo](javascript:window.__xss=3) <a href="#" onclick="window.__xss=4" style="position:fixed;inset:0" class="menu">finto</a>

Ultima riga.
`;

// La nota di prova contiene apposta gestori on…: WebView2 li segnala già mentre DOMPurify legge l'HTML,
// e la CSP li blocca. Nessuno viene eseguito, come controlla la prova. Il suo <img src=x> si cerca nella
// cartella delle note, non c'è (404) e lascia il segnaposto.
export const expectedErrors = [/^error: Executing inline event handler violates the following Content Security Policy/, /status of 404 \(Not Found\)/];

export default async function (page, { notes }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const iso = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
  const file = join(notes, String(now.getFullYear()), p(now.getMonth() + 1), `${iso}-giornata.md`);
  const read = () => readFileSync(file, 'utf8');

  await page.waitForSelector('.cm-content');
  appendFileSync(file, EXTRA);
  await page.waitForFunction(() => document.querySelector('.cm-content')?.innerText.includes('Ultima riga'));
  await page.locator('h1').first().click();
  await page.waitForTimeout(200);

  // Tabelle nell'anteprima viva.
  assert((await page.locator('.cm-table table tr').count()) === 3, 'la tabella diventa una tabella vera, con intestazione e due righe');
  assert((await page.locator('.cm-table .pv-mention', { hasText: '@Giulia' }).count()) === 1, 'nelle celle @persona è riconosciuta');
  assert((await page.locator('.cm-table .pv-due').innerText()) !== 'due:2030-01-02', 'nelle celle la scadenza diventa un\'etichetta');
  await page.locator('.cm-table td', { hasText: 'preventivo' }).click();
  await page.waitForTimeout(150);
  assert((await page.locator('.cm-table').count()) === 0, 'cliccando la tabella si vede il testo grezzo');
  assert((await page.locator('.cm-content').innerText()).includes('| Persona | Compito |'), 'il testo grezzo della tabella è nell\'editor');
  await page.keyboard.press('Control+End');
  await page.waitForTimeout(150);
  assert((await page.locator('.cm-table').count()) === 1, 'uscendo dalla tabella torna la tabella');

  // Menu ⋯ e modalità.
  await page.getByRole('button', { name: 'Altre opzioni' }).click();
  const items = page.getByRole('menuitemradio');
  assert((await items.count()) === 4, 'il menu ⋯ ha le quattro modalità');
  assert((await items.first().getAttribute('aria-checked')) === 'true', 'Anteprima viva è quella attiva');
  assert((await page.locator('.modebar').count()) === 0, 'in anteprima viva la barra in basso non c\'è');
  await page.getByRole('menuitemradio', { name: 'Sorgente' }).click();
  await page.waitForTimeout(150);
  assert((await page.locator('.cm-editor.cm-source .cm-lineNumbers').count()) === 1, 'Sorgente mostra i numeri di riga');
  assert((await page.locator('.cm-table').count()) === 0 && (await page.locator('.cm-task-box').count()) === 0, 'in Sorgente il testo resta grezzo');
  assert((await page.locator('.modebar').count()) === 1, 'fuori dall\'anteprima viva compare la barra in basso');

  await page.locator('.modebar button', { hasText: 'Affiancata' }).click();
  await page.waitForSelector('.preview');
  assert((await page.locator('.body.split .preview').count()) === 1, 'Affiancata mostra editor e Anteprima insieme');
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nScritto in affiancata');
  await page.waitForTimeout(400);
  assert((await page.locator('.preview').innerText()).includes('Scritto in affiancata'), 'l\'Anteprima segue la scrittura');
  await page.waitForTimeout(500);
  assert(read().includes('Scritto in affiancata'), 'il testo scritto in Affiancata arriva nel file');

  await page.locator('.modebar button', { hasText: /^Anteprima$/ }).click();
  await page.waitForTimeout(200);
  assert(!(await page.locator('.host').isVisible()), 'in Anteprima l\'editor è nascosto');
  const pv = page.locator('.preview');
  assert((await pv.locator('.pv-alert-note .pv-alert-title').innerText()) === 'Nota', 'l\'avviso NOTE ha il suo titolo');
  assert((await pv.locator('table tr').count()) === 3, 'la tabella c\'è anche in Anteprima');
  assert((await pv.locator('li.pv-task-done').count()) >= 1 && (await pv.locator('li.pv-task input[disabled]').count()) >= 3, 'le azioni hanno caselle in sola lettura');
  assert(!(await pv.innerText()).includes('done:'), 'done: non si vede');
  assert((await pv.locator('sup.pv-fn-ref').count()) === 1 && (await pv.locator('.pv-footnotes li').count()) === 1, 'la nota a piè di pagina ha rimando e testo');
  const unsafe = await page.evaluate(() => {
    const root = document.querySelector('.preview');
    return {
      xss: window.__xss,
      scripts: root.querySelectorAll('script').length,
      handlers: [...root.querySelectorAll('*')].filter((e) => [...e.attributes].some((a) => a.name.startsWith('on') || a.name === 'style' && !e.classList.contains('pv-tag'))).length,
      js: root.querySelectorAll('a[href^="javascript"]').length,
      fake: root.querySelectorAll('.menu').length,
    };
  });
  assert(unsafe.xss === undefined && unsafe.scripts === 0 && unsafe.handlers === 0 && unsafe.js === 0 && unsafe.fake === 0, `HTML della nota sanificato: ${JSON.stringify(unsafe)}`);
  const refused = await page.evaluate(() => window.pywebview.api.invoke('open_url', { url: 'file:///C:/Windows/notepad.exe' }).then((r) => r.err ?? 'aperto'));
  assert(refused.includes('Si aprono solo'), `open_url rifiuta i file: ${refused}`);

  await pv.locator('.pv-wiki', { hasText: 'Riunione budget Q4' }).click();
  await page.waitForFunction(() => document.querySelector('h1')?.innerText === 'Riunione budget Q4');
  assert(true, 'un [[link]] nell\'Anteprima apre la nota');
  await page.getByRole('tab', { name: /Oggi/ }).click();
  await page.waitForSelector('.preview');
  assert(true, 'tornando sulla scheda resta in Anteprima');

  // Ctrl F e completamento, in anteprima viva.
  await page.locator('.modebar button', { hasText: 'Anteprima viva' }).click();
  await page.waitForTimeout(200);
  assert((await page.locator('.modebar').count()) === 0 && (await page.locator('.cm-task-box').count()) > 0, 'si torna all\'anteprima viva');
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+f');
  await page.waitForSelector('.cm-search');
  await page.keyboard.type('Giulia');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(150);
  assert((await page.locator('.cm-searchMatch').count()) >= 2, 'Ctrl F evidenzia i risultati nella nota');
  assert((await page.locator('.cm-search input[name="search"]').getAttribute('placeholder')) === 'Cerca', 'il pannello di ricerca è in italiano');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(100);
  assert((await page.locator('.cm-search').count()) === 0, 'Esc chiude la ricerca');

  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nCon @Giu');
  await page.waitForSelector('.cm-tooltip-autocomplete');
  await page.keyboard.press('Enter');
  await page.keyboard.type(' e #lavo');
  await page.waitForSelector('.cm-tooltip-autocomplete li:has-text("lavoro-q4")');
  await page.keyboard.press('Enter');
  await page.keyboard.type(' vedi [[Riun');
  await page.waitForSelector('.cm-tooltip-autocomplete li:has-text("Riunione budget Q4")');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(700);
  assert(read().includes('Con @Giulia e #lavoro-q4 vedi [[riunione-budget-q4|Riunione budget Q4]]'), 'il completamento di @, # e [[ scrive il testo giusto');

  await page.locator('h1').first().click();
  await page.locator('.cm-wiki', { hasText: 'Riunione budget Q4' }).first().click();
  await page.waitForFunction(() => document.querySelector('h1')?.innerText === 'Riunione budget Q4');
  assert(true, 'un [[link]] nell\'anteprima viva apre la nota');
}
