// Misure nell'app vera: tasto premuto fino alla pittura, cambio scheda, memoria del processo Python.
// Uso: node scripts/cdp.mjs <cartella con demo-note.mjs> "" scripts/misura-latenza.mjs
import { execSync } from 'node:child_process';
import { appendFileSync } from 'node:fs';
import { join } from 'node:path';

const stats = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const q = (f) => s[Math.min(s.length - 1, Math.floor(f * s.length))];
  return `mediana ${q(0.5).toFixed(1)} ms · 95° percentile ${q(0.95).toFixed(1)} ms · massimo ${s.at(-1).toFixed(1)} ms (${s.length} campioni)`;
};

// Dalla keydown alla fine della prima pittura successiva, letta dalla traccia della timeline.
// Un segnale in pagina dopo requestAnimationFrame non basta: aspetta anche il lavoro in sottofondo
// dopo il fotogramma, e sulle note lunghe misura quello invece del carattere a schermo.
async function typing(page, label, newLine = true) {
  await page.locator('.cm-content').first().click();
  await page.keyboard.press('Control+End');
  if (newLine) await page.keyboard.press('Enter');
  const browser = page.context().browser();
  await browser.startTracing(page, { categories: ['devtools.timeline'] });
  for (const ch of 'Scrivo una riga di prova con @Giulia e #casa per misurare la latenza. '.repeat(2)) {
    await page.keyboard.type(ch);
    await page.waitForTimeout(25);
  }
  const trace = JSON.parse((await browser.stopTracing()).toString('utf8'));
  const ev = trace.traceEvents ?? trace;
  const keys = ev.filter((e) => e.name === 'EventDispatch' && e.args?.data?.type === 'keydown').map((e) => e.ts).sort((a, b) => a - b);
  const paints = ev.filter((e) => e.name === 'Paint' || e.name === 'Commit').map((e) => e.ts + (e.dur ?? 0)).sort((a, b) => a - b);
  const lat = keys.map((k) => paints.find((x) => x > k)).filter(Boolean).map((x, i) => (x - keys[i]) / 1000);
  console.log(`misura: scrittura, ${label}: ${stats(lat)}`);
}

async function tabSwitch(page) {
  const times = [];
  for (let i = 0; i < 12; i++) {
    const name = i % 2 ? /Oggi/ : /Riunione budget Q4/;
    const title = i % 2 ? null : 'Riunione budget Q4';
    const tab = page.getByRole('tab', { name });
    times.push(
      await tab.evaluate(
        (el, want) =>
          new Promise((done) => {
            const t0 = performance.now();
            el.click();
            const check = () => {
              const h1 = document.querySelector('h1')?.innerText ?? '';
              const ok = want ? h1 === want : h1 !== 'Riunione budget Q4';
              if (ok && document.querySelector('.cm-content')) requestAnimationFrame(() => setTimeout(() => done(performance.now() - t0), 0));
              else requestAnimationFrame(check);
            };
            check();
          }),
        title,
      ),
    );
  }
  console.log(`misura: cambio scheda fino all'editor dipinto: ${stats(times.slice(2))}`);
}

export default async function (page, { notes, pid }) {
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const iso = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
  const file = join(notes, String(now.getFullYear()), p(now.getMonth() + 1), `${iso}-giornata.md`);

  await page.waitForSelector('.cm-content');
  await typing(page, 'nota del giorno di prova (~20 righe)');

  // Nota lunga e realistica: 2000 righe divise in sezioni, paragrafi e brevi elenchi di azioni.
  const lines = [];
  for (let i = 0; lines.length < 2000; i++) {
    lines.push(`## Sezione ${i}`, '', `Paragrafo ${i} con @Marco e #lavoro-q4, testo di riempimento per una nota lunga.`, `Seconda riga del paragrafo ${i}, con un [[riunione-budget-q4|link]].`, '');
    for (let j = 0; j < 4; j++) lines.push(`- [ ] Azione ${i}.${j} per @Elena #casa due:2030-01-0${(j % 9) + 1}`);
    lines.push('');
  }
  appendFileSync(file, `\n${lines.join('\n')}\n`);
  await page.waitForFunction(() => document.querySelector('.cm-content')?.innerText.includes('Paragrafo 1 ') || false, null, { timeout: 10000 });
  await page.waitForTimeout(500);
  await typing(page, 'stessa nota con 2000 righe in più, in sezioni');

  // Caso limite: un solo blocco enorme. Lezer riusa solo i blocchi di primo livello, quindi a ogni tasto
  // rianalizza tutto il blocco in cui si scrive.
  const list = [];
  for (let i = 0; i < 500; i++) list.push(`- [ ] Azione in una lista unica ${i} per @Elena #casa`);
  appendFileSync(file, `\n${list.join('\n')}`);
  await page.waitForFunction(() => document.querySelector('.cm-content')?.innerText.includes('lista unica 499') || false, null, { timeout: 10000 });
  await page.waitForTimeout(500);
  await page.locator('.cm-content').first().click();
  await page.keyboard.press('Control+End');
  await typing(page, 'in fondo a una lista unica di 500 righe', false);

  await page.locator('.cm-wiki', { hasText: 'Riunione budget Q4' }).first().click().catch(async () => {
    await page.keyboard.press('Control+Home');
    await page.locator('.cm-wiki').first().click();
  });
  await page.waitForFunction(() => document.querySelector('h1')?.innerText === 'Riunione budget Q4');
  await tabSwitch(page);

  await page.waitForTimeout(3000);
  const mb = (prop) => (Number(execSync(`powershell -NoProfile -Command "(Get-Process -Id ${pid}).${prop}"`, { encoding: 'utf8' }).trim()) / 1048576).toFixed(1);
  console.log(`misura: memoria del processo Python a riposo, escluso WebView2: privata ${mb('PrivateMemorySize64')} MB, insieme di lavoro ${mb('WorkingSet64')} MB`);
}
