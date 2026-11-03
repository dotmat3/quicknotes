// Misura la ricerca Ctrl K nell'app vera, su circa 1000 note.
// Uso: .venv/Scripts/python scripts/genera_note.py <cartella vuota> 1000
//      node scripts/cdp.mjs <cartella> "" scripts/misura-ricerca.mjs
const stats = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const q = (f) => s[Math.min(s.length - 1, Math.floor(f * s.length))];
  return `mediana ${q(0.5).toFixed(1)} ms · 95° percentile ${q(0.95).toFixed(1)} ms · massimo ${s.at(-1).toFixed(1)} ms (${s.length} campioni)`;
};

const QUERIES = ['p', 'pr', 'pre', 'prev', 'preventivo', 'preventivo c', 'preventivo cucina', '@gi', '#tag3', '!budget', 'riunione 42', 'lavello trascrizione modello'];

export default async function (page) {
  await page.waitForSelector('.cm-content');
  // L'indice si allinea in sottofondo all'avvio: si aspetta che risponda.
  await page.waitForFunction(() => window.pywebview?.api?.invoke('search_all', { query: 'preventivo' }).then((r) => r.ok.length > 0), null, { timeout: 30000, polling: 500 });

  const direct = await page.evaluate(async (queries) => {
    const out = {};
    for (let round = 0; round < 5; round++) {
      for (const query of queries) {
        const t0 = performance.now();
        await window.pywebview.api.invoke('search_all', { query });
        (out[query] ??= []).push(performance.now() - t0);
      }
    }
    return out;
  }, QUERIES);
  console.log(`misura: search_all chiamato dalla pagina, compreso il passaggio IPC: ${stats(Object.values(direct).flat())}`);
  const med = (xs) => [...xs].sort((a, b) => a - b)[xs.length >> 1].toFixed(1);
  console.log(`  per ricerca: ${Object.entries(direct).map(([q, xs]) => `"${q}" ${med(xs)}`).join(' · ')}`);

  // Dal tasto all'ultimo aggiornamento dei risultati prima del tasto successivo, e a parte l'ultimo del
  // riquadro di anteprima, che arriva dopo. Ogni tasto chiude la finestra del precedente; si contano solo i
  // caratteri che hanno cambiato qualcosa a schermo.
  await page.evaluate(() => {
    window.__ks = [];
    document.addEventListener('keydown', (e) => {
      window.__ks.push({ t0: e.timeStamp, last: null, pane: null, char: !!document.querySelector('.dialog') && e.key.length === 1 });
    }, true);
    const inside = (records, sel) => records.some((r) => (r.target.nodeType === 1 ? r.target : r.target.parentElement)?.closest(sel));
    new MutationObserver((records) => {
      const k = window.__ks.at(-1);
      if (!k) return;
      if (inside(records, '.dialog .list')) k.last = performance.now();
      if (inside(records, '.dialog .pane')) k.pane = performance.now();
    }).observe(document.body, { subtree: true, childList: true, characterData: true });
  });
  for (const text of ['preventivo cucina', 'riunione budget', 'trascrizione modello']) {
    await page.keyboard.press('Control+k');
    await page.waitForSelector('.dialog .field input');
    for (const ch of text) {
      await page.keyboard.type(ch);
      await page.waitForTimeout(250);
    }
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
  }
  const ks = (await page.evaluate(() => window.__ks)).filter((k) => k.char);
  console.log(`misura: Ctrl K, dal tasto ai risultati aggiornati a schermo: ${stats(ks.filter((k) => k.last).map((k) => k.last - k.t0))}`);
  console.log(`misura: Ctrl K, dal tasto all'anteprima aggiornata: ${stats(ks.filter((k) => k.pane).map((k) => k.pane - k.t0))}`);
}
